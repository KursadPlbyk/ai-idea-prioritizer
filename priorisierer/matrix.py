"""Koordinaten für die Impact/Effort-Matrix – reine Funktionen, das Zeichnen macht app.py.

x = Aufwand (1–5), y = Wert = (Nutzen + Reichweite) / 2, Grenzen aus scoring.py.
"""

import math
from collections import Counter
from string import ascii_lowercase

from pydantic import BaseModel

from priorisierer.models import Evaluation
from priorisierer.scoring import EFFORT_THRESHOLD, VALUE_THRESHOLD

# Mögliche Stufen: Aufwand ist ganzzahlig (Schritt 1), Wert ein Mittel aus zwei ganzen Zahlen (Schritt 0,5).
EFFORT_STEP = 1.0
VALUE_STEP = 0.5
# Radius des Versatzes bei gleichen Koordinaten. Muss kleiner als VALUE_STEP / 2 sein, damit kein Punkt
# über eine Quadrantenlinie rutscht und benachbarte Gruppen getrennt bleiben.
OFFSET_RADIUS = 0.18


class MatrixPoint(BaseModel):
    """Ein Punkt der Matrix: echte Koordinaten und (ggf. versetzte) Zeichenposition."""

    idea_id: str
    effort: int
    value: float
    x: float
    y: float
    # Wie viele Ideen sich diese Koordinate teilen (1 = allein).
    group_size: int


def marker_labels(ranks: list[int]) -> list[str]:
    """Eindeutige Kennzeichen für die Kreise: der Rang, bei Gleichstand mit Buchstaben (1a, 1b, 3).

    Die Matrix zeigt nur diese Kennzeichen, die Titel stehen in einer Liste daneben – so kann sich
    im Diagramm kein Text überschneiden. Ohne Buchstaben wären zwei Kreise mit „1“ nicht zuzuordnen.
    """
    counts = Counter(ranks)
    used: Counter[int] = Counter()
    labels = []
    for rank in ranks:
        if counts[rank] == 1:
            labels.append(str(rank))
        else:
            labels.append(f"{rank}{ascii_lowercase[used[rank]]}")
            used[rank] += 1
    return labels


def idea_value(evaluation: Evaluation) -> float:
    """Wert-Achse: Mittel aus Nutzen und Reichweite."""
    return (evaluation.impact.score + evaluation.reach.score) / 2


def quadrant_lines() -> tuple[float, float]:
    """(x, y) der Quadrantenlinien – jeweils mittig zwischen letzter „niedrig“- und erster „hoch“-Stufe.

    Wert > VALUE_THRESHOLD ist hoch → Linie zwischen 3 und 3,5, also bei 3,25.
    Aufwand ≥ EFFORT_THRESHOLD ist hoch → Linie zwischen 2 und 3, also bei 2,5.
    So liegt kein Punkt auf einer Linie, und die Linien folgen den Konstanten.
    """
    return EFFORT_THRESHOLD - EFFORT_STEP / 2, VALUE_THRESHOLD + VALUE_STEP / 2


def matrix_points(evaluations: list[Evaluation]) -> list[MatrixPoint]:
    """Punkte in der Reihenfolge der Eingabe (z. B. Ranking). Gleiche Koordinaten werden deterministisch versetzt:

    - Paare nebeneinander (erster links, zweiter rechts) – waagrecht ist mehr Platz (Aufwand-Stufen liegen
      1 auseinander, Wert-Stufen nur 0,5), und kein Punkt rückt an die Wert-Linie.
    - Ab 3 Ideen auf einen kleinen Kreis – erster Punkt oben, dann im Uhrzeigersinn.
    """
    groups: dict[tuple[int, float], list[Evaluation]] = {}
    for evaluation in evaluations:
        groups.setdefault((evaluation.effort.score, idea_value(evaluation)), []).append(evaluation)

    points: list[MatrixPoint] = []
    for evaluation in evaluations:
        key = (evaluation.effort.score, idea_value(evaluation))
        group = groups[key]
        dx = dy = 0.0
        if len(group) == 2:
            dx = -OFFSET_RADIUS if group.index(evaluation) == 0 else OFFSET_RADIUS
        elif len(group) > 2:
            angle = math.pi / 2 - 2 * math.pi * group.index(evaluation) / len(group)
            dx, dy = OFFSET_RADIUS * math.cos(angle), OFFSET_RADIUS * math.sin(angle)
        points.append(
            MatrixPoint(
                idea_id=evaluation.idea_id,
                effort=key[0],
                value=key[1],
                x=key[0] + dx,
                y=key[1] + dy,
                group_size=len(group),
            )
        )
    return points
