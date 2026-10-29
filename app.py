"""Streamlit-UI des Ideen-Priorisierers – nur Darstellung und Interaktion.

Die Logik (Ranking, Korrekturen, Prüfstatus, Matrix-Koordinaten, CSV) steckt in priorisierer/.
"""

import uuid
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from priorisierer.evaluators import Evaluator
from priorisierer.evaluators.llm import LLMEvaluator, api_key_configured
from priorisierer.evaluators.mock import MockEvaluator
from priorisierer.matrix import marker_labels, matrix_points, quadrant_lines
from priorisierer.models import AppState, ComplianceReview, Evaluation, Idea, ReviewStatus, ScoreOverride, Weights
from priorisierer.ranking_view import (
    CRITERIA,
    CRITERIA_HEADERS,
    CRITERIA_LABELS,
    STATUS_LABELS,
    RankingView,
    build_ranking,
    display_score,
    format_delta,
    position_summary,
    score_cell,
    score_header,
    to_csv,
)
from priorisierer.scoring import BIG_PROJECT, FILL_IN, QUICK_WIN, TIME_SINK, Formula, other_formula
import priorisierer.storage as storage
from priorisierer.edge_cases import load_edge_cases
from priorisierer.storage import load_example_ideas, load_state, save_state

QUADRANT_ICONS = {QUICK_WIN: "🟢", BIG_PROJECT: "🔵", FILL_IN: "⚪", TIME_SINK: "🔴"}
# Farben passend zu den Icons: (Fläche, Punkt)
QUADRANT_COLORS = {
    QUICK_WIN: ("rgba(46, 160, 67, 0.12)", "#2ea043"),
    BIG_PROJECT: ("rgba(31, 111, 235, 0.12)", "#1f6feb"),
    FILL_IN: ("rgba(140, 140, 140, 0.12)", "#8c8c8c"),
    TIME_SINK: ("rgba(218, 54, 51, 0.12)", "#da3633"),
}
SOURCE_LABELS = {"llm": "🤖 KI", "mock": "🧪 Mock"}
MAX_TOASTS = 5
MARKER_SIZE = 26  # Punktgröße in der Matrix (Beamer-tauglich)

EVALUATOR_MOCK = "Mock"
EVALUATOR_LLM = "KI (Claude)"
KEEP_AI = 0  # Auswahlwert „KI-Wert übernehmen“ im Korrektur-Formular


def get_evaluator() -> Evaluator:
    """Einzige Stelle, an der der konkrete Bewerter gewählt wird."""
    if st.session_state.get("evaluator_choice") == EVALUATOR_LLM:
        return LLMEvaluator()
    return MockEvaluator()


# --- Zustand ----------------------------------------------------------------------


def init_state() -> None:
    """Lädt den gespeicherten Zustand einmal pro Sitzung."""
    if "ideas" not in st.session_state:
        state = load_state()
        st.session_state.ideas = state.ideas
        st.session_state.evaluations = {evaluation.idea_id: evaluation for evaluation in state.evaluations}
        st.session_state.overrides = state.overrides
        st.session_state.reviews = state.compliance_reviews
        # Nur für die Sitzung, nicht in state.json: zuletzt bewertete Ideen und anstehende Toasts.
        st.session_state.recent_ids = set()
        st.session_state.pending_toasts = []


def persist() -> None:
    """Speichert den gesamten Zustand in data/state.json."""
    save_state(current_state())


def override_count() -> int:
    """Anzahl aller Team-Korrekturen (für den Hinweis bei „Alle neu bewerten“)."""
    return sum(len(per_idea) for per_idea in st.session_state.overrides.values())


# --- Aktionen (on_click-Callbacks: laufen vor dem Neuzeichnen) -----------------------


def add_idea(title: str, description: str) -> None:
    """Fügt eine neue Idee hinzu."""
    idea = Idea(id=uuid.uuid4().hex[:8], title=title.strip(), description=description.strip() or None)
    st.session_state.ideas.append(idea)
    persist()


