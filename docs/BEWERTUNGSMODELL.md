# Bewertungsmodell – Intelligenter Ideen-Priorisierer

> **Kernprinzip:** Die KI liefert die Einschätzung, das Team die Werte, die Formel das Ergebnis.

## 1. Kriterien und Rubrik

Skala 1–5 für alle Kriterien, jede Stufe hat einen eigenen Anker (2 und 4 seit Prompt v2).
Die Rubrik ist wörtlich Teil des KI-Prompts (`priorisierer/prompts.py`, Standard: v2), damit Scores über Ideen und Durchläufe hinweg vergleichbar bleiben. Ein Test prüft, dass jeder Ankertext dieser Tabellen im Prompt steht.

Zusätzlich enthält der Prompt (seit v2):
- **Skalen-Anweisung:** „Vergleiche die Idee mit jedem der fünf Anker und wähle den, der am besten passt. 3 ist kein Standardwert für Unsicherheit – vergib 3 nur, wenn die Idee wirklich dem Anker 3 entspricht.“
- **Zwei Kalibrierungsbeispiele** (vollständige Musterbewertungen, bewusst nicht aus den Beispiel-Ideen): niedrig „Farbschema der internen Präsentationsvorlage modernisieren“ (Nutzen 1, Reichweite 2, Aufwand 1, Risiko 1, kein Flag) und hoch „Zentrales Ticketsystem für alle internen Anfragen einführen“ (5 / 5 / 4 / 3, Flag Datenschutz). Sie kalibrieren nur die Skala und sind keine Vorlage für Formulierungen.

### Nutzen – Wie stark verbessert die Idee die Arbeit der Betroffenen? (höher = besser)
| Score | Bedeutung |
|---|---|
| 1 | Kaum spürbar: kosmetische Verbesserung, spart höchstens wenige Minuten pro Monat |
| 2 | Kleine, aber regelmäßige Erleichterung (ca. 15–30 Min. pro Person und Woche) |
| 3 | Spürbar: spart regelmäßig Zeit (ca. 1–2 h pro Person und Woche) oder beseitigt ein wiederkehrendes Ärgernis |
| 4 | Deutliche Zeitersparnis (mehrere Stunden pro Person und Woche) oder spürbar bessere Qualität in einem wichtigen Ablauf |
| 5 | Grundlegend: verändert zentrale Abläufe, große Zeitersparnis oder Qualitätssprung, löst einen kritischen Engpass |

### Reichweite – Wie viele profitieren, und wie oft? (höher = besser)
| Score | Bedeutung |
|---|---|
| 1 | Einzelne Personen oder seltene Anlässe (wenige Male pro Jahr) |
| 2 | Wenige Personen regelmäßig oder ein Teil des Teams selten |
| 3 | Ein Teil des Teams regelmäßig oder alle gelegentlich |
| 4 | Fast das ganze Team, mehrmals pro Woche |
| 5 | Das ganze Team (oder mehr) täglich |

### Aufwand – Zeit, Kosten und Ressourcen bis zur Nutzbarkeit (höher = schlechter)
| Score | Bedeutung |
|---|---|
| 1 | Wenige Tage, eine Person, keine Kosten, keine neuen Tools |
| 2 | 1–2 Wochen, ein bis zwei Personen, keine oder geringe Kosten |
| 3 | Einige Wochen, mehrere Beteiligte oder ein neues Tool / eine neue Lizenz |
| 4 | 1–3 Monate, mehrere Beteiligte, Anbindung an bestehende Systeme |
| 5 | Mehrere Monate, eigenes Projektteam, Integration in mehrere Systeme, deutliche Kosten |

### Risiko – Unsicherheit des Erfolgs: Technik, Akzeptanz, Regulatorik, Abhängigkeiten (höher = schlechter)
| Score | Bedeutung |
|---|---|
| 1 | Bewährte Lösung, klarer Umsetzungsweg, keine Abhängigkeiten |
| 2 | Kleine offene Punkte, gut beherrschbar |
| 3 | Einige offene Fragen: Akzeptanz unklar oder abhängig von anderen Teams/Systemen |
| 4 | Mehrere wesentliche Unsicherheiten oder starke Abhängigkeit von Dritten |
| 5 | Hohe Unsicherheit: unerprobte Technik, Widerstand wahrscheinlich oder regulatorische Hürden |

## 2. Compliance-Hinweis (Flag, geht NICHT in den Score ein)

