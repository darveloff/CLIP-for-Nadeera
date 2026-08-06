#!/usr/bin/env python3
"""Run the sample query set and print a pass/fail table.

This is the instrument for the "relevant results on >=8/10 queries" success
criterion -- re-runnable at any point during tuning, not a one-off at the end.
"""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipmarket import config, embed
from clipmarket.search import search


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", default=str(config.EVAL_QUERIES_PATH))
    ap.add_argument("--top", type=int, default=5,
                    help="How many results to show per query for judging")
    args = ap.parse_args()

    spec = yaml.safe_load(Path(args.queries).read_text())
    records, vecs = embed.load()

    passed = 0
    for i, q in enumerate(spec["queries"], 1):
        text, kind = q["query"], q.get("type", "-")
        expect = q.get("expect_substring")
        results = search(text, top_k=args.top, records=records, vecs=vecs)

        if not results:
            verdict = "NO MATCH"
        elif expect:
            hit = any(expect.lower() in r.path.lower() for r in results)
            verdict = "PASS" if hit else "FAIL"
            passed += hit
        else:
            verdict = "MANUAL"  # judge by eye from the listed results

        print(f"\n[{i:2}] {verdict:8} ({kind}) {text!r}")
        for r in results:
            print(f"       {r.score:.3f}  {Path(r.path).name}")
        if not results:
            print(f"       (nothing above SEARCH_MIN_SCORE={config.SEARCH_MIN_SCORE})")

    auto = [q for q in spec["queries"] if q.get("expect_substring")]
    if auto:
        print(f"\n=== {passed}/{len(auto)} auto-judged queries passed "
              f"({len(spec['queries']) - len(auto)} need manual judgement) ===")
    else:
        print(f"\n=== {len(spec['queries'])} queries need manual judgement ===")


if __name__ == "__main__":
    main()
