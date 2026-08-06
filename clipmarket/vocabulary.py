"""The tag vocabulary: the one piece of design work in an inference-only pipeline.

Tags are grouped by category so the insights step has something to group by, and each
entry carries its own prompt template -- template wording measurably changes zero-shot
accuracy, so it is a per-tag tuning knob rather than a global constant.
"""
from dataclasses import dataclass

DEFAULT_TEMPLATE = "a photo of {tag}"
MOOD_TEMPLATE = "a {tag} photo"
STYLE_TEMPLATE = "a {tag} photograph"


@dataclass(frozen=True)
class Tag:
    name: str
    category: str
    template: str = DEFAULT_TEMPLATE

    def prompt(self) -> str:
        return self.template.format(tag=self.name)


def _mk(category: str, names, template: str = DEFAULT_TEMPLATE):
    return [Tag(n, category, template) for n in names]


VOCABULARY: list[Tag] = [
    *_mk("subject", [
        "a person", "a group of people", "a team working together",
        "a product close-up", "an animal", "food", "a cityscape",
        "nature and landscape", "a building",
    ]),
    *_mk("composition", [
        "bright and high-key", "dark and moody", "minimalist",
        "busy and cluttered", "a close-up shot", "a wide establishing shot",
    ], STYLE_TEMPLATE),
    *_mk("setting", [
        "an office", "the outdoors", "a conference or event", "a photo studio",
        "a retail store", "a home interior",
    ]),
    *_mk("mood", [
        "professional", "casual", "energetic", "calm", "celebratory",
    ], MOOD_TEMPLATE),
    *_mk("brand_elements", [
        "a visible brand logo", "a product held in a hand",
        "a computer screen or device", "text or typography overlay",
    ]),
]

CATEGORIES = sorted({t.category for t in VOCABULARY})

# Categories CLIP is unreliable at (see docs/accuracy_notes.md). Tags in these
# categories are always surfaced for human review regardless of score.
LOW_CONFIDENCE_CATEGORIES = {"mood", "brand_elements"}


def prompts() -> list[str]:
    return [t.prompt() for t in VOCABULARY]
