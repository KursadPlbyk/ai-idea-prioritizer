"""Erzeugt data/demo_state.json: die 10 Beispiel-Ideen, einmal live mit dem Standard-Bewerter bewertet.

Aufruf (im Projektordner, venv aktiv):  python scripts/build_demo_state.py [--force]

Ohne Korrekturen und Prüfentscheidungen. Schlägt auch nur eine Idee fehl, wird nichts geschrieben –
ein unvollständiger Demo-Stand wäre schlimmer als keiner. Verändert data/state.json nicht.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from priorisierer.evaluators.llm import LLMEvaluator, api_key_configured  # noqa: E402
from priorisierer.models import AppState  # noqa: E402
from priorisierer.storage import DEMO_STATE_FILE, load_example_ideas, save_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo-Stand mit echten KI-Bewertungen erzeugen")
    parser.add_argument("--force", action="store_true", help="Bestehenden Demo-Stand überschreiben")
    args = parser.parse_args()

    if not api_key_configured():
        print("Kein ANTHROPIC_API_KEY gefunden (.env oder Umgebung).")
        return 1
    if DEMO_STATE_FILE.exists() and not args.force:
        print(f"{DEMO_STATE_FILE.name} existiert schon – mit --force überschreiben.")
        return 1

    ideas = load_example_ideas()
    evaluator = LLMEvaluator()
    print(f"Bewerte {len(ideas)} Beispiel-Ideen mit {evaluator.model}, Prompt {evaluator.prompt_version}/{evaluator.effort} …")
    run = evaluator.evaluate(ideas)

    if run.failures:
        for failure in run.failures:
            print(f"FEHLGESCHLAGEN {failure.idea_id}: {failure.reason}")
        print("Nichts geschrieben – bitte erneut versuchen.")
        return 1

    save_state(AppState(ideas=ideas, evaluations=run.evaluations), DEMO_STATE_FILE)
    usage = run.usage
    print(
        f"Geschrieben: {DEMO_STATE_FILE} · {usage.api_calls} Aufrufe · "
        f"{usage.input_tokens}/{usage.output_tokens} Tokens · {usage.wall_seconds:.1f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
