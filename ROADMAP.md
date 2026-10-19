# Roadmap

Gepflegt vom `sprache-chef`. Je Zeile: Thema — Nutzen — Aufwand S/M/L — Agent + Modell.
✔ = durch Testprogramm bestätigt. ❓ = vor der Umsetzung Entscheidung des Nutzers nötig.

## Offen

### P1 — Fehler (zuerst)
- (keine offen — alle in 2.7.1 behoben)

### P2 — großer Nutzen, wenig Aufwand
- Typ-Hinweise von Parametern (`funktion f(a: Ganzzahl)`) auch bei Neuzuweisung im Funktionskörper prüfen (heute nur `sei`/`konstante`) — S — entwickler/sonnet
- Fehler in `{…}`-Interpolationen melden falsche Zeile: relativ (Sub-Lexer beginnt bei 1) bzw. Zeile des String-Endes statt des `{` (lexer.py:167) — S — junior/haiku
- Fehlerkopf zeigt Python-Klassennamen (`[ZeroDivisionError]`, main.py:261); deutsche Fehlerarten auch für `fange (…)` — M — entwickler/sonnet ❓ (Namensschema festlegen)
- Fehler-Neuerzeugung: nicht übersetzte Typen behalten den englischen Originaltext; `fange (UnicodeDecodeError)` greift nach dem Rückfall nicht mehr — S — junior/haiku
- Module: `klasse X(modul.Basis)` und Typ-Hinweise mit Punktpfad; Aufrufkette mit Dateiname; `versuche`/`werfe` behält `.datei`/`.zeile` — M — entwickler/sonnet
- Funktionen höherer Ordnung: `abbilden`, `filtere`, `reduziere`, `sortiere`/`min`/`max` mit Schlüsselfunktion + Kurz-Lambda `(x) -> x * 2` — macht Lambdas erst nützlich — S/M — entwickler/sonnet
- CLI: `--version`, `--hilfe`, `-c "code"`, `--pruefen` (nur parsen); `hilfe` in der REPL; BANNER zeigt „Deutsch 2.0" statt `__version__` — S — junior/haiku
- `deutsch/__main__.py` → `py -m deutsch datei.deu` (umgeht auch das Shebang-Problem unter Windows) — S — junior/haiku
- Mehrzeilige Aufrufe, Parameterlisten und Klammerausdrücke (heute SyntaxError) — S — entwickler/sonnet
- Bit-Operatoren `& | ^ ~ << >>`, Literale `0xFF`, `0b101`, `1_000` — S — entwickler/sonnet
- Null-Koaleszenz `??` (Standardwert nur bei `nichts`, anders als `oder`) — S — entwickler/sonnet
- Stdlib Dateien/Pfade: `pfad_verbinden`, `dateiname`, `endung`, `ist_datei`, `ist_ordner`, `datei_loeschen`, `umbenennen`, `zeilen_lesen` — S — junior/haiku
- Stdlib Text/Listen/Mathe: `auffuellen`, `zentrieren`, `ersetze` mit Anzahl, `eindeutig`, `gruppiere`, `zusammenfuehren`, `arcsin`/`arccos`/`arctan`/`atan2`, `runde` mit negativen Stellen, `warte`, Datum parsen — S — junior/haiku
- Spread `f(*liste)`, `[*a, *b]`, `{**a, **b}` und `**kwargs` — M — entwickler/sonnet
- Destrukturierende Neuzuweisung `[a, b] = [b, a]`, Rest `[kopf, *rest]`, Kettenzuweisung — M — entwickler/sonnet
- Tests für main.py (CLI, REPL, Exitcodes) und ungetestete Builtins (`verbinde`, `umkehren`, `runde`, Trigonometrie, Text-Methoden, Typ-Hinweise) — M — qa/haiku
- CI: Windows + Python 3.14, CLI-Lauf, `pip install`-Check, Prüfung Version pyproject = `__init__` — S — release/haiku

