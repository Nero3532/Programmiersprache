# MODELLE – Lernliste (neueste oben)

Der `sprache-chef` liest das (und `~/.claude/team/FIRMENWISSEN.md`) vor jeder Vergabe und ergänzt 1 Zeile,
wenn eskaliert wurde oder ein günstigeres Modell gereicht hat.

Format: Datum · Aufgabenart · Rolle Modell/effort · Ergebnis (ok / eskaliert → Modell) · Lehre

2026-11-14 · Anbindung · Lehren aus P1/P2 (2.7.1–2.8.0) übernommen · ok · siehe Zeilen darunter
2026-10-20 · Strg+C unter Python 3.13 · architekt opus/high · ok nach 2 Fehlversuchen (sonnet) · Ursache python/cpython#139622; opus erst nach 2 Fehlversuchen, mit Fehlerbefund im Auftrag
2026-10-20 · QA 2.8.0 · qa haiku/medium · ok (fand 5 echte Grammatiklücken: mehrzeilige sei/für, Token-Namen, f(a, a), Parameter nach *rest, datum_formatieren) · haiku-QA lohnt; Nachbesserung danach sonnet
2026-10-20 · Doku je Runde · release haiku/low parallel zur nächsten Baurunde · ok · spart Wartezeit, ändert keine Code-Dateien
2026-10-19 · Sprachmerkmale quer (Lambda, Spread, Destrukturierung, Fehlerarten, Module) · entwickler sonnet · ok · sonnet reicht für Lexer+Parser+Interpreter gemeinsam
2026-10-19 · Stdlib nach Vorlage, CLI-Flags, CI-YAML, Builtin-Tests · junior haiku · ok · haiku reicht bei klarer Vorlage und ≤ 2 Dateien
2026-10-19 · Parallelität · Chef · Regel · nie zwei Schreiber an parser.py/interpreter.py; Doku/Tests/CI daneben ist sicher
