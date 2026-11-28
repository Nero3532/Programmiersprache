---
name: sprache
description: Auftrag an das Team der Programmiersprache „Deutsch" (Projektchef sprache-chef; Firmen-Chef mit Modellwahl, Rollen-Nachbesetzung, Roadmap).
argument-hint: "[Auftrag]"
---
Übergib den Auftrag mit einem einzigen Agent-Aufruf im Vordergrund an `sprache-chef`:
- Auftrag: $ARGUMENTS · Projektordner = Repo-Wurzel · Fakten `team/PROJEKT.md`
- Dazu: relevante Entscheidungen aus diesem Gespräch, ≤ 5 Zeilen. Einfacher Auftrag: `effort: medium`, sonst Standard.
- Berichtslänge ≤ 6 Stichpunkte.

Der Chef führt `bedarf.ps1` aus, wählt Modell und Aufwand je Agent, holt fehlende Rollen über `firma-personal`,
pflegt `team/BOARD.md`, `team/MODELLE.md` und `ROADMAP.md`. Nichts veröffentlichen, kein Push ohne Nutzerauftrag.

Danach dem Nutzer kompakt auf Deutsch antworten (≤ 5 Stichpunkte). Rückfragen des Chefs dem Nutzer
stellen und die Antwort per SendMessage an den Chef geben.
