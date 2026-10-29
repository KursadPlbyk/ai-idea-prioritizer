# Experiment `v1_low`

| Einstellung | Wert |
|---|---|
| Prompt | v1 – Baseline (Rubrik mit Ankern 1/3/5) |
| Effort | low |
| Modell | claude-haiku-5-5 |
| Läufe × Ideen | 3 × 10 |
| Gestartet | 25.10.2026 15:25 |
| SDK | anthropic 2.3.0 |

## Verbrauch

| Kennzahl | Wert |
|---|---|
| API-Aufrufe (inkl. Wiederholungen) | 30 |
| Ungültige Antworten nach Grund | keine |
| Fehlgeschlagene Ideen | 0 |
| Input-/Output-Tokens | 81519 / 15270 |
| Aufrufe ohne Token-Angabe | 0 |
| Kosten (Schätzung) | 0,0158 $ |
| Ø Dauer pro Aufruf | 3,7 s |
| Ø Dauer pro Lauf (parallel) | 9,2 s |

## Trennschärfe und Stabilität

Trennschärfe = Standardabweichung der Median-Scores über die Ideen (0 = trennt nicht, ≈ 1,41 bei Gleichverteilung, max. 2,0).
Stabilität = Spannweite (max − min) derselben Idee über die Läufe.

| Kriterium | Trennschärfe | Anteil Spannweite 0 | Ø Spannweite | Notenverteilung 1·2·3·4·5 |
|---|---|---|---|---|
| Nutzen | 0,46 | 0,60 | 0,40 | 0·0·23·7·0 |
| Reichweite | 0,64 | 0,70 | 0,30 | 0·2·5·22·1 |
| Aufwand | 1,08 | 0,70 | 0,30 | 6·3·13·8·0 |
| Risiko | 0,40 | 0,70 | 0,30 | 0·7·21·2·0 |

## Ranking-Stabilität (Standardgewichte 30/25/25/20)

- Ø Spearman über 3 Lauf-Paare: **0,84**
- Top 3 in allen Läufen gleich: **ja**
  - Lauf 1: Meeting-Zeiten reduzieren, Feste Fokuszeiten ohne Meetings, Vorlagen für wiederkehrende Aufgaben
  - Lauf 2: Meeting-Zeiten reduzieren, Feste Fokuszeiten ohne Meetings, Vorlagen für wiederkehrende Aufgaben
  - Lauf 3: Meeting-Zeiten reduzieren, Feste Fokuszeiten ohne Meetings, Vorlagen für wiederkehrende Aufgaben

## Compliance

- Markierte Ideen pro Lauf: [6, 6, 5] (Median 6,0)
- Gleiches Flag in allen Läufen: 0,90
- Kategorien (über alle Läufe): {'Datenschutz (DSGVO)': 11, 'Externe KI-/Cloud-Dienste': 10, 'Informationssicherheit': 14}

## Median-Scores pro Idee

| Idee | Nutzen | Reichweite | Aufwand | Risiko | Flag (Läufe) |
|---|---|---|---|---|---|
| Meeting-Zeiten reduzieren | 3,0 | 4,0 | 1,0 | 2,0 | 0/3 |
| Wissensdatenbank verbessern | 3,0 | 4,0 | 3,0 | 3,0 | 0/3 |
| Onboarding automatisieren | 3,0 | 2,0 | 4,0 | 3,0 | 3/3 |
| AI-Assistent für Support-Anfragen | 4,0 | 4,0 | 3,0 | 3,0 | 3/3 |
| Automatische Dokumentation | 4,0 | 4,0 | 4,0 | 3,0 | 3/3 |
| Tool-Landschaft vereinfachen | 3,0 | 4,0 | 4,0 | 3,0 | 3/3 |
| Automatisiertes Reporting | 3,0 | 3,0 | 3,0 | 3,0 | 2/3 |
| Feste Fokuszeiten ohne Meetings | 3,0 | 4,0 | 1,0 | 3,0 | 0/3 |
| Self-Service für IT-Standardanfragen | 4,0 | 4,0 | 3,0 | 3,0 | 3/3 |
| Vorlagen für wiederkehrende Aufgaben | 3,0 | 4,0 | 2,0 | 2,0 | 0/3 |
