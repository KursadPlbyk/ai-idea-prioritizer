"""Grenzfälle (Sanity Check): Ideen mit offensichtlicher Erwartung und deren Prüfung.

Die Erwartung (`expected`) dient nur dem Vergleich – sie gelangt nie in den Prompt.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field

from priorisierer.models import ComplianceCategory, Evaluation, Idea

EDGE_CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "edge_case_ideas.json"

CRITERIA_LABELS = {"impact": "Nutzen", "reach": "Reichweite", "effort": "Aufwand", "risk": "Risiko"}


class ScoreRule(BaseModel):
    """Erlaubter Bereich für einen Score. „Genau 1“ = min 1, max 1."""

    min: int | None = Field(default=None, ge=1, le=5)
    max: int | None = Field(default=None, ge=1, le=5)


class Expectation(BaseModel):
    """Was bei einem Grenzfall herauskommen muss. Nicht gesetzte Felder werden nicht geprüft."""

    scores: dict[str, ScoreRule] = Field(default_factory=dict)
    flag: bool | None = None
    categories_include: list[ComplianceCategory] = Field(default_factory=list)
    # Für Prompt-Injection: Nicht alle vier Scores dürfen diesen Wert haben.
    not_all_scores_equal: int | None = Field(default=None, ge=1, le=5)


class EdgeCase(BaseModel):
    """Idee plus Erwartung – getrennt gehalten, damit nur die Idee bewertet wird."""

    id: str
    title: str
    description: str | None = None
    expected: Expectation

    def to_idea(self) -> Idea:
        """Die reine Idee ohne Erwartung – das Einzige, was der Evaluator bekommt."""
        return Idea(id=self.id, title=self.title, description=self.description)


class CheckResult(BaseModel):
    """Eine Teilprüfung, z. B. „Nutzen ≤ 2“ – erfüllt oder nicht, mit dem tatsächlichen Wert."""

    description: str
    passed: bool
    actual: str


def load_edge_cases(path: Path = EDGE_CASES_FILE) -> list[EdgeCase]:
    """Lädt die Grenzfälle samt Erwartungen."""
    return [EdgeCase.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def _describe_rule(label: str, rule: ScoreRule) -> str:
    if rule.min is not None and rule.min == rule.max:
        return f"{label} = {rule.min}"
    parts = []
    if rule.min is not None:
        parts.append(f"≥ {rule.min}")
    if rule.max is not None:
        parts.append(f"≤ {rule.max}")
    return f"{label} " + " und ".join(parts)


def check_expectation(evaluation: Evaluation, expectation: Expectation) -> list[CheckResult]:
    """Prüft eine Bewertung gegen die Erwartung – eine Teilprüfung pro Regel. Reine Funktion."""
    results: list[CheckResult] = []
    for name, rule in expectation.scores.items():
        score = getattr(evaluation, name).score
        passed = (rule.min is None or score >= rule.min) and (rule.max is None or score <= rule.max)
        results.append(CheckResult(description=_describe_rule(CRITERIA_LABELS[name], rule), passed=passed, actual=str(score)))

    compliance = evaluation.compliance
    if expectation.flag is not None:
        results.append(
            CheckResult(
                description="Flag gesetzt" if expectation.flag else "kein Flag",
                passed=compliance.flag == expectation.flag,
                actual="Flag" if compliance.flag else "kein Flag",
            )
        )
    for category in expectation.categories_include:
        results.append(
            CheckResult(
                description=f"Kategorie „{category.value}“",
                passed=category in compliance.categories,
                actual=", ".join(c.value for c in compliance.categories) or "keine",
            )
        )
    if expectation.not_all_scores_equal is not None:
        scores = [getattr(evaluation, name).score for name in CRITERIA_LABELS]
        results.append(
            CheckResult(
                description=f"nicht alle Scores {expectation.not_all_scores_equal}",
                passed=any(score != expectation.not_all_scores_equal for score in scores),
                actual="/".join(map(str, scores)),
            )
        )
    return results


def all_passed(results: list[CheckResult]) -> bool:
    """Erwartung erfüllt = alle Teilprüfungen bestanden."""
    return all(result.passed for result in results)


# --- Bericht ----------------------------------------------------------------------


def render_report(cases: list[EdgeCase], runs: list[list[Evaluation]], header: str) -> str:
    """Markdown-Bericht: Übersicht „erfüllt in x/n Läufen“ und pro Idee alle Bewertungen mit Teilprüfungen."""
    by_run = [{evaluation.idea_id: evaluation for evaluation in run} for run in runs]
    lines = [
        "# Grenzfälle (Sanity Check)",
        "",
        header,
        "",
        "Erwartungen stehen in `data/edge_case_ideas.json` und gelangen nicht in den Prompt. "
        "Erfüllt = alle Teilprüfungen eines Laufs bestanden. Die **Annahme** wird nicht automatisch geprüft "
        "(bei edge-05 manuell lesen).",
        "",
        "| ID | Idee | Erwartung erfüllt |",
        "|---|---|---|",
    ]
    for case in cases:
        evaluations = [run[case.id] for run in by_run if case.id in run]
        passed = sum(all_passed(check_expectation(e, case.expected)) for e in evaluations)
        lines.append(f"| {case.id} | {case.title} | {passed}/{len(runs)} |")

    for case in cases:
        lines += ["", f"## {case.id} – {case.title}", ""]
        if case.description:
            lines += [f"> {case.description}", ""]
        for number, run in enumerate(by_run, start=1):
            evaluation = run.get(case.id)
            if evaluation is None:
                lines += [f"**Lauf {number}:** keine Bewertung (Aufruf fehlgeschlagen)", ""]
                continue
            results = check_expectation(evaluation, case.expected)
            scores = " / ".join(f"{label} {getattr(evaluation, name).score}" for name, label in CRITERIA_LABELS.items())
            compliance = evaluation.compliance
            flag_text = (
                "Flag: " + ", ".join(c.value for c in compliance.categories) if compliance.flag else "kein Flag"
            )
            checks = " · ".join(f"{'✅' if r.passed else '❌'} {r.description} (ist: {r.actual})" for r in results)
            lines += [
                f"**Lauf {number}:** {'erfüllt' if all_passed(results) else 'NICHT erfüllt'} – {scores} – {flag_text}",
                f"- Prüfungen: {checks}",
                f"- Annahme: {evaluation.assumption}",
            ]
            if compliance.flag:
                lines.append(f"- Compliance-Begründung: {compliance.note}")
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
