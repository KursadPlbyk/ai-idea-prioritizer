# Scoring model – Intelligent Idea Prioritizer

> **Core principle:** The AI provides the assessment, the team sets the values, the formula produces the result.

## 1. Criteria and rubric

Scale 1–5 for all criteria; every level has its own anchor (2 and 4 since prompt v2).
The rubric is part of the AI prompt word for word (`priorisierer/prompts.py`, default: v2), so that scores stay comparable across ideas and runs. The prompt is in German; the column "Prompt wording (German)" quotes it verbatim, and a test checks that every anchor text in that column appears in the prompt.

In addition, the prompt contains (since v2):
- **Scale instruction:** "Compare the idea with each of the five anchors and pick the one that fits best. 3 is not a default value for uncertainty – only give 3 if the idea really matches anchor 3." (German original: „Vergleiche die Idee mit jedem der fünf Anker und wähle den, der am besten passt. 3 ist kein Standardwert für Unsicherheit – vergib 3 nur, wenn die Idee wirklich dem Anker 3 entspricht.“)
- **Two calibration examples** (complete sample evaluations, deliberately not taken from the example ideas): low – "Modernize the color scheme of the internal presentation template" (impact 1, reach 2, effort 1, risk 1, no flag) – and high – "Introduce a central ticket system for all internal requests" (5 / 5 / 4 / 3, flag data protection). They only calibrate the scale and are not a template for wording.

### Impact (Nutzen) – How much does the idea improve the work of those affected? (higher = better)
| Score | Meaning | Prompt wording (German) |
|---|---|---|
| 1 | Barely noticeable: cosmetic improvement, saves a few minutes per month at most | Kaum spürbar: kosmetische Verbesserung, spart höchstens wenige Minuten pro Monat |
| 2 | Small but regular relief (approx. 15–30 min per person and week) | Kleine, aber regelmäßige Erleichterung (ca. 15–30 Min. pro Person und Woche) |
| 3 | Noticeable: regularly saves time (approx. 1–2 h per person and week) or removes a recurring annoyance | Spürbar: spart regelmäßig Zeit (ca. 1–2 h pro Person und Woche) oder beseitigt ein wiederkehrendes Ärgernis |
| 4 | Significant time savings (several hours per person and week) or noticeably better quality in an important process | Deutliche Zeitersparnis (mehrere Stunden pro Person und Woche) oder spürbar bessere Qualität in einem wichtigen Ablauf |
| 5 | Fundamental: changes core processes, large time savings or a leap in quality, resolves a critical bottleneck | Grundlegend: verändert zentrale Abläufe, große Zeitersparnis oder Qualitätssprung, löst einen kritischen Engpass |

### Reach (Reichweite) – How many benefit, and how often? (higher = better)
| Score | Meaning | Prompt wording (German) |
|---|---|---|
| 1 | Individual people or rare occasions (a few times a year) | Einzelne Personen oder seltene Anlässe (wenige Male pro Jahr) |
| 2 | A few people regularly or part of the team rarely | Wenige Personen regelmäßig oder ein Teil des Teams selten |
| 3 | Part of the team regularly or everyone occasionally | Ein Teil des Teams regelmäßig oder alle gelegentlich |
| 4 | Almost the whole team, several times a week | Fast das ganze Team, mehrmals pro Woche |
| 5 | The whole team (or more) daily | Das ganze Team (oder mehr) täglich |

### Effort (Aufwand) – Time, cost and resources until usable (higher = worse)
| Score | Meaning | Prompt wording (German) |
|---|---|---|
| 1 | A few days, one person, no cost, no new tools | Wenige Tage, eine Person, keine Kosten, keine neuen Tools |
| 2 | 1–2 weeks, one or two people, no or low cost | 1–2 Wochen, ein bis zwei Personen, keine oder geringe Kosten |
| 3 | Several weeks, several people involved, or a new tool / a new license | Einige Wochen, mehrere Beteiligte oder ein neues Tool / eine neue Lizenz |
| 4 | 1–3 months, several people involved, integration with existing systems | 1–3 Monate, mehrere Beteiligte, Anbindung an bestehende Systeme |
| 5 | Several months, dedicated project team, integration into several systems, significant cost | Mehrere Monate, eigenes Projektteam, Integration in mehrere Systeme, deutliche Kosten |

