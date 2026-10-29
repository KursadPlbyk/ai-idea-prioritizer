"""Evaluator-Schnittstelle – UI und Scoring kennen nur diese Klasse."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from priorisierer.models import Evaluation, Idea


class EvaluationFailure(BaseModel):
    """Eine Idee, die nicht bewertet werden konnte, mit verständlichem Grund."""

    idea_id: str
    reason: str


class RunUsage(BaseModel):
    """Verbrauch eines Laufs: Aufrufe, Wiederholungen, Tokens und Zeit (beim Mock alles 0)."""

    api_calls: int = 0
    # Ungültige Antworten nach Grund, z. B. {"schema": 1, "max_tokens": 2}. Auf jede außer der
    # letzten einer Idee folgt ein erneuter Versuch.
    invalid_responses: dict[str, int] = Field(default_factory=dict)
    input_tokens: int = 0
    # Enthält auch die Denk-Tokens des Modells.
    output_tokens: int = 0
    # Aufrufe, deren Tokens unbekannt sind: parse() scheiterte, bevor die Antwort zugänglich war.
    calls_without_usage: int = 0
    # Summe der Dauer aller Einzelaufrufe (bei Parallelität größer als wall_seconds).
    call_seconds: float = 0.0
    # Gesamtdauer des Laufs von Start bis Ende.
    wall_seconds: float = 0.0

    def __add__(self, other: "RunUsage") -> "RunUsage":
        """Addiert zwei Messungen (wall_seconds wird separat gesetzt, nicht addiert)."""
        invalid = dict(self.invalid_responses)
        for reason, count in other.invalid_responses.items():
            invalid[reason] = invalid.get(reason, 0) + count
        return RunUsage(
            api_calls=self.api_calls + other.api_calls,
            invalid_responses=invalid,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            calls_without_usage=self.calls_without_usage + other.calls_without_usage,
            call_seconds=self.call_seconds + other.call_seconds,
            wall_seconds=self.wall_seconds,
        )


class EvaluationRun(BaseModel):
    """Ergebnis eines Bewertungslaufs: erfolgreiche Bewertungen, Fehlschläge pro Idee und Verbrauch."""

    evaluations: list[Evaluation]
    failures: list[EvaluationFailure] = Field(default_factory=list)
    usage: RunUsage = Field(default_factory=RunUsage)


class Evaluator(ABC):
    """Bewertet Ideen anhand der Rubrik."""

    @abstractmethod
    def evaluate(self, ideas: list[Idea]) -> EvaluationRun:
        """Bewertet die übergebenen Ideen (Reihenfolge der Bewertungen bleibt erhalten)."""
