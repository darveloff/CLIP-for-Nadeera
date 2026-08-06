"""Turn the asset pool into a persisted embedding index.

Output contract, read by every other module:
  data/embeddings.npy   float32 [N, D], L2-normalized, row i <-> metadata[i]
  data/metadata.json    list of asset records (see ingest.Asset + tags added by tag.py)
"""
import json
from pathlib import Path

import numpy as np

from . import config, model
from .ingest import Asset


def _dedup_keyframes(assets: list[Asset], vecs: np.ndarray) -> tuple[list[Asset], np.ndarray]:
    """Drop keyframes that are near-identical to the last kept frame of the same video.

    Cheap because the embeddings already exist: similarity is one dot product.
    """
    keep, last_by_video = [], {}
    for i, a in enumerate(assets):
        if a.kind == "keyframe":
            prev = last_by_video.get(a.source_video)
            if prev is not None and float(vecs[prev] @ vecs[i]) > config.KEYFRAME_DEDUP_THRESHOLD:
                continue
            last_by_video[a.source_video] = i
        keep.append(i)
    dropped = len(assets) - len(keep)
    if dropped:
        print(f"De-duplicated {dropped} near-identical keyframes")
    return [assets[i] for i in keep], vecs[keep]


def build(assets: list[Asset]) -> tuple[list[Asset], np.ndarray]:
    if not assets:
        raise SystemExit(
            f"No assets found. Put images/videos in {config.ASSETS_DIR} "
            f"(or run scripts/fetch_samples.py) and try again."
        )
    print(f"Encoding {len(assets)} images with {config.MODEL_NAME}/{config.PRETRAINED}...")
    vecs = model.encode_images([a.path for a in assets])
    return _dedup_keyframes(assets, vecs)


def save(assets: list[Asset], vecs: np.ndarray, records: list[dict] | None = None) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(config.EMBEDDINGS_PATH, vecs)
    payload = records if records is not None else [a.to_dict() for a in assets]
    config.METADATA_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {vecs.shape[0]} embeddings -> {config.EMBEDDINGS_PATH}")
    print(f"Wrote metadata -> {config.METADATA_PATH}")


def load() -> tuple[list[dict], np.ndarray]:
    if not config.EMBEDDINGS_PATH.exists() or not config.METADATA_PATH.exists():
        raise SystemExit("No index found. Run: python scripts/build_index.py")
    vecs = np.load(config.EMBEDDINGS_PATH)
    records = json.loads(config.METADATA_PATH.read_text())
    if len(records) != vecs.shape[0]:
        raise SystemExit("Index is corrupt (metadata/embedding count mismatch). Rebuild it.")
    return records, vecs
