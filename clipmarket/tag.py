"""Zero-shot tagging: score every asset against the fixed, categorized vocabulary.

Closed vocabulary on purpose -- consistent categories are what make the aggregate
reporting in insights.py meaningful.
"""
import numpy as np

from . import config, model
from .vocabulary import VOCABULARY, LOW_CONFIDENCE_CATEGORIES


def tag_all(vecs: np.ndarray) -> list[list[dict]]:
    """Return, per asset, its top-N tags with scores and a needs_review flag."""
    tag_vecs = model.encode_texts([t.prompt() for t in VOCABULARY])
    sims = vecs @ tag_vecs.T  # [n_assets, n_tags], cosine (both normalized)

    out = []
    for row in sims:
        order = np.argsort(-row)[: config.TAG_TOP_N]
        tags = []
        for j in order:
            t = VOCABULARY[j]
            score = float(row[j])
            tags.append(
                {
                    "tag": t.name,
                    "category": t.category,
                    "score": round(score, 4),
                    # Low scores and categories CLIP is known to be weak at are
                    # surfaced for a human rather than silently trusted.
                    "needs_review": bool(
                        score < config.TAG_MIN_SCORE
                        or t.category in LOW_CONFIDENCE_CATEGORIES
                    ),
                }
            )
        out.append(tags)
    return out


def confident_tags(record: dict) -> list[str]:
    return [t["tag"] for t in record.get("tags", []) if not t["needs_review"]]


def all_tag_names(records: list[dict]) -> list[str]:
    return sorted({t["tag"] for r in records for t in r.get("tags", [])})
