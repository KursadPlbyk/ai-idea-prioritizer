"""Tests für die Bewertungsformeln (Beispielwerte aus docs/prompts/01_grundgeruest.md)."""

import pytest
from pydantic import ValidationError

from priorisierer.models import Compliance, CriterionScore, Evaluation, Weights
from priorisierer.scoring import (
    BIG_PROJECT,
    FILL_IN,
    QUICK_WIN,
    TIME_SINK,
    normalized_weights,
    quadrant,
    rank,
    rice_score,
    to_points,
    weighted_score,
)

EQUAL_WEIGHTS = Weights(impact=25, reach=25, effort=25, risk=25)


def make_evaluation(impact: int, reach: int, effort: int, risk: int, idea_id: str = "x") -> Evaluation:
    """Erzeugt eine Evaluation mit den angegebenen Scores."""
    return Evaluation(
        idea_id=idea_id,
        assumption="Test",
        impact=CriterionScore(score=impact, reasoning="Test"),
        reach=CriterionScore(score=reach, reasoning="Test"),
        effort=CriterionScore(score=effort, reasoning="Test"),
        risk=CriterionScore(score=risk, reasoning="Test"),
        compliance=Compliance(flag=False, categories=[], note=""),
    )


# (Nutzen, Reichweite, Aufwand, Risiko, gewichtete Summe, RICE)
EXAMPLES = {
    "A": (3, 5, 1, 2, 4.25, 12.0),
    "B": (5, 3, 4, 4, 3.0, 1.5),
    "C": (5, 5, 5, 3, 3.5, 3.0),
    "D": (2, 2, 1, 1, 3.5, 4.0),
}


@pytest.mark.parametrize("name", EXAMPLES)
def test_weighted_score_examples(name: str) -> None:
    impact, reach, effort, risk, expected, _ = EXAMPLES[name]
    evaluation = make_evaluation(impact, reach, effort, risk)
    assert weighted_score(evaluation, EQUAL_WEIGHTS) == pytest.approx(expected)


@pytest.mark.parametrize("name", EXAMPLES)
def test_rice_score_examples(name: str) -> None:
    impact, reach, effort, risk, _, expected = EXAMPLES[name]
    evaluation = make_evaluation(impact, reach, effort, risk)
    assert rice_score(evaluation) == pytest.approx(expected)


def test_to_points_range() -> None:
    assert to_points(1) == 0
    assert to_points(3) == 50
    assert to_points(5) == 100


@pytest.mark.parametrize(
    ("impact", "reach", "effort", "expected"),
    [
        (4, 4, 1, QUICK_WIN),
        (5, 5, 5, BIG_PROJECT),
        (2, 2, 1, FILL_IN),
        (2, 1, 4, TIME_SINK),
    ],
)
def test_quadrant(impact: int, reach: int, effort: int, expected: str) -> None:
    assert quadrant(make_evaluation(impact, reach, effort, 3)) == expected


@pytest.mark.parametrize(
    ("impact", "reach", "effort", "expected"),
    [
        (3, 3, 2, FILL_IN),  # Wert = 3 → niedrig
        (3, 3, 3, TIME_SINK),  # Wert = 3 → niedrig, Aufwand = 3 → hoch
        (4, 3, 2, QUICK_WIN),  # Wert = 3,5 → hoch
        (4, 3, 3, BIG_PROJECT),  # Wert = 3,5 → hoch, Aufwand = 3 → hoch
    ],
)
def test_quadrant_thresholds(impact: int, reach: int, effort: int, expected: str) -> None:
    assert quadrant(make_evaluation(impact, reach, effort, 3)) == expected


def test_weights_are_normalized() -> None:
    evaluation = make_evaluation(3, 5, 1, 2)
    small = Weights(impact=1, reach=1, effort=1, risk=1)
    assert weighted_score(evaluation, small) == pytest.approx(weighted_score(evaluation, EQUAL_WEIGHTS))
    assert sum(normalized_weights(Weights(impact=3, reach=1, effort=0, risk=0)).values()) == pytest.approx(1)


def test_all_zero_weights_raise() -> None:
    with pytest.raises(ValueError):
        normalized_weights(Weights(impact=0, reach=0, effort=0, risk=0))


def test_rank_sorts_descending() -> None:
    evaluations = [make_evaluation(*EXAMPLES[name][:4], idea_id=name) for name in EXAMPLES]
    ranked = rank(evaluations, EQUAL_WEIGHTS)
    assert [evaluation.idea_id for evaluation, _ in ranked] == ["A", "C", "D", "B"]


def test_weights_change_ranking() -> None:
    evaluations = [make_evaluation(*EXAMPLES[name][:4], idea_id=name) for name in ("C", "D")]
    impact_heavy = Weights(impact=100, reach=0, effort=0, risk=0)
    effort_heavy = Weights(impact=0, reach=0, effort=100, risk=0)
    assert rank(evaluations, impact_heavy)[0][0].idea_id == "C"
    assert rank(evaluations, effort_heavy)[0][0].idea_id == "D"


@pytest.mark.parametrize("invalid", [0, 6, -1, 3.5])
def test_scores_outside_range_are_rejected(invalid: float) -> None:
    with pytest.raises(ValidationError):
        CriterionScore(score=invalid, reasoning="Test")


# --- Formel-Umschalter, Wettkampf-Rangfolge, Δ-Rang (Auftrag 4) -----------------------

from priorisierer.scoring import Formula, rank_delta, rank_positions, score  # noqa: E402


def test_rank_with_rice_uses_rice_order() -> None:
    # A: RICE 12, B: 1,5, C: 3, D: 4 → Reihenfolge A, D, C, B
    evaluations = [make_evaluation(*EXAMPLES[name][:4], idea_id=name) for name in EXAMPLES]
    ranked = rank(evaluations, EQUAL_WEIGHTS, Formula.RICE)
    assert [evaluation.idea_id for evaluation, _ in ranked] == ["A", "D", "C", "B"]
    assert ranked[0][1] == pytest.approx(12.0)


def test_rice_ignores_weights() -> None:
    evaluation = make_evaluation(3, 5, 1, 2)
    assert score(evaluation, Weights(impact=0, reach=0, effort=0, risk=0), Formula.RICE) == pytest.approx(12.0)


def test_rank_positions_share_place_on_tie() -> None:
    # Gewichtete Summe gleich: A 4,25, C 3,5, D 3,5, B 3,0 → Plätze 1, 2, 2, 4
    evaluations = [make_evaluation(*EXAMPLES[name][:4], idea_id=name) for name in EXAMPLES]
    assert rank_positions(evaluations, EQUAL_WEIGHTS) == {"A": 1, "B": 4, "C": 2, "D": 2}


def test_rank_delta_between_formulas() -> None:
    # Gewichtet: A1 C2 D2 B4 · RICE: A1 D2 C3 B4
    evaluations = [make_evaluation(*EXAMPLES[name][:4], idea_id=name) for name in EXAMPLES]
    delta = rank_delta(evaluations, EQUAL_WEIGHTS, Formula.WEIGHTED)
    assert delta == {"A": 0, "B": 0, "C": 1, "D": 0}  # C steht gewichtet 1 Platz besser als bei RICE
    assert rank_delta(evaluations, EQUAL_WEIGHTS, Formula.RICE) == {"A": 0, "B": 0, "C": -1, "D": 0}


def test_rank_delta_none_when_weights_zero() -> None:
    evaluations = [make_evaluation(3, 3, 3, 3, idea_id="x")]
    assert rank_delta(evaluations, Weights(impact=0, reach=0, effort=0, risk=0), Formula.RICE) is None
