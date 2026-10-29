"""Vergleicht gespeicherte Experimente und schreibt experiments/VERGLEICH.md.

Aufruf:  python scripts/compare_experiments.py v1_low v2_low v2_medium
Ruft keine API auf – rechnet nur aus den Rohdaten in experiments/<label>.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from priorisierer.experiments import EXPERIMENTS_DIR, load_experiment, render_comparison  # noqa: E402


def main() -> int:
    labels = sys.argv[1:]
    if not labels:
        print("Bitte mindestens ein Label angeben, z. B.: v1_low v2_low v2_medium")
        return 1
    records = [load_experiment(label) for label in labels]
    path = EXPERIMENTS_DIR / "VERGLEICH.md"
    path.write_text(render_comparison(records), encoding="utf-8")
    print(f"Geschrieben: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