### Risk (Risiko) – Uncertainty of success: technology, acceptance, regulation, dependencies (higher = worse)
| Score | Meaning | Prompt wording (German) |
|---|---|---|
| 1 | Proven solution, clear path to implementation, no dependencies | Bewährte Lösung, klarer Umsetzungsweg, keine Abhängigkeiten |
| 2 | Minor open points, easily manageable | Kleine offene Punkte, gut beherrschbar |
| 3 | Some open questions: acceptance unclear or dependent on other teams/systems | Einige offene Fragen: Akzeptanz unklar oder abhängig von anderen Teams/Systemen |
| 4 | Several significant uncertainties or strong dependence on third parties | Mehrere wesentliche Unsicherheiten oder starke Abhängigkeit von Dritten |
| 5 | High uncertainty: untested technology, resistance likely or regulatory hurdles | Hohe Unsicherheit: unerprobte Technik, Widerstand wahrscheinlich oder regulatorische Hürden |

## 2. Compliance note (flag, NOT part of the score)

The AI flags ideas that require a review before implementation – **but only if the idea, in the form described, necessarily entails it.** Possible risks of individual conceivable implementation variants are no reason for a flag (since prompt v2; before that, the flag was set for more than half of the ideas). The category names are used in German in the app:
- **Datenschutz (DSGVO)** – data protection (GDPR): processing of personal data (employees or customers)
- **Mitbestimmung** – co-determination: if the solution makes the performance or behavior of individual employees visible or analyzable (works council)
- **Externe KI-/Cloud-Dienste** – external AI/cloud services: only if the idea explicitly uses an external AI or cloud service or this is unavoidable (sharing internal or customer data with third parties)
- **Informationssicherheit** – information security: access to sensitive systems or data

Output: flag yes/no, category(ies), a one-sentence justification. Notice in the UI: „Erste Einschätzung, keine Rechtsprüfung.“ (first assessment, not a legal review).
Why a flag instead of a score: compliance is not "more or less good" but a review task – it should be visible without distorting the ranking.

## 3. AI output per idea

Field names in the code are English; the user interface is German.

| Field | Content |
|---|---|
| `assumption` | one sentence on how the AI interpreted the (often keyword-style) idea |
| `impact`, `reach`, `effort`, `risk` | each `score` (1–5, integer) + `reasoning` (one sentence, specific to the idea) |
| `compliance` | `flag` (bool), `categories` (list), `note` (one sentence) |

Criteria mapping: Nutzen = `impact`, Reichweite = `reach`, Aufwand = `effort`, Risiko = `risk`.

The `assumption` field makes visible *what* was scored – vague ideas stand out, and the team can make the description more precise.

## 4. Prioritization

