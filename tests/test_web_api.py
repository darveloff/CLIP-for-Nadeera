#!/usr/bin/env python3
"""API smoke checks that do not need CLIP weights."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from server import app, _cache


def main() -> int:
    _cache.update(mtime=None, records=None, vecs=None)
    client = TestClient(app)

    health = client.get("/health").json()
    assert health["ok"] and health["assets"] >= 1
    print(f"PASS health: {health['assets']} assets, clip_search={health['clip_search']}")

    lib = client.get("/library").json()
    assert lib["total"] == health["assets"]
    assert lib["assets"][0]["media_url"].startswith("/backend/media/")
    print(f"PASS library: {lib['total']} records")

    asset_id = lib["assets"][0]["id"]
    media = client.get(f"/media/{asset_id}")
    assert media.status_code == 200
    print("PASS media")

    vocab = client.get("/vocabulary").json()
    assert len(vocab["categories"]) == 5
    print("PASS vocabulary")

    insights = client.get("/insights").json()
    assert "# Content Insights" in insights["report_markdown"]
    print("PASS insights")

    search = client.post("/search", json={"query": "office team", "top_k": 8, "min_score": 0.0}).json()
    assert search["mode"] in {"clip", "lexical"}
    print(f"PASS search mode={search['mode']} hits={len(search.get('assets') or [])}")

    similar = client.post("/similar", json={"asset_id": asset_id}).json()
    assert similar["source"]["id"] == asset_id
    print(f"PASS similar hits={len(similar['assets'])}")

    review = client.get("/review").json()
    if review["assets"]:
        rid = review["assets"][0]["id"]
        flagged = [t["tag"] for t in review["assets"][0]["tags"] if t["needs_review"]]
        saved = client.post("/review", json={"asset_id": rid, "confirm_tags": flagged[:1]}).json()
        assert saved["saved"] >= 1
        print(f"PASS review saved={saved['saved']}")
    else:
        print("PASS review (empty queue)")

    csv_body = client.get("/export.csv").text
    assert csv_body.startswith("id,path")
    print("PASS csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
