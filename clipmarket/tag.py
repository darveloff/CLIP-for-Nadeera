"""Zero-shot tagging: score every asset against the fixed, categorized vocabulary.

Closed vocabulary on purpose -- consistent categories are what make the aggregate
reporting in insights.py meaningful.

Two corrections to naive top-N tagging, both of which matter a lot in practice:

1. Raw cosine similarity is not comparable across tag prompts. Some prompts sit closer
   to every image in the library than others for reasons unrelated to content (prompt
   wording and length shift the baseline). Ranking on raw cosine therefore lets a few
   "loud" tags win on almost every asset. We rank on a per-tag z-score instead: how
   unusually high this asset scores for that tag, relative to the whole library.

2. Tags are selected per category rather than globally, so every category contributes
   and one category cannot crowd out the others.
"""
import numpy as np

from . import config, model
from .vocabulary import VOCABULARY, LOW_CONFIDENCE_CATEGORIES

_CATEGORY_INDICES = {}
for _j, _t in enumerate(VOCABULARY):
    _CATEGORY_INDICES.setdefault(_t.category, []).append(_j)


def normalize_scores(sims: np.ndarray) -> tuple[np.ndarray, bool]:
    """Convert raw [n_assets, n_tags] cosines into per-tag z-scores.

    Returns (ranking_scores, normalized). Falls back to the raw cosines on a library
    too small for the per-tag statistics to mean anything.
    """
    if sims.shape[0] < config.TAG_NORM_MIN_ASSETS:
        return sims, False
    mean = sims.mean(axis=0, keepdims=True)
    std = sims.std(axis=0, keepdims=True)
    return (sims - mean) / np.maximum(std, 1e-6), True


def tag_all(vecs: np.ndarray) -> list[list[dict]]:
    """Return, per asset, its top tags per category with scores and review flags."""
    tag_vecs = model.encode_texts([t.prompt() for t in VOCABULARY])
    sims = vecs @ tag_vecs.T  # [n_assets, n_tags], cosine (both normalized)
    ranking, normalized = normalize_scores(sims)

    out = []
    for row_raw, row_rank in zip(sims, ranking):
        tags = []
        for category, cols in _CATEGORY_INDICES.items():
            cols_arr = np.array(cols)
            order = cols_arr[np.argsort(-row_rank[cols_arr])][
                : config.TAG_TOP_N_PER_CATEGORY
            ]
            for j in order:
                t = VOCABULARY[int(j)]
                raw = float(row_raw[j])
                rank_score = float(row_rank[j])
                weak = (
                    rank_score < config.TAG_MIN_Z
                    if normalized
                    else raw < config.TAG_MIN_SCORE
                )
                tags.append(
                    {
                        "tag": t.name,
                        "category": t.category,
                        "score": round(raw, 4),
                        # How far above this tag's library-wide average the asset sits.
                        "z": round(rank_score, 3) if normalized else None,
                        # A weak signal: kept, but not counted as confident.
                        "needs_review": bool(weak),
                        # Categories CLIP is known to be unreliable at. Surfaced in the
                        # UI, but NOT excluded from aggregates -- mood and brand
                        # distribution is exactly what the insights step reports on.
                        "low_confidence": t.category in LOW_CONFIDENCE_CATEGORIES,
                    }
                )
        tags.sort(key=lambda d: -(d["z"] if d["z"] is not None else d["score"]))
        out.append(tags)
    return out


def confident_tags(record: dict) -> list[str]:
    return [t["tag"] for t in record.get("tags", []) if not t["needs_review"]]


def all_tag_names(records: list[dict]) -> list[str]:
    return sorted({t["tag"] for r in records for t in r.get("tags", [])})
