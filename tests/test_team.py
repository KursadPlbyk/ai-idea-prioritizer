"""Tests für Team-Korrekturen und Compliance-Prüfstatus."""

from priorisierer.models import (
    Compliance,
    ComplianceCategory,
    ComplianceReview,
    CriterionScore,
    Evaluation,
    ReviewStatus,
    ScoreOverride,
)
from priorisierer.team import apply_overrides, review_status

GDPR, CODET = ComplianceCategory.GDPR, ComplianceCategory.CODETERMINATION


def ev(impact: int = 3, categories: list[ComplianceCategory] | None = None) -> Evaluation:
    categories = categories or []
    return Evaluation(
        idea_id="x",
        assumption="Test",
        impact=CriterionScore(reasoning="KI-Grund", score=impact),
        reach=CriterionScore(reasoning="t", score=3),
        effort=CriterionScore(reasoning="t", score=3),
        risk=CriterionScore(reasoning="t", score=3),
        compliance=Compliance(flag=bool(categories), categories=categories, note="x" if categories else ""),
    )


# --- apply_overrides ------------------------------------------------------------


def test_override_replaces_only_that_score() -> None:
    ai = ev(impact=3)
    effective = apply_overrides(ai, {"impact": ScoreOverride(score=5, reason="Team")})
    assert effective.impact.score == 5
    assert effective.impact.reasoning == "KI-Grund"  # KI-Begründung bleibt
    assert effective.reach == ai.reach


def test_override_does_not_change_ai_evaluation() -> None:
    ai = ev(impact=3)
    apply_overrides(ai, {"impact": ScoreOverride(score=5)})
    assert ai.impact.score == 3


def test_no_overrides_returns_same() -> None:
    ai = ev()
    assert apply_overrides(ai, None) is ai
    assert apply_overrides(ai, {}) is ai


def test_override_survives_reevaluation() -> None:
    # Neue KI-Bewertung mit anderem Wert – die Korrektur liegt getrennt und wirkt weiter.
    overrides = {"impact": ScoreOverride(score=4)}
    first, second = ev(impact=2), ev(impact=5)
    assert apply_overrides(first, overrides).impact.score == 4
    assert apply_overrides(second, overrides).impact.score == 4


# --- review_status ------------------------------------------------------------------


def review(status: ReviewStatus, categories: list[ComplianceCategory] | None = None) -> ComplianceReview:
    return ComplianceReview(status=status, categories=categories or [])


def test_no_flag_needs_no_status() -> None:
    assert review_status(ev(), None) is None
    assert review_status(ev(), review(ReviewStatus.CLEARED, [GDPR])) is None


def test_flag_without_review_is_open() -> None:
    assert review_status(ev(categories=[GDPR]), None) == ReviewStatus.OPEN


def test_cleared_stays_cleared_for_same_categories() -> None:
    assert review_status(ev(categories=[GDPR]), review(ReviewStatus.CLEARED, [GDPR])) == ReviewStatus.CLEARED


def test_cleared_reopens_on_new_category() -> None:
    evaluation = ev(categories=[GDPR, CODET])
    assert review_status(evaluation, review(ReviewStatus.CLEARED, [GDPR])) == ReviewStatus.OPEN


def test_flag_newly_added_after_reevaluation_is_open() -> None:
    # Vorher kein Flag → kein Review gespeichert; nach Neubewertung Flag → offen.
    assert review_status(ev(categories=[CODET]), None) == ReviewStatus.OPEN


def test_rejected_is_sticky_even_without_flag() -> None:
    assert review_status(ev(), review(ReviewStatus.REJECTED, [GDPR])) == ReviewStatus.REJECTED
    assert review_status(ev(categories=[GDPR]), review(ReviewStatus.REJECTED, [GDPR])) == ReviewStatus.REJECTED


def test_explicit_open_review_is_open() -> None:
    assert review_status(ev(categories=[GDPR]), review(ReviewStatus.OPEN, [GDPR])) == ReviewStatus.OPEN
