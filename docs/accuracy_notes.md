# Tagging Accuracy Notes

Zero-shot CLIP has a well-defined shape of strengths and weaknesses. Documenting it is
part of the deliverable, not an admission — the scoping decisions below are deliberate.

Numbers in this file get filled in from a real `scripts/run_eval.py` run against the
production library; the qualitative shape below holds regardless.

## Where it is strong

- Concrete objects — laptops, coffee cups, food, vehicles.
- Broad scene type — indoor vs. outdoor, office vs. nature vs. street.
- Obvious subject matter — people, animals, buildings.
- Overall visual style — bright/high-key vs. dark/moody, cluttered vs. minimal.

These map to the `subject`, `setting`, and `composition` categories in
`clipmarket/vocabulary.py`, which is why those categories are trusted by default.

## Where it is weak

- **Counting.** "Exactly three people" is unreliable; CLIP has no explicit count notion.
- **Text and logos.** Small embedded text and brand marks are read inconsistently at
  ViT-B/32 resolution.
- **Fine emotional distinction.** "Energetic" vs. "celebratory" separates poorly.
- **Similar products.** Distinguishing one SKU from a near-identical one needs
  brand-specific fine-tuning, which is out of scope.
- **Compositional judgement** requiring context CLIP was not trained on (e.g. "leaves room
  for a headline in the top third").

## How the weakness is handled

Rather than trusting low-confidence scores, `clipmarket/tag.py` marks a tag
`needs_review = true` when either:

1. its score is below `TAG_MIN_SCORE`, or
2. its category is in `LOW_CONFIDENCE_CATEGORIES` (`mood`, `brand_elements`).

Flagged tags are still stored and still shown in the UI (with a `?` marker) — they are
useful as suggestions — but they are **excluded from the aggregate counts** that produce
`docs/insights.md`. The insights are therefore built only on the categories CLIP is
actually reliable at.

## Query-type expectations

`eval/queries.yaml` mixes four query types on purpose:

| Type | Example | Expectation |
|---|---|---|
| object | "a photo with a laptop or computer" | strong |
| scene | "an outdoor team photo" | strong |
| mood | "a bright energetic photo" | mixed — sensitive to prompt wording |
| compound | "people outdoors smiling" | weakest — CLIP tends to satisfy one clause |

When a query underperforms, reword it with a CLIP-style prompt template before concluding
the model can't do it — template wording changes results meaningfully.

## Known limits of this build

- Small library: some queries legitimately have only 1–2 good matches. `SEARCH_MIN_SCORE`
  returns "no strong match" rather than padding the grid with weak results.
- ViT-B/32 is the accuracy/speed tradeoff chosen for a CPU-only, two-week scope. A larger
  backbone (ViT-L/14) would improve fine-grained tagging at several times the encode cost.
- Similarity scores are comparable *within* one query, not across queries — don't read an
  absolute score as a quality measure.
