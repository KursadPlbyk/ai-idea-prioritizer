"""Prüft den committeten Demo-Stand (data/demo_state.json) – die Präsentation hängt davon ab."""

from priorisierer.storage import DEMO_STATE_FILE, load_example_ideas, load_state


def test_demo_state_is_complete_llm_v2_without_team_input() -> None:
    state = load_state(DEMO_STATE_FILE)
    example_ids = [idea.id for idea in load_example_ideas()]

    assert [idea.id for idea in state.ideas] == example_ids
    assert sorted(e.idea_id for e in state.evaluations) == sorted(example_ids)
    assert all(e.source == "llm" and e.prompt_version == "v2" for e in state.evaluations)
    assert all(e.model and e.evaluated_at for e in state.evaluations)
    assert state.overrides == {}
    assert state.compliance_reviews == {}
