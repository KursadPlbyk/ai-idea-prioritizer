"""Reine Bewertungsfunktionen: gewichtete Summe, RICE, Matrix-Quadrant, Ranking.

Formeln laut docs/BEWERTUNGSMODELL.md, Abschnitte 4 und 5.
"""

from enum import StrEnum

from priorisierer.models import Evaluation, Weights

QUICK_WIN = "Quick Win"
BIG_PROJECT = "Großes Projekt"
FILL_IN = "Lückenfüller"
TIME_SINK = "Zeitfresser"

# Absichtlich asymmetrisch: Wert ist ein Mittelwert aus Nutzen und Reichweite, und 3 ist dort
# genau die Skalenmitte – erst ein überdurchschnittlicher Wert (> 3) zählt als „hoch“.
# Aufwand 3 bedeutet laut Rubrik bereits „einige Wochen, mehrere Beteiligte oder neues Tool“
# und ist damit kein niedriger Aufwand mehr (≥ 3). So wird ein Quick Win nur, was klar
# nützlich und wirklich günstig ist.
VALUE_THRESHOLD = 3  # Wert > VALUE_THRESHOLD = hoch
EFFORT_THRESHOLD = 3  # Aufwand ≥ EFFORT_THRESHOLD = hoch


def invert(score: int) -> int:
    """Dreht einen 'höher = schlechter'-Score um (Aufwand, Risiko): s' = 6 − s."""
    return 6 - score


def normalized_weights(weights: Weights) -> dict[str, float]:
    """Teilt die Gewichte durch ihre Summe. Wirft ValueError, wenn alle 0 sind."""
    raw = weights.model_dump()
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("Mindestens ein Gewicht muss größer als 0 sein.")
    return {name: value / total for name, value in raw.items()}


def weighted_score(evaluation: Evaluation, weights: Weights) -> float:
    """Gewichtete Summe im Bereich 1–5 (höher = besser)."""
    w = normalized_weights(weights)
    return (
        w["impact"] * evaluation.impact.score
        + w["reach"] * evaluation.reach.score
        + w["effort"] * invert(evaluation.effort.score)
        + w["risk"] * invert(evaluation.risk.score)
    )


def to_points(score: float) -> float:
    """Rechnet einen Score von 1–5 in 0–100 Punkte um."""
    return (score - 1) / 4 * 100


def rice_score(evaluation: Evaluation) -> float:
    """RICE = Reichweite × Nutzen × Confidence / Aufwand, Confidence = (6 − Risiko) / 5."""
    confidence = invert(evaluation.risk.score) / 5
    return evaluation.reach.score * evaluation.impact.score * confidence / evaluation.effort.score


def quadrant(evaluation: Evaluation) -> str:
    """Ordnet die Idee einem Quadranten der Impact/Effort-Matrix zu."""
    value = (evaluation.impact.score + evaluation.reach.score) / 2
    high_value = value > VALUE_THRESHOLD
    high_effort = evaluation.effort.score >= EFFORT_THRESHOLD
    if high_value:
        return BIG_PROJECT if high_effort else QUICK_WIN
    return TIME_SINK if high_effort else FILL_IN


class Formula(StrEnum):
    """Rechenregel für das Ranking. Gleiche KI-Scores, andere Wertentscheidung."""

    WEIGHTED = "Gewichtete Summe"
    RICE = "RICE"


def other_formula(formula: Formula) -> Formula:
    """Die jeweils andere Formel – für den Δ-Rang."""
    return Formula.RICE if formula == Formula.WEIGHTED else Formula.WEIGHTED


def score(evaluation: Evaluation, weights: Weights, formula: Formula = Formula.WEIGHTED) -> float:
    """Score nach gewählter Formel: gewichtete Summe (1–5) oder RICE-Wert (RICE ignoriert die Gewichte)."""
    if formula == Formula.RICE:
        return rice_score(evaluation)
    return weighted_score(evaluation, weights)


def rank(
    evaluations: list[Evaluation], weights: Weights, formula: Formula = Formula.WEIGHTED
) -> list[tuple[Evaluation, float]]:
    """Sortiert Bewertungen absteigend nach Score der gewählten Formel (stabil bei Gleichstand)."""
    scored = [(evaluation, score(evaluation, weights, formula)) for evaluation in evaluations]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


def rank_positions(
    evaluations: list[Evaluation], weights: Weights, formula: Formula = Formula.WEIGHTED
) -> dict[str, int]:
    """Platz pro Idee nach Wettkampf-Rangfolge: Gleichstand teilt sich den Platz (1, 2, 2, 4).

    Platz = 1 + Anzahl der Ideen mit echt höherem Score. So entsteht keine Rangverschiebung,
    die nur aus der Eingabereihenfolge kommt.
    """
    scores = {e.idea_id: score(e, weights, formula) for e in evaluations}
    # Rundung gegen Gleitkomma-Rauschen (0,1 + 0,2 ≠ 0,3), sonst wären Gleichstände keine.
    rounded = {idea_id: round(value, 9) for idea_id, value in scores.items()}
    return {idea_id: 1 + sum(other > value for other in rounded.values()) for idea_id, value in rounded.items()}


def rank_delta(evaluations: list[Evaluation], weights: Weights, formula: Formula) -> dict[str, int] | None:
    """Rangunterschied zur anderen Formel: positiv = in der aktuellen Formel um so viele Plätze besser.

    None, wenn der Vergleich nicht möglich ist (gewichtete Summe mit allen Gewichten 0).
    """
    try:
        current = rank_positions(evaluations, weights, formula)
        other = rank_positions(evaluations, weights, other_formula(formula))
    except ValueError:
        return None
    return {idea_id: other[idea_id] - current[idea_id] for idea_id in current}
