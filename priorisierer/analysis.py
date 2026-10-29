"""Reine Auswertungsfunktionen für Kalibrierungs-Experimente (Auftrag 3).

Eingabe ist immer `runs`: pro Durchlauf eine Liste von Evaluations derselben Ideen.
Zuordnung über idea_id – fehlt eine Idee in einem Lauf (Aufruf gescheitert), zählen nur die vorhandenen Werte.
Keine API-Aufrufe, keine Dateien, keine Seiteneffekte.
"""

import math
from itertools import combinations
from statistics import median, pstdev

from pydantic import BaseModel

from priorisierer.models import Evaluation, Weights
from priorisierer.scoring import rank, weighted_score

CRITERIA = ("impact", "reach", "effort", "risk")
SCORES = (1, 2, 3, 4, 5)
TOP_N = 3

Runs = list[list[Evaluation]]


class CriterionStability(BaseModel):
    """Stabilität eines Kriteriums über die Läufe."""

    # Anteil der Ideen, die in allen Läufen dieselbe Note bekamen.
    share_zero_range: float
    # Durchschnitt von (max − min) über die Ideen.
    mean_range: float


class RankingStability(BaseModel):
    """Wie ähnlich sich die Rankings der Läufe sind (bei festen Gewichten)."""

    # Mittelwert der Spearman-Korrelation über alle Lauf-Paare; None bei < 2 Läufen.
    mean_spearman: float | None
    pair_count: int
    # Top-N als Menge (Reihenfolge innerhalb egal); None bei < 2 Läufen.
    top_identical: bool | None
    top_per_run: list[list[str]]


class ComplianceSummary(BaseModel):
    """Wie oft und wie beständig das Compliance-Flag gesetzt wird."""

    flagged_per_run: list[int]
    flagged_median: float
    # Häufigkeit je Kategorie über alle Läufe und Ideen zusammen.
    category_counts: dict[str, int]
    # Anteil der Ideen mit gleichem Flag in allen Läufen; None, wenn keine Idee in ≥ 2 Läufen vorkommt.
    share_consistent_flag: float | None


class ExperimentSummary(BaseModel):
    """Alle Kennzahlen eines Experiments."""

    run_count: int
    idea_count: int
    distribution: dict[str, dict[int, int]]
    median_scores: dict[str, dict[str, float]]
    discrimination: dict[str, float]
    stability: dict[str, CriterionStability | None]
    ranking: RankingStability
    compliance: ComplianceSummary


def scores_by_idea(runs: Runs) -> dict[str, dict[str, list[int]]]:
    """Sammelt pro Idee und Kriterium die Scores aller Läufe (Reihenfolge: erstes Auftreten)."""
    collected: dict[str, dict[str, list[int]]] = {}
    for run in runs:
        for evaluation in run:
            per_criterion = collected.setdefault(evaluation.idea_id, {name: [] for name in CRITERIA})
            for name in CRITERIA:
                per_criterion[name].append(getattr(evaluation, name).score)
    return collected


def score_distribution(runs: Runs) -> dict[str, dict[int, int]]:
    """Wie oft kam jede Note 1–5 vor, pro Kriterium über alle Ideen und Läufe."""
    distribution = {name: {score: 0 for score in SCORES} for name in CRITERIA}
    for run in runs:
        for evaluation in run:
            for name in CRITERIA:
                distribution[name][getattr(evaluation, name).score] += 1
    return distribution


def median_scores(runs: Runs) -> dict[str, dict[str, float]]:
    """Median-Score pro Idee und Kriterium über die Läufe."""
    return {
        idea_id: {name: float(median(values)) for name, values in per_criterion.items()}
        for idea_id, per_criterion in scores_by_idea(runs).items()
    }


def discrimination(runs: Runs) -> dict[str, float]:
    """Trennschärfe: Standardabweichung der Median-Scores über die Ideen, pro Kriterium.

    0 = alle Ideen gleich bewertet. Gleichverteilte Noten 1–5 ergeben ca. 1,41, Maximum ist 2,0.
    pstdev (Gesamtheit), weil wir genau diese Ideen beschreiben, keine Stichprobe.
    """
    medians = median_scores(runs)
    return {
        name: pstdev([per_criterion[name] for per_criterion in medians.values()]) if medians else 0.0
        for name in CRITERIA
    }


