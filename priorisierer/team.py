"""Team-Eingaben über der KI-Bewertung: Score-Korrekturen und Compliance-Prüfstatus.

Die KI-Bewertung wird nie verändert. Die *wirksame* Bewertung wird bei Bedarf aus
KI-Bewertung + Korrekturen berechnet – reine Funktionen, nichts wird gespeichert.
"""

from priorisierer.models import ComplianceReview, Criterion, Evaluation, ReviewStatus, ScoreOverride


def apply_overrides(evaluation: Evaluation, overrides: dict[Criterion, ScoreOverride] | None) -> Evaluation:
    """Wirksame Bewertung: Kopie der KI-Bewertung, in der nur die korrigierten Scores ersetzt sind.

    Die KI-Begründung bleibt stehen; KI- und Team-Wert werden in der Oberfläche nebeneinander gezeigt.
    """
    if not overrides:
        return evaluation
    update = {
        criterion: getattr(evaluation, criterion).model_copy(update={"score": override.score})
        for criterion, override in overrides.items()
    }
    return evaluation.model_copy(update=update)


def review_status(evaluation: Evaluation, review: ComplianceReview | None) -> ReviewStatus | None:
    """Der Prüfstatus, der gerade gilt – einzige Stelle, die darüber entscheidet.

    - abgelehnt                                → abgelehnt (Team-Entscheidung, gilt auch ohne Flag)
    - kein Flag                                → None (braucht keinen Status)
    - Flag, nie geprüft                        → offen
    - Flag, geklärt, keine neue Kategorie      → geklärt
    - Flag, geklärt, aber neue Kategorie dazu  → offen (die Klärung deckt das Neue nicht ab)
    """
    if review is not None and review.status == ReviewStatus.REJECTED:
        return ReviewStatus.REJECTED
    if not evaluation.compliance.flag:
        return None
    if review is None or review.status == ReviewStatus.OPEN:
        return ReviewStatus.OPEN
    if set(evaluation.compliance.categories) <= set(review.categories):
        return ReviewStatus.CLEARED
    return ReviewStatus.OPEN
