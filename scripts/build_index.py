#!/usr/bin/env python3
"""One command: ingest -> embed -> tag -> persist -> insights."""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipmarket import config, embed, ingest, insights, tag


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", default=str(config.ASSETS_DIR),
                    help="Directory to scan for images and videos")
    ap.add_argument("--no-insights", action="store_true",
                    help="Skip writing docs/insights.md")
    ap.add_argument(
        "--incremental", action="store_true",
        help="Skip re-encoding images unchanged since the last build (matched by "
             "source path + mtime). Videos are always reprocessed, since keyframes "
             "are regenerated fresh every run. Reused images keep their previously "
             "computed tags rather than being re-tagged against the current library.",
    )
    args = ap.parse_args()

    pool = ingest.build_pool(Path(args.assets))

    to_encode, reused_records, reused_vecs = pool, [], None
    if args.incremental and config.EMBEDDINGS_PATH.exists() and config.METADATA_PATH.exists():
        old_records, old_vecs = embed.load()
        to_encode, reused_records, reused_vecs = embed.split_for_incremental(
            pool, old_records, old_vecs
        )
        print(
            f"Incremental build: reusing {len(reused_records)} unchanged embedding(s), "
            f"encoding {len(to_encode)} new/changed asset(s)"
        )

    if to_encode:
        assets, new_vecs = embed.build(to_encode)
        print("Tagging against the curated vocabulary...")
        new_tags = tag.tag_all(new_vecs)
        new_records = [a.to_dict() | {"tags": t} for a, t in zip(assets, new_tags)]
    elif reused_records:
        dim = reused_vecs.shape[1] if reused_vecs is not None and reused_vecs.size else 512
        new_vecs, new_records = np.zeros((0, dim), dtype="float32"), []
    else:
        raise SystemExit(
            f"No assets found. Put images/videos in {args.assets} "
            f"(or run scripts/fetch_samples.py) and try again."
        )

    vecs = (
        np.concatenate([reused_vecs, new_vecs], axis=0)
        if reused_vecs is not None and reused_vecs.size
        else new_vecs
    )
    records = reused_records + new_records

    dup_of = embed.find_near_duplicates(vecs)
    for i, r in enumerate(records):
        r["near_duplicate_of"] = records[dup_of[i]].get("id") if i in dup_of else None
    if dup_of:
        print(f"Flagged {len(dup_of)} near-duplicate asset(s) (see docs/insights.md)")

    embed.save([], vecs, records)

    if not args.no_insights:
        print(f"Wrote insights -> {insights.write_report(records)}")
    print(f"\nDone. {len(records)} assets indexed. Next: streamlit run app.py")


if __name__ == "__main__":
    main()
