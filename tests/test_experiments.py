"""Tests für Durchführung, Speichern und Berichte von Experimenten – mit dem Mock, ohne API."""

from datetime import datetime
from pathlib import Path

import pytest

from priorisierer.evaluators.base import RunUsage
from priorisierer.evaluators.mock import MockEvaluator
from priorisierer.experiments import (
    ExperimentConfig,
    estimate_cost,
    load_experiment,
    render_comparison,
    run_experiment,
    save_experiment,
)
from priorisierer.storage import load_example_ideas


def make_config(label: str, prompt_version: str = "v1") -> ExperimentConfig:
    return ExperimentConfig(
        label=label,
        prompt_version=prompt_version,
        effort="low",
        model="claude-haiku-5-5",
        run_count=2,
        sdk_version="test",
        started_at=datetime(2026, 10, 25, 12, 0).astimezone(),
    )


def test_run_save_load_roundtrip(tmp_path: Path) -> None:
    ideas = load_example_ideas()
    record = run_experiment(MockEvaluator(), ideas, make_config("mock_test"))

    path = save_experiment(record, tmp_path)

    assert path == tmp_path / "mock_test.json"
    assert (tmp_path / "mock_test.md").exists()
    loaded = load_experiment("mock_test", tmp_path)
    assert loaded == record
    assert len(loaded.runs) == 2


def test_summary_markdown_contains_key_figures(tmp_path: Path) -> None:
    record = run_experiment(MockEvaluator(), load_example_ideas(), make_config("mock_test"))
    save_experiment(record, tmp_path)
    text = (tmp_path / "mock_test.md").read_text(encoding="utf-8")

    assert "Trennschärfe" in text
    assert "Spearman" in text
    # Der Mock ist deterministisch → perfekt stabil
    assert "1,00" in text
    assert "Meeting-Zeiten reduzieren" in text


def test_comparison_mentions_bundled_v2_changes() -> None:
    ideas = load_example_ideas()
    records = [
        run_experiment(MockEvaluator(), ideas, make_config("a", "v1")),
        run_experiment(MockEvaluator(), ideas, make_config("b", "v2")),
    ]
    text = render_comparison(records)
    assert "`a`" in text and "`b`" in text
    assert "gebündelt" in text
    assert "Ablation" in text


def test_comparison_without_v2_has_no_ablation_note() -> None:
    record = run_experiment(MockEvaluator(), load_example_ideas(), make_config("a", "v1"))
    assert "Ablation" not in render_comparison([record])


def test_estimate_cost() -> None:
    usage = RunUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert estimate_cost(usage, "claude-haiku-5-5") == pytest.approx(0.60)
    assert estimate_cost(usage, "unbekanntes-modell") is None
