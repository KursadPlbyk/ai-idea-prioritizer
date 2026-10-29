"""LLMEvaluator – bewertet Ideen über die Anthropic API nach der Rubrik."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from priorisierer.evaluators.base import EvaluationFailure, EvaluationRun, Evaluator, RunUsage
from priorisierer.models import Assessment, Evaluation, Idea
from priorisierer.prompts import DEFAULT_PROMPT_VERSION, SYSTEM_PROMPTS, build_user_message

DEFAULT_MODEL = "claude-haiku-5-5"
# Thinking ist beim Modell standardmäßig an und zählt gegen max_tokens – daher großzügig.
MAX_TOKENS = 4000
MAX_PARALLEL_REQUESTS = 5
DEFAULT_EFFORT = "low"
# Erster Versuch + ein erneuter Versuch bei ungültiger Antwort.
MAX_ATTEMPTS = 2


def api_key_configured() -> bool:
    """Prüft, ob ein API-Key gesetzt ist (aus .env oder Umgebung). Der Wert selbst wird nie ausgegeben."""
    load_dotenv()
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def describe_api_error(error: anthropic.APIError) -> str:
    """Übersetzt SDK-Fehler in verständliche deutsche Meldungen (spezifischste Klasse zuerst)."""
    if isinstance(error, anthropic.AuthenticationError):
        return "API-Key ungültig – bitte ANTHROPIC_API_KEY in .env prüfen."
    if isinstance(error, anthropic.PermissionDeniedError):
        return "Der API-Key hat keine Berechtigung für diese Anfrage."
    if isinstance(error, anthropic.NotFoundError):
        return "Modell nicht gefunden – bitte ANTHROPIC_MODEL in .env prüfen."
    if isinstance(error, anthropic.RateLimitError):
        return "Rate-Limit erreicht – bitte kurz warten und erneut versuchen."
    if isinstance(error, anthropic.BadRequestError):
        # Für fehlendes Guthaben gibt es keine eigene Fehlerklasse, nur diesen Text.
        if "credit balance" in error.message.lower():
            return "Kein Guthaben mehr auf dem Anthropic-Konto."
        return f"Anfrage von der API abgelehnt: {error.message}"
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code >= 500:
            return "Der Anthropic-Dienst ist gerade nicht erreichbar – bitte später erneut versuchen."
        return f"API-Fehler {error.status_code}: {error.message}"
    if isinstance(error, anthropic.APITimeoutError):
        return "Zeitüberschreitung bei der Anfrage an die Anthropic API."
    if isinstance(error, anthropic.APIConnectionError):
        return "Keine Verbindung zur Anthropic API – bitte Internetverbindung prüfen."
    return f"Unerwarteter API-Fehler: {error}"


class LLMEvaluator(Evaluator):
    """Bewertet jede Idee mit einem eigenen API-Aufruf, bis zu fünf parallel."""

    def __init__(
        self,
        client: Any = None,
        model: str | None = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        effort: str = DEFAULT_EFFORT,
    ) -> None:
        """client ist injizierbar (Tests nutzen einen Fake); sonst echter Anthropic-Client."""
        if prompt_version not in SYSTEM_PROMPTS:
            raise ValueError(f"Unbekannte Prompt-Version {prompt_version!r}, verfügbar: {sorted(SYSTEM_PROMPTS)}")
        load_dotenv()
        self._client = client if client is not None else anthropic.Anthropic()
        self.model = model or os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODEL
        self.prompt_version = prompt_version
        self.effort = effort

    def evaluate(self, ideas: list[Idea]) -> EvaluationRun:
        """Bewertet die Ideen parallel; Fehlschläge werden pro Idee gemeldet, nicht geworfen."""
        if not ideas:
            return EvaluationRun(evaluations=[])
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_REQUESTS, len(ideas))) as executor:
            # map liefert die Ergebnisse in der Reihenfolge der Eingabe, egal wer zuerst fertig ist.
            results = list(executor.map(self._evaluate_one, ideas))
        # Jeder Thread hat seine eigene Messung geliefert; summiert wird erst hier, ohne gemeinsame Zähler.
        usage = sum((call_usage for _, call_usage in results), RunUsage())
        usage.wall_seconds = time.perf_counter() - started
        outcomes = [outcome for outcome, _ in results]
        return EvaluationRun(
            evaluations=[outcome for outcome in outcomes if isinstance(outcome, Evaluation)],
            failures=[outcome for outcome in outcomes if isinstance(outcome, EvaluationFailure)],
            usage=usage,
        )

    def _evaluate_one(self, idea: Idea) -> tuple[Evaluation | EvaluationFailure, RunUsage]:
        """Ein Aufruf pro Idee, bei ungültiger Antwort ein erneuter Versuch. Liefert auch den Verbrauch."""
        usage = RunUsage()
        problem = ""
        for _ in range(MAX_ATTEMPTS):
            started = time.perf_counter()
            try:
                response = self._call_api(idea)
            except ValidationError as error:
                # parse() validiert schon beim Empfang – auch eine abgeschnittene Antwort landet hier.
                # Die Antwort (und damit ihre Token-Zahl) ist dann nicht zugänglich.
                usage += _call_usage(started, token_usage=None, invalid_kind="schema")
                problem = f"Antwort passt nicht zum Schema: {error.error_count()} Fehler"
                continue
            except anthropic.APIError as error:
                # API-Fehler wiederholt das SDK bei Bedarf schon selbst (429, 5xx, Verbindung).
                usage += _call_usage(started, token_usage=None)
                return EvaluationFailure(idea_id=idea.id, reason=describe_api_error(error)), usage

            invalid = _check_response(response)
            usage += _call_usage(started, token_usage=response.usage, invalid_kind=invalid and invalid[0])
            if invalid:
                problem = invalid[1]
                continue
            evaluation = Evaluation(
                **response.parsed_output.model_dump(),
                idea_id=idea.id,
                source="llm",
                model=self.model,
                evaluated_at=datetime.now().astimezone(),
                prompt_version=self.prompt_version,
            )
            return evaluation, usage
        failure = EvaluationFailure(
            idea_id=idea.id, reason=f"Keine gültige Antwort nach {MAX_ATTEMPTS} Versuchen ({problem})."
        )
        return failure, usage

    def _call_api(self, idea: Idea) -> Any:
        """Der eigentliche API-Aufruf: Assessment-Schema, gewählte Prompt-Version und Effort."""
        return self._client.messages.parse(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPTS[self.prompt_version],
            messages=[{"role": "user", "content": build_user_message(idea)}],
            output_format=Assessment,
            output_config={"effort": self.effort},
        )


def _check_response(response: Any) -> tuple[str, str] | None:
    """Prüft eine geparste Antwort. Gibt (Grund-Schlüssel, Meldung) zurück, wenn sie unbrauchbar ist."""
    if response.stop_reason == "refusal":
        return "refusal", "Modell hat die Bewertung abgelehnt"
    if response.stop_reason == "max_tokens":
        return "max_tokens", "Antwort wurde wegen max_tokens abgeschnitten"
    if response.parsed_output is None:
        return "empty", "Antwort enthielt keine auswertbaren Daten"
    return None


def _call_usage(started: float, token_usage: Any, invalid_kind: str | None = None) -> RunUsage:
    """Verbrauch eines einzelnen API-Aufrufs. token_usage=None heißt: Tokens unbekannt."""
    return RunUsage(
        api_calls=1,
        invalid_responses={invalid_kind: 1} if invalid_kind else {},
        input_tokens=token_usage.input_tokens if token_usage else 0,
        output_tokens=token_usage.output_tokens if token_usage else 0,
        calls_without_usage=0 if token_usage else 1,
        call_seconds=time.perf_counter() - started,
    )
