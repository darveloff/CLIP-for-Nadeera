"""Central configuration. Tuning happens here and nowhere else."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
KEYFRAMES_DIR = DATA_DIR / "keyframes"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
METADATA_PATH = DATA_DIR / "metadata.json"
DOCS_DIR = ROOT / "docs"
EVAL_QUERIES_PATH = ROOT / "eval" / "queries.yaml"

# --- Model ---
# PRETRAINED may be a named open_clip tag (downloaded from HuggingFace) or a path to a
# local checkpoint -- override with CLIPMARKET_PRETRAINED when the weights host is
# unreachable and the checkpoint has been copied in by hand.
MODEL_NAME = os.environ.get("CLIPMARKET_MODEL", "ViT-B-32")
PRETRAINED = os.environ.get("CLIPMARKET_PRETRAINED", "laion2b_s34b_b79k")
DEVICE = os.environ.get("CLIPMARKET_DEVICE", "cpu")
BATCH_SIZE = 16

# --- Ingestion ---
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
KEYFRAME_INTERVAL_S = 3.0
# Drop a keyframe if it is this similar to the last kept frame of the same video.
KEYFRAME_DEDUP_THRESHOLD = 0.95

# --- Tagging ---
TAG_TOP_N = 6          # candidate tags kept per asset, per category pass
TAG_MIN_SCORE = 0.22   # below this a tag is kept but flagged needs_review

# --- Search ---
SEARCH_TOP_K = 12
SEARCH_MIN_SCORE = 0.20  # below this we report "no strong match"
