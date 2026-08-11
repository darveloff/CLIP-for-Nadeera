"""Streamlit UI: search the asset library in natural language, browse by tag."""
import csv
import io
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import streamlit as st

from clipmarket import config, embed, tag as tagmod
from clipmarket.search import Result, group_by_video, search, search_similar_to
from clipmarket.vocabulary import CATEGORIES, VOCABULARY

st.set_page_config(page_title="Marketing Asset Search", layout="wide")

APP_PASSWORD = os.environ.get("CLIPMARKET_APP_PASSWORD")
if APP_PASSWORD:
    if not st.session_state.get("authed"):
        st.title("Marketing Asset Search")
        st.caption("Password protected -- set by CLIPMARKET_APP_PASSWORD.")
        pw = st.text_input("Password", type="password")
        if st.button("Enter"):
            if pw == APP_PASSWORD:
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()


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
    query: str,
    top_k: int,
    min_score: float,
    tag_filter: str | None,
    exclude: str | None,
    _cache_key: float,
):
    records, vecs = load_index(_cache_key)
    results = search(
        query, top_k=top_k, min_score=min_score,
        records=records, vecs=vecs, tag_filter=tag_filter, exclude=exclude or None,
    )
    return [(r.record, r.score) for r in results]


@st.cache_data
def run_similar(
    asset_id: str, top_k: int, min_score: float, tag_filter: str | None, _cache_key: float
):
    records, vecs = load_index(_cache_key)
    results = search_similar_to(
        asset_id, top_k=top_k, min_score=min_score,
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


def show_grid(items, columns: int = 4, key_prefix: str = "grid", enable_similar: bool = False):
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
                if record.get("near_duplicate_of"):
                    st.caption(f"⚠ near-duplicate of {record['near_duplicate_of']}")
                st.caption(tag_chips(record))
                if enable_similar:
                    if st.button("Find similar", key=f"{key_prefix}_similar_{record['id']}"):
                        st.session_state["similar_to"] = record["id"]
                        st.rerun()


def show_grouped_grid(groups, columns: int = 4):
    for row_start in range(0, len(groups), columns):
        cols = st.columns(columns)
        for col, g in zip(cols, groups[row_start : row_start + columns]):
            with col:
                record = g["best"].record
                path = Path(record["path"])
                if path.exists():
                    st.image(str(path), use_container_width=True)
                else:
                    st.warning(f"missing: {path.name}")
                if g["source_video"]:
                    st.markdown(f"**{Path(g['source_video']).name}**")
                    times = ", ".join(f"{h.record['timestamp_s']}s" for h in g["hits"])
                    st.caption(f"{len(g['hits'])} matching moment(s) at {times}")
                    st.caption(f"best match {g['best'].score:.3f}")
                else:
                    st.markdown(f"**{path.name}**")
                    st.caption(f"{g['best'].score:.3f}")
                st.caption(tag_chips(record))


def records_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "path", "kind", "source_video", "timestamp_s", "confident_tags"])
    for r in rows:
        confident = "; ".join(t["tag"] for t in r.get("tags", []) if not t["needs_review"])
        writer.writerow(
            [r["id"], r["path"], r["kind"], r.get("source_video") or "",
             r.get("timestamp_s") if r.get("timestamp_s") is not None else "", confident]
        )
    return buf.getvalue()


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
    group_videos = st.checkbox(
        "Group video hits by source video", value=False,
        help="Roll multiple matching keyframes from the same clip into one card "
             "instead of scattering them across the grid.",
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

    st.divider()
    st.header("Maintenance")
    incremental = st.checkbox(
        "Incremental (skip re-encoding unchanged images)", value=True,
    )
    if st.button("Rebuild index now"):
        with st.spinner("Running scripts/build_index.py..."):
            cmd = [sys.executable, "scripts/build_index.py"]
            if incremental:
                cmd.append("--incremental")
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(config.ROOT))
        st.code((proc.stdout or "") + (proc.stderr or ""), language="text")
        if proc.returncode == 0:
            st.success("Rebuild complete -- reloading index.")
            load_index.clear()
            run_query.clear()
            run_similar.clear()
            st.rerun()
        else:
            st.error(f"Rebuild failed (exit {proc.returncode}); see output above.")