def delete_idea(idea_id: str) -> None:
    """Löscht eine Idee samt Bewertung, Korrekturen und Prüfstatus."""
    st.session_state.ideas = [idea for idea in st.session_state.ideas if idea.id != idea_id]
    st.session_state.evaluations.pop(idea_id, None)
    st.session_state.overrides.pop(idea_id, None)
    st.session_state.reviews.pop(idea_id, None)
    st.session_state.recent_ids.discard(idea_id)
    persist()


def current_state() -> AppState:
    """Der Zustand der Sitzung als AppState (zum Speichern oder Sichern)."""
    return AppState(
        ideas=st.session_state.ideas,
        evaluations=list(st.session_state.evaluations.values()),
        overrides=st.session_state.overrides,
        compliance_reviews=st.session_state.reviews,
    )


def add_new_ideas(ideas: list[Idea]) -> int:
    """Hängt Ideen an, deren ID noch nicht vorhanden ist – nichts wird ersetzt. Gibt die Anzahl zurück."""
    existing_ids = {idea.id for idea in st.session_state.ideas}
    new_ideas = [idea for idea in ideas if idea.id not in existing_ids]
    st.session_state.ideas.extend(new_ideas)
    persist()
    return len(new_ideas)


def load_edge_case_ideas() -> None:
    """Fügt die Grenzfälle als normale, unbewertete Ideen hinzu – ohne Erwartung (to_idea)."""
    added = add_new_ideas([case.to_idea() for case in load_edge_cases()])
    st.toast(f"{added} Grenzfall-Idee(n) ergänzt – noch unbewertet." if added else "Alle Grenzfälle sind schon vorhanden.")


def ask_demo_confirmation(ask: bool) -> None:
    """Erster Klick auf „Demo-Stand laden“ fragt nach; „Abbrechen“ setzt zurück."""
    st.session_state.confirm_demo = ask


def load_demo_state() -> None:
    """Sichert den aktuellen Stand nach state.backup.json und lädt den vorbereiteten Demo-Stand."""
    save_state(current_state(), storage.BACKUP_FILE)
    demo = load_state(storage.DEMO_STATE_FILE)
    # Formular-Zustände verwerfen: Demo-Ideen haben dieselben IDs, sonst stünden alte Team-Werte im Formular.
    for key in [k for k in st.session_state if str(k).startswith(("ov_", "reason_", "review_"))]:
        del st.session_state[key]
    st.session_state.ideas = demo.ideas
    st.session_state.evaluations = {evaluation.idea_id: evaluation for evaluation in demo.evaluations}
    st.session_state.overrides = demo.overrides
    st.session_state.reviews = demo.compliance_reviews
    st.session_state.recent_ids = set()
    st.session_state.pending_toasts = []
    st.session_state.last_failures = []
    st.session_state.confirm_demo = False
    persist()
    st.toast(f"Demo-Stand geladen · Backup des vorherigen Stands: data/{storage.BACKUP_FILE.name}")


def load_examples() -> None:
    """Ergänzt die Beispiel-Ideen, deren ID noch nicht vorhanden ist – nichts wird ersetzt."""
    added = add_new_ideas(load_example_ideas())
    st.toast(f"{added} Beispiel-Ideen ergänzt." if added else "Alle Beispiel-Ideen sind schon vorhanden.")


def evaluate(ideas: list[Idea], mark_recent: bool) -> None:
    """Lässt die Ideen bewerten. Ersetzt nur KI-Bewertungen – Team-Korrekturen und Prüfstatus bleiben."""
    if not ideas:
        return
    with st.spinner(f"Bewerte {len(ideas)} Idee(n) …"):
        run = get_evaluator().evaluate(ideas)
    for evaluation in run.evaluations:
        st.session_state.evaluations[evaluation.idea_id] = evaluation
    titles = {idea.id: idea.title for idea in ideas}
    st.session_state.last_failures = [(titles[failure.idea_id], failure.reason) for failure in run.failures]
    evaluated_ids = [evaluation.idea_id for evaluation in run.evaluations]
    if mark_recent:
        # Markierung gilt bis zur nächsten Bewertung; Toasts mit Platzierung zeigt main() nach dem Ranking.
        st.session_state.recent_ids = set(evaluated_ids)
        st.session_state.pending_toasts = evaluated_ids
    else:
        st.session_state.recent_ids = set()
        st.toast(f"{len(evaluated_ids)} Idee(n) neu bewertet · {override_count()} Team-Korrektur(en) erhalten")
    persist()


