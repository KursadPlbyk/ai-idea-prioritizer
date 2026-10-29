"""Tests für die Matrix-Koordinaten."""

import math

import pytest

from priorisierer.matrix import OFFSET_RADIUS, VALUE_STEP, idea_value, matrix_points, quadrant_lines
from priorisierer.models import Compliance, CriterionScore, Evaluation
from priorisierer.scoring import BIG_PROJECT, FILL_IN, QUICK_WIN, TIME_SINK, quadrant


def ev(idea_id: str, impact: int, reach: int, effort: int) -> Evaluation:
    return Evaluation(
        idea_id=idea_id,
        assumption="t",
        impact=CriterionScore(reasoning="t", score=impact),
        reach=CriterionScore(reasoning="t", score=reach),
        effort=CriterionScore(reasoning="t", score=effort),
        risk=CriterionScore(reasoning="t", score=3),
        compliance=Compliance(flag=False, categories=[], note=""),
    )


def test_quadrant_lines_follow_thresholds() -> None:
    # Wert > 3 hoch → zwischen 3 und 3,5; Aufwand ≥ 3 hoch → zwischen 2 und 3
    assert quadrant_lines() == (2.5, 3.25)


def test_lines_separate_quadrants_consistently_with_scoring() -> None:
    # Jeder mögliche Punkt liegt auf der Seite der Linien, die zu quadrant() passt.
    x_line, y_line = quadrant_lines()
    for impact in range(1, 6):
        for reach in range(1, 6):
            for effort in range(1, 6):
                evaluation = ev("x", impact, reach, effort)
                high_value = idea_value(evaluation) > y_line
                high_effort = effort > x_line
                expected = {
                    (True, False): QUICK_WIN, (True, True): BIG_PROJECT,
                    (False, False): FILL_IN, (False, True): TIME_SINK,
                }[(high_value, high_effort)]  # fmt: skip
                assert quadrant(evaluation) == expected


def test_single_point_is_not_offset() -> None:
    [point] = matrix_points([ev("a", 4, 3, 2)])
    assert (point.x, point.y) == (2, 3.5)
    assert point.group_size == 1


def test_identical_coordinates_are_spread_deterministically() -> None:
    evaluations = [ev(i, 4, 4, 1) for i in ("a", "b", "c")]
    first = matrix_points(evaluations)
    second = matrix_points(evaluations)
    assert first == second  # deterministisch
    assert len({(p.x, p.y) for p in first}) == 3  # keine Überdeckung
    for point in first:
        assert point.group_size == 3
        assert (point.effort, point.value) == (1, 4.0)  # echte Werte bleiben erhalten
        assert math.dist((point.x, point.y), (1, 4.0)) == pytest.approx(OFFSET_RADIUS)
    assert first[0].x == pytest.approx(1) and first[0].y == pytest.approx(4 + OFFSET_RADIUS)  # erster oben


def test_pair_is_spread_horizontally() -> None:
    # Zwei Ideen am selben Punkt: nebeneinander, Wert (y) bleibt exakt – kein Rutschen an die Wert-Linie.
    first, second = matrix_points([ev("a", 4, 3, 1), ev("b", 4, 3, 1)])
    assert (first.x, first.y) == (pytest.approx(1 - OFFSET_RADIUS), 3.5)
    assert (second.x, second.y) == (pytest.approx(1 + OFFSET_RADIUS), 3.5)
    assert first.group_size == second.group_size == 2


def test_pair_near_value_line_keeps_distance() -> None:
    # Wert 3,5 liegt 0,25 über der Linie (3,25) – beim waagrechten Versatz bleibt der volle Abstand.
    _, y_line = quadrant_lines()
    for point in matrix_points([ev("a", 4, 3, 3), ev("b", 4, 3, 3)]):
        assert point.y - y_line == pytest.approx(0.25)


def test_offset_never_crosses_quadrant_line() -> None:
    assert OFFSET_RADIUS < VALUE_STEP / 2
    x_line, y_line = quadrant_lines()
    evaluations = (
        [ev(str(i), 3, 3, 2) for i in range(6)]
        + [ev(f"h{i}", 4, 3, 3) for i in range(6)]
        + [ev(f"p{i}", 3, 3, 3) for i in range(2)]  # Paar direkt an beiden Linien
        + [ev(f"q{i}", 4, 3, 2) for i in range(2)]
    )
    for point in matrix_points(evaluations):
        assert (point.x > x_line) == (point.effort > x_line)
        assert (point.y > y_line) == (point.value > y_line)


def test_order_is_kept() -> None:
    evaluations = [ev("b", 1, 1, 1), ev("a", 5, 5, 5)]
    assert [p.idea_id for p in matrix_points(evaluations)] == ["b", "a"]


# --- Kennzeichen der Kreise (Auftrag 5) --------------------------------------------

from priorisierer.matrix import marker_labels  # noqa: E402


def test_marker_labels_are_rank_without_ties() -> None:
    assert marker_labels([1, 2, 3]) == ["1", "2", "3"]


def test_marker_labels_add_letters_on_ties() -> None:
    assert marker_labels([1, 1, 3, 3, 3, 6]) == ["1a", "1b", "3a", "3b", "3c", "6"]


def test_marker_labels_are_unique() -> None:
    ranks = [1, 1, 3, 3, 3, 6, 7, 8, 9, 9]  # Ränge des Demo-Stands
    labels = marker_labels(ranks)
    assert len(set(labels)) == len(labels)
    assert [label.rstrip("abc") for label in labels] == [str(rank) for rank in ranks]  # passt zur Spalte „Rang“