### Default: weighted sum (utility analysis)
Effort and risk are inverted so that "higher = better" applies everywhere: `s' = 6 − s`.

    Score = Σ (weight_i × s'_i) / Σ weight_i           → range 1–5
    Display = (Score − 1) / 4 × 100                     → 0–100 points

Default weights (adjustable via sliders in the UI):

| Impact | Reach | Effort | Risk |
|---|---|---|---|
| 30 % | 25 % | 25 % | 20 % |

### Optional: RICE variant (switch)
Same AI scores, different calculation rule:

    RICE = Reach × Impact × Confidence / Effort
    Confidence = (6 − Risk) / 5                         → risk 1 = 100 %, risk 5 = 20 %

Property: favors small, safe quick wins more strongly than the weighted sum.
Purpose in the demo: to show that the choice of formula is itself a value judgment. Selectable via a switch in the app; the **„Δ Rang“** (Δ rank) column shows how many places an idea gains (▲) or loses (▼) compared with the other formula. With RICE, the weight sliders are disabled.

**Rank on ties:** ideas with the same score share the place (1, 2, 2, 4).

## 5. Impact/effort matrix

- x-axis: effort (1–5)
- y-axis: value = (impact + reach) / 2
- Thresholds: value > 3 = high; effort ≥ 3 = high
- Rationale for the asymmetry: value is an average, and 3 is exactly the middle of the scale – only an above-average value counts as high. According to the rubric, effort 3 already means "several weeks, several people involved or a new tool" and is therefore no longer low effort. A quick win must thus be clearly useful *and* genuinely cheap.

| | Low effort | High effort |
|---|---|---|
| **High value** | 🟢 Quick Win | 🔵 Big Project (Großes Projekt) |
| **Low value** | ⚪ Fill-in (Lückenfüller) | 🔴 Time Sink (Zeitfresser) |

## 6. Stability (dealing with non-determinism)

1. Rubric with anchor points in the prompt
2. Temperature cannot be set for the model used (claude-haiku-5-5). Instead, stability comes from the rubric with anchor points, the order "justify first, then score" (`reasoning` before `score` in the response schema), storing the result and, optionally, multiple scoring (point 5)
3. Score once, store the result – changing the weights only triggers a recalculation, no new AI call
4. The team can manually override any score (marked with ✏️ in the table, see section 8)
5. Optional: multiple scoring (e.g. 3×), use the median, show high spread as "idea unclear"

## 7. Prompt version and decision (calibration experiment)

The default is **prompt v2 with `effort="low"`**. It is based on an experiment with 3 runs each over the 10 example ideas (metrics and raw data: `experiments/VERGLEICH.md`).

**Rationale:** v2 markedly improves discrimination on impact without loss of stability and halves the compliance flags. There is no reliable difference in quality between low and medium (2 of 10 ideas with 3 runs), but medium is measurably ~40 % slower per call – for the live demo, speed matters.

v1 (anchors 1/3/5 only) stays frozen and selectable via a parameter, so that the baseline remains reproducible. v2 bundles four changes (anchors 2/4, scale instruction, compliance rule, calibration examples); which of them contributes how much is open (possible next step: ablation). Every AI evaluation stores its prompt version and shows it in the app.

## 8. Team corrections (human-in-the-loop)

The team can override the score per idea and criterion, optionally with a short justification.
- **The AI evaluation stays stored unchanged**; corrections are kept separately alongside it (`overrides` in `state.json`). What stays visible: „KI 3 → Team 4“ (AI 3 → team 4).
- Calculations use the **effective evaluation** = AI evaluation with the team values inserted – for ranking, RICE, matrix and Δ rank.
- „Alle neu bewerten“ (re-evaluate all) only replaces the AI evaluation, **never** a team correction. If the AI then returns a different value, the correction remains in effect.
- A correction can be reset; the AI value applies again afterwards. Deleting an idea also deletes its corrections.

## 9. Compliance review status

The AI flag is a review task (section 2). The team closes it with a review status:

| Status | Meaning | Effect |
|---|---|---|
| **offen** (open, default) | not yet reviewed | clearly marked in the ranking („🛑 Prüfung offen“ – review open), can optionally be hidden with the filter „Nur freigegebene Ideen ranken“ (rank approved ideas only) |
| **geklärt** (cleared) | reviewed, no obstacle | normal in the ranking („✅ geklärt“) |
| **abgelehnt** (rejected) | idea will not be pursued | not in the ranking, but in the collapsed section „Abgelehnt“ (rejected) – with note, restorable |

Rules:
- Ideas without a flag need no status.
- If a flag is newly added after a re-evaluation → **open**.
- **cleared** only applies to the categories that were present at the time of the review. If a new category is added → **open** again.
- **rejected** is a team decision and stays in place even if the AI no longer sets the flag later.

The notice „Erste Einschätzung, keine Rechtsprüfung.“ (first assessment, not a legal review) remains in the user interface.