def save_overrides(idea_id: str) -> None:
    """Übernimmt das Korrektur-Formular einer Idee. „KI-Wert“ entfernt eine Korrektur."""
    reason = st.session_state.get(f"reason_{idea_id}", "").strip()
    current = dict(st.session_state.overrides.get(idea_id, {}))
    for criterion in CRITERIA:
        choice = st.session_state.get(f"ov_{idea_id}_{criterion}", KEEP_AI)
        existing = current.get(criterion)
        if choice == KEEP_AI:
            current.pop(criterion, None)
        elif existing is None or existing.score != choice:
            current[criterion] = ScoreOverride(score=choice, reason=reason, created_at=datetime.now().astimezone())
        elif reason:
            current[criterion] = existing.model_copy(update={"reason": reason})
    if current:
        st.session_state.overrides[idea_id] = current
    else:
        st.session_state.overrides.pop(idea_id, None)
    persist()


def reset_override(idea_id: str, criterion: str) -> None:
    """Entfernt eine Korrektur; danach gilt wieder der KI-Wert."""
    per_idea = st.session_state.overrides.get(idea_id, {})
    per_idea.pop(criterion, None)
    if not per_idea:
        st.session_state.overrides.pop(idea_id, None)
    # Widget-Zustand verwerfen, sonst zeigt das Formular noch den alten Team-Wert.
    st.session_state.pop(f"ov_{idea_id}_{criterion}", None)
    persist()


def save_review(idea_id: str, categories: list) -> None:
    """Speichert den Prüfstatus samt Notiz und den Kategorien, die bei der Prüfung vorlagen."""
    st.session_state.reviews[idea_id] = ComplianceReview(
        status=ReviewStatus(st.session_state[f"review_{idea_id}"]),
        note=st.session_state.get(f"review_note_{idea_id}", "").strip(),
        categories=categories,
        updated_at=datetime.now().astimezone(),
    )
    persist()


def restore_idea(idea_id: str) -> None:
    """Holt eine abgelehnte Idee zurück: Prüfentscheidung entfernen → bei Flag wieder „offen“."""
    st.session_state.reviews.pop(idea_id, None)
    st.session_state.pop(f"review_{idea_id}", None)
    persist()


# --- Sidebar ----------------------------------------------------------------------


def render_sidebar() -> tuple[Weights, Formula, bool]:
    """Bewerter, Formel, Gewichte und Filter. Gibt (Gewichte, Formel, nur freigegebene) zurück."""
    st.sidebar.header("Bewerter")
    has_key = api_key_configured()
    if not has_key:
        st.session_state.evaluator_choice = EVALUATOR_MOCK
    st.sidebar.radio("Bewerter", [EVALUATOR_MOCK, EVALUATOR_LLM], key="evaluator_choice", disabled=not has_key)
    if not has_key:
        st.sidebar.caption("KI nicht verfügbar: kein ANTHROPIC_API_KEY in .env gefunden.")

    st.sidebar.header("Formel")
    formula = Formula(st.sidebar.radio("Formel", [f.value for f in Formula], key="formula"))

    st.sidebar.header("Gewichtung")
    is_rice = formula == Formula.RICE
    if is_rice:
        st.sidebar.caption("RICE hat eine feste Struktur (Reichweite × Nutzen × Confidence / Aufwand) – Gewichte wirken nicht.")
    else:
        st.sidebar.caption("Gewichte werden automatisch normalisiert – die Summe muss nicht 100 ergeben.")
    defaults = Weights()
    values = {
        name: st.sidebar.slider(label, 0, 100, int(getattr(defaults, name)), step=5, disabled=is_rice)
        for name, label in CRITERIA_LABELS.items()
    }

    st.sidebar.header("Filter")
    only_cleared = st.sidebar.toggle("Nur freigegebene Ideen ranken", key="only_cleared")
    st.sidebar.caption("Blendet Ideen mit offener Compliance-Prüfung aus Ranking und Matrix aus.")
    return Weights(**values), formula, only_cleared


