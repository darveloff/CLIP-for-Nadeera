#!/usr/bin/env python3
"""Download a set of freely-licensed sample photos so the pipeline is runnable before
the real marketing library is available.

Images come from picsum.photos (public-domain Unsplash mirror). The valid photo ids are
fetched from the picsum listing API rather than hardcoded, so the set is reproducible
without guessing which ids exist.

Filenames are deliberately neutral (sample_001.jpg ...). We do not know what these
photos depict, and naming them as though we did makes eval output misleading -- judge
these by looking at them, not by their names. Real assets keep their own filenames.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipmarket import config

LIST_URL = "https://picsum.photos/v2/list?page={page}&limit=100"


def picsum_ids(count: int) -> list[str]:
    """Fetch `count` valid photo ids, in listing order (stable across runs)."""
    ids: list[str] = []
    page = 1
    while len(ids) < count:
        with urllib.request.urlopen(LIST_URL.format(page=page)) as r:
            batch = json.load(r)
        if not batch:
            break
        ids.extend(str(p["id"]) for p in batch)
        page += 1
    return ids[:count]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(config.ASSETS_DIR))
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--size", default="640")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    try:
        ids = picsum_ids(args.count)
    except Exception as e:
        print(f"Could not reach the picsum listing API: {e}")
        return

    ok = 0
    for n, pid in enumerate(ids, start=1):
        dest = out / f"sample_{n:03d}.jpg"
        if dest.exists():
            ok += 1
            continue
        url = f"https://picsum.photos/id/{pid}/{args.size}/{args.size}.jpg"
        try:
            urllib.request.urlretrieve(url, dest)
            ok += 1
            if n % 10 == 0:
                print(f"  {n}/{len(ids)}")
        except Exception as e:  # network is best-effort; keep going
            print(f"  ! {dest.name}: {e}")
    print(f"\n{ok}/{len(ids)} sample images in {out}")


if __name__ == "__main__":
    main()
