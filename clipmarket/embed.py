"""Turn the asset pool into a persisted embedding index.

Output contract, read by every other module:
  data/embeddings.npy   float32 [N, D], L2-normalized, row i <-> metadata[i]
  data/metadata.json    list of asset records (see ingest.Asset + tags added by tag.py)
"""
import json
import os
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


def split_for_incremental(
    pool: list[Asset], old_records: list[dict], old_vecs: np.ndarray
) -> tuple[list[Asset], list[dict], np.ndarray]:
    """Split a freshly discovered pool into (needs_encoding, reused_records, reused_vecs)
    by matching images against the previous build on source path + mtime.

    Videos are always re-processed -- keyframes are regenerated fresh every run, so
    there's no stable per-keyframe identity to match against between builds. Reused
    image records keep whatever tags were computed for them last time (a small
    staleness tradeoff for skipping the CLIP encode of unchanged files).
    """
    by_source = {
        r["source"]: (r.get("mtime"), i)
        for i, r in enumerate(old_records)
        if r.get("kind") == "image"
    }

    needs_encoding: list[Asset] = []
    reused_records: list[dict] = []
    reused_idx: list[int] = []
    for a in pool:
        cached = by_source.get(a.source) if a.kind == "image" else None
        if cached is not None and cached[0] is not None and cached[0] == a.mtime:
            reused_records.append(old_records[cached[1]])
            reused_idx.append(cached[1])
        else:
            needs_encoding.append(a)

    dim = old_vecs.shape[1] if old_vecs.ndim == 2 else 0
    reused_vecs = old_vecs[reused_idx] if reused_idx else np.zeros((0, dim), dtype="float32")
    return needs_encoding, reused_records, reused_vecs


def find_near_duplicates(vecs: np.ndarray, threshold: float | None = None) -> dict[int, int]:
    """Flag near-identical assets across the *whole* pool (not just consecutive
    keyframes of one video, which `_dedup_keyframes` already drops automatically).

    Returns {index_of_duplicate: index_of_first_occurrence}. Only flags -- callers
    decide whether to surface, exclude from insights, or otherwise act on it.
    """
    threshold = config.DUPLICATE_THRESHOLD if threshold is None else threshold
    n = vecs.shape[0]
    if n > config.DUPLICATE_MAX_ASSETS:
        print(
            f"Skipping duplicate detection: {n} assets exceeds "
            f"DUPLICATE_MAX_ASSETS={config.DUPLICATE_MAX_ASSETS} (O(n^2) cost)."
        )
        return {}

    sims = vecs @ vecs.T
    dup_of: dict[int, int] = {}
    for j in range(n):
        for i in range(j):
            if i in dup_of:
                continue  # only compare against canonical (non-duplicate) originals
            if sims[i, j] >= threshold:
                dup_of[j] = i
                break
    return dup_of


def _atomic_write(path: Path, write_fn) -> None:
    """Write via a same-directory temp file + os.replace so a rebuild interrupted
    mid-sync (e.g. on a Google Drive FUSE mount) can never leave a half-written,
    corrupt file in place. ``write_fn`` receives the exact temp path to write to,
    with the same suffix as ``path`` (numpy appends ".npy" otherwise).
    """
    tmp_path = path.with_name(f"{path.name}.tmp{os.getpid()}{path.suffix}")
    write_fn(tmp_path)
    os.replace(tmp_path, path)


def save(assets: list[Asset], vecs: np.ndarray, records: list[dict] | None = None) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    _atomic_write(config.EMBEDDINGS_PATH, lambda tmp: np.save(tmp, vecs))

    payload = records if records is not None else [a.to_dict() for a in assets]
    _atomic_write(
        config.METADATA_PATH,
        lambda tmp: tmp.write_text(json.dumps(payload, indent=2)),
    )
    print(f"Wrote {vecs.shape[0]} embeddings -> {config.EMBEDDINGS_PATH}")
    print(f"Wrote metadata -> {config.METADATA_PATH}")


def save_records(records: list[dict]) -> None:
    """Persist edited metadata only (e.g. human tag corrections from the review UI)
    without touching embeddings.npy -- the vectors haven't changed.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(config.METADATA_PATH, lambda tmp: tmp.write_text(json.dumps(records, indent=2)))


def load() -> tuple[list[dict], np.ndarray]:
    if not config.EMBEDDINGS_PATH.exists() or not config.METADATA_PATH.exists():
        raise SystemExit("No index found. Run: python scripts/build_index.py")
    vecs = np.load(config.EMBEDDINGS_PATH)
    records = json.loads(config.METADATA_PATH.read_text())
    if len(records) != vecs.shape[0]:
        raise SystemExit("Index is corrupt (metadata/embedding count mismatch). Rebuild it.")
    return records, vecs
