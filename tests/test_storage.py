"""Tests für das Laden und Speichern des Zustands."""

import json
from pathlib import Path

from priorisierer.evaluators.mock import MockEvaluator
from priorisierer.models import AppState, ComplianceCategory, ComplianceReview, Idea, ReviewStatus, ScoreOverride
from priorisierer.storage import load_state, save_state

# Eine Bewertung im Format aus Auftrag 1: ohne source/model/evaluated_at, score vor reasoning.
OLD_STATE = {
    "ideas": [{"id": "ex-07", "title": "Automatisiertes Reporting", "description": None}],
    "evaluations": [
        {
            "idea_id": "ex-07",
            "assumption": "Dashboards ersetzen Excel-Reports.",
            "impact": {"score": 4, "reasoning": "Spart Zeit."},
            "reach": {"score": 3, "reasoning": "Mehrere profitieren."},
            "effort": {"score": 3, "reasoning": "Einige Wochen."},
            "risk": {"score": 2, "reasoning": "Etabliert."},
            "compliance": {"flag": True, "categories": ["Mitbestimmung"], "note": "Leistungsdaten."},
        }
    ],
}


def test_old_state_without_new_fields_loads(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps(OLD_STATE), encoding="utf-8")

    state = load_state(path)

    assert len(state.ideas) == 1
    assert state.overrides == {}  # Schlüssel gab es in alten Dateien nicht
    assert state.compliance_reviews == {}
    [evaluation] = state.evaluations
    assert evaluation.source == "mock"
    assert evaluation.model is None
    assert evaluation.evaluated_at is None
    assert evaluation.prompt_version is None
    assert evaluation.compliance.categories == [ComplianceCategory.CODETERMINATION]


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    ideas = [Idea(id="ex-01", title="Meeting-Zeiten reduzieren")]
    evaluations = MockEvaluator().evaluate(ideas).evaluations

    state = AppState(
        ideas=ideas,
        evaluations=evaluations,
        overrides={"ex-01": {"impact": ScoreOverride(score=5, reason="Team sieht mehr Nutzen")}},
        compliance_reviews={"ex-01": ComplianceReview(status=ReviewStatus.CLEARED, note="ok")},
    )

    save_state(state, path)

    assert load_state(path) == state


def test_missing_file_gives_empty_state(tmp_path: Path) -> None:
    assert load_state(tmp_path / "fehlt.json") == AppState()


def test_default_path_is_resolved_at_call_time(tmp_path: Path, monkeypatch) -> None:
    # Damit Tests (und der App-Test) die echte data/state.json nie berühren.
    import priorisierer.storage as storage

    monkeypatch.setattr(storage, "STATE_FILE", tmp_path / "umgeleitet.json")
    save_state(AppState())
    assert (tmp_path / "umgeleitet.json").exists()
