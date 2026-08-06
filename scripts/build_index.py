#!/usr/bin/env python3
"""One command: ingest -> embed -> tag -> persist -> insights."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipmarket import config, embed, ingest, insights, tag


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", default=str(config.ASSETS_DIR),
                    help="Directory to scan for images and videos")
    ap.add_argument("--no-insights", action="store_true",
                    help="Skip writing docs/insights.md")
    args = ap.parse_args()

    pool = ingest.build_pool(Path(args.assets))
    assets, vecs = embed.build(pool)

    print("Tagging against the curated vocabulary...")
    tags = tag.tag_all(vecs)
    records = [a.to_dict() | {"tags": t} for a, t in zip(assets, tags)]
    embed.save(assets, vecs, records)

    if not args.no_insights:
        print(f"Wrote insights -> {insights.write_report(records)}")
    print(f"\nDone. {len(records)} assets indexed. Next: streamlit run app.py")


if __name__ == "__main__":
    main()