# --- Hauptbereich -------------------------------------------------------------------


def render_new_idea() -> None:
    """Einklappbares Formular für neue Ideen – aufgeklappt, solange es noch keine gibt."""
    with st.expander("➕ Neue Idee", expanded=not st.session_state.ideas):
        with st.form("add_idea", clear_on_submit=True):
            title = st.text_input("Titel")
            description = st.text_area("Beschreibung (optional)")
            if st.form_submit_button("Hinzufügen"):
                if title.strip():
                    add_idea(title, description)
                    st.rerun()
                else:
                    st.warning("Bitte einen Titel eingeben.")


def render_evaluate_buttons() -> None:
    """Buttons zum Bewerten neuer bzw. aller Ideen, mit Hinweis auf erhaltene Korrekturen."""
    unevaluated = [idea for idea in st.session_state.ideas if idea.id not in st.session_state.evaluations]
    col_new, col_all, col_hint = st.columns([2, 2, 3])
    col_new.button(
        f"Ideen bewerten ({len(unevaluated)} neu)",
        type="primary",
        disabled=not unevaluated,
        on_click=evaluate,
        args=(unevaluated, True),
    )
    col_all.button(
        "Alle neu bewerten",
        disabled=not st.session_state.ideas,
        on_click=evaluate,
        args=(st.session_state.ideas, False),
    )
    if count := override_count():
        col_hint.caption(f"✏️ {count} Team-Korrektur(en) bleiben bei „Alle neu bewerten“ erhalten.")


def render_failures() -> None:
    """Warnung für Ideen, die beim letzten Lauf nicht bewertet werden konnten – gruppiert nach Grund."""
    failures: list[tuple[str, str]] = st.session_state.get("last_failures", [])
    titles_by_reason: dict[str, list[str]] = {}
    for title, reason in failures:
        titles_by_reason.setdefault(reason, []).append(title)
    for reason, titles in titles_by_reason.items():
        st.warning(f"**{len(titles)} Idee(n) nicht bewertet:** {reason}\n\n" + ", ".join(titles))


def show_pending_toasts(view: RankingView | None) -> None:
    """Nach „Ideen bewerten“: pro Idee ein Toast mit Platzierung (höchstens MAX_TOASTS, Rest zusammengefasst)."""
    pending: list[str] = st.session_state.pending_toasts
    if not pending:
        return
    titles = {idea.id: idea.title for idea in st.session_state.ideas}
    for idea_id in pending[:MAX_TOASTS]:
        where = position_summary(view, idea_id) if view else None
        st.toast(f"„{titles.get(idea_id, idea_id)}“ → {where or 'nicht im Ranking (abgelehnt oder ausgeblendet)'}")
    if len(pending) > MAX_TOASTS:
        st.toast(f"… und {len(pending) - MAX_TOASTS} weitere Idee(n) bewertet")
    st.session_state.pending_toasts = []


