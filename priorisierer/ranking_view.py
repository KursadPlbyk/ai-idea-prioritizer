"""Ranking-Ansicht: führt KI-Bewertung, Team-Korrekturen, Prüfstatus und Formel zusammen.

Reine Funktionen – die App zeichnet nur, was hier berechnet wird (Tabelle, Matrix, CSV).
"""

import csv
import io

from pydantic import BaseModel

from priorisierer.models import ComplianceReview, Criterion, Evaluation, Idea, ReviewStatus, ScoreOverride, Weights
from priorisierer.scoring import Formula, quadrant, rank, rank_delta, rank_positions, to_points
from priorisierer.team import apply_overrides, review_status

CRITERIA: tuple[Criterion, ...] = ("impact", "reach", "effort", "risk")
CRITERIA_LABELS = {"impact": "Nutzen", "reach": "Reichweite", "effort": "Aufwand", "risk": "Risiko"}
# Richtung im Spaltenkopf: ↑ höher ist besser, ↓ niedriger ist besser.
CRITERIA_HEADERS = {"impact": "Nutzen ↑", "reach": "Reichweite ↑", "effort": "Aufwand ↓", "risk": "Risiko ↓"}
STATUS_LABELS = {
    ReviewStatus.OPEN: "🛑 Prüfung offen",
    ReviewStatus.CLEARED: "✅ geklärt",
    ReviewStatus.REJECTED: "⛔ abgelehnt",
}


class RankedIdea(BaseModel):
    """Eine Idee, wie sie im Ranking erscheint."""

    idea: Idea
    ai: Evaluation  # unveränderte KI-/Mock-Bewertung
    effective: Evaluation  # mit Team-Korrekturen – damit wird gerechnet
    overrides: dict[Criterion, ScoreOverride]
    status: ReviewStatus | None
    review: ComplianceReview | None
    score: float
    rank: int
    delta: int | None
    quadrant: str
    is_recent: bool


class SetAsideIdea(BaseModel):
    """Eine bewertete Idee außerhalb des Rankings (abgelehnt oder per Filter ausgeblendet)."""

    idea: Idea
    ai: Evaluation
    status: ReviewStatus
    review: ComplianceReview | None


class RankingView(BaseModel):
    """Alles, was Tabelle, Matrix und Export brauchen."""

    formula: Formula
    rows: list[RankedIdea]
    rejected: list[SetAsideIdea]
    hidden_open: list[SetAsideIdea]


def build_ranking(
    ideas: list[Idea],
    evaluations: dict[str, Evaluation],
    overrides: dict[str, dict[Criterion, ScoreOverride]],
    reviews: dict[str, ComplianceReview],
    weights: Weights,
    formula: Formula,
    only_cleared: bool = False,
    recent_ids: set[str] | frozenset[str] = frozenset(),
) -> RankingView:
    """Baut das Ranking: nur bewertete Ideen; abgelehnte (und bei only_cleared offene) kommen beiseite.

    Wirft ValueError bei gewichteter Summe mit allen Gewichten 0 (wie scoring.normalized_weights).
    """
    rankable: list[tuple[Idea, Evaluation]] = []
    rejected: list[SetAsideIdea] = []
    hidden_open: list[SetAsideIdea] = []
    for idea in ideas:
        ai = evaluations.get(idea.id)
        if ai is None:
            continue
        review = reviews.get(idea.id)
        status = review_status(ai, review)
        if status == ReviewStatus.REJECTED:
            rejected.append(SetAsideIdea(idea=idea, ai=ai, status=status, review=review))
        elif status == ReviewStatus.OPEN and only_cleared:
            hidden_open.append(SetAsideIdea(idea=idea, ai=ai, status=status, review=review))
        else:
            rankable.append((idea, ai))

    effective = {idea.id: apply_overrides(ai, overrides.get(idea.id)) for idea, ai in rankable}
    ordered = rank(list(effective.values()), weights, formula)
    positions = rank_positions(list(effective.values()), weights, formula)
    deltas = rank_delta(list(effective.values()), weights, formula)
    by_id = {idea.id: (idea, ai) for idea, ai in rankable}

    rows = []
    for evaluation, value in ordered:
        idea, ai = by_id[evaluation.idea_id]
        review = reviews.get(idea.id)
        rows.append(
            RankedIdea(
                idea=idea,
                ai=ai,
                effective=evaluation,
                overrides=overrides.get(idea.id, {}),
                status=review_status(ai, review),
                review=review,
                score=value,
                rank=positions[idea.id],
                delta=deltas[idea.id] if deltas is not None else None,
                quadrant=quadrant(evaluation),
                is_recent=idea.id in recent_ids,
            )
        )
    return RankingView(formula=formula, rows=rows, rejected=rejected, hidden_open=hidden_open)


