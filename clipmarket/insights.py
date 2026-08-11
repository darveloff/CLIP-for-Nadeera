"""Read content insights straight off the tagging pass.

Every insight is framed observation -> so-what -> action, which is what makes it
usable by a marketing team rather than merely descriptive.
"""
from collections import Counter
from itertools import combinations
from pathlib import Path

from .vocabulary import CATEGORIES, VOCABULARY
from . import config

TAGS_BY_CATEGORY = {c: [t.name for t in VOCABULARY if t.category == c] for c in CATEGORIES}


def _confident(record):
    return [t for t in record.get("tags", []) if not t["needs_review"]]


def tag_counts(records) -> Counter:
    c = Counter()
    for r in records:
        for t in _confident(r):
            c[t["tag"]] += 1
    return c


def category_share(records, category: str) -> list[tuple[str, int, float]]:
    """Distribution within one category, as (tag, count, share-of-tagged-assets)."""
    names = set(TAGS_BY_CATEGORY[category])
    counts = Counter()
    tagged_assets = 0
    for r in records:
        hits = [t["tag"] for t in _confident(r) if t["tag"] in names]
        if hits:
            tagged_assets += 1
            counts.update(hits)
    total = tagged_assets or 1
    return [(tag, n, n / total) for tag, n in counts.most_common()]


def cooccurrence_gaps(records, min_support: int = 3) -> list[tuple[str, str]]:
    """Tag pairs that are individually common but never appear together.

    These are the content gaps -- combinations the library simply does not cover.
    """
    counts = tag_counts(records)
    common = [t for t, n in counts.items() if n >= min_support]
    seen = set()
    for r in records:
        names = [t["tag"] for t in _confident(r)]
        seen.update(frozenset(p) for p in combinations(sorted(names), 2))
    return [
        (a, b)
        for a, b in combinations(sorted(common), 2)
        if frozenset((a, b)) not in seen
    ]


def build_report(records) -> str:
    n = len(records)
    counts = tag_counts(records)
    lines = [
        "# Content Insights",
        "",
        f"Library: **{n} assets** "
        f"({sum(1 for r in records if r['kind'] == 'keyframe')} video keyframes, "
        f"{sum(1 for r in records if r['kind'] == 'image')} images).",
        "",
        "Counts below use only high-confidence tags; mood and brand-element tags are",
        "excluded from the confident set by design (see docs/accuracy_notes.md).",
        "",
        "## Tag distribution by category",
        "",
    ]
    for cat in CATEGORIES:
        rows = category_share(records, cat)
        if not rows:
            continue
        lines.append(f"### {cat.replace('_', ' ').title()}")
        lines.append("")
        lines.append("| tag | assets | share |")
        lines.append("|---|---:|---:|")
        for tag, cnt, share in rows:
            lines.append(f"| {tag} | {cnt} | {share:.0%} |")
        lines.append("")

    lines += ["## Findings", ""]
    for i, finding in enumerate(_findings(records, counts), 1):
        lines.append(f"**{i}. {finding['observation']}**")
        lines.append("")
        lines.append(f"- *So what:* {finding['so_what']}")
        lines.append(f"- *Action:* {finding['action']}")
        lines.append("")

    dupes = [r for r in records if r.get("near_duplicate_of")]
    if dupes:
        lines += [
            "## Near-duplicate assets",
            "",
            f"{len(dupes)} asset(s) are near-identical (cosine >= "
            f"{config.DUPLICATE_THRESHOLD}) to another asset already in the library. "
            "Flagged for review, not removed --",
            "confirm before deleting either side.",
            "",
        ]
        for r in dupes[:20]:
            lines.append(f"- `{Path(r['path']).name}` duplicates `{r['near_duplicate_of']}`")
        if len(dupes) > 20:
            lines.append(f"- ...and {len(dupes) - 20} more")
        lines.append("")

    unused = [t.name for t in VOCABULARY if counts[t.name] == 0]
    if unused:
        lines += [
            "## Vocabulary with zero confident matches",
            "",
            "Either the library genuinely lacks this content, or the tag prompt needs",
            "rewording -- worth checking both before reporting it as a gap.",
            "",
            *(f"- {t}" for t in unused),
            "",
        ]
    return "\n".join(lines)


def _findings(records, counts) -> list[dict]:
    """Derive concrete findings from the aggregates. Kept small and legible on purpose."""
    findings = []

    setting = category_share(records, "setting")
    if setting:
        top, cnt, share = setting[0]
        findings.append(
            {
                "observation": f"{share:.0%} of assets with a detected setting are '{top}' "
                f"({cnt} assets).",
                "so_what": "The library skews to a single environment, which limits how many "
                "distinct campaign contexts can be illustrated without reusing shots.",
                "action": "Commission a shoot in the least-represented settings "
                + ", ".join(f"'{t}'" for t, _, _ in setting[-2:])
                + " before the next campaign cycle.",
            }
        )

    subject = category_share(records, "subject")
    if subject:
        people = sum(c for t, c, _ in subject if "person" in t or "people" in t or "team" in t)
        product = sum(c for t, c, _ in subject if "product" in t)
        findings.append(
            {
                "observation": f"People-centric assets ({people}) vs. product-centric "
                f"assets ({product}).",
                "so_what": "The ratio determines whether the library can support "
                "product-led launch creative or only brand/culture storytelling.",
                "action": "Rebalance toward whichever side is thinner for the next quarter's "
                "content calendar.",
            }
        )

    gaps = cooccurrence_gaps(records)
    if gaps:
        pairs = ", ".join(f"'{a}' + '{b}'" for a, b in gaps[:3])
        findings.append(
            {
                "observation": f"Common tags that never co-occur: {pairs}.",
                "so_what": "These are combinations the library cannot currently illustrate at "
                "all, even though each element exists in isolation.",
                "action": "Add these specific combinations to the next shot list -- they are "
                "cheap to capture alongside shots already planned.",
            }
        )
    return findings


def write_report(records) -> str:
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DOCS_DIR / "insights.md"
    path.write_text(build_report(records))
    return str(path)