def render_ranking_tab(view: RankingView) -> None:
    """Tabelle, Legende, Export, Details mit Korrektur-/Prüfformular, Bereich „Abgelehnt“."""
    origins = {describe_origin(row.ai) for row in view.rows}
    if len(origins) > 1:
        st.info(
            f"Das Ranking mischt Bewertungen verschiedener Herkunft ({', '.join(sorted(origins))}) – "
            "die Punkte sind nicht direkt vergleichbar. Tipp: Mit einem Bewerter „Alle neu bewerten“."
        )
    if view.hidden_open:
        st.caption(
            f"🛑 {len(view.hidden_open)} Idee(n) mit offener Prüfung ausgeblendet: "
            + ", ".join(item.idea.title for item in view.hidden_open)
        )
    if not view.rows:
        st.info("Keine Ideen im Ranking.")
    else:
        other = other_formula(view.formula)
        rows = [
            {
                "Rang": row.rank,
                "Idee": ("🆕 " if row.is_recent else "") + row.idea.title,
                score_header(view.formula): display_score(row.score, view.formula),
                "Δ Rang": format_delta(row.delta),
                **{CRITERIA_HEADERS[c]: score_cell(row, c) for c in CRITERIA},
                "Quadrant": f"{QUADRANT_ICONS[row.quadrant]} {row.quadrant}",
                "Compliance": STATUS_LABELS[row.status] if row.status else "",
                "Quelle": SOURCE_LABELS[row.ai.source],
            }
            for row in view.rows
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption(
            f"↑ höher ist besser · ↓ niedriger ist besser · ✏️ Team-Korrektur · 🆕 zuletzt bewertet · "
            f"Δ Rang: Platz im Vergleich zu „{other.value}“ (▲ = hier besser platziert)  \n"
            "Gleicher Punktstand = gleicher Rang; der nächste Rang zählt alle Ideen davor (1, 2, 2, 4)."
        )
        col_excel, col_tools = st.columns(2)
        col_excel.download_button(
            "📥 CSV für Excel (;)",
            data=to_csv(view, for_excel=True),
            file_name="ranking_excel.csv",
            mime="text/csv",
            key="csv_excel",
            help="Semikolon und Dezimalkomma – öffnet sich im deutschen Excel per Doppelklick richtig.",
        )
        col_tools.download_button(
            "📥 CSV für Analyse-Tools (,)",
            data=to_csv(view, for_excel=False),
            file_name="ranking.csv",
            mime="text/csv",
            key="csv_tools",
            help="Komma und Dezimalpunkt – Standard für pandas, Data Wrangler, Skripte.",
        )

        st.subheader("Details")
        for row in view.rows:
            render_details(row, view.formula)

    if view.rejected:
        with st.expander(f"⛔ Abgelehnt ({len(view.rejected)})", expanded=False):
            for item in view.rejected:
                col_text, col_button = st.columns([5, 1])
                note = f" – _{item.review.note}_" if item.review and item.review.note else ""
                col_text.markdown(f"**{item.idea.title}**{note}")
                col_button.button("Wiederherstellen", key=f"restore_{item.idea.id}", on_click=restore_idea, args=(item.idea.id,))


def render_details(row, formula: Formula) -> None:
    """Aufklappbare Details einer Idee: Herkunft, Begründungen, Korrekturen, Compliance-Prüfung."""
    idea_id = row.idea.id
    status = f" · {STATUS_LABELS[row.status]}" if row.status else ""
    unit = "" if formula == Formula.RICE else " Punkte"
    marker = "🆕 " if row.is_recent else ""
    with st.expander(f"{row.rank}. {marker}{row.idea.title} – {display_score(row.score, formula)}{unit}{status}"):
        st.caption(describe_source(row.ai))
        st.markdown(f"**Annahme:** {row.ai.assumption}")
        for criterion in CRITERIA:
            ai_score = getattr(row.ai, criterion)
            override = row.overrides.get(criterion)
            label = CRITERIA_HEADERS[criterion]
            if override:
                reason = f" – „{override.reason}“" if override.reason else ""
                col_text, col_button = st.columns([5, 1])
                col_text.markdown(
                    f"- **{label}: KI {ai_score.score} → Team {override.score} ✏️**{reason}  \n"
                    f"  KI-Begründung: {ai_score.reasoning}"
                )
                col_button.button(
                    "Zurücksetzen", key=f"reset_{idea_id}_{criterion}", on_click=reset_override, args=(idea_id, criterion)
                )
            else:
                st.markdown(f"- **{label} ({ai_score.score}):** {ai_score.reasoning}")

        with st.form(f"overrides_{idea_id}"):
            st.markdown("**Team-Korrektur**")
            columns = st.columns(len(CRITERIA))
            for column, criterion in zip(columns, CRITERIA):
                ai_value = getattr(row.ai, criterion).score
                override = row.overrides.get(criterion)
                options = [KEEP_AI, 1, 2, 3, 4, 5]
                column.selectbox(
                    CRITERIA_LABELS[criterion],
                    options,
                    index=options.index(override.score) if override else 0,
                    format_func=lambda value, ai=ai_value: f"KI-Wert ({ai})" if value == KEEP_AI else str(value),
                    key=f"ov_{idea_id}_{criterion}",
                )
            st.text_input("Begründung (optional)", key=f"reason_{idea_id}")
            st.form_submit_button("Korrektur speichern", on_click=save_overrides, args=(idea_id,))

        render_compliance(row)


def render_compliance(row) -> None:
    """Compliance-Hinweis und – bei Flag – Formular für den Prüfstatus."""
    compliance = row.ai.compliance
    if not compliance.flag:
        st.caption("Kein Compliance-Hinweis. Erste Einschätzung, keine Rechtsprüfung.")
        return
    categories = ", ".join(category.value for category in compliance.categories)
    box = st.error if row.status == ReviewStatus.OPEN else st.warning
    box(
        f"**{STATUS_LABELS[row.status]} – Compliance-Hinweis ({categories}):** {compliance.note}\n\n"
        "_Erste Einschätzung, keine Rechtsprüfung._"
    )
    idea_id = row.idea.id
    with st.form(f"review_form_{idea_id}"):
        options = [status.value for status in ReviewStatus]
        st.radio(
            "Prüfstatus",
            options,
            index=options.index(row.status.value),
            horizontal=True,
            key=f"review_{idea_id}",
        )
        st.text_input("Notiz (optional)", value=row.review.note if row.review else "", key=f"review_note_{idea_id}")
        st.form_submit_button("Prüfstatus speichern", on_click=save_review, args=(idea_id, list(compliance.categories)))


def render_matrix_tab(view: RankingView) -> None:
    """Impact/Effort-Matrix mit Quadranten-Flächen; Koordinaten aus priorisierer.matrix."""
    if not view.rows:
        st.info("Keine Ideen im Ranking.")
        return
    x_line, y_line = quadrant_lines()
    low, high = 0.5, 5.5
    fig = go.Figure()
    areas = {
        QUICK_WIN: (low, x_line, y_line, high),
        BIG_PROJECT: (x_line, high, y_line, high),
        FILL_IN: (low, x_line, low, y_line),
        TIME_SINK: (x_line, high, low, y_line),
    }
    for name, (x0, x1, y0, y1) in areas.items():
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=QUADRANT_COLORS[name][0], line_width=0, layer="below")
        fig.add_annotation(
            x=(x0 + x1) / 2, y=y1 - 0.15 if y1 == high else y0 + 0.15, text=f"{QUADRANT_ICONS[name]} {name}",
            showarrow=False, font={"size": 16, "color": QUADRANT_COLORS[name][1]},
        )  # fmt: skip
    fig.add_vline(x=x_line, line_dash="dash", line_color="gray")
    fig.add_hline(y=y_line, line_dash="dash", line_color="gray")

    by_id = {row.idea.id: row for row in view.rows}
    points = matrix_points([row.effective for row in view.rows])
    header = score_header(view.formula)
    # Eindeutige Kennzeichen (Rang, bei Gleichstand 1a/1b) – Titel stehen in der Liste daneben.
    labels = dict(zip(by_id, marker_labels([row.rank for row in view.rows])))

    def hover(row) -> str:
        status = f"<br>{STATUS_LABELS[row.status]}" if row.status else ""
        return (
            f"<b>{row.idea.title}</b><br>Rang {row.rank} · {header}: {display_score(row.score, view.formula)}"
            f"<br>{row.quadrant}{status}"
        )

    # Zuerst (also ganz hinten) der orangefarbene Ring für zuletzt bewertete Ideen.
    recent = [p for p in points if by_id[p.idea_id].is_recent]
    if recent:
        fig.add_trace(
            go.Scatter(
                x=[p.x for p in recent],
                y=[p.y for p in recent],
                mode="markers",
                name="🆕 zuletzt bewertet",
                hoverinfo="skip",
                marker={"size": 40, "symbol": "circle-open", "color": "#f5a623", "line": {"width": 4}},
            )
        )
    # Punkte: gefüllter Kreis mit Rangnummer; offene Prüfung = dicker roter Rand (statt ✕, dort war die Zahl unlesbar).
    groups = {
        "Ideen": ([p for p in points if by_id[p.idea_id].status != ReviewStatus.OPEN], {"width": 1, "color": "white"}),
        "🛑 Prüfung offen": (
            [p for p in points if by_id[p.idea_id].status == ReviewStatus.OPEN],
            {"width": 4, "color": "#b00020"},
        ),
    }
    for name, (group, outline) in groups.items():
        if not group:
            continue
        fig.add_trace(
            go.Scatter(
                x=[p.x for p in group],
                y=[p.y for p in group],
                mode="markers+text",
                name=name,
                text=[labels[p.idea_id] for p in group],
                textposition="middle center",
                textfont={"color": "white", "size": 13, "weight": "bold"},
                hovertext=[hover(by_id[p.idea_id]) for p in group],
                hoverinfo="text",
                marker={
                    "size": MARKER_SIZE,
                    "color": [QUADRANT_COLORS[by_id[p.idea_id].quadrant][1] for p in group],
                    "line": outline,
                },
            )
        )
    axis = {"range": [low, high], "tickvals": [1, 2, 3, 4, 5], "showgrid": False, "tickfont": {"size": 14}}
    fig.update_layout(
        xaxis=axis | {"title": {"text": "Aufwand ↓ (1 = gering)", "font": {"size": 16}}},
        yaxis=axis | {"title": {"text": "Wert ↑ = (Nutzen + Reichweite) / 2", "font": {"size": 16}}},
        height=700,
        font={"size": 14},
        legend={"orientation": "h", "y": -0.12, "font": {"size": 14}},
        margin={"t": 20},
    )
    col_chart, col_list = st.columns([3, 1])
    col_chart.plotly_chart(fig, width="stretch", key="matrix")
    with col_list:
        # Titel als Liste statt im Diagramm: kann sich bei keiner Fenstergröße überschneiden.
        for name in (QUICK_WIN, BIG_PROJECT, FILL_IN, TIME_SINK):
            rows = [row for row in view.rows if row.quadrant == name]
            if not rows:
                continue
            st.markdown(f"**{QUADRANT_ICONS[name]} {name}**")
            st.markdown(
                "\n".join(
                    f"- **{labels[row.idea.id]}** "
                    + ("🛑 " if row.status == ReviewStatus.OPEN else "")
                    + ("🆕 " if row.is_recent else "")
                    + row.idea.title
                    for row in rows
                )
            )
    st.caption(
        "Zahl im Punkt = Rang (bei Gleichstand 1a, 1b …) · roter Rand = 🛑 Prüfung offen · "
        "orangefarbener Ring = 🆕 zuletzt bewertet · Ideen mit gleichen Koordinaten sind leicht versetzt."
    )


