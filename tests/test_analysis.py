"""Tests für die Auswertungsfunktionen – mit handgerechneten Beispielen."""

import pytest

from priorisierer.analysis import (
    average_ranks,
    compliance_summary,
    discrimination,
    median_scores,
    ranking_stability,
    score_distribution,
    spearman,
    stability,
    summarize,
)
from priorisierer.models import Compliance, ComplianceCategory, CriterionScore, Evaluation, Weights

EQUAL = Weights(impact=25, reach=25, effort=25, risk=25)


def ev(idea_id: str, impact: int, reach: int = 3, effort: int = 3, risk: int = 3, flag: bool = False) -> Evaluation:
    """Kurzform für eine Evaluation; flag=True setzt die Kategorie Datenschutz."""
    return Evaluation(
        idea_id=idea_id,
        assumption="Test",
        impact=CriterionScore(reasoning="t", score=impact),
        reach=CriterionScore(reasoning="t", score=reach),
        effort=CriterionScore(reasoning="t", score=effort),
        risk=CriterionScore(reasoning="t", score=risk),
        compliance=Compliance(
            flag=flag, categories=[ComplianceCategory.GDPR] if flag else [], note="x" if flag else ""
        ),
    )


# --- Spearman ---------------------------------------------------------------


def test_average_ranks_with_ties() -> None:
    assert average_ranks([10, 20, 20, 30]) == [4, 2.5, 2.5, 1]
    assert average_ranks([5, 5, 5]) == [2, 2, 2]


def test_spearman_hand_calculated_without_ties() -> None:
    # Ränge x: 1 2 3 4 5, y: 2 1 4 3 5 → d = −1 1 −1 1 0 → Σd² = 4
    # ρ = 1 − 6·4 / (5·(25 − 1)) = 1 − 24/120 = 0,8
    x = [50, 40, 30, 20, 10]
    y = [40, 50, 20, 30, 10]
    assert spearman(x, y) == pytest.approx(0.8)


def test_spearman_hand_calculated_with_ties() -> None:
    # Ränge x: [4, 2.5, 2.5, 1], y: [4, 3, 2, 1], beide Mittel 2,5
    # Kovarianz-Summe 4,5; Σ(x−x̄)² = 4,5; Σ(y−ȳ)² = 5 → ρ = 4,5 / √22,5 = 3/√10 ≈ 0,9487
    assert spearman([10, 20, 20, 30], [1, 2, 3, 4]) == pytest.approx(3 / 10**0.5)


def test_spearman_extremes_and_undefined() -> None:
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    assert spearman([1, 2, 3], [7, 7, 7]) is None  # konstante Rangliste
    assert spearman([1], [1]) is None
    with pytest.raises(ValueError):
        spearman([1, 2], [1])


# --- Verteilung, Trennschärfe, Stabilität -----------------------------------------


RUNS = [
    [ev("a", 1), ev("b", 3), ev("c", 5)],
    [ev("a", 1), ev("b", 3), ev("c", 4)],
    [ev("a", 2), ev("b", 3), ev("c", 5)],
]


def test_score_distribution_counts_all_runs() -> None:
    assert score_distribution(RUNS)["impact"] == {1: 2, 2: 1, 3: 3, 4: 1, 5: 2}
    assert score_distribution(RUNS)["reach"] == {1: 0, 2: 0, 3: 9, 4: 0, 5: 0}


def test_median_scores() -> None:
    medians = median_scores(RUNS)
    assert medians["a"]["impact"] == 1
    assert medians["c"]["impact"] == 5


def test_discrimination_is_population_std_of_medians() -> None:
    # Mediane Nutzen: 1, 3, 5 → Mittel 3 → Varianz (4 + 0 + 4)/3 → σ = √(8/3) ≈ 1,633
    result = discrimination(RUNS)
    assert result["impact"] == pytest.approx((8 / 3) ** 0.5)
    assert result["reach"] == 0  # alle 3 → trennt nicht


def test_discrimination_reference_values() -> None:
    # Gleichverteilt 1–5 → ≈ 1,41; Hälfte 1, Hälfte 5 → Maximum 2,0
    uniform = [[ev(str(s), s) for s in (1, 2, 3, 4, 5)]]
    extreme = [[ev("a", 1), ev("b", 1), ev("c", 5), ev("d", 5)]]
    assert discrimination(uniform)["impact"] == pytest.approx(2**0.5)
    assert discrimination(extreme)["impact"] == pytest.approx(2.0)


def test_stability_ranges() -> None:
    # Spannweiten Nutzen: a 1, b 0, c 1 → Anteil 0 = 1/3, Mittel 2/3
    impact = stability(RUNS)["impact"]
    assert impact is not None
    assert impact.share_zero_range == pytest.approx(1 / 3)
    assert impact.mean_range == pytest.approx(2 / 3)
    assert stability(RUNS)["reach"].share_zero_range == 1


def test_stability_needs_two_runs() -> None:
    assert stability([RUNS[0]])["impact"] is None


def test_missing_idea_in_one_run_is_tolerated() -> None:
    runs = [[ev("a", 1), ev("b", 5)], [ev("a", 2)]]  # b scheiterte im 2. Lauf
    assert median_scores(runs)["b"]["impact"] == 5
    impact = stability(runs)["impact"]
    assert impact.mean_range == 1  # nur a zählt


# --- Ranking-Stabilität ------------------------------------------------------------


def test_ranking_stability_identical_runs() -> None:
    run = [ev("a", 5), ev("b", 3), ev("c", 1), ev("d", 2)]
    result = ranking_stability([run, run], EQUAL)
    assert result.mean_spearman == pytest.approx(1.0)
    assert result.pair_count == 1
    assert result.top_identical is True


def test_ranking_stability_detects_changed_top3() -> None:
    first = [ev("a", 5), ev("b", 4), ev("c", 3), ev("d", 1)]
    second = [ev("a", 5), ev("b", 4), ev("c", 1), ev("d", 3)]  # c und d tauschen
    result = ranking_stability([first, second], EQUAL)
    assert result.top_identical is False
    assert result.top_per_run == [["a", "b", "c"], ["a", "b", "d"]]
    # Ränge [1,2,3,4] vs. [1,2,4,3] → Σd² = 2 → ρ = 1 − 12/60 = 0,8
    assert result.mean_spearman == pytest.approx(0.8)


def test_ranking_stability_single_run() -> None:
    result = ranking_stability([RUNS[0]], EQUAL)
    assert result.mean_spearman is None
    assert result.top_identical is None


# --- Compliance ----------------------------------------------------------------------


def test_compliance_summary() -> None:
    runs = [
        [ev("a", 3, flag=True), ev("b", 3, flag=False), ev("c", 3, flag=True)],
        [ev("a", 3, flag=True), ev("b", 3, flag=True), ev("c", 3, flag=True)],
        [ev("a", 3, flag=True), ev("b", 3, flag=False), ev("c", 3, flag=False)],
    ]
    result = compliance_summary(runs)
    assert result.flagged_per_run == [2, 3, 1]
    assert result.flagged_median == 2
    assert result.category_counts == {"Datenschutz (DSGVO)": 6}
    assert result.share_consistent_flag == pytest.approx(1 / 3)  # nur a immer gleich


def test_summarize_combines_everything() -> None:
    summary = summarize(RUNS, EQUAL)
    assert summary.run_count == 3
    assert summary.idea_count == 3
    assert summary.ranking.top_identical is True
