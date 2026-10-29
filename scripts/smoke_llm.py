"""Smoke-Test: bewertet genau eine Beispiel-Idee live über die Anthropic API.

Aufruf (im Projektordner, venv aktiv):  python scripts/smoke_llm.py
Kostet Bruchteile eines Cents. Gibt nie den API-Key aus.
"""

import sys
from pathlib import Path

# Projektordner in den Suchpfad, damit "priorisierer" ohne Installation gefunden wird.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from priorisierer.evaluators.llm import LLMEvaluator, api_key_configured  # noqa: E402
from priorisierer.storage import load_example_ideas  # noqa: E402


def main() -> int:
    if not api_key_configured():
        print("Kein ANTHROPIC_API_KEY gefunden (.env oder Umgebung).")
        return 1

    idea = load_example_ideas()[0]
    evaluator = LLMEvaluator()
    print(f"Bewerte „{idea.title}“ mit {evaluator.model} …")
    run = evaluator.evaluate([idea])

    for failure in run.failures:
        print(f"FEHLGESCHLAGEN: {failure.reason}")
    for evaluation in run.evaluations:
        print(evaluation.model_dump_json(indent=2))
    return 0 if run.evaluations else 1


if __name__ == "__main__":
    sys.exit(main())
