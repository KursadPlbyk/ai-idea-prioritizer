"""Prüft, dass die Rubrik in docs/BEWERTUNGSMODELL.md und der Standard-Prompt übereinstimmen."""

import re
from pathlib import Path

from priorisierer.prompts import DEFAULT_PROMPT_VERSION, SYSTEM_PROMPTS

DOC = Path(__file__).resolve().parent.parent / "docs" / "BEWERTUNGSMODELL.md"
ANCHOR_ROW = re.compile(r"^\| ([1-5]) \| (.+) \|$")


def rubric_anchors() -> list[tuple[str, str]]:
    """Alle (Score, Ankertext)-Zeilen aus Abschnitt 1 der Doku."""
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## 1. Kriterien und Rubrik", 1)[1].split("\n## 2.", 1)[0]
    return [match.groups() for line in section.splitlines() if (match := ANCHOR_ROW.match(line))]


def test_doc_has_all_twenty_anchors() -> None:
    assert len(rubric_anchors()) == 20  # 4 Kriterien × 5 Stufen


def test_every_doc_anchor_is_in_default_prompt() -> None:
    prompt = SYSTEM_PROMPTS[DEFAULT_PROMPT_VERSION]
    missing = [f"{score}: {text}" for score, text in rubric_anchors() if f"- {score}: {text}\n" not in prompt]
    assert missing == [], f"Doku und Prompt {DEFAULT_PROMPT_VERSION} weichen ab: {missing}"
