# CLIP-Powered Marketing Asset Tagging Tool

Zero-shot tagging and natural-language search over a marketing asset library, using a
pretrained CLIP model. No training, no fine-tuning — inference plus a thin app layer.

One embedding space serves two jobs:

- **Search** — free-text query embedded and compared against every asset (open vocabulary).
- **Tagging** — a fixed, categorized label list embedded once and scored against every
  asset (closed vocabulary, so aggregate reporting is consistent).

## Setup

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu  # smaller
pip install -r requirements.txt
```

If the CPU wheel index is unreachable, plain `pip install -r requirements.txt` works but
pulls the CUDA build (~3 GB).

Model weights (`ViT-B-32` / `laion2b_s34b_b79k`) download from HuggingFace on first run.
On a network where HuggingFace is blocked, download the checkpoint elsewhere and point at
it: `export CLIPMARKET_PRETRAINED=/path/to/open_clip_pytorch_model.bin`.

## Use

```bash
# 1. Put images and videos in assets/  (or: python scripts/fetch_samples.py)
# 2. Build the index — ingest, embed, tag, write insights
python scripts/build_index.py                 # --assets /some/other/folder
# 3. Measure against the sample query set
python scripts/run_eval.py
# 4. Demo UI
streamlit run app.py
```

Videos are decoded with OpenCV and sampled into keyframes (one every
`KEYFRAME_INTERVAL_S` seconds); near-identical frames are dropped after embedding. Each
keyframe is indexed as an ordinary asset that links back to its source video.

## Running in Colab with Google Drive

The "database" here is just files (`data/embeddings.npy`, `data/metadata.json`, and
`assets/`) — nothing to install. In Colab, `/content` is wiped on every session, so
point those directories at a mounted Drive folder to keep a consistent library across
sessions instead of re-ingesting and re-embedding from scratch each time.

```python
from google.colab import drive
drive.mount('/content/drive')

import os
os.environ["CLIPMARKET_ASSETS_DIR"] = "/content/drive/MyDrive/clipmarket/assets"
os.environ["CLIPMARKET_DATA_DIR"] = "/content/drive/MyDrive/clipmarket/data"
os.environ["CLIPMARKET_DOCS_DIR"] = "/content/drive/MyDrive/clipmarket/docs"
```

Run this **before** importing `clipmarket` or launching Streamlit (env vars are read
once, at import time, in `clipmarket/config.py`). Both `ASSETS_DIR` and `DATA_DIR` need
to move together: asset/keyframe paths are stored as absolute strings inside
`metadata.json`, so if the index lives on Drive but the raw assets stay local, those
paths break the moment the local runtime resets.

First session: mount Drive, set the env vars, put files in `CLIPMARKET_ASSETS_DIR`
(or run `scripts/fetch_samples.py`), then `python scripts/build_index.py` to build the
index directly onto Drive.

Every later session: mount Drive, set the same env vars, and go straight to
`streamlit run app.py` — the index from last time is already there. Re-run
`build_index.py` only when the asset library changes; the running Streamlit app picks
up a fresh index automatically (it watches the embeddings file's modification time).

If you're running Streamlit through a cloud tunnel/service, keep the tunnel process and
the Colab runtime that mounted Drive in the same session/kernel — Drive is mounted into
that runtime's filesystem, not globally.

## Layout

| Path | Role |
|---|---|
| `clipmarket/config.py` | All paths, thresholds, model choice — the only file to touch when tuning |
| `clipmarket/vocabulary.py` | The categorized tag list and per-tag prompt templates |
| `clipmarket/model.py` | Loads CLIP once; the only place anything becomes a vector |
| `clipmarket/ingest.py` | Walks the library; images pass through, videos → keyframes |
| `clipmarket/embed.py` | Batch encoding, keyframe de-duplication, index persistence |
| `clipmarket/tag.py` | Zero-shot scoring against the vocabulary |
| `clipmarket/search.py` | Query → ranked results, with a "no strong match" floor |
| `clipmarket/insights.py` | Aggregates tags into `docs/insights.md` |
| `app.py` | Streamlit search / browse / insights UI |
| `eval/queries.yaml` | The 10 sample queries backing the ≥8/10 criterion |
| `tests/test_pipeline_smoke.py` | End-to-end run with a stubbed encoder (no weights needed) |

## Index format

`data/embeddings.npy` is a float32 `[N, D]` array of L2-normalized vectors; row *i*
corresponds to record *i* in `data/metadata.json`:

```json
{"id": "...", "path": "...", "kind": "image|keyframe", "source": "...",
 "source_video": null, "timestamp_s": null,
 "tags": [{"tag": "an office", "category": "setting", "score": 0.27, "needs_review": false}]}
```

Because the vectors are normalized, cosine similarity is a plain dot product everywhere
downstream.

## Tuning

Everything adjustable lives in `clipmarket/config.py`: `TAG_TOP_N`, `TAG_MIN_SCORE`,
`SEARCH_TOP_K`, `SEARCH_MIN_SCORE`, `KEYFRAME_INTERVAL_S`, `KEYFRAME_DEDUP_THRESHOLD`.
Prompt wording is the other lever, and it lives per-tag in `vocabulary.py` — reword a
weak tag's template before concluding CLIP can't handle it.

See `docs/accuracy_notes.md` for what this approach is and isn't good at.
