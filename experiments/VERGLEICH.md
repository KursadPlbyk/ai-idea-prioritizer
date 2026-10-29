# Vergleich der Kalibrierungs-Experimente

| Kennzahl | `v1_low` | `v2_low` | `v2_medium` |
|---|---|---|---|
| Prompt / Effort | v1 / low | v2 / low | v2 / medium |
| Läufe × Ideen | 3 × 10 | 3 × 10 | 3 × 10 |
| **Trennschärfe** (σ der Mediane) |  |  |  |
|   Nutzen | 0,46 | 0,78 | 0,70 |
|   Reichweite | 0,64 | 0,66 | 0,67 |
|   Aufwand | 1,08 | 1,18 | 1,18 |
|   Risiko | 0,40 | 0,60 | 0,54 |
| **Stabilität** (Anteil Spannweite 0 / Ø Spannweite) |  |  |  |
|   Nutzen | 0,60 / 0,40 | 0,60 / 0,40 | 0,80 / 0,20 |
|   Reichweite | 0,70 / 0,30 | 0,50 / 0,50 | 0,60 / 0,40 |
|   Aufwand | 0,70 / 0,30 | 0,90 / 0,10 | 0,90 / 0,10 |
|   Risiko | 0,70 / 0,30 | 0,70 / 0,30 | 0,90 / 0,10 |
| **Notenverteilung** 1·2·3·4·5 |  |  |  |
|   Nutzen | 0·0·23·7·0 | 0·5·13·12·0 | 0·6·15·9·0 |
|   Reichweite | 0·2·5·22·1 | 0·3·6·20·1 | 0·3·7·20·0 |
|   Aufwand | 6·3·13·8·0 | 6·3·5·16·0 | 6·3·5·16·0 |
|   Risiko | 0·7·21·2·0 | 0·5·17·8·0 | 0·3·20·7·0 |
| **Ranking**: Ø Spearman | 0,84 | 0,76 | 0,88 |
| **Ranking**: Top 3 in allen Läufen gleich | ja | nein | nein |
| **Compliance**: markiert pro Lauf (Median) | [6, 6, 5] (6,0) | [3, 4, 3] (3,0) | [4, 3, 3] (3,0) |
| **Compliance**: gleiches Flag in allen Läufen | 0,90 | 0,90 | 0,90 |
| **Verbrauch**: API-Aufrufe | 30 | 30 | 30 |
| **Verbrauch**: ungültige Antworten | keine | keine | keine |
| **Verbrauch**: Input-/Output-Tokens | 81519 / 15270 | 122409 / 13820 | 122409 / 20617 |
| **Verbrauch**: Kosten (Schätzung) | 0,0158 $ | 0,0192 $ | 0,0225 $ |
| **Verbrauch**: Ø Dauer pro Aufruf | 3,7 s | 3,6 s | 5,1 s |

## Hinweise zur Aussagekraft

- **v1:** Baseline (Rubrik mit Ankern 1/3/5)
- **v2:** v1 + vier gebündelte Änderungen: Anker 2/4, Skalen-Anweisung, schärfere Compliance-Regel, zwei Kalibrierungsbeispiele
- **v2 testet vier Änderungen gebündelt** (Anker 2/4, Skalen-Anweisung, Compliance-Regel, Kalibrierungsbeispiele). Ein Unterschied zu v1 lässt sich daher **keiner einzelnen Änderung** zuordnen.
- Möglicher nächster Schritt: **Ablation** – jede Änderung einzeln weglassen (v2 ohne Beispiele, v2 ohne Anker 2/4, …) und erneut messen, um den Beitrag jeder Änderung zu sehen.
- Kleine Stichprobe (wenige Läufe × 10 Ideen): kleine Unterschiede, z. B. Spearman 0,90 gegenüber 0,93, können Zufall sein.
- Mehr Streuung allein ist kein Erfolg – Trennschärfe immer zusammen mit Stabilität lesen.
