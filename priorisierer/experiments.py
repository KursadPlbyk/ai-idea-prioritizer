"""Kalibrierungs-Experimente durchführen, speichern, laden und als Markdown berichten.

Berührt data/state.json nie – Experimente schreiben nur nach experiments/.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from priorisierer.analysis import CRITERIA, SCORES, ExperimentSummary, summarize
from priorisierer.evaluators.base import EvaluationRun, Evaluator, RunUsage
from priorisierer.models import Idea, Weights
from priorisierer.prompts import PROMPT_DESCRIPTIONS

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent / "experiments"

# US-$ pro 1 Mio. Tokens (Input, Output). Stand: Okt. 2026, Prompts bis 100K Tokens.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {"claude-haiku-5-5": (0.10, 0.50)}

CRITERIA_LABELS = {"impact": "Nutzen", "reach": "Reichweite", "effort": "Aufwand", "risk": "Risiko"}


class ExperimentConfig(BaseModel):
    """Womit ein Experiment gelaufen ist – damit es nachvollziehbar und wiederholbar bleibt."""

    label: str
    prompt_version: str
    effort: str
    model: str
    run_count: int
    sdk_version: str
    started_at: datetime


class ExperimentRecord(BaseModel):
    """Rohdaten eines Experiments: Konfiguration, bewertete Ideen und alle Läufe."""

    config: ExperimentConfig
    ideas: list[Idea]
    runs: list[EvaluationRun]

    def evaluation_runs(self) -> list[list]:
        """Nur die Bewertungen pro Lauf – Eingabeformat für analysis.summarize."""
        return [run.evaluations for run in self.runs]

    def total_usage(self) -> RunUsage:
        """Verbrauch über alle Läufe; wall_seconds ist hier die Summe der Laufzeiten."""
        total = sum((run.usage for run in self.runs), RunUsage())
        total.wall_seconds = sum(run.usage.wall_seconds for run in self.runs)
        return total


def run_experiment(evaluator: Evaluator, ideas: list[Idea], config: ExperimentConfig) -> ExperimentRecord:
    """Bewertet die Ideen config.run_count-mal nacheinander mit demselben Evaluator."""
    runs = []
    for number in range(1, config.run_count + 1):
        run = evaluator.evaluate(ideas)
        print(f"  Lauf {number}/{config.run_count}: {len(run.evaluations)} bewertet, {len(run.failures)} fehlgeschlagen")
        runs.append(run)
    return ExperimentRecord(config=config, ideas=ideas, runs=runs)


def experiment_path(label: str, directory: Path = EXPERIMENTS_DIR) -> Path:
    """Pfad der Rohdaten-Datei zu einem Label."""
    return directory / f"{label}.json"


def save_experiment(record: ExperimentRecord, directory: Path = EXPERIMENTS_DIR) -> Path:
    """Speichert Rohdaten (.json) und Zusammenfassung (.md). Gibt den JSON-Pfad zurück."""
    directory.mkdir(parents=True, exist_ok=True)
    path = experiment_path(record.config.label, directory)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(render_summary(record), encoding="utf-8")
    return path


def load_experiment(label: str, directory: Path = EXPERIMENTS_DIR) -> ExperimentRecord:
    """Lädt die Rohdaten eines Experiments."""
    return ExperimentRecord.model_validate_json(experiment_path(label, directory).read_text(encoding="utf-8"))


def estimate_cost(usage: RunUsage, model: str) -> float | None:
    """Kosten in US-$ aus den Tokens; None bei unbekanntem Preis. Untergrenze, falls Tokens fehlen."""
    if model not in PRICES_PER_MTOK:
        return None
    input_price, output_price = PRICES_PER_MTOK[model]
    return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1_000_000


# --- Markdown ---------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 2) -> str:
    """Zahl mit Komma als Dezimaltrenner; „–“ für nicht definiert."""
    return "–" if value is None else f"{value:.{digits}f}".replace(".", ",")


def _fmt_bool(value: bool | None) -> str:
    return "–" if value is None else ("ja" if value else "nein")


def _distribution_cell(counts: dict[int, int]) -> str:
    """Kompakte Notenverteilung, z. B. „0·3·20·7·0“ für die Noten 1 bis 5."""
    return "·".join(str(counts[score]) for score in SCORES)


def _cost_text(usage: RunUsage, model: str) -> str:
    cost = estimate_cost(usage, model)
    if cost is None:
        return "unbekannt (kein Preis hinterlegt)"
    lower_bound = " (Untergrenze, Tokens teils unbekannt)" if usage.calls_without_usage else ""
    return f"{cost:.4f} $".replace(".", ",") + lower_bound


def render_summary(record: ExperimentRecord) -> str:
    """Lesbare Zusammenfassung eines Experiments."""
    config = record.config
    summary = summarize(record.evaluation_runs(), Weights())
    usage = record.total_usage()
    titles = {idea.id: idea.title for idea in record.ideas}
    seconds_per_call = usage.call_seconds / usage.api_calls if usage.api_calls else None
    failures = sum(len(run.failures) for run in record.runs)

    lines = [
        f"# Experiment `{config.label}`",
        "",
        "| Einstellung | Wert |",
        "|---|---|",
        f"| Prompt | {config.prompt_version} – {PROMPT_DESCRIPTIONS.get(config.prompt_version, '')} |",
        f"| Effort | {config.effort} |",
        f"| Modell | {config.model} |",
        f"| Läufe × Ideen | {summary.run_count} × {len(record.ideas)} |",
        f"| Gestartet | {config.started_at:%d.%m.%Y %H:%M} |",
        f"| SDK | anthropic {config.sdk_version} |",
        "",
        "## Verbrauch",
        "",
        "| Kennzahl | Wert |",
        "|---|---|",
        f"| API-Aufrufe (inkl. Wiederholungen) | {usage.api_calls} |",
        f"| Ungültige Antworten nach Grund | {usage.invalid_responses or 'keine'} |",
        f"| Fehlgeschlagene Ideen | {failures} |",
        f"| Input-/Output-Tokens | {usage.input_tokens} / {usage.output_tokens} |",
        f"| Aufrufe ohne Token-Angabe | {usage.calls_without_usage} |",
        f"| Kosten (Schätzung) | {_cost_text(usage, config.model)} |",
        f"| Ø Dauer pro Aufruf | {_fmt(seconds_per_call, 1)} s |",
        f"| Ø Dauer pro Lauf (parallel) | {_fmt(usage.wall_seconds / summary.run_count if summary.run_count else None, 1)} s |",
        "",
        "## Trennschärfe und Stabilität",
        "",
        "Trennschärfe = Standardabweichung der Median-Scores über die Ideen "
        "(0 = trennt nicht, ≈ 1,41 bei Gleichverteilung, max. 2,0).",
        "Stabilität = Spannweite (max − min) derselben Idee über die Läufe.",
        "",
        "| Kriterium | Trennschärfe | Anteil Spannweite 0 | Ø Spannweite | Notenverteilung 1·2·3·4·5 |",
        "|---|---|---|---|---|",
    ]
    for name in CRITERIA:
        stab = summary.stability[name]
        lines.append(
            f"| {CRITERIA_LABELS[name]} | {_fmt(summary.discrimination[name])} "
            f"| {_fmt(stab.share_zero_range if stab else None)} | {_fmt(stab.mean_range if stab else None)} "
            f"| {_distribution_cell(summary.distribution[name])} |"
        )

    ranking = summary.ranking
    lines += [
        "",
        "## Ranking-Stabilität (Standardgewichte 30/25/25/20)",
        "",
        f"- Ø Spearman über {ranking.pair_count} Lauf-Paare: **{_fmt(ranking.mean_spearman)}**",
        f"- Top {len(ranking.top_per_run[0]) if ranking.top_per_run else 3} in allen Läufen gleich: "
        f"**{_fmt_bool(ranking.top_identical)}**",
    ]
    for number, top in enumerate(ranking.top_per_run, start=1):
        lines.append(f"  - Lauf {number}: " + ", ".join(titles.get(i, i) for i in top))

    compliance = summary.compliance
    lines += [
        "",
        "## Compliance",
        "",
        f"- Markierte Ideen pro Lauf: {compliance.flagged_per_run} (Median {_fmt(compliance.flagged_median, 1)})",
        f"- Gleiches Flag in allen Läufen: {_fmt(compliance.share_consistent_flag)}",
        f"- Kategorien (über alle Läufe): {compliance.category_counts or 'keine'}",
        "",
        "## Median-Scores pro Idee",
        "",
        "| Idee | Nutzen | Reichweite | Aufwand | Risiko | Flag (Läufe) |",
        "|---|---|---|---|---|---|",
    ]
    flags = _flags_per_idea(record)
    for idea_id, medians in summary.median_scores.items():
        cells = " | ".join(_fmt(medians[name], 1) for name in CRITERIA)
        lines.append(f"| {titles.get(idea_id, idea_id)} | {cells} | {flags.get(idea_id, 0)}/{summary.run_count} |")
    return "\n".join(lines) + "\n"


def _flags_per_idea(record: ExperimentRecord) -> dict[str, int]:
    """Wie oft jede Idee markiert wurde."""
    counts: dict[str, int] = {}
    for run in record.runs:
        for evaluation in run.evaluations:
            counts[evaluation.idea_id] = counts.get(evaluation.idea_id, 0) + evaluation.compliance.flag
    return counts


def render_comparison(records: list[ExperimentRecord]) -> str:
    """Vergleichstabelle mehrerer Experimente: eine Zeile pro Kennzahl, eine Spalte pro Experiment."""
    summaries: list[ExperimentSummary] = [summarize(r.evaluation_runs(), Weights()) for r in records]
    usages = [r.total_usage() for r in records]
    labels = [r.config.label for r in records]

    def row(name: str, values: list[str]) -> str:
        return f"| {name} | " + " | ".join(values) + " |"

    lines = [
        "# Vergleich der Kalibrierungs-Experimente",
        "",
        "| Kennzahl | " + " | ".join(f"`{label}`" for label in labels) + " |",
        "|---|" + "---|" * len(labels),
        row("Prompt / Effort", [f"{r.config.prompt_version} / {r.config.effort}" for r in records]),
        row("Läufe × Ideen", [f"{s.run_count} × {len(r.ideas)}" for s, r in zip(summaries, records)]),
        row("**Trennschärfe** (σ der Mediane)", ["" for _ in records]),
    ]
    for name in CRITERIA:
        lines.append(row(f"  {CRITERIA_LABELS[name]}", [_fmt(s.discrimination[name]) for s in summaries]))
    lines.append(row("**Stabilität** (Anteil Spannweite 0 / Ø Spannweite)", ["" for _ in records]))
    for name in CRITERIA:
        values = []
        for s in summaries:
            stab = s.stability[name]
            values.append(f"{_fmt(stab.share_zero_range)} / {_fmt(stab.mean_range)}" if stab else "–")
        lines.append(row(f"  {CRITERIA_LABELS[name]}", values))
    lines.append(row("**Notenverteilung** 1·2·3·4·5", ["" for _ in records]))
    for name in CRITERIA:
        lines.append(row(f"  {CRITERIA_LABELS[name]}", [_distribution_cell(s.distribution[name]) for s in summaries]))
    lines += [
        row("**Ranking**: Ø Spearman", [_fmt(s.ranking.mean_spearman) for s in summaries]),
        row("**Ranking**: Top 3 in allen Läufen gleich", [_fmt_bool(s.ranking.top_identical) for s in summaries]),
        row("**Compliance**: markiert pro Lauf (Median)", [f"{s.compliance.flagged_per_run} ({_fmt(s.compliance.flagged_median, 1)})" for s in summaries]),
        row("**Compliance**: gleiches Flag in allen Läufen", [_fmt(s.compliance.share_consistent_flag) for s in summaries]),
        row("**Verbrauch**: API-Aufrufe", [str(u.api_calls) for u in usages]),
        row("**Verbrauch**: ungültige Antworten", [str(u.invalid_responses or "keine") for u in usages]),
        row("**Verbrauch**: Input-/Output-Tokens", [f"{u.input_tokens} / {u.output_tokens}" for u in usages]),
        row("**Verbrauch**: Kosten (Schätzung)", [_cost_text(u, r.config.model) for u, r in zip(usages, records)]),
        row("**Verbrauch**: Ø Dauer pro Aufruf", [f"{_fmt(u.call_seconds / u.api_calls if u.api_calls else None, 1)} s" for u in usages]),
        "",
        "## Hinweise zur Aussagekraft",
        "",
    ]
    versions = {r.config.prompt_version for r in records}
    for version in sorted(versions):
        lines.append(f"- **{version}:** {PROMPT_DESCRIPTIONS.get(version, '')}")
    if "v2" in versions:
        lines += [
            "- **v2 testet vier Änderungen gebündelt** (Anker 2/4, Skalen-Anweisung, Compliance-Regel, "
            "Kalibrierungsbeispiele). Ein Unterschied zu v1 lässt sich daher **keiner einzelnen Änderung** "
            "zuordnen.",
            "- Möglicher nächster Schritt: **Ablation** – jede Änderung einzeln weglassen (v2 ohne Beispiele, "
            "v2 ohne Anker 2/4, …) und erneut messen, um den Beitrag jeder Änderung zu sehen.",
        ]
    lines += [
        "- Kleine Stichprobe (wenige Läufe × 10 Ideen): kleine Unterschiede, z. B. Spearman 0,90 gegenüber 0,93, "
        "können Zufall sein.",
        "- Mehr Streuung allein ist kein Erfolg – Trennschärfe immer zusammen mit Stabilität lesen.",
    ]
    return "\n".join(lines) + "\n"