def stability(runs: Runs) -> dict[str, CriterionStability | None]:
    """Stabilität: Spannweite (max − min) pro Idee über die Läufe. None, wenn keine Idee ≥ 2 Werte hat."""
    result: dict[str, CriterionStability | None] = {}
    for name in CRITERIA:
        ranges = [
            max(values) - min(values)
            for per_criterion in scores_by_idea(runs).values()
            if len(values := per_criterion[name]) >= 2
        ]
        result[name] = (
            CriterionStability(
                share_zero_range=sum(r == 0 for r in ranges) / len(ranges),
                mean_range=sum(ranges) / len(ranges),
            )
            if ranges
            else None
        )
    return result


def average_ranks(values: list[float]) -> list[float]:
    """Rang je Wert (1 = höchster). Bei Gleichstand bekommen alle den Mittelwert ihrer Plätze.

    Beispiel: [10, 20, 20, 30] → [4, 2.5, 2.5, 1]
    """
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        # Gruppe gleicher Werte finden: belegt die Plätze position+1 … end.
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        shared_rank = (position + 1 + end + 1) / 2
        for k in range(position, end + 1):
            ranks[order[k]] = shared_rank
        position = end + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman-Rangkorrelation: Pearson-Korrelation der (gemittelten) Ränge.

    +1 = gleiche Reihenfolge, 0 = kein Zusammenhang, −1 = umgekehrt.
    Funktioniert auch bei Gleichständen (die Kurzformel 1 − 6Σd²/(n(n²−1)) nicht).
    None, wenn weniger als 2 Werte oder eine Rangliste konstant ist (Division durch 0).
    """
    if len(x) != len(y):
        raise ValueError("Beide Listen müssen gleich lang sein.")
    if len(x) < 2:
        return None
    rank_x, rank_y = average_ranks(x), average_ranks(y)
    mean_x, mean_y = sum(rank_x) / len(rank_x), sum(rank_y) / len(rank_y)
    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(rank_x, rank_y))
    spread_x = math.sqrt(sum((a - mean_x) ** 2 for a in rank_x))
    spread_y = math.sqrt(sum((b - mean_y) ** 2 for b in rank_y))
    if spread_x == 0 or spread_y == 0:
        return None
    return covariance / (spread_x * spread_y)


def ranking_stability(runs: Runs, weights: Weights) -> RankingStability:
    """Spearman zwischen allen Lauf-Paaren (gemittelt) und ob die Top-N in allen Läufen gleich ist."""
    scores_per_run = [{e.idea_id: weighted_score(e, weights) for e in run} for run in runs]
    correlations: list[float] = []
    for first, second in combinations(scores_per_run, 2):
        common = sorted(first.keys() & second.keys())
        rho = spearman([first[i] for i in common], [second[i] for i in common])
        if rho is not None:
            correlations.append(rho)

    top_per_run = [[evaluation.idea_id for evaluation, _ in rank(run, weights)[:TOP_N]] for run in runs]
    top_identical = len({frozenset(top) for top in top_per_run}) == 1 if len(runs) >= 2 else None
    return RankingStability(
        mean_spearman=sum(correlations) / len(correlations) if correlations else None,
        pair_count=len(correlations),
        top_identical=top_identical,
        top_per_run=top_per_run,
    )


def compliance_summary(runs: Runs) -> ComplianceSummary:
    """Anzahl markierter Ideen pro Lauf, Kategorie-Häufigkeit und Beständigkeit des Flags."""
    flagged_per_run = [sum(e.compliance.flag for e in run) for run in runs]
    category_counts: dict[str, int] = {}
    flags_by_idea: dict[str, list[bool]] = {}
    for run in runs:
        for evaluation in run:
            flags_by_idea.setdefault(evaluation.idea_id, []).append(evaluation.compliance.flag)
            for category in evaluation.compliance.categories:
                category_counts[category.value] = category_counts.get(category.value, 0) + 1

    repeated = [flags for flags in flags_by_idea.values() if len(flags) >= 2]
    return ComplianceSummary(
        flagged_per_run=flagged_per_run,
        flagged_median=float(median(flagged_per_run)) if flagged_per_run else 0.0,
        category_counts=dict(sorted(category_counts.items())),
        share_consistent_flag=sum(len(set(f)) == 1 for f in repeated) / len(repeated) if repeated else None,
    )


def summarize(runs: Runs, weights: Weights) -> ExperimentSummary:
    """Alle Kennzahlen eines Experiments in einem Objekt."""
    return ExperimentSummary(
        run_count=len(runs),
        idea_count=len(scores_by_idea(runs)),
        distribution=score_distribution(runs),
        median_scores=median_scores(runs),
        discrimination=discrimination(runs),
        stability=stability(runs),
        ranking=ranking_stability(runs, weights),
        compliance=compliance_summary(runs),
    )
