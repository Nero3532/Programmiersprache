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
- [x] 2026-10-20 P2 → 2.8.0, 1168 Tests grün (3.14 + 3.12), Commit je Runde
  - P2 Runde 1a: Ausdrücke — Bit-Ops + Literale, `??`, mehrzeilige Aufrufe, Interpolations-Zeile (sonnet) → 95 Tests; Runde 1 committet (d601262, 567 Tests)
  - Nebenbei (haiku): REPL zählt `(`/`[` mit → 8 Tests; Lücke: Interpolation mit eigenen `"` im REPL-Scanner (ROADMAP)
  - P2 Runde 1b: CLI — `--version`, `--hilfe`, `-c`, `--pruefen`, REPL `hilfe`, BANNER, `py -m deutsch` (haiku; main.py, deutsch/__main__.py) → 26 Tests; Docstring main.py nennt noch „Deutsch 2.0" (Release)
  - P2 Runde 1c: CI — Windows + 3.14, CLI-Lauf, pip-Check, Versionsgleichheit (haiku; .github, tests/test_version.py) → lokal grün, CI remote erst nach Push prüfbar
  - P2 Runde 1d: Tests für ungetestete Builtins (haiku; tests/test_builtins.py) → 114 Tests grün; Funde für Runde 4: `runde` mit negativen Stellen, englische Texte bei `abs("x")`, `runde(nichts)`, `logarithmus(8, 1)`, `exponential(1000)`, `"abc".ersetze("a")`; `runde("3.7")` vs. `runde("3.7", 1)` uneinheitlich; `runde(2.5)` → 2 (Banker's Rounding, ❓)
  - P2 Runde 2: Lambda-Kurzform + abbilden/filtere/reduziere/Schlüsselfunktion (sonnet) → 135 Tests, committet (7d32436, 710 Tests); offen: Listen-Methoden max/min, Wörterbücher als Sammlung
  - Doku Runden 1–2 parallel zu Runde 3 (haiku; README, CHANGELOG [Unreleased]) → committet
  - P2 Runde 3: Spread, `**kwargs`, Destrukturierung bei Zuweisung, Rest, Kettenzuweisung (sonnet) → nach Sitzungsabbruch fortgesetzt, 146 Tests, committet (8bca1f5, 856 Tests); offen: `sei [PI, x] = …` prüft Konstanten nicht
  - Doku Runde 3 parallel zu Runde 4 (haiku) → committet
  - P2 Runde 4: Stdlib Dateien/Pfade/Text/Listen/Mathe (haiku) → 128 Tests, committet (9bf68c7, 984 Tests); Chef-Entscheidung: `ordnername` liefert Ordnerpfad wie dirname
  - Doku Runde 4 parallel zu Runde 5a (haiku) → committet
  - P2 Runde 5a: deutsche Fehlerarten + Fehler-Neuerzeugung (sonnet) → 50 Tests, committet (8a2c8f7, 1034 Tests); `werfe WertFehler(…)` → ROADMAP P3
  - Doku Runde 5a parallel zu 5b (haiku) → committet
  - P2 Runde 5b: Module-Rest + Parameter-Typ-Hinweise (sonnet) → 74 Tests, committet (87bd7a6, 1108 Tests); neue Funde → ROADMAP P2/P3
  - Release 2.8.0 vorbereitet (haiku): Version, CHANGELOG aufgeräumt, README korrigiert (nicht committet)
  - QA (haiku): NICHT bestanden — mehrzeilige `sei`/`für`-Muster, englische Token-Namen in Syntaxfehlern, `f(a, a)`, Parameter nach `*rest`, `datum_formatieren`
  - Nachbesserung QA-Funde (sonnet) → 60 Tests; Chef-Nachprüfung: 1168 Tests grün (3.14 + 3.12), alle 5 Funde behoben, kein Tempoverlust (Benchmark 1,05 s → 1,11 s); Suite dauert wegen Unterprozess-Tests ~80 s

## Entscheidungen
- 2026-10-19 Team als Projekt-Agenten in `.claude/agents/sprache-*.md`, Einstieg über `/sprache`.
- 2026-10-19 Nutzer: `nicht` bindet wie in Python schwächer als Vergleiche (`nicht a == b` = `nicht (a == b)`).
- 2026-10-19 Nutzer: Zuweisung an nicht deklarierten Namen → NameError mit „meintest du …?" und Hinweis auf `sei`.
- 2026-10-19 Nutzer: P1 als 2.7.1 veröffentlichen, Commit auf dem Branch, kein Push.
- 2026-10-19 Nutzer: Fehlerarten deutsch (TypFehler, WertFehler, NamensFehler, IndexFehler, SchluesselFehler, AttributFehler, DateiFehler, SyntaxFehler, LaufzeitFehler, RekursionsFehler, ZusicherungsFehler, ImportFehler, EingabeEndeFehler, DivisionDurchNullFehler); englische Namen bleiben in `fange` gültig.
- 2026-10-19 Nutzer: Lambda-Kurzform `funktion(x) -> ausdruck`.
- 2026-10-19 Nutzer: Bit-Operatoren als Symbole `& | ^ ~ << >>` + Verbund-Zuweisungen.
- 2026-10-19 Nutzer: P2 mit einem Commit je Runde, am Ende 2.8.0, kein Push.
- 2026-10-19 Nutzer: `runde` rundet kaufmännisch (ab ,5 vom Nullpunkt weg, per `decimal` auf der Dezimaldarstellung).
- 2026-10-19 Neue Stdlib-Namen mit Umlaut immer in beiden Schreibweisen (wie `laenge`/`länge`).
- 2026-10-19 Thread-Stack 128 MB statt 255 MB: Windows setzt den Stack voll als Commit-Speicher an; reicht für ~5900 Aufrufe.
- 2026-10-19 Beispiele starten mit `uv run --no-project python main.py <datei>`; `py main.py` scheitert hier an der Shebang-Zeile.
