"""Pydantic-Modelle für Ideen und Bewertungen (siehe docs/BEWERTUNGSMODELL.md, Abschnitt 3)."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class Idea(BaseModel):
    """Eine Idee des Teams."""

    id: str
    title: str = Field(min_length=1)
    description: str | None = None


class CriterionScore(BaseModel):
    """Score für ein Kriterium (ganze Zahl 1–5) mit einsätziger Begründung."""

    # Reihenfolge ist Absicht: Das LLM schreibt die Felder in dieser Reihenfolge –
    # erst begründen, dann die Note vergeben.
    reasoning: str
    # strict: 3.5 oder "3" werden abgelehnt statt still umgewandelt.
    score: int = Field(ge=1, le=5, strict=True)


class ComplianceCategory(StrEnum):
    """Die vier Prüfkategorien aus BEWERTUNGSMODELL Abschnitt 2."""

    GDPR = "Datenschutz (DSGVO)"
    CODETERMINATION = "Mitbestimmung"
    EXTERNAL_AI = "Externe KI-/Cloud-Dienste"
    INFOSEC = "Informationssicherheit"


class Compliance(BaseModel):
    """Compliance-Hinweis – Prüfauftrag, fließt nicht in den Score ein."""

    # Bewusst ohne Defaults: Felder mit Default wären im Schema für das LLM optional.
    flag: bool
    categories: list[ComplianceCategory]
    note: str

    @field_validator("categories", mode="before")
    @classmethod
    def match_categories_case_insensitive(cls, value: Any) -> Any:
        """Ordnet Kategorien unabhängig von Groß-/Kleinschreibung den festen Werten zu."""
        if not isinstance(value, list):
            return value
        by_lower = {category.value.lower(): category for category in ComplianceCategory}
        return [by_lower.get(item.strip().lower(), item) if isinstance(item, str) else item for item in value]

    @model_validator(mode="after")
    def check_flag_matches_categories(self) -> Self:
        """flag=True braucht mindestens eine Kategorie, flag=False keine."""
        if self.flag and not self.categories:
            raise ValueError("Compliance-Flag gesetzt, aber keine Kategorie angegeben.")
        if not self.flag and self.categories:
            raise ValueError("Kategorien angegeben, aber Compliance-Flag nicht gesetzt.")
        return self


class Assessment(BaseModel):
    """Die inhaltliche Einschätzung einer Idee – genau das, was ein Bewerter (z. B. das LLM) liefert."""

    assumption: str
    impact: CriterionScore
    reach: CriterionScore
    effort: CriterionScore
    risk: CriterionScore
    compliance: Compliance


class Evaluation(Assessment):
    """Gespeicherte Bewertung: Einschätzung plus Zuordnung und Herkunft, die der Code setzt."""

    idea_id: str
    # Defaults, damit eine state.json aus Auftrag 1 (nur Mock, ohne diese Felder) ladbar bleibt.
    source: Literal["mock", "llm"] = "mock"
    model: str | None = None
    evaluated_at: datetime | None = None
    # Seit Auftrag 3b. None = unbekannt (Mock oder KI-Bewertung von vor 3b).
    prompt_version: str | None = None


class Weights(BaseModel):
    """Gewichte der vier Kriterien. Müssen nicht 100 ergeben – werden normalisiert."""

    impact: float = Field(default=30, ge=0)
    reach: float = Field(default=25, ge=0)
    effort: float = Field(default=25, ge=0)
    risk: float = Field(default=20, ge=0)


# --- Team-Eingaben (Auftrag 4) – getrennt von der KI-Bewertung gespeichert --------------

Criterion = Literal["impact", "reach", "effort", "risk"]


class ScoreOverride(BaseModel):
    """Team-Korrektur eines einzelnen Scores. Die KI-Bewertung selbst bleibt unverändert."""

    score: int = Field(ge=1, le=5, strict=True)
    reason: str = ""
    created_at: datetime | None = None


class ReviewStatus(StrEnum):
    """Prüfstatus einer Idee mit Compliance-Flag – vom Team gesetzt."""

    OPEN = "offen"
    CLEARED = "geklärt"
    REJECTED = "abgelehnt"


class ComplianceReview(BaseModel):
    """Prüfentscheidung des Teams. `categories` hält fest, welche Kategorien bei der Prüfung vorlagen."""

    status: ReviewStatus
    note: str = ""
    categories: list[ComplianceCategory] = Field(default_factory=list)
    updated_at: datetime | None = None


class AppState(BaseModel):
    """Gesamter gespeicherter Zustand. Defaults, damit ältere state.json-Dateien ladbar bleiben."""

    ideas: list[Idea] = Field(default_factory=list)
    evaluations: list[Evaluation] = Field(default_factory=list)
    # {idea_id: {kriterium: Korrektur}}
    overrides: dict[str, dict[Criterion, ScoreOverride]] = Field(default_factory=dict)
    # {idea_id: Prüfentscheidung}
    compliance_reviews: dict[str, ComplianceReview] = Field(default_factory=dict)