Die KI markiert Ideen, bei denen vor der Umsetzung eine Prüfung nötig ist – **aber nur, wenn die Idee in ihrer beschriebenen Form das zwingend mit sich bringt.** Mögliche Risiken einzelner denkbarer Umsetzungsvarianten sind kein Grund für ein Flag (seit Prompt v2; vorher war das Flag bei mehr als der Hälfte der Ideen gesetzt).
- **Datenschutz (DSGVO):** Verarbeitung personenbezogener Daten (Mitarbeitende oder Kunden)
- **Mitbestimmung:** wenn die Lösung Leistung oder Verhalten einzelner Mitarbeitender sichtbar oder auswertbar macht (Betriebsrat)
- **Externe KI-/Cloud-Dienste:** nur, wenn die Idee ausdrücklich einen externen KI- oder Cloud-Dienst nutzt oder das unvermeidbar ist (Weitergabe interner oder Kundendaten an Drittanbieter)
- **Informationssicherheit:** Zugriff auf sensible Systeme oder Daten

Ausgabe: Flag ja/nein, Kategorie(n), ein Satz Begründung. Hinweis in der UI: „Erste Einschätzung, keine Rechtsprüfung.“
Begründung für das Flag statt Score: Compliance ist kein „mehr oder weniger gut“, sondern ein Prüfauftrag – er soll sichtbar sein, ohne das Ranking zu verzerren.

## 3. KI-Ausgabe pro Idee

Feldnamen im Code sind englisch, die Oberfläche ist deutsch.

| Feld | Inhalt |
|---|---|
| `assumption` | ein Satz, wie die KI die (oft stichwortartige) Idee interpretiert hat |
| `impact`, `reach`, `effort`, `risk` | je `score` (1–5, ganzzahlig) + `reasoning` (ein Satz, konkret auf die Idee bezogen) |
| `compliance` | `flag` (bool), `categories` (Liste), `note` (ein Satz) |

Kriterien-Mapping: Nutzen = `impact`, Reichweite = `reach`, Aufwand = `effort`, Risiko = `risk`.

Das Feld `assumption` macht sichtbar, *was* bewertet wurde – vage Ideen fallen dadurch auf, und das Team kann die Beschreibung präzisieren.

## 4. Priorisierung