def render_manage_tab() -> None:
    """Ideenliste mit Löschen; Beispiel-Ideen, Grenzfälle und Demo-Stand laden."""
    col_examples, col_edge, col_demo = st.columns(3)
    col_examples.button("Beispiel-Ideen laden", on_click=load_examples)
    col_edge.button(
        "Grenzfälle laden",
        on_click=load_edge_case_ideas,
        help="5 Ideen mit offensichtlicher Erwartung, u. a. ein Prompt-Injection-Versuch – werden unbewertet ergänzt.",
    )
    has_demo = storage.DEMO_STATE_FILE.exists()
    col_demo.button(
        "Demo-Stand laden",
        on_click=ask_demo_confirmation,
        args=(True,),
        disabled=not has_demo,
        help="Die 10 Beispiel-Ideen, vorab live mit der KI bewertet – funktioniert auch ohne Netz.",
    )
    if st.session_state.get("confirm_demo"):
        st.warning(
            "Der aktuelle Stand (Ideen, Bewertungen, Korrekturen, Prüfstatus) wird ersetzt. "
            f"Vorher wird ein Backup nach `data/{storage.BACKUP_FILE.name}` geschrieben."
        )
        col_yes, col_no, _ = st.columns([1, 1, 4])
        col_yes.button("Ja, laden", type="primary", on_click=load_demo_state, key="confirm_demo_yes")
        col_no.button("Abbrechen", on_click=ask_demo_confirmation, args=(False,), key="confirm_demo_no")
    for idea in st.session_state.ideas:
        col_text, col_button = st.columns([6, 1])
        status = "" if idea.id in st.session_state.evaluations else " · _noch nicht bewertet_"
        col_text.markdown(f"**{idea.title}**{status}")
        if idea.description:
            col_text.caption(idea.description)
        col_button.button("Löschen", key=f"delete_{idea.id}", on_click=delete_idea, args=(idea.id,))


