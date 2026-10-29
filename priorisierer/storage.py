"""Zustand (Ideen, Bewertungen, Team-Korrekturen, Prüfstatus) als JSON speichern und laden."""

import json
from pathlib import Path

from priorisierer.models import AppState, Idea

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATE_FILE = DATA_DIR / "state.json"
# Vorab einmal live bewerteter Stand für die Präsentation (wird committet) – Demo ohne Netz möglich.
DEMO_STATE_FILE = DATA_DIR / "demo_state.json"
# Sicherung des Arbeitsstands, bevor der Demo-Stand ihn ersetzt (in .gitignore).
BACKUP_FILE = DATA_DIR / "state.backup.json"
EXAMPLE_IDEAS_FILE = DATA_DIR / "example_ideas.json"


def _state_path(path: Path | None) -> Path:
    # Erst beim Aufruf auflösen (nicht als Default-Argument), damit Tests STATE_FILE umleiten können.
    return path if path is not None else STATE_FILE


def load_state(path: Path | None = None) -> AppState:
    """Lädt den Zustand. Fehlt die Datei, ist er leer; fehlende Schlüssel (alte Dateien) gelten als leer."""
    path = _state_path(path)
    if not path.exists():
        return AppState()
    return AppState.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_state(state: AppState, path: Path | None = None) -> None:
    """Speichert den Zustand als JSON."""
    path = _state_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")


def load_example_ideas(path: Path = EXAMPLE_IDEAS_FILE) -> list[Idea]:
    """Lädt die mitgelieferten Beispiel-Ideen."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Idea.model_validate(item) for item in raw]
