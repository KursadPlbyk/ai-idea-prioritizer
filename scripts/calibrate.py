"""Kalibrierungs-Experiment: bewertet die 10 Beispiel-Ideen mehrfach live und speichert die Kennzahlen.

Aufruf (im Projektordner, venv aktiv):
    python scripts/calibrate.py --prompt v1 --effort low --runs 3 --label v1_low

Schreibt experiments/<label>.json (Rohdaten) und experiments/<label>.md (Zusammenfassung).
Verändert data/state.json nicht. Kostet echtes Geld (bei Haiku wenige Cent).
"""

import argparse
import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

# Projektordner in den Suchpfad, damit "priorisierer" ohne Installation gefunden wird.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from priorisierer.evaluators.llm import LLMEvaluator, api_key_configured  # noqa: E402
from priorisierer.experiments import ExperimentConfig, experiment_path, run_experiment, save_experiment  # noqa: E402
from priorisierer.prompts import SYSTEM_PROMPTS  # noqa: E402
from priorisierer.storage import load_example_ideas  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kalibrierungs-Experiment mit dem LLM-Bewerter")
    parser.add_argument("--prompt", choices=sorted(SYSTEM_PROMPTS), required=True, help="Prompt-Version")
    parser.add_argument("--effort", choices=["low", "medium", "high"], required=True)
    parser.add_argument("--runs", type=int, default=3, help="Anzahl Durchläufe (Standard: 3)")
    parser.add_argument("--label", required=True, help="Name der Ergebnisdateien, z. B. v1_low")
    parser.add_argument("--force", action="store_true", help="Bestehendes Experiment überschreiben")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not api_key_configured():
        print("Kein ANTHROPIC_API_KEY gefunden (.env oder Umgebung).")
        return 1
    if experiment_path(args.label).exists() and not args.force:
        print(f"Experiment „{args.label}“ existiert schon – mit --force überschreiben.")
        return 1

    ideas = load_example_ideas()
    evaluator = LLMEvaluator(prompt_version=args.prompt, effort=args.effort)
    config = ExperimentConfig(
        label=args.label,
        prompt_version=args.prompt,
        effort=args.effort,
        model=evaluator.model,
        run_count=args.runs,
        sdk_version=version("anthropic"),
        started_at=datetime.now().astimezone(),
    )
    print(f"Experiment {args.label}: {args.prompt}/{args.effort}, {evaluator.model}, {args.runs} × {len(ideas)} Ideen")
    record = run_experiment(evaluator, ideas, config)
    path = save_experiment(record)
    usage = record.total_usage()
    print(f"Gespeichert: {path} (+ .md) · {usage.api_calls} Aufrufe · {usage.input_tokens}/{usage.output_tokens} Tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
