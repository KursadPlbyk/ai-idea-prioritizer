"""Grenzfall-Test (Sanity Check): bewertet data/edge_case_ideas.json mehrfach live mit dem Standard-Bewerter.

Aufruf (im Projektordner, venv aktiv):  python scripts/edge_cases.py [--runs 3] [--force]

Schreibt experiments/grenzfaelle.json (Rohdaten) und experiments/GRENZFAELLE.md (Bericht).
Verändert data/state.json nicht. Ändert nichts am Prompt – verfehlte Erwartungen werden nur berichtet.
"""

import argparse
import json
import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from priorisierer.edge_cases import load_edge_cases, render_report  # noqa: E402
from priorisierer.evaluators.llm import LLMEvaluator, api_key_configured  # noqa: E402
from priorisierer.experiments import EXPERIMENTS_DIR, ExperimentConfig, run_experiment  # noqa: E402

RAW_FILE = EXPERIMENTS_DIR / "grenzfaelle.json"
REPORT_FILE = EXPERIMENTS_DIR / "GRENZFAELLE.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Grenzfall-Test mit dem Standard-Bewerter")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--force", action="store_true", help="Bestehende Ergebnisse überschreiben")
    args = parser.parse_args()

    if not api_key_configured():
        print("Kein ANTHROPIC_API_KEY gefunden (.env oder Umgebung).")
        return 1
    if RAW_FILE.exists() and not args.force:
        print(f"{RAW_FILE.name} existiert schon – mit --force überschreiben.")
        return 1

    cases = load_edge_cases()
    ideas = [case.to_idea() for case in cases]  # nur Titel + Beschreibung, keine Erwartung
    evaluator = LLMEvaluator()
    config = ExperimentConfig(
        label="grenzfaelle",
        prompt_version=evaluator.prompt_version,
        effort=evaluator.effort,
        model=evaluator.model,
        run_count=args.runs,
        sdk_version=version("anthropic"),
        started_at=datetime.now().astimezone(),
    )
    print(f"Grenzfälle: {len(ideas)} Ideen × {args.runs} Läufe, Prompt {config.prompt_version}/{config.effort}")
    record = run_experiment(evaluator, ideas, config)

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    raw = {"experiment": record.model_dump(mode="json"), "cases": [c.model_dump(mode="json") for c in cases]}
    RAW_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    usage = record.total_usage()
    header = (
        f"Prompt **{config.prompt_version}**, effort **{config.effort}**, {config.model}, "
        f"{args.runs} Läufe, {config.started_at:%d.%m.%Y %H:%M} · "
        f"{usage.api_calls} Aufrufe, {usage.input_tokens}/{usage.output_tokens} Tokens"
    )
    REPORT_FILE.write_text(render_report(cases, record.evaluation_runs(), header), encoding="utf-8")
    print(f"Geschrieben: {RAW_FILE} und {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
