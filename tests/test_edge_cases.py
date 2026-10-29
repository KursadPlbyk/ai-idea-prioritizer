"""Tests für die Grenzfall-Prüfung – reine Funktionen, ohne API."""

import pytest
from pydantic import ValidationError

from priorisierer.edge_cases import Expectation, ScoreRule, all_passed, check_expectation, load_edge_cases
from priorisierer.models import Compliance, ComplianceCategory, CriterionScore, Evaluation
from priorisierer.prompts import build_user_message


def ev(impact: int, reach: int, effort: int, risk: int, categories: list[ComplianceCategory] | None = None) -> Evaluation:
    categories = categories or []
    return Evaluation(
        idea_id="x",
        assumption="Test",
        impact=CriterionScore(reasoning="t", score=impact),
        reach=CriterionScore(reasoning="t", score=reach),
        effort=CriterionScore(reasoning="t", score=effort),
        risk=CriterionScore(reasoning="t", score=risk),
        compliance=Compliance(flag=bool(categories), categories=categories, note="x" if categories else ""),
    )


def test_exact_score_rule() -> None:
    expectation = Expectation(scores={"impact": ScoreRule(min=1, max=1)}, flag=False)
    assert all_passed(check_expectation(ev(1, 2, 1, 1), expectation))
    results = check_expectation(ev(2, 2, 1, 1), expectation)
    assert not all_passed(results)
    assert results[0].description == "Nutzen = 1"
    assert results[0].actual == "2"


def test_min_and_max_rules() -> None:
    expectation = Expectation(scores={"risk": ScoreRule(min=4), "impact": ScoreRule(max=2)})
    assert all_passed(check_expectation(ev(2, 3, 3, 4), expectation))
    assert not all_passed(check_expectation(ev(3, 3, 3, 4), expectation))
    assert not all_passed(check_expectation(ev(2, 3, 3, 3), expectation))
    assert [r.description for r in check_expectation(ev(2, 3, 3, 4), expectation)] == ["Risiko ≥ 4", "Nutzen ≤ 2"]


def test_required_categories_each_checked_separately() -> None:
    expectation = Expectation(
        flag=True, categories_include=[ComplianceCategory.CODETERMINATION, ComplianceCategory.GDPR]
    )
    only_codetermination = check_expectation(ev(3, 3, 3, 3, [ComplianceCategory.CODETERMINATION]), expectation)
    assert [r.passed for r in only_codetermination] == [True, True, False]  # Flag, Mitbestimmung, DSGVO
    assert not all_passed(only_codetermination)
    both = [ComplianceCategory.CODETERMINATION, ComplianceCategory.GDPR]
    assert all_passed(check_expectation(ev(3, 3, 3, 3, both), expectation))


def test_flag_expected_false() -> None:
    expectation = Expectation(flag=False)
    assert not all_passed(check_expectation(ev(1, 1, 1, 1, [ComplianceCategory.INFOSEC]), expectation))


def test_not_all_scores_equal_for_injection() -> None:
    expectation = Expectation(not_all_scores_equal=5)
    assert not all_passed(check_expectation(ev(5, 5, 5, 5), expectation))
    assert all_passed(check_expectation(ev(5, 5, 5, 4), expectation))
    assert check_expectation(ev(5, 5, 5, 5), expectation)[0].actual == "5/5/5/5"


def test_empty_expectation_has_no_checks() -> None:
    assert check_expectation(ev(3, 3, 3, 3), Expectation()) == []


def test_score_rule_range_validated() -> None:
    with pytest.raises(ValidationError):
        ScoreRule(min=0)


def test_edge_case_file_loads_with_agreed_expectations() -> None:
    cases = {case.id: case for case in load_edge_cases()}
    assert list(cases) == ["edge-01", "edge-02", "edge-03", "edge-04", "edge-05"]
    assert cases["edge-03"].expected.categories_include == [ComplianceCategory.CODETERMINATION, ComplianceCategory.GDPR]
    assert cases["edge-05"].expected.scores["impact"].max == 2
    assert cases["edge-05"].expected.not_all_scores_equal == 5


def test_expectation_never_reaches_prompt() -> None:
    for case in load_edge_cases():
        idea = case.to_idea()
        assert not hasattr(idea, "expected")
        message = build_user_message(idea)
        assert "expected" not in message
        assert "categories_include" not in message


def test_report_shows_pass_counts_and_assumptions() -> None:
    from priorisierer.edge_cases import EdgeCase, render_report

    case = EdgeCase(
        id="x", title="Testidee", expected=Expectation(scores={"impact": ScoreRule(max=2)})
    )
    good, bad = ev(1, 1, 1, 1), ev(4, 1, 1, 1)
    report = render_report([case], [[good], [bad], []], header="Kopf")
    assert "| x | Testidee | 1/3 |" in report
    assert "❌ Nutzen ≤ 2 (ist: 4)" in report
    assert "Annahme: Test" in report
    assert "Lauf 3:** keine Bewertung" in report
