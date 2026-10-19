# Board

## In Arbeit

## Erledigt
- [x] 2026-10-19 Bestandsaufnahme „Was fehlt?" — Sprachkern (sonnet), Stdlib (haiku), Werkzeuge (haiku) → ROADMAP.md (10× P1, 12× P2, 17× P3)
- [x] 2026-10-19 P1-Fehler → 2.7.1, 331 Tests grün (3.14 + 3.12), alle Beispiele grün
  - Runde 1a main.py (sonnet): Ausführung in Thread mit großem Stack, Strg+C sauber, REPL-Klammerzählung; Nacharbeit (haiku): Fehleranzeige für `lade`-Dateien, Stack 128 MB, BANNER-Breite
  - Runde 1b lexer/parser (sonnet): `nicht`-Vorrang, `"""`-Zeilen, Klassenkörper; `x == nicht y` ist jetzt SyntaxError (wie Python)
  - Runde 1c interpreter/umgebung (sonnet): Schleifensignale, Typ-Hinweis bei Neuzuweisung, Zuweisung ohne `sei`
  - Runde 2 `lade` (sonnet): relative Pfade, deutsche Meldung, `neu a.b.K()`, Dateiname in Fehlern
  - Runde 3 Fehlertexte (haiku): 8 Stellen + JSON/Datei-Funktionen, robuste Fehler-Neuerzeugung
  - QA (haiku): bestanden, 3.10-Syntax statisch geprüft; Release (haiku): CHANGELOG, README, Version
  - Neue Funde → ROADMAP P2: Interpolations-Zeilennummer, Python-Klassennamen im Fehlerkopf, Parameter-Typ-Hinweise, Module-Rest, BANNER-Version

## Entscheidungen
- 2026-10-19 Team als Projekt-Agenten in `.claude/agents/sprache-*.md`, Einstieg über `/sprache`.
- 2026-10-19 Nutzer: `nicht` bindet wie in Python schwächer als Vergleiche (`nicht a == b` = `nicht (a == b)`).
- 2026-10-19 Nutzer: Zuweisung an nicht deklarierten Namen → NameError mit „meintest du …?" und Hinweis auf `sei`.
- 2026-10-19 Nutzer: P1 als 2.7.1 veröffentlichen, Commit auf dem Branch, kein Push.
- 2026-10-19 Thread-Stack 128 MB statt 255 MB: Windows setzt den Stack voll als Commit-Speicher an; reicht für ~5900 Aufrufe.
- 2026-10-19 Beispiele starten mit `uv run --no-project python main.py <datei>`; `py main.py` scheitert hier an der Shebang-Zeile.
