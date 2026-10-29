# Experiment `v2_medium`

| Einstellung | Wert |
|---|---|
| Prompt | v2 – v1 + vier gebündelte Änderungen: Anker 2/4, Skalen-Anweisung, schärfere Compliance-Regel, zwei Kalibrierungsbeispiele |
| Effort | medium |
| Modell | claude-haiku-5-5 |
| Läufe × Ideen | 3 × 10 |
| Gestartet | 25.10.2026 15:26 |
| SDK | anthropic 2.3.0 |

## Verbrauch

| Kennzahl | Wert |
|---|---|
| API-Aufrufe (inkl. Wiederholungen) | 30 |
| Ungültige Antworten nach Grund | keine |
| Fehlgeschlagene Ideen | 0 |
| Input-/Output-Tokens | 122409 / 20617 |
| Aufrufe ohne Token-Angabe | 0 |
| Kosten (Schätzung) | 0,0225 $ |
| Ø Dauer pro Aufruf | 5,1 s |
| Ø Dauer pro Lauf (parallel) | 12,9 s |

## Trennschärfe und Stabilität

Trennschärfe = Standardabweichung der Median-Scores über die Ideen (0 = trennt nicht, ≈ 1,41 bei Gleichverteilung, max. 2,0).
Stabilität = Spannweite (max − min) derselben Idee über die Läufe.

| Kriterium | Trennschärfe | Anteil Spannweite 0 | Ø Spannweite | Notenverteilung 1·2·3·4·5 |
|---|---|---|---|---|
| Nutzen | 0,70 | 0,80 | 0,20 | 0·6·15·9·0 |
| Reichweite | 0,67 | 0,60 | 0,40 | 0·3·7·20·0 |
| Aufwand | 1,18 | 0,90 | 0,10 | 6·3·5·16·0 |
| Risiko | 0,54 | 0,90 | 0,10 | 0·3·20·7·0 |

## Ranking-Stabilität (Standardgewichte 30/25/25/20)

- Ø Spearman über 3 Lauf-Paare: **0,88**
- Top 3 in allen Läufen gleich: **nein**
  - Lauf 1: Feste Fokuszeiten ohne Meetings, Meeting-Zeiten reduzieren, Automatisiertes Reporting
  - Lauf 2: Feste Fokuszeiten ohne Meetings, Automatisiertes Reporting, Meeting-Zeiten reduzieren
  - Lauf 3: Feste Fokuszeiten ohne Meetings, Automatisiertes Reporting, Wissensdatenbank verbessern

## Compliance

- Markierte Ideen pro Lauf: [4, 3, 3] (Median 3,0)
- Gleiches Flag in allen Läufen: 0,90
- Kategorien (über alle Läufe): {'Datenschutz (DSGVO)': 7, 'Externe KI-/Cloud-Dienste': 1, 'Informationssicherheit': 7}

## Median-Scores pro Idee

| Idee | Nutzen | Reichweite | Aufwand | Risiko | Flag (Läufe) |
|---|---|---|---|---|---|
| Meeting-Zeiten reduzieren | 2,0 | 4,0 | 1,0 | 3,0 | 0/3 |
| Wissensdatenbank verbessern | 3,0 | 4,0 | 3,0 | 3,0 | 0/3 |
| Onboarding automatisieren | 3,0 | 2,0 | 4,0 | 3,0 | 3/3 |
| AI-Assistent für Support-Anfragen | 4,0 | 3,0 | 4,0 | 4,0 | 3/3 |
| Automatische Dokumentation | 4,0 | 4,0 | 4,0 | 3,0 | 1/3 |
| Tool-Landschaft vereinfachen | 3,0 | 4,0 | 4,0 | 4,0 | 0/3 |
| Automatisiertes Reporting | 4,0 | 4,0 | 3,0 | 3,0 | 0/3 |
| Feste Fokuszeiten ohne Meetings | 3,0 | 4,0 | 1,0 | 3,0 | 0/3 |
| Self-Service für IT-Standardanfragen | 3,0 | 3,0 | 4,0 | 3,0 | 3/3 |
| Vorlagen für wiederkehrende Aufgaben | 2,0 | 3,0 | 2,0 | 2,0 | 0/3 |
