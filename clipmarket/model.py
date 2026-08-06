"""Single place where CLIP is loaded and where anything becomes a vector.

Both tagging and search consume the same L2-normalized embedding space, so cosine
similarity is always just a dot product downstream.
"""
from functools import lru_cache

import numpy as np
import torch
from PIL import Image

from . import config


@lru_cache(maxsize=1)
def _load():
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(
        config.MODEL_NAME, pretrained=config.PRETRAINED
    )
    model = model.to(config.DEVICE).eval()
    tokenizer = open_clip.get_tokenizer(config.MODEL_NAME)
    return model, preprocess, tokenizer


def _normalize(x: torch.Tensor) -> np.ndarray:
    x = x / x.norm(dim=-1, keepdim=True)
    return x.cpu().numpy().astype("float32")


@torch.no_grad()
def encode_images(paths) -> np.ndarray:
    """Encode image files in batches. Unreadable files raise -- callers filter first."""
    model, preprocess, _ = _load()
    out = []
    paths = list(paths)
    for i in range(0, len(paths), config.BATCH_SIZE):
        batch = paths[i : i + config.BATCH_SIZE]
        tensors = [preprocess(Image.open(p).convert("RGB")) for p in batch]
        feats = model.encode_image(torch.stack(tensors).to(config.DEVICE))
        out.append(_normalize(feats))
    if not out:
        return np.zeros((0, 512), dtype="float32")
    return np.concatenate(out, axis=0)


@torch.no_grad()
def encode_texts(texts) -> np.ndarray:
    model, _, tokenizer = _load()
    tokens = tokenizer(list(texts)).to(config.DEVICE)
    return _normalize(model.encode_text(tokens))
