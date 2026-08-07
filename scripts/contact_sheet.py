#!/usr/bin/env python3
"""Build a single contact-sheet image of the whole library, labelled with filenames.

Sample photos have neutral names, so this is how you see what is actually in the
library -- open the output, or display it inline in a notebook.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipmarket import config, ingest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", default=str(config.ASSETS_DIR))
    ap.add_argument("--out", default=str(config.DOCS_DIR / "contact_sheet.jpg"))
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--cell", type=int, default=160)
    args = ap.parse_args()

    images, _videos = ingest.discover(Path(args.assets))
    paths = sorted(images)
    if not paths:
        print(f"No images found in {args.assets}")
        return

    cell, cols = args.cell, args.cols
    label_h = 14
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), "white")
    draw = ImageDraw.Draw(sheet)

    for i, p in enumerate(paths):
        x, y = (i % cols) * cell, (i // cols) * (cell + label_h)
        try:
            im = Image.open(p).convert("RGB")
        except Exception as e:
            print(f"  ! {p.name}: {e}")
            continue
        im.thumbnail((cell, cell))
        sheet.paste(im, (x + (cell - im.width) // 2, y))
        draw.text((x + 2, y + cell + 2), p.stem[:24], fill="black")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    print(f"{len(paths)} images -> {out}")


if __name__ == "__main__":
    main()