def describe_origin(evaluation: Evaluation) -> str:
    """Kurzform der Herkunft für den Mischhinweis: Mock oder KI mit Prompt-Version."""
    if evaluation.source == "mock":
        return "Mock"
    return f"KI Prompt {evaluation.prompt_version or 'unbekannt'}"


def describe_source(evaluation: Evaluation) -> str:
    """Herkunftszeile für den Detailbereich."""
    if evaluation.source == "mock":
        return "Mock-Bewertung"
    parts = [f"Bewertet von {evaluation.model}", f"Prompt {evaluation.prompt_version or 'unbekannt'}"]
    if evaluation.evaluated_at:
        parts.append(f"am {evaluation.evaluated_at:%d.%m.%Y, %H:%M}")
    return " · ".join(parts)


def main() -> None:
    st.set_page_config(page_title="Ideen-Priorisierer", page_icon="💡", layout="wide")
    st.title("💡 Intelligenter Ideen-Priorisierer")
    init_state()
    weights, formula, only_cleared = render_sidebar()
    render_new_idea()
    render_evaluate_buttons()
    render_failures()

    view: RankingView | None = None
    if not st.session_state.evaluations:
        message = "Noch keine Bewertungen vorhanden."
    else:
        try:
            view = build_ranking(
                st.session_state.ideas,
                st.session_state.evaluations,
                st.session_state.overrides,
                st.session_state.reviews,
                weights,
                formula,
                only_cleared=only_cleared,
                recent_ids=st.session_state.recent_ids,
            )
        except ValueError:
            message = "Alle Gewichte stehen auf 0 – bitte mindestens ein Gewicht erhöhen."
    show_pending_toasts(view)

    tab_ranking, tab_matrix, tab_manage = st.tabs(["📊 Ranking", "🗺️ Matrix", "📝 Ideen verwalten"])
    # Bewusst if/else statt `a() if view else st.info(...)`: Ein alleinstehender ternärer Ausdruck ist kein
    # Funktionsaufruf, Streamlit-„Magic“ würde ihn in st.write() verpacken (Hilfe-Box bzw. „None“).
    with tab_ranking:
        if view:
            render_ranking_tab(view)
        else:
            st.info(message)
    with tab_matrix:
        if view:
            render_matrix_tab(view)
        else:
            st.info(message)
    with tab_manage:
        render_manage_tab()


main()
