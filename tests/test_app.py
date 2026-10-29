"""App-Durchlauf mit Streamlit AppTest und Mock-Bewerter – berührt data/state.json nicht."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import priorisierer.evaluators.llm as llm
import priorisierer.storage as storage
from priorisierer.evaluators.mock import MockEvaluator
from priorisierer.models import AppState, ScoreOverride

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """Frische App mit temporären Dateien (state, Demo-Stand, Backup) und ohne API-Key (→ Mock-Bewerter)."""
    monkeypatch.setattr(storage, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(storage, "BACKUP_FILE", tmp_path / "state.backup.json")
    monkeypatch.setattr(storage, "DEMO_STATE_FILE", tmp_path / "demo_state.json")
    # Test-Demo-Stand: Beispiel-Ideen, mit dem Mock bewertet (der echte stammt von der KI)
    ideas = storage.load_example_ideas()
    storage.save_state(AppState(ideas=ideas, evaluations=MockEvaluator().evaluate(ideas).evaluations), tmp_path / "demo_state.json")
    monkeypatch.setattr(llm, "api_key_configured", lambda: False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    button(at, "Beispiel-Ideen laden").click().run()
    button(at, "Ideen bewerten").click().run()
    assert not at.exception
    return at


def button(at: AppTest, label_start: str, index: int = 0):
    return [b for b in at.button if b.label.startswith(label_start)][index]


def table(at: AppTest):
    return at.dataframe[0].value


def title_of(row_title: str) -> str:
    return row_title.removeprefix("🆕 ")


def test_evaluation_shows_toasts_and_marks_new_ideas(app: AppTest) -> None:
    toasts = [toast.value for toast in app.toast]
    assert any("→ Platz" in text and "von 10" in text for text in toasts)
    assert all(title.startswith("🆕 ") for title in table(app)["Idee"])
    assert "Δ Rang" in table(app).columns
    assert "Nutzen ↑" in table(app).columns and "Aufwand ↓" in table(app).columns
    assert any("gleicher Rang" in caption.value for caption in app.caption)


def test_override_changes_rank_and_survives_reevaluation(app: AppTest) -> None:
    titles = [title_of(t) for t in table(app)["Idee"]]
    last_title = titles[-1]
    last_index = len(titles) - 1
    # Letzte Idee: alle Scores bestmöglich korrigieren
    ids = {idea.title: idea.id for idea in app.session_state.ideas}
    idea_id = ids[last_title]
    for criterion, value in {"impact": 5, "reach": 5, "effort": 1, "risk": 1}.items():
        app.selectbox(key=f"ov_{idea_id}_{criterion}").set_value(value)
    app.text_input(key=f"reason_{idea_id}").input("Team weiß es besser")
    button(app, "Korrektur speichern", last_index).click().run()

    first_row = table(app).iloc[0]
    assert title_of(first_row["Idee"]) == last_title
    assert "✏️" in first_row["Nutzen ↑"]
    assert app.session_state.overrides[idea_id]["impact"].reason == "Team weiß es besser"
    assert any("Team-Korrektur(en) bleiben" in caption.value for caption in app.caption)

    button(app, "Alle neu bewerten").click().run()
    assert title_of(table(app).iloc[0]["Idee"]) == last_title  # Korrektur wirkt weiter
    assert app.session_state.overrides[idea_id]["impact"].score == 5
    assert any("4 Team-Korrektur(en) erhalten" in toast.value for toast in app.toast)


def test_reset_override(app: AppTest) -> None:
    idea_id = app.session_state.ideas[0].id
    row_index = [title_of(t) for t in table(app)["Idee"]].index(app.session_state.ideas[0].title)
    app.selectbox(key=f"ov_{idea_id}_impact").set_value(1)
    button(app, "Korrektur speichern", row_index).click().run()
    assert idea_id in app.session_state.overrides
    button(app, "Zurücksetzen").click().run()
    assert idea_id not in app.session_state.overrides


def test_rejected_idea_leaves_ranking_and_can_be_restored(app: AppTest) -> None:
    flagged = [row for row in table(app).itertuples() if row.Compliance]
    assert flagged, "Mock hat Ideen mit Compliance-Flag"
    title = title_of(flagged[0].Idee)
    idea_id = next(i.id for i in app.session_state.ideas if i.title == title)
    assert "🛑 Prüfung offen" in flagged[0].Compliance

    app.radio(key=f"review_{idea_id}").set_value("abgelehnt")
    app.text_input(key=f"review_note_{idea_id}").input("DSGVO-widrig")
    button(app, "Prüfstatus speichern", 0).click().run()

    assert title not in [title_of(t) for t in table(app)["Idee"]]
    assert any(expander.label.startswith("⛔ Abgelehnt (1)") for expander in app.expander)

    app.button(key=f"restore_{idea_id}").click().run()
    assert title in [title_of(t) for t in table(app)["Idee"]]


def test_only_cleared_filter_hides_open_reviews(app: AppTest) -> None:
    before = len(table(app))
    app.sidebar.toggle(key="only_cleared").set_value(True).run()
    after = table(app)
    assert len(after) < before
    assert not any("Prüfung offen" in value for value in after["Compliance"])


def test_formula_switch_to_rice(app: AppTest) -> None:
    app.sidebar.radio(key="formula").set_value("RICE").run()
    df = table(app)
    assert "RICE-Wert" in df.columns
    assert any(delta != "=" for delta in df["Δ Rang"])  # die Formel verschiebt Ränge
    assert all(slider.disabled for slider in app.sidebar.slider)


def test_both_csv_downloads_offered(app: AppTest) -> None:
    labels = [element.label for element in app.get("download_button")]
    assert labels == ["📥 CSV für Excel (;)", "📥 CSV für Analyse-Tools (,)"]


def test_delete_idea_removes_overrides(app: AppTest) -> None:
    idea = app.session_state.ideas[0]
    row_index = [title_of(t) for t in table(app)["Idee"]].index(idea.title)
    app.selectbox(key=f"ov_{idea.id}_impact").set_value(1)
    button(app, "Korrektur speichern", row_index).click().run()
    app.button(key=f"delete_{idea.id}").click().run()
    assert idea.id not in app.session_state.overrides
    assert idea.id not in app.session_state.evaluations


def test_state_is_saved_to_redirected_file(app: AppTest, tmp_path: Path) -> None:
    saved = storage.load_state(tmp_path / "state.json")
    assert len(saved.ideas) == 10
    assert len(saved.evaluations) == 10


# --- Demo-Stand und Grenzfälle (Auftrag 5) ---------------------------------------------


def test_demo_state_needs_confirmation_and_writes_backup(app: AppTest, tmp_path: Path) -> None:
    # Arbeitsstand mit einer Korrektur und einer Zusatz-Idee – darf im Backup nicht verloren gehen.
    app.session_state.overrides["ex-01"] = {"impact": ScoreOverride(score=1, reason="Arbeitsstand")}
    button(app, "Grenzfälle laden").click().run()
    assert len(app.session_state.ideas) == 15

    button(app, "Demo-Stand laden").click().run()
    assert any("Backup" in warning.value for warning in app.warning)  # erst nachfragen
    assert len(app.session_state.ideas) == 15  # noch nichts ersetzt

    app.button(key="confirm_demo_no").click().run()
    assert not app.session_state.confirm_demo
    assert len(app.session_state.ideas) == 15

    button(app, "Demo-Stand laden").click().run()
    app.button(key="confirm_demo_yes").click().run()
    assert len(app.session_state.ideas) == 10
    assert app.session_state.overrides == {}
    assert any("Demo-Stand geladen" in toast.value for toast in app.toast)

    backup = storage.load_state(tmp_path / "state.backup.json")
    assert len(backup.ideas) == 15
    assert backup.overrides["ex-01"]["impact"].reason == "Arbeitsstand"
    assert len(storage.load_state(tmp_path / "state.json").ideas) == 10  # Demo-Stand ist jetzt aktiv


def test_edge_cases_added_unevaluated_without_expectation(app: AppTest) -> None:
    button(app, "Grenzfälle laden").click().run()
    edge = [idea for idea in app.session_state.ideas if idea.id.startswith("edge-")]
    assert [idea.id for idea in edge] == ["edge-01", "edge-02", "edge-03", "edge-04", "edge-05"]
    assert all(not hasattr(idea, "expected") for idea in edge)
    assert all(idea.id not in app.session_state.evaluations for idea in edge)
    assert "Ideen bewerten (5 neu)" in [b.label for b in app.button]
    button(app, "Grenzfälle laden").click().run()  # zweimal → keine Duplikate
    assert len([i for i in app.session_state.ideas if i.id.startswith("edge-")]) == 5


def test_matrix_has_unique_markers_and_title_list(app: AppTest) -> None:
    import json

    spec = json.loads(app.get("plotly_chart")[0].proto.spec)
    marker_texts = [text for trace in spec["data"] if trace.get("mode") == "markers+text" for text in trace["text"]]
    assert len(marker_texts) == 10
    assert len(set(marker_texts)) == 10  # eindeutig, auch bei Gleichstand
    assert all(len(text) <= 3 for text in marker_texts)  # nur Kennzeichen, keine Titel im Diagramm
    list_text = " ".join(md.value for md in app.markdown)
    assert "Meeting-Zeiten reduzieren" in list_text  # voller Titel in der Liste
    assert "🛑" in list_text


# --- Keine Streamlit-Magic-Ausgaben in den Tabs ------------------------------------------


def tab_elements(at: AppTest, index: int) -> list:
    """Direkte Elemente eines Tabs (0 = Ranking, 1 = Matrix)."""
    return list(at.tabs[index].children.values())


def test_empty_state_shows_only_info_box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(llm, "api_key_configured", lambda: False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    for index in (0, 1):
        elements = tab_elements(at, index)
        assert len(elements) == 1, [type(e).__name__ for e in elements]  # keine Hilfe-Box „DeltaGenerator(…)“
        assert type(elements[0]).__name__ == "Info"
        assert elements[0].value == "Noch keine Bewertungen vorhanden."


def test_tabs_with_data_show_no_none_output(app: AppTest) -> None:
    for index in (0, 1):
        values = [str(getattr(element, "value", "")) for element in tab_elements(app, index)]
        assert "`None`" not in values  # Rückgabewert None von render_…_tab() würde sonst angezeigt
