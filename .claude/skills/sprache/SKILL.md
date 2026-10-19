---
name: sprache
description: Gibt einen Auftrag an das Entwicklerteam der Programmiersprache „Deutsch". Der sprache-chef plant, verteilt an Architekt, Entwickler, Junior, QA und Release und wählt pro Aufgabe das günstigste passende Modell.
argument-hint: "[Auftrag]"
---
Übergib den Auftrag mit einem einzigen Agent-Aufruf im Vordergrund an `sprache-chef`:
- Auftrag: $ARGUMENTS
- Dazu: relevante Entscheidungen aus diesem Gespräch, ≤ 5 Zeilen.

Danach dem Nutzer kompakt auf Deutsch antworten (≤ 5 Stichpunkte). Rückfragen des Chefs dem Nutzer
stellen und die Antwort per SendMessage an den Chef geben.
