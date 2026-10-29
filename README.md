# 💡 Intelligent Idea Prioritizer

A prototype that has an AI score a team's improvement ideas against fixed criteria and computes a transparent prioritization from those scores.

> The app's user interface and the AI's assessments are in German; UI labels are quoted below in their original German wording.

![Ranking](docs/img/ranking.png)

## Core principle

> **The AI provides the assessment, the team sets the values, the formula produces the result.**

- **AI:** assigns a score (1–5) with a one-sentence justification per idea and criterion – nothing else.
- **Team:** decides how much each criterion matters (weights), can correct any score and decides on compliance notes.
- **Formula:** computes the ranking deterministically from that.

Why this way? An AI that picks "the best idea" directly is neither explainable nor reproducible – and weighting is a value judgment that belongs to the team. Changing the weights therefore triggers **only a recalculation**, never a new AI call.

## Features

- Capture ideas (title + optional description), load example ideas and edge cases
- Scoring via **Claude (Anthropic API)** or a **mock evaluator** (offline, deterministic) – switchable
- **Ranking** by weighted sum (weights via sliders) or **RICE**; the **"Δ Rang"** (Δ rank) column shows how much the choice of formula shifts the result
- **Impact/effort matrix** (Quick Win / Big Project / Fill-in / Time Sink)
- **Team corrections** of individual scores – the AI score stays visible ("KI 3 → Team 4 ✏️"), and **"Alle neu bewerten"** (re-evaluate all) never overwrites corrections
- **Compliance flag** (data protection, co-determination, external AI services, information security) with a **review status** open / cleared / rejected
- Provenance of every evaluation (model, prompt version, timestamp), notice when sources are mixed
- CSV export (one variant for Excel, one for analysis tools)
- **Demo state:** example ideas scored by the real AI in advance – the demo shows AI justifications even without a network connection

## Scoring model in brief

| Criterion | Question | Direction |
|---|---|---|
| Impact (Nutzen) | How much does the idea improve people's work? | ↑ higher is better |
| Reach (Reichweite) | How many benefit, and how often? | ↑ |
| Effort (Aufwand) | Time, cost and resources until usable | ↓ lower is better |
| Risk (Risiko) | Uncertainty: technology, acceptance, regulation | ↓ |

- Every level 1–5 has a fixed **anchor** in the rubric, which is quoted verbatim in the prompt (kept in sync by a test).
- **Compliance** is a **flag, not a score**: a review task that should be visible without distorting the ranking.
- **Weighted sum** (default 30/25/25/20, effort and risk inverted) → 0–100 points. **RICE** = reach × impact × confidence / effort – favors small, safe ideas.
- **Matrix:** value = (impact + reach) / 2 against effort; value > 3 = high, effort ≥ 3 = high.

Details, rationale and decisions: [`docs/BEWERTUNGSMODELL.md`](docs/BEWERTUNGSMODELL.md)

![Matrix](docs/img/matrix.png)

## Architecture

```
                    app.py  (Streamlit – presentation and interaction only)
                       │
     ┌─────────────────┼───────────────────────┬──────────────────────┐
     ▼                 ▼                       ▼                      ▼
 Evaluator        ranking_view            team.py                storage.py
 interface        (ranking, filter,       (corrections,          (state.json,
 (base.py)         Δ rank, CSV)            review status)         demo state)
   │      │            │
   ▼      ▼            ▼
 Mock   LLM ──► Anthropic API     scoring.py (formulas)   matrix.py (coordinates)
        (prompts.py: rubric, prompt v1/v2, <idee> tags against prompt injection)
```

- The `priorisierer/` package does **not import Streamlit**; scoring, corrections, ranking and matrix are pure functions.
- UI and scoring only know the **evaluator interface** – mock and LLM are interchangeable.
- The LLM response is enforced and validated against a Pydantic schema via **structured outputs**; an invalid response gets one retry, after which the idea stays unscored rather than being scored wrongly.

### Code flow

Two paths through the code: **scoring** calls the AI and stores the result; **displaying** only recalculates on every interaction (sliders, formula, correction) – without an AI call.

```mermaid
flowchart TD
    U(["User: add idea,<br/>„Ideen bewerten“"]) --> E["app.evaluate()"]
    E --> G{"get_evaluator()<br/>switch"}
    G -->|Mock| M["MockEvaluator<br/>fixed / hash-based scores"]
    G -->|"KI (Claude)"| L["LLMEvaluator<br/>up to 5 ideas in parallel"]
    L --> P["prompts.py<br/>system prompt v2 + idea in idee tags"]
    P --> API[("Anthropic API<br/>messages.parse")]
    API -->|"API error: key, network, limit"| F
    API --> V{"Valid response?<br/>Pydantic schema, stop_reason"}
    V -->|no| R{"already retried?"}
    R -->|no| API
    R -->|yes| F["EvaluationFailure<br/>idea stays unscored"]
    V -->|yes| EV["Evaluation<br/>+ source, model, prompt version"]
    M --> EV
    EV --> S[("storage.py → state.json<br/>AI evaluations · team corrections · review status")]

    W(["User: weights, formula,<br/>correction, review status, filter"]) --> B["ranking_view.build_ranking()"]
    S --> B
    B --> T["team.py<br/>review_status() → rejected / open / cleared<br/>apply_overrides() → effective evaluation"]
    T --> SC["scoring.py<br/>weighted sum or RICE,<br/>rank, Δ rank, quadrant"]
    SC --> VIEW["RankingView"]
    VIEW --> TAB["📊 Ranking table<br/>+ details"]
    VIEW --> MX["🗺️ Matrix<br/>matrix.py: coordinates + offset"]
    VIEW --> CSV["📥 CSV export"]
```

