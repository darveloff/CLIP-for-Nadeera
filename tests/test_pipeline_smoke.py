#!/usr/bin/env python3
"""End-to-end smoke test with a stubbed CLIP encoder.

Exercises ingest -> embed -> dedup -> tag -> search -> insights against synthetic
images and a synthetic video, so the pipeline wiring can be validated without
downloading model weights. Run: python tests/test_pipeline_smoke.py
"""
import sys
import tempfile
from pathlib import Path

from collections import Counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipmarket import config, embed, ingest, insights, model, tag
from clipmarket.search import search

DIM = 512


def _stub_vecs(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, DIM)).astype("float32")
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def install_stub_encoder():
    """Deterministic fake encoder: same input text/path always maps to the same vector."""
    model.encode_images = lambda paths: _stub_vecs(len(list(paths)), 1)
    model.encode_texts = lambda texts: _stub_vecs(len(list(texts)), 2)
    embed.model = model


def make_assets(dirpath: Path) -> None:
    from PIL import Image
    import cv2

    for i in range(6):
        Image.new("RGB", (64, 64), (i * 40 % 255, 80, 160)).save(dirpath / f"img_{i:02d}.jpg")

    # A 2-second video: enough frames for the 3s sampler to emit at least one keyframe.
    out = cv2.VideoWriter(
        str(dirpath / "clip_01.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 64)
    )
    for i in range(20):
        out.write(np.full((64, 64, 3), i * 10 % 255, dtype=np.uint8))
    out.release()


def main() -> int:
    install_stub_encoder()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "assets"
        src.mkdir()
        config.DATA_DIR = Path(td) / "data"
        config.KEYFRAMES_DIR = config.DATA_DIR / "keyframes"
        config.EMBEDDINGS_PATH = config.DATA_DIR / "embeddings.npy"
        config.METADATA_PATH = config.DATA_DIR / "metadata.json"
        make_assets(src)

        pool = ingest.build_pool(src)
        assert len(pool) >= 6, f"expected >=6 assets, got {len(pool)}"
        assert any(a.kind == "keyframe" for a in pool), "video produced no keyframes"
        print(f"PASS ingest: {len(pool)} assets "
              f"({sum(a.kind == 'keyframe' for a in pool)} keyframes)")

        assets, vecs = embed.build(pool)
        assert vecs.shape[0] == len(assets)
        assert np.allclose(np.linalg.norm(vecs, axis=1), 1.0, atol=1e-4), "vectors not normalized"
        print(f"PASS embed: {vecs.shape}")

        tags = tag.tag_all(vecs)
        assert len(tags) == len(assets)
        from clipmarket.vocabulary import CATEGORIES
        expected = len(CATEGORIES) * config.TAG_TOP_N_PER_CATEGORY
        assert all(len(t) == expected for t in tags), "expected top-N from every category"
        assert all({"tag", "category", "score", "z", "needs_review", "low_confidence"}
                   <= set(t[0]) for t in tags)
        for ts in tags:
            per_cat = Counter(t["category"] for t in ts)
            assert set(per_cat) == set(CATEGORIES), "a category produced no tags"
            assert max(per_cat.values()) <= config.TAG_TOP_N_PER_CATEGORY
        print(f"PASS tag: {expected} tags/asset across {len(CATEGORIES)} categories, "
              f"{sum(t['needs_review'] for ts in tags for t in ts)} flagged for review")

        records = [a.to_dict() | {"tags": t} for a, t in zip(assets, tags)]
        embed.save(assets, vecs, records)
        loaded, lvecs = embed.load()
        assert len(loaded) == len(records) and lvecs.shape == vecs.shape
        print("PASS persist + reload")

        hits = search("an outdoor team photo", records=loaded, vecs=lvecs, min_score=-1.0)
        assert hits and hits[0].score >= hits[-1].score, "results not ranked"
        assert search("anything", records=loaded, vecs=lvecs, min_score=1.1) == [], \
            "min_score gate did not suppress weak matches"
        print(f"PASS search: {len(hits)} ranked results, threshold gate works")

        some_tag = loaded[0]["tags"][0]["tag"]
        filtered = search("x", records=loaded, vecs=lvecs, min_score=-1.0, tag_filter=some_tag)
        assert all(any(t["tag"] == some_tag for t in r.record["tags"]) for r in filtered)
        print(f"PASS tag filter: {len(filtered)} results for {some_tag!r}")

        report = insights.build_report(loaded)
        assert "# Content Insights" in report and "Findings" in report
        print(f"PASS insights: {len(report.splitlines())}-line report generated")

    print("\nAll smoke checks passed (stubbed encoder; real weights untested here).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
