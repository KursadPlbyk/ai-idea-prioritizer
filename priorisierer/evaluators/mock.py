"""MockEvaluator – deterministisch und offline, für Entwicklung und als Demo-Fallback."""

import hashlib
from datetime import datetime

from priorisierer.evaluators.base import EvaluationRun, Evaluator
from priorisierer.models import Compliance, ComplianceCategory, CriterionScore, Evaluation, Idea

GDPR = ComplianceCategory.GDPR
CODETERMINATION = ComplianceCategory.CODETERMINATION
EXTERNAL_AI = ComplianceCategory.EXTERNAL_AI
INFOSEC = ComplianceCategory.INFOSEC

NO_COMPLIANCE = Compliance(flag=False, categories=[], note="")

# Fest hinterlegte Bewertungen für die Beispiel-Ideen, zugeordnet über die Idee-ID.
# Je Kriterium: (Score, Begründung).
EXAMPLE_EVALUATIONS: dict[str, dict] = {
    "ex-01": {
        "assumption": "Regelmeetings werden gekürzt und nur noch mit Agenda abgehalten.",
        "impact": (3, "Spart jeder Person pro Woche etwa eine Stunde Meetingzeit."),
        "reach": (5, "Betrifft das ganze Team, da alle täglich in Meetings sitzen."),
        "effort": (1, "Reine Absprache im Team, keine Tools und keine Kosten."),
        "risk": (2, "Bewährtes Vorgehen; offen ist nur, ob sich alle dauerhaft daran halten."),
        "compliance": NO_COMPLIANCE,
    },
    "ex-02": {
        "assumption": "Das bestehende Wiki wird aufgeräumt, einheitlich strukturiert und besser durchsuchbar gemacht.",
        "impact": (4, "Weniger Suchzeit und weniger Rückfragen bei Kolleg:innen."),
        "reach": (4, "Fast alle nutzen das Wiki mehrmals pro Woche."),
        "effort": (3, "Mehrere Wochen Aufräumarbeit mit Beteiligung aller Wissensträger."),
        "risk": (2, "Klarer Weg; Risiko liegt darin, dass die Pflege danach wieder einschläft."),
        "compliance": NO_COMPLIANCE,
    },
    "ex-03": {
        "assumption": "Zugänge, Checklisten und Einführungstermine für neue Mitarbeitende werden automatisch angestoßen.",
        "impact": (3, "Spart bei jedem Onboarding spürbar Zeit und vermeidet vergessene Schritte."),
        "reach": (2, "Betrifft nur neue Mitarbeitende und deren Betreuer, wenige Male pro Jahr."),
        "effort": (3, "Erfordert Anbindung an HR- und IT-Systeme über einige Wochen."),
        "risk": (2, "Standardprozess mit erprobten Werkzeugen, aber abhängig von der IT."),
        "compliance": Compliance(
            flag=True,
            categories=[GDPR, INFOSEC],
            note="Verarbeitet Personaldaten neuer Mitarbeitender und vergibt automatisch Systemzugänge.",
        ),
    },
    "ex-04": {
        "assumption": "Ein KI-Assistent schlägt Support-Mitarbeitenden Antworten auf Kundenanfragen vor.",
        "impact": (5, "Kann die Bearbeitungszeit von Support-Anfragen deutlich senken."),
        "reach": (3, "Nutzt vor allem der Support-Teil des Teams, dort aber täglich."),
        "effort": (4, "Integration ins Ticketsystem, Prompt-Entwicklung und laufende API-Kosten."),
        "risk": (4, "Antwortqualität und Akzeptanz bei Mitarbeitenden und Kunden sind unsicher."),
        "compliance": Compliance(
            flag=True,
            categories=[GDPR, EXTERNAL_AI],
            note="Kundendaten aus Anfragen würden an einen externen KI-Anbieter übermittelt.",
        ),
    },
    "ex-05": {
        "assumption": "Technische Dokumentation wird automatisch aus Code, Tickets und Konfigurationen erzeugt.",
        "impact": (3, "Hält Dokumentation aktuell und spart regelmäßig Schreibarbeit."),
        "reach": (3, "Hilft vor allem den technischen Rollen im Team regelmäßig."),
        "effort": (4, "Anbindung mehrerer Quellsysteme und Aufbau einer Generierungs-Pipeline."),
        "risk": (4, "Unklar, ob die erzeugten Texte verständlich genug sind, um genutzt zu werden."),
        "compliance": NO_COMPLIANCE,
    },
    "ex-06": {
        "assumption": "Überlappende Tools werden konsolidiert, sodass es pro Aufgabe nur noch ein Werkzeug gibt.",
        "impact": (5, "Weniger Medienbrüche und Kontextwechsel verändern den Arbeitsalltag grundlegend."),
        "reach": (5, "Das ganze Team arbeitet täglich mit diesen Tools."),
        "effort": (5, "Migration von Daten und Abläufen über mehrere Monate mit Projektteam."),
        "risk": (3, "Abhängig von Lizenzverträgen und davon, ob alle den Wechsel mittragen."),
        "compliance": NO_COMPLIANCE,
    },
    "ex-07": {
        "assumption": "Automatisch aktualisierte Dashboards ersetzen manuell erstellte Excel-Reports.",
        "impact": (4, "Entfällt die wöchentliche manuelle Report-Erstellung, spart das mehrere Stunden."),
        "reach": (3, "Ersteller und Empfänger der Reports profitieren regelmäßig."),
        "effort": (3, "Datenanbindung und Dashboard-Aufbau dauern einige Wochen."),
        "risk": (2, "Etablierte BI-Werkzeuge, offen ist nur die Datenqualität der Quellen."),
        "compliance": Compliance(
            flag=True,
            categories=[CODETERMINATION],
            note="Dashboards könnten Leistungskennzahlen einzelner Mitarbeitender sichtbar machen.",
        ),
    },
    "ex-08": {
        "assumption": "Zwei feste Blöcke pro Woche, in denen teamweit keine Meetings stattfinden.",
        "impact": (4, "Ungestörte Zeit für konzentrierte Arbeit steigert Qualität und Tempo spürbar."),
        "reach": (5, "Gilt für das ganze Team jede Woche."),
        "effort": (1, "Nur eine Kalenderregel, keine Tools und keine Kosten."),
        "risk": (3, "Akzeptanz unklar, wenn externe Termine oder Kunden kollidieren."),
        "compliance": NO_COMPLIANCE,
    },
    "ex-09": {
        "assumption": "Häufige IT-Anfragen wie Passwort-Reset oder Software-Freigaben laufen über ein Self-Service-Portal.",
        "impact": (3, "Wartezeiten auf Standardanfragen entfallen, die IT wird entlastet."),
        "reach": (4, "Fast alle stellen gelegentlich solche Anfragen."),
        "effort": (3, "Einrichtung des Portals und Anbindung an die IT-Systeme über einige Wochen."),
        "risk": (2, "Verbreitete Lösung, abhängig von der Zusammenarbeit mit der IT."),
        "compliance": Compliance(
            flag=True,
            categories=[INFOSEC],
            note="Self-Service für Passwörter und Berechtigungen berührt sicherheitskritische Systeme.",
        ),
    },
    "ex-10": {
        "assumption": "Gemeinsame Vorlagen für Protokolle, Statusberichte und Standard-E-Mails werden bereitgestellt.",
        "impact": (2, "Spart bei jeder Nutzung ein paar Minuten und vereinheitlicht Dokumente."),
        "reach": (3, "Ein Teil des Teams nutzt solche Vorlagen regelmäßig."),
        "effort": (1, "Eine Person kann die Vorlagen in wenigen Tagen erstellen."),
        "risk": (1, "Bewährt, ohne Abhängigkeiten."),
        "compliance": NO_COMPLIANCE,
    },
}

