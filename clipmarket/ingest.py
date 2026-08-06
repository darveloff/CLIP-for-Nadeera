"""Walk the asset library and reduce everything to a pool of still images.

Images pass through untouched. Videos are decoded with OpenCV (no system ffmpeg
required) and sampled into keyframes that are treated as ordinary image assets,
linked back to their source video via metadata.
"""
from dataclasses import dataclass, asdict
from pathlib import Path

from . import config


@dataclass
class Asset:
    id: str
    path: str                    # path to the still image on disk
    kind: str                    # "image" | "keyframe"
    source: str                  # original file the asset came from
    source_video: str | None = None
    timestamp_s: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def discover(assets_dir: Path) -> tuple[list[Path], list[Path]]:
    """Return (image_files, video_files) found beneath assets_dir."""
    images, videos = [], []
    for p in sorted(Path(assets_dir).rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in config.IMAGE_EXTS:
            images.append(p)
        elif ext in config.VIDEO_EXTS:
            videos.append(p)
    return images, videos


def extract_keyframes(video: Path, out_dir: Path) -> list[Asset]:
    """Sample one frame every KEYFRAME_INTERVAL_S seconds.

    Near-duplicate frames are not removed here -- that happens in embed.py, where
    the embeddings needed to judge similarity already exist.
    """
    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        print(f"  ! could not decode {video.name} -- skipping")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    if fps <= 0:
        print(f"  ! {video.name} reports no frame rate -- assuming 25fps")
        fps = 25.0
    step = max(1, int(round(fps * config.KEYFRAME_INTERVAL_S)))

    assets, frame_idx, kept = [], 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % step == 0:
            ts = frame_idx / fps
            name = f"{video.stem}_{kept:04d}.jpg"
            dest = out_dir / name
            cv2.imwrite(str(dest), frame)
            assets.append(
                Asset(
                    id=f"{video.stem}#{kept}",
                    path=str(dest),
                    kind="keyframe",
                    source=str(video),
                    source_video=str(video),
                    timestamp_s=round(ts, 2),
                )
            )
            kept += 1
        frame_idx += 1
    cap.release()
    print(f"  {video.name}: {kept} keyframes from {frame_idx} frames")
    return assets


def build_pool(assets_dir: Path | None = None) -> list[Asset]:
    assets_dir = Path(assets_dir or config.ASSETS_DIR)
    images, videos = discover(assets_dir)
    print(f"Found {len(images)} images and {len(videos)} videos in {assets_dir}")

    pool = [
        Asset(id=p.stem, path=str(p), kind="image", source=str(p))
        for p in images
    ]
    for v in videos:
        pool.extend(extract_keyframes(v, config.KEYFRAMES_DIR))
    return pool
