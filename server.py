#!/usr/bin/env python3
"""HTTP API in front of clipmarket, consumed by the Next.js UI.

Search uses CLIP when weights/index are available. Otherwise the same endpoints
keep working against metadata.json (or a seeded demo library) with lexical matching,
so the web UI is usable without a GPU or a prior Streamlit session.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from clipmarket import config, insights  # noqa: E402
from clipmarket.vocabulary import CATEGORIES, LOW_CONFIDENCE_CATEGORIES, VOCABULARY  # noqa: E402

app = FastAPI(title="Clipmarket API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchBody(BaseModel):
    query: str
    exclude: str | None = None
    tag_filter: str | None = None
    top_k: int = 12
    min_score: float = 0.15
    group_videos: bool = False


class SimilarBody(BaseModel):
    asset_id: str
    tag_filter: str | None = None
    top_k: int = 12
    min_score: float = 0.15


class ReviewBody(BaseModel):
    asset_id: str
    confirm_tags: list[str]


class RebuildBody(BaseModel):
    incremental: bool = True


def _clip_available() -> bool:
    try:
        import torch  # noqa: F401
        import open_clip  # noqa: F401
        return True
    except Exception:
        return False


def _seed_demo_library() -> list[dict]:
    """Write a small browsable library when no index exists yet."""
    from PIL import Image, ImageDraw

    assets_dir = config.ASSETS_DIR
    assets_dir.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    samples = [
        ("office_standup", (214, 196, 176), "an office", "a team working together", "professional"),
        ("product_packaging", (196, 176, 168), "a product close-up", "minimalist", "a photo studio"),
        ("outdoor_field_day", (176, 188, 168), "the outdoors", "a group of people", "energetic"),
        ("retail_aisle", (188, 180, 196), "a retail store", "a product close-up", "busy and cluttered"),
        ("home_kitchen", (212, 200, 184), "a home interior", "food", "calm"),
        ("conference_keynote", (180, 184, 196), "a conference or event", "a person", "professional"),
        ("cafe_notes", (200, 188, 172), "a home interior", "a computer screen or device", "casual"),
        ("city_dusk", (168, 176, 188), "a cityscape", "a wide establishing shot", "dark and moody"),
    ]
    records = []
    for i, (name, color, *tag_names) in enumerate(samples):
        path = assets_dir / f"{name}.jpg"
        if not path.exists():
            im = Image.new("RGB", (640, 480), color)
            draw = ImageDraw.Draw(im)
            draw.rectangle((40, 40, 600, 440), outline=(255, 255, 255), width=2)
            draw.text((56, 56), name.replace("_", " "), fill=(255, 255, 255))
            im.save(path, quality=88)
        tags = []
        for j, tag_name in enumerate(tag_names):
            cat = next(t.category for t in VOCABULARY if t.name == tag_name)
            tags.append(
                {
                    "tag": tag_name,
                    "category": cat,
                    "score": round(0.28 - j * 0.03, 3),
                    "z": None,
                    "needs_review": cat in LOW_CONFIDENCE_CATEGORIES or j == 2,
                    "low_confidence": cat in LOW_CONFIDENCE_CATEGORIES,
                }
            )
        records.append(
            {
                "id": name,
                "path": str(path),
                "kind": "image",
                "source": str(path),
                "source_video": None,
                "timestamp_s": None,
                "mtime": path.stat().st_mtime,
                "tags": tags,
                "near_duplicate_of": "office_standup" if name == "cafe_notes" else None,
            }
        )
    config.METADATA_PATH.write_text(json.dumps(records, indent=2))
    return records


_cache: dict[str, Any] = {"mtime": None, "records": None, "vecs": None}


def load_library() -> tuple[list[dict], Any, bool]:
    """Return (records, vecs_or_None, clip_search_ready)."""
    mtime = (
        config.EMBEDDINGS_PATH.stat().st_mtime
        if config.EMBEDDINGS_PATH.exists()
        else (config.METADATA_PATH.stat().st_mtime if config.METADATA_PATH.exists() else 0)
    )
    if _cache["records"] is not None and _cache["mtime"] == mtime:
        return _cache["records"], _cache["vecs"], _cache["vecs"] is not None and _clip_available()

    records: list[dict] = []
    vecs = None
    if config.METADATA_PATH.exists() and config.EMBEDDINGS_PATH.exists():
        try:
            from clipmarket import embed

            records, vecs = embed.load()
        except SystemExit:
            records = json.loads(config.METADATA_PATH.read_text())
            vecs = None
    elif config.METADATA_PATH.exists():
        records = json.loads(config.METADATA_PATH.read_text())
    else:
        records = _seed_demo_library()

    _cache.update(mtime=mtime, records=records, vecs=vecs)
    return records, vecs, vecs is not None and _clip_available()


def _public_record(record: dict, score: float | None = None) -> dict:
    return {
        "id": record["id"],
        "filename": Path(record["path"]).name,
        "kind": record.get("kind", "image"),
        "source_video": Path(record["source_video"]).name if record.get("source_video") else None,
        "timestamp_s": record.get("timestamp_s"),
        "near_duplicate_of": record.get("near_duplicate_of"),
        "tags": record.get("tags", []),
        "score": score,
        "media_url": f"/backend/media/{record['id']}",
    }


def _lexical_search(
    records: list[dict],
    query: str,
    exclude: str | None,
    tag_filter: str | None,
    top_k: int,
) -> list[tuple[dict, float]]:
    q = query.lower().strip()
    ex = (exclude or "").lower().strip()
    scored = []
    for r in records:
        hay = " ".join(
            [r.get("id", ""), Path(r.get("path", "")).stem.replace("_", " ")]
            + [t["tag"] for t in r.get("tags", [])]
        ).lower()
        if tag_filter and not any(t["tag"] == tag_filter for t in r.get("tags", [])):
            continue
        hits = sum(1 for token in q.split() if token in hay)
        if not hits:
            continue
        penalty = 0.15 if ex and ex in hay else 0.0
        scored.append((r, min(0.34, 0.12 + 0.06 * hits) - penalty))
    scored.sort(key=lambda pair: -pair[1])
    return scored[:top_k]


@app.get("/health")
def health():
    records, vecs, clip_ready = load_library()
    return {
        "ok": True,
        "assets": len(records),
        "clip_search": clip_ready,
        "model": config.MODEL_NAME,
        "pretrained": config.PRETRAINED,
        "data_dir": str(config.DATA_DIR),
    }


@app.get("/library")
def library(tag: str | None = None, page: int = 1, per_page: int = 60):
    records, _, clip_ready = load_library()
    shown = [
        r for r in records
        if not tag or any(t["tag"] == tag for t in r.get("tags", []))
    ]
    pages = max(1, (len(shown) + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    window = shown[start : start + per_page]
    return {
        "total": len(shown),
        "page": page,
        "pages": pages,
        "clip_search": clip_ready,
        "assets": [_public_record(r) for r in window],
        "all_tags": sorted({t["tag"] for r in records for t in r.get("tags", [])}),
    }


@app.get("/vocabulary")
def vocabulary():
    records, _, _ = load_library()
    counts = Counter(
        t["tag"] for r in records for t in r.get("tags", []) if not t["needs_review"]
    )
    cats = []
    for cat in CATEGORIES:
        cats.append(
            {
                "id": cat,
                "label": cat.replace("_", " "),
                "low_confidence": cat in LOW_CONFIDENCE_CATEGORIES,
                "tags": [
                    {"name": t.name, "confident_matches": counts.get(t.name, 0)}
                    for t in VOCABULARY
                    if t.category == cat
                ],
            }
        )
    return {"categories": cats}


@app.get("/insights")
def get_insights():
    records, _, _ = load_library()
    counts = Counter(
        t["tag"] for r in records for t in r.get("tags", []) if not t["needs_review"]
    )
    by_category = []
    for cat in CATEGORIES:
        names = [t.name for t in VOCABULARY if t.category == cat]
        by_category.append(
            {
                "id": cat,
                "label": cat.replace("_", " "),
                "rows": [{"tag": n, "count": counts.get(n, 0)} for n in names],
            }
        )
    dupes = [
        {"id": r["id"], "filename": Path(r["path"]).name, "of": r["near_duplicate_of"]}
        for r in records
        if r.get("near_duplicate_of")
    ]
    report = insights.build_report(records)
    return {
        "by_category": by_category,
        "duplicates": dupes,
        "report_markdown": report,
        "asset_count": len(records),
        "keyframe_count": sum(1 for r in records if r.get("kind") == "keyframe"),
        "image_count": sum(1 for r in records if r.get("kind") == "image"),
    }


@app.post("/search")
def do_search(body: SearchBody):
    records, vecs, clip_ready = load_library()
    tag_filter = body.tag_filter or None
    if clip_ready:
        from clipmarket.search import Result, group_by_video, search

        results = search(
            body.query,
            top_k=body.top_k,
            min_score=body.min_score,
            records=records,
            vecs=vecs,
            tag_filter=tag_filter,
            exclude=body.exclude or None,
        )
        if body.group_videos:
            groups = group_by_video(results)
            return {
                "mode": "clip",
                "grouped": True,
                "groups": [
                    {
                        "source_video": g["source_video"] and Path(g["source_video"]).name,
                        "best": _public_record(g["best"].record, g["best"].score),
                        "hits": [_public_record(h.record, h.score) for h in g["hits"]],
                    }
                    for g in groups
                ],
            }
        return {
            "mode": "clip",
            "grouped": False,
            "assets": [_public_record(r.record, r.score) for r in results],
        }

    pairs = _lexical_search(records, body.query, body.exclude, tag_filter, body.top_k)
    return {
        "mode": "lexical",
        "grouped": False,
        "assets": [_public_record(r, s) for r, s in pairs],
        "note": "CLIP weights are not loaded in this runtime, so ranking is lexical over tags and filenames.",
    }


@app.post("/similar")
def similar(body: SimilarBody):
    records, vecs, clip_ready = load_library()
    src = next((r for r in records if r["id"] == body.asset_id), None)
    if src is None:
        raise HTTPException(404, "Unknown asset")
    if clip_ready:
        from clipmarket.search import search_similar_to

        results = search_similar_to(
            body.asset_id,
            top_k=body.top_k,
            min_score=body.min_score,
            records=records,
            vecs=vecs,
            tag_filter=body.tag_filter or None,
        )
        return {
            "mode": "clip",
            "source": _public_record(src),
            "assets": [_public_record(r.record, r.score) for r in results],
        }
    src_tags = {t["tag"] for t in src.get("tags", [])}
    scored = []
    for r in records:
        if r["id"] == src["id"]:
            continue
        overlap = len(src_tags & {t["tag"] for t in r.get("tags", [])})
        if overlap:
            scored.append((r, min(0.34, 0.14 + 0.05 * overlap)))
    scored.sort(key=lambda pair: -pair[1])
    return {
        "mode": "lexical",
        "source": _public_record(src),
        "assets": [_public_record(r, s) for r, s in scored[: body.top_k]],
    }


@app.get("/review")
def review_queue():
    records, _, _ = load_library()
    reviewable = [r for r in records if any(t["needs_review"] for t in r.get("tags", []))]
    return {"total": len(reviewable), "assets": [_public_record(r) for r in reviewable]}


@app.post("/review")
def save_review(body: ReviewBody):
    records, vecs, _ = load_library()
    rec = next((r for r in records if r["id"] == body.asset_id), None)
    if rec is None:
        raise HTTPException(404, "Unknown asset")
    confirmed = 0
    for t in rec.get("tags", []):
        if t["tag"] in body.confirm_tags and t["needs_review"]:
            t["needs_review"] = False
            t["human_confirmed"] = True
            confirmed += 1
    try:
        from clipmarket import embed

        embed.save_records(records)
    except Exception:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.METADATA_PATH.write_text(json.dumps(records, indent=2))
    _cache["records"] = records
    return {"saved": confirmed, "asset": _public_record(rec)}


@app.post("/rebuild")
def rebuild(body: RebuildBody):
    cmd = [sys.executable, str(ROOT / "scripts" / "build_index.py")]
    if body.incremental:
        cmd.append("--incremental")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    _cache["mtime"] = None
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


@app.get("/media/{asset_id}")
def media(asset_id: str):
    records, _, _ = load_library()
    rec = next((r for r in records if r["id"] == asset_id), None)
    if rec is None:
        raise HTTPException(404, "Unknown asset")
    path = Path(rec["path"])
    if not path.exists():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(path)


@app.get("/export.csv")
def export_csv(tag: str | None = None):
    records, _, _ = load_library()
    shown = [
        r for r in records
        if not tag or any(t["tag"] == tag for t in r.get("tags", []))
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "path", "kind", "source_video", "timestamp_s", "confident_tags"])
    for r in shown:
        confident = "; ".join(t["tag"] for t in r.get("tags", []) if not t["needs_review"])
        writer.writerow(
            [
                r["id"],
                r["path"],
                r.get("kind"),
                r.get("source_video") or "",
                r.get("timestamp_s") if r.get("timestamp_s") is not None else "",
                confident,
            ]
        )
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