MOCK_REASONING = "Mock-Bewertung"
CRITERIA = ("impact", "reach", "effort", "risk")


class MockEvaluator(Evaluator):
    """Liefert feste Bewertungen für Beispiel-Ideen und Hash-basierte für alle anderen."""

    def evaluate(self, ideas: list[Idea]) -> EvaluationRun:
        """Bewertet jede Idee deterministisch, ohne externen Aufruf – der Mock scheitert nie."""
        evaluated_at = datetime.now().astimezone()
        evaluations = [
            self._evaluate_one(idea).model_copy(update={"evaluated_at": evaluated_at}) for idea in ideas
        ]
        return EvaluationRun(evaluations=evaluations)

    def _evaluate_one(self, idea: Idea) -> Evaluation:
        if idea.id in EXAMPLE_EVALUATIONS:
            return _from_example(idea.id, EXAMPLE_EVALUATIONS[idea.id])
        return _from_hash(idea)


def _from_example(idea_id: str, data: dict) -> Evaluation:
    """Baut eine Evaluation aus den fest hinterlegten Beispieldaten."""
    scores = {
        name: CriterionScore(score=data[name][0], reasoning=data[name][1]) for name in CRITERIA
    }
    return Evaluation(
        idea_id=idea_id,
        source="mock",
        assumption=data["assumption"],
        compliance=data["compliance"],
        **scores,
    )


def _from_hash(idea: Idea) -> Evaluation:
    """Leitet Scores aus einem SHA-256 des Inhalts ab – gleiche Idee, gleiche Scores.

    Pythons eingebautes hash() ist pro Prozess zufällig und daher ungeeignet.
    """
    content = f"{idea.title}\n{idea.description or ''}"
    digest = hashlib.sha256(content.encode("utf-8")).digest()
    scores = {
        name: CriterionScore(score=digest[i] % 5 + 1, reasoning=MOCK_REASONING)
        for i, name in enumerate(CRITERIA)
    }
    return Evaluation(
        idea_id=idea.id,
        source="mock",
        assumption=f"{MOCK_REASONING}: Idee „{idea.title}“ wurde nicht inhaltlich interpretiert.",
        compliance=NO_COMPLIANCE,
        **scores,
    )