def score_header(formula: Formula) -> str:
    """Spaltenname der Punkte-Spalte je nach Formel."""
    return "RICE-Wert" if formula == Formula.RICE else "Punkte (0–100)"


def display_score(value: float, formula: Formula) -> float:
    """Anzeigewert: gewichtete Summe als 0–100 Punkte, RICE als Wert mit 2 Nachkommastellen."""
    return round(value, 2) if formula == Formula.RICE else round(to_points(value), 1)


def format_delta(delta: int | None) -> str:
    """▲n = in der aktuellen Formel n Plätze besser als in der anderen, ▼n = schlechter, = gleich."""
    if delta is None:
        return "–"
    if delta == 0:
        return "="
    return f"▲{delta}" if delta > 0 else f"▼{-delta}"


def score_cell(row: RankedIdea, criterion: Criterion) -> str:
    """Score für die Tabelle; korrigierte Werte mit ✏️ markiert."""
    value = str(getattr(row.effective, criterion).score)
    return f"{value} ✏️" if criterion in row.overrides else value


def position_summary(view: RankingView, idea_id: str) -> str | None:
    """„Platz X von N · Quadrant“ für eine Idee im Ranking, sonst None (z. B. abgelehnt)."""
    for row in view.rows:
        if row.idea.id == idea_id:
            return f"Platz {row.rank} von {len(view.rows)} · {row.quadrant}"
    return None


def to_csv(view: RankingView, for_excel: bool = True) -> str:
    """CSV des aktuellen Rankings inkl. Begründungen, Korrekturen, Quelle und Prüfstatus.

    for_excel=True:  Semikolon, Dezimalkomma, UTF-8-BOM – ein deutsches Excel öffnet Spalten und
                     Umlaute per Doppelklick korrekt (Komma ist dort Dezimalzeichen).
    for_excel=False: Komma, Dezimalpunkt, kein BOM – der Standard, den pandas, Data Wrangler & Co. erwarten.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";" if for_excel else ",")
    header = ["Rang", "Idee", "Beschreibung", score_header(view.formula), "Δ Rang"]
    for criterion in CRITERIA:
        label = CRITERIA_LABELS[criterion]
        header += [f"{label} (wirksam)", f"{label} KI", f"{label} Team", f"{label} Team-Begründung", f"{label} KI-Begründung"]
    header += [
        "Quadrant", "Annahme", "Compliance-Kategorien", "Compliance-Hinweis", "Prüfstatus", "Prüfnotiz",
        "Quelle", "Modell", "Prompt-Version",
    ]  # fmt: skip
    writer.writerow(header)
    for row in view.rows:
        cells: list[object] = [
            row.rank,
            row.idea.title,
            row.idea.description or "",
            _decimal(display_score(row.score, view.formula), for_excel),
            format_delta(row.delta),
        ]
        for criterion in CRITERIA:
            override = row.overrides.get(criterion)
            cells += [
                getattr(row.effective, criterion).score,
                getattr(row.ai, criterion).score,
                override.score if override else "",
                override.reason if override else "",
                getattr(row.ai, criterion).reasoning,
            ]
        compliance = row.ai.compliance
        cells += [
            row.quadrant,
            row.ai.assumption,
            ", ".join(category.value for category in compliance.categories),
            compliance.note,
            row.status.value if row.status else "",
            row.review.note if row.review else "",
            row.ai.source,
            row.ai.model or "",
            row.ai.prompt_version or "",
        ]
        writer.writerow(cells)
    # \ufeff = BOM (Byte Order Mark): unsichtbares Zeichen, an dem Excel UTF-8 erkennt.
    return ("\ufeff" if for_excel else "") + buffer.getvalue()


def _decimal(value: float, for_excel: bool) -> str:
    """Zahl als Text – mit Dezimalkomma für deutsches Excel, sonst mit Punkt."""
    text = str(value)
    return text.replace(".", ",") if for_excel else text