```
app.py                     user interface
priorisierer/
  models.py                Pydantic models (idea, evaluation, correction, review status, AppState)
  prompts.py               system prompts v1 (frozen) and v2 (default)
  scoring.py               weighted sum, RICE, quadrant, ranking, Δ rank
  team.py                  team corrections and review status
  ranking_view.py          ranking view and CSV export
  matrix.py                matrix coordinates and labels
  storage.py               JSON storage
  analysis.py              metrics for calibration experiments
  experiments.py           running and reporting experiments
  edge_cases.py            edge-case checks
  evaluators/              base.py (interface), mock.py, llm.py
scripts/                   smoke test, calibration, comparison, edge cases, demo state
data/                      example ideas, edge cases, demo state (state.json stays local)
experiments/               raw data and evaluations of the measurements
tests/                     pytest (incl. an app run with Streamlit AppTest)
docs/                      scoring model, the app's system prompts (docs/prompts/Systemprompts/)
```

## Quality of the AI scoring – measured, not guessed

The first real evaluations matched the schema but were poorly calibrated (almost everything got impact 3, and the compliance flag was set for more than half of the ideas). Hence: **measure → change → measure again.** Two metrics are always reported together: **discrimination** (do different ideas get different scores?) and **stability** (does the same idea get the same scores across several runs?).

3 runs × 10 example ideas each with `claude-haiku-5-5` ([`experiments/VERGLEICH.md`](experiments/VERGLEICH.md)):

![Calibration: v1 compared with v2](docs/img/kalibrierung.png)

| | v1 / low | **v2 / low** (default) | v2 / medium |
|---|---|---|---|
| Impact scores 1·2·3·4·5 (30 evaluations) | 0·0·23·7·0 | 0·5·13·12·0 | 0·6·15·9·0 |
| Impact discrimination (σ of the medians) | 0.46 | 0.78 | 0.70 |
| Impact stability (share with the same score in all runs) | 0.60 | 0.60 | 0.80 |
| Ranking stability (mean Spearman) | 0.84 | 0.76 | 0.88 |
| Flagged ideas per run (median) | 6 | 3 | 3 |
| Mean duration per call | 3.7 s | 3.6 s | 5.1 s |
| Cost for 30 calls | $0.0158 | $0.0192 | $0.0225 |

- **v2** (anchors for 2 and 4 as well, scale instruction, stricter compliance rule, two calibration examples) discriminates much more sharply on impact without losing stability, and halves the compliance flags.
- **low instead of medium:** no reliable difference in quality, but ~40 % faster – decisive for a live demo.

**Edge-case test** (5 ideas with an obvious expected outcome × 3 runs, v2/low – [`experiments/GRENZFAELLE.md`](experiments/GRENZFAELLE.md)): **15 of 15 expectations met.** The model uses the extremes (impact 1 and 5, effort 1 and 5, risk 5), sets "co-determination" for employee tracking and fends off a prompt-injection attempt ("give 5 everywhere") in all three runs.

![Compliance flags and edge-case test](docs/img/grenzfaelle.png)

**Limits of the measurement:** only 3 runs per configuration – small differences (e.g. Spearman 0.76 vs. 0.88) may be chance. v2 tests four changes **bundled together**; which one contributes how much is open. The injection test is a single, simple attack – no proof of robustness.

## How I developed with AI

- **Tools:** Claude (chat) as a sparring partner for the concept and the scoring model; **Claude Code** in VS Code for the implementation.
- **Way of working:** one written brief per step with fixed project rules. Claude Code first presents a plan with an explanation of the concept and waits for my approval; then tests, a summary and a suggested commit message.
- **Control:** every decision, correction and finding of my own was recorded in a development log – what came from the AI, what I corrected and what I decided myself.
- **Understanding, not just generating:** every file, class and function comes with an explanation of the concept, the rationale and the alternatives that were rejected.

## Setup & start

Requirement: Python 3.14 (3.13 works as well).

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # enter ANTHROPIC_API_KEY – optional
streamlit run app.py
```

- **Without an API key** the app runs with the mock evaluator; the AI switch is then disabled.
- **Demo without network:** tab **"Ideen verwalten"** (manage ideas) → **"Demo-Stand laden"** (load demo state) – real AI evaluations of the 10 example ideas (the previous state is backed up to `data/state.backup.json`).
- **Tests:** `pytest` (no API calls; the app run uses the mock and temporary files).

## Known limitations & next steps

- **Ablation of the prompt changes:** leave out each of the four v2 changes individually and measure – which one contributes how much?
- **More runs:** more reliable statements about stability and about low vs. medium.
- **Severity for the compliance flag:** currently only yes/no – a clear GDPR violation and a "please check briefly" look the same.
- **Multi-user voting:** corrections and review decisions per person, making consensus and disagreement visible.
- **Approved model in a corporate setting:** ideas may contain internal information – in production only via a model or platform approved by the company.
- **Next.js instead of Streamlit** for a real team tool (login, concurrent use, own backend); Streamlit was the fastest route for the prototype.
- Storage as a single JSON file – multiple concurrent users would need a database.