### Standard: Gewichtete Summe (Nutzwertanalyse)
Aufwand und Risiko werden umgedreht, damit überall gilt „höher = besser“: `s' = 6 − s`.

    Score = Σ (Gewicht_i × s'_i) / Σ Gewicht_i        → Bereich 1–5
    Anzeige = (Score − 1) / 4 × 100                     → 0–100 Punkte

Standard-Gewichte (im UI per Regler änderbar):

| Nutzen | Reichweite | Aufwand | Risiko |
|---|---|---|---|
| 30 % | 25 % | 25 % | 20 % |

### Optional: RICE-Variante (Umschalter)
Gleiche KI-Scores, andere Rechenregel:

    RICE = Reichweite × Nutzen × Confidence / Aufwand
    Confidence = (6 − Risiko) / 5                       → Risiko 1 = 100 %, Risiko 5 = 20 %

Eigenschaft: bevorzugt kleine, sichere Quick Wins stärker als die gewichtete Summe.
Zweck in der Demo: zeigen, dass die Wahl der Formel selbst eine Wertentscheidung ist. In der App per Umschalter wählbar; die Spalte **„Δ Rang“** zeigt, wie viele Plätze eine Idee gegenüber der jeweils anderen Formel gewinnt (▲) oder verliert (▼). Bei RICE sind die Gewichte-Regler deaktiviert.

**Rang bei Gleichstand:** Ideen mit gleichem Score teilen sich den Platz (1, 2, 2, 4).

## 5. Impact/Effort-Matrix

- x-Achse: Aufwand (1–5)
- y-Achse: Wert = (Nutzen + Reichweite) / 2
- Grenzen: Wert > 3 = hoch; Aufwand ≥ 3 = hoch
- Begründung der Asymmetrie: Wert ist ein Mittelwert, 3 ist genau die Skalenmitte – erst ein überdurchschnittlicher Wert gilt als hoch. Aufwand 3 bedeutet laut Rubrik bereits „einige Wochen, mehrere Beteiligte oder neues Tool“ und ist damit kein niedriger Aufwand mehr. Ein Quick Win muss also klar nützlich *und* wirklich günstig sein.

| | Aufwand niedrig | Aufwand hoch |
|---|---|---|
| **Wert hoch** | 🟢 Quick Win | 🔵 Großes Projekt |
| **Wert niedrig** | ⚪ Lückenfüller | 🔴 Zeitfresser |

## 6. Stabilität (Umgang mit Nicht-Determinismus)

1. Rubrik mit Ankerpunkten im Prompt
2. Temperatur ist beim verwendeten Modell (claude-haiku-5-5) nicht einstellbar. Stabilität entsteht stattdessen über die Rubrik mit Ankerpunkten, die Reihenfolge „erst begründen, dann bewerten“ (`reasoning` vor `score` im Antwortschema), die Speicherung des Ergebnisses und optional Mehrfachbewertung (Punkt 5)
3. Einmal bewerten, Ergebnis speichern – Gewichte ändern löst nur Neuberechnung aus, keinen neuen KI-Aufruf
4. Team kann jeden Score manuell überschreiben (in der Tabelle mit ✏️ markiert, siehe Abschnitt 8)
5. Optional: Mehrfachbewertung (z. B. 3×), Median verwenden, hohe Streuung als „Idee unklar“ anzeigen

## 7. Prompt-Version und Entscheidung (Auftrag 3)

Standard ist **Prompt v2 mit `effort="low"`**. Grundlage ist ein Experiment mit je 3 Läufen über die 10 Beispiel-Ideen (Kennzahlen und Rohdaten: `experiments/VERGLEICH.md`).

**Begründung:** v2 verbessert die Trennschärfe beim Nutzen deutlich ohne Stabilitätsverlust und halbiert die Compliance-Flags. Zwischen low und medium gibt es keinen belastbaren Qualitätsunterschied (2 von 10 Ideen bei 3 Läufen), medium ist aber messbar ~40 % langsamer pro Aufruf – für die Live-Demo zählt Geschwindigkeit.

v1 (nur Anker 1/3/5) bleibt eingefroren und per Parameter auswählbar, damit die Baseline reproduzierbar bleibt. v2 bündelt vier Änderungen (Anker 2/4, Skalen-Anweisung, Compliance-Regel, Kalibrierungsbeispiele); welche davon wie viel beiträgt, ist offen (möglicher nächster Schritt: Ablation). Jede KI-Bewertung speichert ihre Prompt-Version und zeigt sie in der App an.

## 8. Team-Korrekturen (Human-in-the-Loop)

Das Team kann pro Idee und Kriterium den Score überschreiben, optional mit kurzer Begründung.
- **Die KI-Bewertung bleibt unverändert gespeichert**; Korrekturen liegen getrennt daneben (`overrides` in `state.json`). Sichtbar bleibt: „KI 3 → Team 4“.
- Gerechnet wird mit der **wirksamen Bewertung** = KI-Bewertung mit eingesetzten Team-Werten – für Ranking, RICE, Matrix und Δ Rang.
- „Alle neu bewerten“ ersetzt nur die KI-Bewertung, **nie** eine Team-Korrektur. Liefert die KI danach einen anderen Wert, bleibt die Korrektur wirksam.
- Eine Korrektur lässt sich zurücksetzen; danach gilt wieder der KI-Wert. Löschen einer Idee löscht auch ihre Korrekturen.

## 9. Compliance-Prüfstatus

Das KI-Flag ist ein Prüfauftrag (Abschnitt 2). Das Team schließt ihn mit einem Prüfstatus ab:

| Status | Bedeutung | Wirkung |
|---|---|---|
| **offen** (Standard) | noch nicht geprüft | im Ranking deutlich markiert („🛑 Prüfung offen“), optional per Filter „Nur freigegebene Ideen ranken“ ausblendbar |
| **geklärt** | Prüfung erfolgt, kein Hindernis | normal im Ranking („✅ geklärt“) |
| **abgelehnt** | Idee wird nicht verfolgt | nicht im Ranking, sondern im eingeklappten Bereich „Abgelehnt“ (mit Notiz, wiederherstellbar) |

Regeln:
- Ideen ohne Flag brauchen keinen Status.
- Kommt nach einer Neubewertung ein Flag neu hinzu → **offen**.
- **geklärt** gilt nur für die Kategorien, die bei der Prüfung vorlagen. Kommt eine neue Kategorie hinzu → wieder **offen**.
- **abgelehnt** ist eine Team-Entscheidung und bleibt bestehen, auch wenn die KI das Flag später nicht mehr setzt.

Der Hinweis „Erste Einschätzung, keine Rechtsprüfung.“ bleibt in der Oberfläche stehen.
