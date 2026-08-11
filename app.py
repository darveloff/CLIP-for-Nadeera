"""Streamlit UI: search the asset library in natural language, browse by tag."""
from collections import Counter
from pathlib import Path

import streamlit as st

from clipmarket import config, embed, tag as tagmod
from clipmarket.search import search
from clipmarket.vocabulary import CATEGORIES, VOCABULARY

st.set_page_config(page_title="Marketing Asset Search", layout="wide")


def _index_cache_key() -> float:
    """mtime of the embeddings file, so a rebuild (e.g. from a separate Colab cell
    writing to the same Google-Drive-backed data dir) invalidates the cache instead
    of the app silently serving a stale in-memory index all session long.
    """
    return config.EMBEDDINGS_PATH.stat().st_mtime if config.EMBEDDINGS_PATH.exists() else 0.0


@st.cache_resource
def load_index(_cache_key: float):
    return embed.load()


@st.cache_data
def run_query(
    query: str, top_k: int, min_score: float, tag_filter: str | None, _cache_key: float
):
    records, vecs = load_index(_cache_key)
    results = search(
        query, top_k=top_k, min_score=min_score,
        records=records, vecs=vecs, tag_filter=tag_filter,
    )
    return [(r.record, r.score) for r in results]


def tag_chips(record: dict) -> str:
    parts = []
    for t in record.get("tags", [])[:4]:
        mark = " ?" if t["needs_review"] else ""
        mark += " *" if t.get("low_confidence") else ""
        parts.append(f"{t['tag']} ({t['score']:.2f}){mark}")
    return " · ".join(parts)


def show_grid(items, columns: int = 4):
    for row_start in range(0, len(items), columns):
        cols = st.columns(columns)
        for col, (record, score) in zip(cols, items[row_start : row_start + columns]):
            with col:
                path = Path(record["path"])
                if path.exists():
                    st.image(str(path), use_container_width=True)
                else:
                    st.warning(f"missing: {path.name}")
                caption = f"**{path.name}**"
                if score is not None:
                    caption += f" — {score:.3f}"
                st.markdown(caption)
                if record["kind"] == "keyframe":
                    st.caption(
                        f"keyframe @ {record['timestamp_s']}s of "
                        f"{Path(record['source_video']).name}"
                    )
                st.caption(tag_chips(record))


try:
    index_cache_key = _index_cache_key()
    records, vecs = load_index(index_cache_key)
except SystemExit as e:
    st.error(str(e))
    st.stop()

st.title("Marketing Asset Search")
st.caption(
    f"{len(records)} assets indexed with CLIP {config.MODEL_NAME} "
    f"({config.PRETRAINED}). Tagging and search share one embedding space."
)

with st.sidebar:
    st.header("Filters")
    all_tags = ["(any)"] + tagmod.all_tag_names(records)
    chosen = st.selectbox("Tag filter", all_tags)
    tag_filter = None if chosen == "(any)" else chosen
    top_k = st.slider("Results", 4, 40, config.SEARCH_TOP_K)
    min_score = st.slider(
        "Minimum similarity", 0.0, 0.40, float(config.SEARCH_MIN_SCORE), 0.01,
        help="Results below this are hidden rather than padding the grid with weak matches.",
    )

    st.divider()
    st.header("Vocabulary")
    st.caption(
        "The fixed, closed tag list every asset is scored against -- this is the "
        "complete set; tagging never produces anything outside it."
    )
    tag_counts = Counter(
        t["tag"] for r in records for t in r.get("tags", []) if not t["needs_review"]
    )
    for cat in CATEGORIES:
        cat_tags = [t for t in VOCABULARY if t.category == cat]
        with st.expander(f"{cat.replace('_', ' ').title()} ({len(cat_tags)})"):
            low_conf = cat in tagmod.LOW_CONFIDENCE_CATEGORIES
            if low_conf:
                st.caption("CLIP is known to be unreliable here -- always flagged for review.")
            for t in cat_tags:
                st.markdown(f"- {t.name} — *{tag_counts.get(t.name, 0)} confident matches*")

search_tab, browse_tab, insight_tab = st.tabs(["Search", "Browse", "Insights"])

with search_tab:
    query = st.text_input(
        "Describe what you're looking for",
        placeholder="e.g. an outdoor team photo, bright and energetic",
    )
    if query:
        items = run_query(query, top_k, min_score, tag_filter, index_cache_key)
        if not items:
            st.info(
                "No strong match in the library for that query. Try rephrasing, or "
                "lower the minimum similarity in the sidebar."
            )
        else:
            st.success(f"{len(items)} match(es)")
            show_grid(items)

with browse_tab:
    shown = [
        r for r in records
        if not tag_filter or any(t["tag"] == tag_filter for t in r.get("tags", []))
    ]
    per_page = 60
    pages = max(1, (len(shown) + per_page - 1) // per_page)
    page = 1
    if pages > 1:
        page = st.number_input(
            f"Page (1-{pages})", min_value=1, max_value=pages, value=1, step=1
        )
    start = (page - 1) * per_page
    window = shown[start : start + per_page]
    st.write(f"{len(shown)} asset(s) — showing {start + 1}-{start + len(window)}")
    show_grid([(r, None) for r in window])

with insight_tab:
    counts = Counter()
    for r in records:
        for t in r.get("tags", []):
            if not t["needs_review"]:
                counts[t["tag"]] += 1
    for cat in CATEGORIES:
        names = [t.name for t in VOCABULARY if t.category == cat]
        rows = {n: counts.get(n, 0) for n in names}
        st.subheader(cat.replace("_", " ").title())
        st.bar_chart(rows)
    st.caption(
        "Full write-up with observation / so-what / action framing: docs/insights.md "
        "(regenerated by scripts/build_index.py)."
    )
