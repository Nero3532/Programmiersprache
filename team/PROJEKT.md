# Deutsch – feste Projektfakten

Einzige Quelle für die Agenten `sprache-*` und firmenweite Rollen (`dev-audit`, `dev-qa`, `markt-*`, `vertrieb-*`, `marketing-*`). Lesen statt herleiten. Unbekanntes als `OFFEN:` markieren.

## Gemeinsam (alle Rollen)
- Projekt: Deutsch (`<Repo>`, Branch master) — Programmiersprache mit deutschen Schlüsselwörtern.
- Art: Baum-Interpreter in Python ≥ 3.10, nur Standardbibliothek; Version in `deutsch/__init__.py`.
- Ordner: `deutsch/lexer.py` (SCHLUESSELWOERTER) → `parser.py` → `ast_knoten.py` → `interpreter.py` (Auswertung + Stdlib); `umgebung.py` (Geltungsbereiche), `token_typen.py`, `main.py` (CLI/REPL), `deutsch/__main__.py`, `tests/test_*.py` (mehrere Dateien), `beispiele/*.deu`, `ROADMAP.md`, `CHANGELOG.md`, `README.md`.
- Prüfen: `py -m unittest discover -s tests` (~1510 Tests, ~80 s wegen Unterprozess-Tests; einzelne Datei: `py -m unittest tests.test_builtins`).
- Starten: `py -m deutsch <datei>` · `py -m deutsch -c "code"`. `py main.py` scheitert an der Shebang-Zeile; `python` ist nur ein Store-Alias.
- Python-Versionen: 3.12 `py -V:Astral/CPython3.12.13 -m unittest discover -s tests`; 3.13 nur `C:\Program Files\LibreOffice\program\python-core-3.13.*\bin\python.exe` (Ordnername wechselt mit LibreOffice-Updates, z. B. 3.13.17) mit `C:\Program Files\LibreOffice\program` im PATH, sonst DLL-Fehler.
- CI: GitHub Actions, Linux + Windows, Python 3.10–3.14. Remote erst nach Push prüfbar.
- Feste Regeln:
  - Fehlermeldungen und Fehlerarten deutsch (TypFehler, WertFehler, NamensFehler …); rohe Python-Fehler nie durchreichen; englische Namen bleiben in `fange` gültig.
  - Variablen nur mit `sei` deklarieren; Zuweisung ohne `sei` an unbekannten Namen = NamensFehler.
  - Keine Syntax neuer als 3.10, keine Abhängigkeiten.
  - Neue Stdlib-Namen mit Umlaut in beiden Schreibweisen (`laenge`/`länge`).
  - Neues Sprachmerkmal = Schlüsselwort (falls nötig) + AST-Knoten + Parser + Interpreter + Regressionstest + README + CHANGELOG `[Unreleased]`.
  - Version in `pyproject.toml` und `deutsch/__init__.py` gleich (`tests/test_version.py`).
  - `beispiele/*.deu` müssen weiter laufen. Syntaxentscheidungen mit mehreren Varianten → Rückfrage an den Nutzer.
- Sprache Code/Kommentare: Deutsch, kurze Kommentare zum Warum.

## sprache-chef
- Board: `team/BOARD.md`, Lernliste `team/MODELLE.md`, Ausbau `ROADMAP.md`. Nur der Chef schreibt dort.
- Modellwahl-Beispiele: Stdlib nach Vorlage → junior haiku · Sprachmerkmal quer → entwickler sonnet · Grammatik/Evaluator-Umbau → architekt opus (Entwurf) · Audit → `dev-audit`.

## sprache-architekt / sprache-entwickler / sprache-junior
- Kritisch: `parser.py`, `interpreter.py` (nie zwei Schreiber gleichzeitig), `lexer.py` (Schlüsselwörter), Thread-Stack/Strg+C in `main.py` (CPython-3.13-Fehler python/cpython#139622 – Lösung ohne Interpreter-Änderung).
- Junior: keine Grammatikänderung.

## sprache-qa
- Abnahme: volle Reihe + alle `beispiele/*.deu` mit `py -m deutsch <datei>`; bei Änderung an Strg+C/Threads zusätzlich 3.13.

## sprache-release
- Version steht in: `pyproject.toml`, `deutsch/__init__.py`. Auslieferung: Commit auf Branch; Push/Veröffentlichen nur auf Nutzerauftrag.
