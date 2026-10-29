"""Tests für die Ranking-Ansicht: Korrekturen, Prüfstatus, Filter, Δ-Rang, CSV."""

import csv
import io

import pandas as pd

from priorisierer.models import (
    Compliance,
    ComplianceCategory,
    ComplianceReview,
    CriterionScore,
    Evaluation,
    Idea,
    ReviewStatus,
    ScoreOverride,
    Weights,
)
from priorisierer.ranking_view import build_ranking, format_delta, position_summary, score_cell, to_csv
from priorisierer.scoring import Formula

GDPR = ComplianceCategory.GDPR


def ev(idea_id: str, impact: int, flag: bool = False) -> Evaluation:
    return Evaluation(
        idea_id=idea_id,
        assumption=f"Annahme {idea_id}",
        impact=CriterionScore(reasoning=f"Grund {idea_id}", score=impact),
        reach=CriterionScore(reasoning="t", score=3),
        effort=CriterionScore(reasoning="t", score=3),
        risk=CriterionScore(reasoning="t", score=3),
        compliance=Compliance(flag=flag, categories=[GDPR] if flag else [], note="Daten" if flag else ""),
    )


IDEAS = [Idea(id=i, title=f"Idee {i}") for i in ("a", "b", "c", "d")]
EVALUATIONS = {"a": ev("a", 5), "b": ev("b", 4), "c": ev("c", 3, flag=True), "d": ev("d", 1)}


def build(**kwargs):
    defaults = dict(
        ideas=IDEAS, evaluations=EVALUATIONS, overrides={}, reviews={}, weights=Weights(), formula=Formula.WEIGHTED
    )
    return build_ranking(**(defaults | kwargs))


def order(view) -> list[str]:
    return [row.idea.id for row in view.rows]


def test_default_ranking_order_and_open_status() -> None:
    view = build()
    assert order(view) == ["a", "b", "c", "d"]
    assert [row.rank for row in view.rows] == [1, 2, 3, 4]
    assert view.rows[2].status == ReviewStatus.OPEN


def test_override_changes_rank_but_keeps_ai_value() -> None:
    view = build(overrides={"d": {"impact": ScoreOverride(score=5)}})
    assert order(view)[0] in {"a", "d"} and view.rows[0].rank == 1
    row_d = next(row for row in view.rows if row.idea.id == "d")
    assert row_d.rank == 1  # Gleichstand mit a → teilt Platz 1
    assert row_d.ai.impact.score == 1
    assert row_d.effective.impact.score == 5
    assert score_cell(row_d, "impact") == "5 ✏️"
    assert score_cell(row_d, "reach") == "3"


def test_rejected_goes_to_separate_list() -> None:
    view = build(reviews={"c": ComplianceReview(status=ReviewStatus.REJECTED, note="DSGVO-widrig")})
    assert "c" not in order(view)
    assert [item.idea.id for item in view.rejected] == ["c"]


def test_only_cleared_hides_open_but_keeps_cleared() -> None:
    hidden = build(only_cleared=True)
    assert "c" not in order(hidden)
    assert [item.idea.id for item in hidden.hidden_open] == ["c"]
    cleared = build(only_cleared=True, reviews={"c": ComplianceReview(status=ReviewStatus.CLEARED, categories=[GDPR])})
    assert "c" in order(cleared)
    assert cleared.hidden_open == []


def test_unevaluated_ideas_are_skipped() -> None:
    view = build(ideas=IDEAS + [Idea(id="neu", title="Neu")])
    assert "neu" not in order(view)


def test_recent_marking_and_position_summary() -> None:
    view = build(recent_ids={"b"})
    assert [row.is_recent for row in view.rows] == [False, True, False, False]
    assert position_summary(view, "b") == "Platz 2 von 4 · Großes Projekt"  # Wert 3,5, Aufwand 3
    assert position_summary(view, "gibt-es-nicht") is None


def test_rice_formula_and_delta() -> None:
    view = build(formula=Formula.RICE)
    assert view.formula == Formula.RICE
    assert all(row.delta is not None for row in view.rows)


def test_format_delta() -> None:
    assert format_delta(2) == "▲2"
    assert format_delta(-3) == "▼3"
    assert format_delta(0) == "="
    assert format_delta(None) == "–"


def test_csv_contains_reasons_overrides_and_status() -> None:
    view = build(overrides={"a": {"impact": ScoreOverride(score=4, reason="zu optimistisch")}})
    text = to_csv(view)
    assert text.startswith("\ufeff")
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"))
    header, first = rows[0], rows[1]
    assert len(rows) == 1 + len(view.rows)
    record = dict(zip(header, first))
    assert record["Idee"] == "Idee a"
    assert record["Nutzen KI"] == "5"
    assert record["Nutzen Team"] == "4"
    assert record["Nutzen Team-Begründung"] == "zu optimistisch"
    assert record["Nutzen KI-Begründung"] == "Grund a"
    assert record["Quelle"] == "mock"
    flagged = dict(zip(header, next(r for r in rows[1:] if r[1] == "Idee c")))
    assert flagged["Prüfstatus"] == "offen"
    assert flagged["Compliance-Kategorien"] == "Datenschutz (DSGVO)"


def test_csv_for_tools_reads_with_pandas_defaults() -> None:
    # Genau der Fall aus Data Wrangler: pandas mit Standard-Einstellungen (Komma).
    view = build(overrides={"a": {"impact": ScoreOverride(score=4, reason="zu optimistisch, sagt das Team")}})
    text = to_csv(view, for_excel=False)
    assert not text.startswith("\ufeff")
    df = pd.read_csv(io.StringIO(text))
    assert df.shape == (len(view.rows), 34)
    assert df.columns[0] == "Rang"
    assert df.loc[0, "Nutzen Team-Begründung"] == "zu optimistisch, sagt das Team"  # Komma im Text sicher
    assert df["Punkte (0–100)"].dtype == float  # Dezimalpunkt → echte Zahl


def test_csv_for_excel_uses_decimal_comma() -> None:
    view = build()
    text = to_csv(view, for_excel=True)
    df = pd.read_csv(io.StringIO(text.lstrip("\ufeff")), sep=";", decimal=",")
    assert df.shape == (len(view.rows), 34)
    assert df["Punkte (0–100)"].dtype == float