### P3 — größere Vorhaben
- Mustervergleich ausbauen: Guards (`fall x wenn …`), Listen-/Dict-/Typmuster mit Bindung, als Ausdruck — M — architekt/opus (Entwurf) → entwickler/sonnet
- Eigene Fehlerklassen: `fange (MeinFehler)` erkennt heute keine Nutzerklassen, `werfe f` verliert den Typ; Fehlerobjekt mit Typ/Nachricht/Zeile; `ist_instanz` — M — architekt/opus (Entwurf) → entwickler/sonnet
- Iterator-Protokoll (`__iter__`/`__naechstes__`), lazy `bereich`; später Generatoren `ergib` (L, braucht Umbau der Auswertung) — M/L — architekt/opus
- Weitere Dunder-Hooks: `__laenge__`, `__hole__`/`__setze__`, `__enthaelt__`, `__aufruf__` — M — entwickler/sonnet
- Eigenschaften (Getter/Setter) und abstrakte Methoden/Schnittstellen — M — entwickler/sonnet
- Aufzählungstypen `aufzaehlung Farbe { rot, gruen }` — M — entwickler/sonnet
- Dekoratoren `@name` (nach Funktionen höherer Ordnung) — S — entwickler/sonnet
- Optional-Chaining `?.`, Schleifen-`sonst`, Label-`abbrechen` — S/M — entwickler/sonnet
- Stdlib CSV und HTTP-Abruf (urllib), wählbare Zeichenkodierung — M — entwickler/sonnet
- Syntax-Hervorhebung für VS Code (TextMate-Grammatik aus SCHLUESSELWOERTER) — M — entwickler/sonnet
- Linter (auf `--pruefen` aufbauend), Formatierer (L) — M/L — entwickler/sonnet
- Debugger/Schrittmodus — L — architekt/opus
- Performance: Namensauflösung zur Parse-Zeit oder Bytecode-VM — L — architekt/opus
- REPL-Verlauf unter Windows — S — junior/haiku ❓ (braucht `pyreadline3` = neue Abhängigkeit)
- Einheitliche Stdlib-Namen (`Woerterbuch`/`Wörterbuch`, Umlaut-Paare, Verb vs. Substantiv) — S — junior/haiku ❓ (Benennungsregel festlegen)
- Veröffentlichung auf PyPI, Git-Tags, Release-Workflow — S — release/haiku ❓ (PyPI-Konto)
- Online-Spielwiese (Pyodide, ohne Datei-/Umgebungsfunktionen) — L — architekt/opus

## Erledigt
- [2.7.1] `nicht` bindet stärker als Vergleiche: `nicht 1 == 2` ergibt `falsch` (parser.py:510)
- [2.7.1] `abbrechen`/`weiter` in einer Funktion beendet die Schleife des Aufrufers; auf oberster Ebene erscheint `[_AbbrechenSignal]` als Fehlertext
- [2.7.1] Typ-Hinweis wird bei Neuzuweisung nicht geprüft (`sei x: Ganzzahl = 1` dann `x = "text"` läuft), obwohl README es verspricht
- [2.7.1] Rekursion bricht schon bei ~1000 Ebenen ab; das Limit 10000 in main.py:15 greift nicht (Python-Stack zu klein) → Interpreter in Thread mit größerem `stack_size`
- [2.7.1] Rohe englische Fehler: `5 % 0`; dazu laut Analyse unäres Minus auf Text, `"x".zahl()`, `max`/`min` mit gemischten Typen, `entferne()` auf leerer Liste, `lade` mit fehlender Datei, EOF bei `eingabe`, Instanz in `für`
- [2.7.1] REPL: `{` innerhalb einer Zeichenkette lässt die REPL weiterlesen, folgende Eingaben gehen still verloren
- [2.7.1] Lexer zählt Zeilen in `"""`-Zeichenketten doppelt → falsche Zeilennummern in Fehlern (lexer.py:172)
- [2.7.1] `lade`: Fehler zeigen Zeile der Hauptdatei ohne Dateinamen; Pfade relativ zum Hauptskript statt zur ladenden Datei; `neu modul.Klasse()` ist SyntaxError (parser.py:723)
- [2.7.1] Klassenkörper überspringt unbekannte Tokens still (`funtion` → Folgefehler an falscher Stelle, parser.py:259)
- [2.7.1] Zuweisung ohne `sei` legt still eine neue Variable an (`zaehlr = 2` neben `zaehler`); der Tippfehler-Vorschlag in umgebung.py:51 ist damit toter Code
