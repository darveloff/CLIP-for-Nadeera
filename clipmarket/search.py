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
    query: str,
    top_k: int | None = None,
    min_score: float | None = None,
    records: list[dict] | None = None,
    vecs: np.ndarray | None = None,
    tag_filter: str | None = None,
) -> list[Result]:
    """Rank assets against a free-text query.

    Returns [] when nothing clears min_score -- the caller shows a "no strong match"
    message rather than forcing weak results, which matters on a small library.
    """
    top_k = top_k or config.SEARCH_TOP_K
    min_score = config.SEARCH_MIN_SCORE if min_score is None else min_score
    if records is None or vecs is None:
        records, vecs = embed.load()

    idx = np.arange(len(records))
    if tag_filter:
        idx = np.array(
            [i for i in idx if any(t["tag"] == tag_filter for t in records[i].get("tags", []))],
            dtype=int,
        )
        if idx.size == 0:
            return []

    qvec = model.encode_texts([query])[0]
    sims = vecs[idx] @ qvec

    order = np.argsort(-sims)[:top_k]
    return [
        Result(records[int(idx[j])], float(sims[j])) for j in order if sims[j] >= min_score
    ]
