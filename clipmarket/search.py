"""Natural-language search: same embedding space as tagging, open vocabulary."""
from dataclasses import dataclass

import numpy as np

from . import config, embed, model


@dataclass
class Result:
    record: dict
    score: float

    @property
    def path(self) -> str:
        return self.record["path"]


def search(
    query: str | None = None,
    top_k: int | None = None,
    min_score: float | None = None,
    records: list[dict] | None = None,
    vecs: np.ndarray | None = None,
    tag_filter: str | None = None,
    *,
    query_vec: np.ndarray | None = None,
    exclude: str | None = None,
    exclude_weight: float | None = None,
    exclude_ids: set[str] | None = None,
) -> list[Result]:
    """Rank assets against a free-text query, or against a precomputed query vector.

    Passing ``query_vec`` instead of ``query`` supports "find similar to this asset"
    (the caller looks up the asset's own embedding first) without a second, redundant
    text-encode. ``exclude`` embeds a second phrase and subtracts its similarity, so a
    result that strongly matches the excluded concept is pushed down rather than simply
    filtered by a hard tag. ``exclude_ids`` drops specific asset ids outright (e.g. the
    source asset itself, when searching "by similarity").

    Returns [] when nothing clears min_score -- the caller shows a "no strong match"
    message rather than forcing weak results, which matters on a small library.
    """
    top_k = top_k or config.SEARCH_TOP_K
    min_score = config.SEARCH_MIN_SCORE if min_score is None else min_score
    if records is None or vecs is None:
        records, vecs = embed.load()
    if query is None and query_vec is None:
        raise ValueError("search() needs either `query` or `query_vec`")

    idx = np.arange(len(records))
    if tag_filter:
        idx = np.array(
            [i for i in idx if any(t["tag"] == tag_filter for t in records[i].get("tags", []))],
            dtype=int,
        )
    if exclude_ids:
        idx = np.array([i for i in idx if records[i].get("id") not in exclude_ids], dtype=int)
    if idx.size == 0:
        return []

    qvec = query_vec if query_vec is not None else model.encode_texts([query])[0]
    sims = vecs[idx] @ qvec

    if exclude:
        exclude_weight = config.SEARCH_EXCLUDE_WEIGHT if exclude_weight is None else exclude_weight
        exvec = model.encode_texts([exclude])[0]
        exsims = vecs[idx] @ exvec
        sims = sims - exclude_weight * np.clip(exsims, 0, None)

    order = np.argsort(-sims)[:top_k]
    return [
        Result(records[int(idx[j])], float(sims[j])) for j in order if sims[j] >= min_score
    ]


def search_similar_to(
    asset_id: str,
    top_k: int | None = None,
    min_score: float | None = None,
    records: list[dict] | None = None,
    vecs: np.ndarray | None = None,
    tag_filter: str | None = None,
) -> list[Result]:
    """"Find more like this": search using an existing asset's own embedding as the query.

    Reuses the already-computed vector for that asset -- no extra CLIP call needed.
    """
    if records is None or vecs is None:
        records, vecs = embed.load()
    match = next((i for i, r in enumerate(records) if r.get("id") == asset_id), None)
    if match is None:
        return []
    return search(
        query_vec=vecs[match],
        top_k=top_k,
        min_score=min_score,
        records=records,
        vecs=vecs,
        tag_filter=tag_filter,
        exclude_ids={asset_id},
    )


def group_by_video(results: list[Result]) -> list[dict]:
    """Roll keyframe hits up to one entry per source video.

    Each group keeps its best-scoring keyframe as the representative thumbnail and lists
    every matching timestamp, so a search doesn't scatter one video's hits across
    unrelated results -- useful once a library has enough footage that several keyframes
    of the same clip can independently clear the score threshold.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    standalone: list[Result] = []
    for r in results:
        video = r.record.get("source_video")
        if not video:
            standalone.append(r)
            continue
        if video not in groups:
            groups[video] = {"source_video": video, "best": r, "hits": []}
            order.append(video)
        groups[video]["hits"].append(r)
        if r.score > groups[video]["best"].score:
            groups[video]["best"] = r

    grouped = [groups[v] for v in order]
    grouped.sort(key=lambda g: -g["best"].score)
    for g in grouped:
        g["hits"].sort(key=lambda r: -r.score)
    return grouped + [{"source_video": None, "best": r, "hits": [r]} for r in standalone]