search_tab, browse_tab, insight_tab, review_tab = st.tabs(
    ["Search", "Browse", "Insights", "Review"]
)

if st.session_state.get("similar_to"):
    src_id = st.session_state["similar_to"]
    src_record = next((r for r in records if r["id"] == src_id), None)
    if src_record is None:
        st.session_state["similar_to"] = None
    else:
        st.subheader(f"Similar to: {Path(src_record['path']).name}")
        if st.button("Clear similarity search"):
            st.session_state["similar_to"] = None
            st.rerun()
        sim_items = run_similar(src_id, top_k, min_score, tag_filter, index_cache_key)
        if not sim_items:
            st.info("No strong matches for this asset in the library.")
        else:
            show_grid(sim_items, key_prefix="similar")
        st.divider()

with search_tab:
    query = st.text_input(
        "Describe what you're looking for",
        placeholder="e.g. an outdoor team photo, bright and energetic",
    )
    exclude_query = st.text_input(
        "Exclude (optional)",
        placeholder="e.g. people",
        help="Results that strongly match this are pushed down rather than hard-filtered.",
    )
    if query:
        items = run_query(query, top_k, min_score, tag_filter, exclude_query, index_cache_key)
        if not items:
            st.info(
                "No strong match in the library for that query. Try rephrasing, or "
                "lower the minimum similarity in the sidebar."
            )
        else:
            st.success(f"{len(items)} match(es)")
            if group_videos:
                groups = group_by_video([Result(r, s) for r, s in items])
                show_grouped_grid(groups)
            else:
                show_grid(items, key_prefix="search", enable_similar=True)
            st.download_button(
                "Download results as CSV",
                records_to_csv([r for r, _ in items]),
                file_name="clipmarket_search_results.csv",
                mime="text/csv",
            )

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
    show_grid([(r, None) for r in window], key_prefix="browse", enable_similar=True)
    st.download_button(
        "Download full library as CSV",
        records_to_csv(shown),
        file_name="clipmarket_library.csv",
        mime="text/csv",
    )

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
    dupes = [r for r in records if r.get("near_duplicate_of")]
    if dupes:
        st.subheader("Near-duplicates")
        st.write(f"{len(dupes)} asset(s) flagged as near-identical to another asset.")
        for r in dupes[:20]:
            st.caption(f"`{Path(r['path']).name}` duplicates `{r['near_duplicate_of']}`")
    st.caption(
        "Full write-up with observation / so-what / action framing: docs/insights.md "
        "(regenerated by scripts/build_index.py)."
    )

with review_tab:
    reviewable = [r for r in records if any(t["needs_review"] for t in r.get("tags", []))]
    st.write(f"{len(reviewable)} asset(s) have at least one tag flagged for review.")
    st.caption(
        "Confirming a tag here only affects this session until you click Save -- "
        "saving writes the correction back to metadata.json (no re-embedding needed)."
    )
    if not reviewable:
        st.info("Nothing flagged for review right now.")
    else:
        options = {f"{Path(r['path']).name} ({r['id']})": r["id"] for r in reviewable}
        choice = st.selectbox("Asset to review", list(options.keys()))
        rec = next(r for r in records if r["id"] == options[choice])
        path = Path(rec["path"])
        if path.exists():
            st.image(str(path), width=320)
        pending = []
        for t in rec.get("tags", []):
            if t["needs_review"] and not t.get("human_confirmed"):
                key = f"confirm_{rec['id']}_{t['tag']}"
                confirmed = st.checkbox(
                    f"Confirm '{t['tag']}' ({t['score']:.2f}) is correct", key=key
                )
                if confirmed:
                    pending.append(t)
        # Mutation happens on click, not on checkbox-check, so the checkbox for a tag
        # doesn't vanish (it's still needs_review until saved) before Save actually runs.
        if st.button("Save corrections", disabled=not pending):
            for t in pending:
                t["needs_review"] = False
                t["human_confirmed"] = True
            embed.save_records(records)
            st.success(f"Saved {len(pending)} correction(s) to metadata.json.")
            st.rerun()
