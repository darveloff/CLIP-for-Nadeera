#!/usr/bin/env python3
"""Download a small set of freely-licensed sample photos so the pipeline is runnable
before the real marketing library is available.

Images come from picsum.photos (public-domain Unsplash mirror). Filenames encode the
intended content so eval expectations stay readable; replace assets/ with the real
library and rebuild when it arrives.
"""
import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipmarket import config

# (filename stem, picsum photo id) -- ids chosen for varied subject matter
SAMPLES = [
    ("desk_laptop_01", 0), ("desk_laptop_02", 48), ("office_people_01", 3),
    ("office_people_02", 20), ("nature_landscape_01", 10), ("nature_landscape_02", 15),
    ("city_street_01", 122), ("city_street_02", 164), ("food_closeup_01", 292),
    ("food_closeup_02", 312), ("coffee_desk_01", 30), ("coffee_desk_02", 42),
    ("people_outdoors_01", 64), ("people_outdoors_02", 91), ("portrait_01", 65),
    ("portrait_02", 177), ("product_object_01", 250), ("product_object_02", 367),
    ("minimal_bright_01", 106), ("minimal_bright_02", 175), ("dark_moody_01", 129),
    ("dark_moody_02", 143), ("interior_home_01", 155), ("interior_home_02", 219),
    ("animal_01", 200), ("animal_02", 237), ("building_01", 101), ("building_02", 142),
    ("event_crowd_01", 287), ("event_crowd_02", 334),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(config.ASSETS_DIR))
    ap.add_argument("--size", default="640")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ok = 0
    for stem, pid in SAMPLES:
        dest = out / f"{stem}.jpg"
        if dest.exists():
            ok += 1
            continue
        url = f"https://picsum.photos/id/{pid}/{args.size}/{args.size}.jpg"
        try:
            urllib.request.urlretrieve(url, dest)
            ok += 1
            print(f"  {dest.name}")
        except Exception as e:  # network is best-effort; keep going
            print(f"  ! {dest.name}: {e}")
    print(f"\n{ok}/{len(SAMPLES)} sample images in {out}")


if __name__ == "__main__":
    main()
