# Änderungsprotokoll

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

## [2.4.0]

### Hinzugefügt
- Datum/Zeit: `jetzt()`, `datum_formatieren(zeitstempel, format)`.
- Statistik: `mittelwert`, `median`, `stdabweichung` (Populations-Standardabweichung).
- Liste/Zeichenkette: `index_von` (wirft bei fehlendem Treffer, anders als stilles `-1`/`find`),
  `zaehle` (Vorkommen zählen).
- `tiefe_kopie(wert)` — rekursive Kopie für Listen/Wörterbücher/Mengen/Instanzen (`.kopiere()`
  bleibt flach).
- `umgebungsvariable(name)`/`umgebungsvariable(name, standard)`.
- Dateisystem: `pfad_existiert`, `dateien_auflisten`, `ordner_erstellen`.
- Hashing/Kodierung: `hash_sha256`, `base64_kodieren`, `base64_dekodieren`.
- 19 neue Regressionstests (93 gesamt).

## [2.3.0]

### Hinzugefügt
- Automatisierte CI (GitHub Actions) führt die Testsuite bei jedem Push/PR gegen Python 3.10–3.13 aus.
- `pyproject.toml` für `pip install -e .` und ein `deutsch`-Kommandozeilenbefehl.
- Diagnostik: `NameError` bei unbekannten Variablen/Funktionen schlägt bei Tippfehlern ähnliche
  bekannte Namen vor ("meintest du '...'?"), via `difflib.get_close_matches`.
- Stdlib: `boden`, `decke` (Mathe); `zufall`, `zufallszahl`, `mische` (Zufall); `summe`, `alle`,
  `einige`, `aufzaehlen`, `zippe` (funktional); `json_lesen`, `json_schreiben`; `passt_zu`,
  `regex_ersetze`, `regex_finde`, `regex_finde_alle` (Regex, Pythons `re`-Syntax);
  `kommandozeilen_argumente()` (Argumente hinter dem Skriptnamen, `deutsch skript.deu a b`).
- 20 neue Regressionstests (74 gesamt).

### Geändert
- Performance: Visitor-Dispatch (`Interpreter._besuche`) nutzt ein einmalig aufgebautes Dict statt
  bei jedem Knotenbesuch `getattr(f'_besuche_{...}')` neu aufzulösen.
- Performance: `Umgebung.hole`/`weise_zu`/`existiert` sind iterativ statt rekursiv (weniger
  Python-Stack-Verbrauch bei tiefen Scopes).
- Performance: eingebaute Methoden für Liste/Zeichenkette/Wörterbuch/Menge (`.laenge()`,
  `.anhängen()`, …) werden einmalig aufgebaut statt bei jedem `.attribut`-Zugriff neu.

## [2.2.0]

### Hinzugefügt
- Ternärer Ausdruck: `dann_wert wenn bedingung sonst sonst_wert`.
- Destrukturierung: `sei [a, b, c] = liste`.
- Mengen-Typ: `{1, 2, 3}`-Literal, `.vereinigung()`/`.schnittmenge()`/`.differenz()`, `menge()`-Builtin,
  Typ-Hinweis `Menge`.
- Format-Spezifizierer in String-Interpolation: `"{wert:.2f}"` (Pythons `format()`-Minisprache).

### Behoben
- Vergleichsverkettung (`1 < x < 10`) wertete bisher `(1<x) < 10` aus statt `(1<x) und (x<10)` –
  lieferte dadurch fast immer `wahr` unabhängig vom tatsächlichen Wert. Jetzt korrekte Verkettung,
  jeder Operand nur einmal ausgewertet.
- Grammatik-Kollision zwischen dem neuen Ternär-Lookahead und dem `wenn`-Filter von
  List-Comprehensions (`[x für v in iterable wenn bedingung]`).

## [2.1.0]

### Hinzugefügt
- `werfe`-Anweisung und eigene Exceptions (beliebiger Werttyp werfbar, nicht nur Zeichenketten).
- Operatoren `**` (Potenz) und `//` (Ganzzahldivision) inkl. `**=`/`//=`.
- Slicing für Listen/Zeichenketten: `liste[1:3]`, `[::2]`, `[::-1]` (lesend).
- Anonyme Funktionen/Lambdas: `funktion(x) { zurück x*x }` als Ausdruck.
- Mehrfachvererbung für Klassen: `klasse C(A, B) { }` (links-nach-rechts-Tiefensuche).
- Zur Laufzeit geprüfte Typ-Hinweise (`sei x: Ganzzahl`, Parameter- und Rückgabetypen).
- `passe`/`fall`/`sonst`-Match-Anweisung.
- Mathe-Stdlib (`pi`, `e`, `wurzel`, `sinus`, `kosinus`, `tangens`, `logarithmus`, `exponential`).
- Datei-I/O-Stdlib (`datei_lesen`, `datei_schreiben`, `datei_anhaengen`).
- Aufruf-Stacktraces bei unbehandelten Fehlern in Funktionsaufrufen.
- `nicht in`-Operator (Infix).

### Behoben
- Laufzeitfehler (NameError, TypeError, …) zeigten keine Zeilennummer, nur Syntaxfehler taten das.
- `sortiere()` sortierte Zahlen alphabetisch statt numerisch (`[1,10,2]` statt `[1,2,10]`).
- Schlüsselwörter waren case-insensitive (`Wenn` kollidierte mit `wenn`).
- Wissenschaftliche Notation (`1.0e308`) wurde vom Lexer nicht erkannt.
- `KeyError`-Anzeige verdoppelte Anführungszeichen durch Pythons `repr()`-basierte `__str__`.
- Index-Fehler (Bereich, Typ) zeigten teils rohe englische Python-Meldungen statt deutscher Texte.
- Jeder Operator-Typfehler (`5 < "text"`) leckte rohe englische Python-Meldungen; jetzt zentral
  übersetzt.
- Rekursionslimit auf 10000 angehoben (`sys.setrecursionlimit`).

## [1.0.0]

- Erste Version: Lexer, Parser, AST, Baum-Interpreter.
- Kernsprache: Variablen, Funktionen (Defaults, variadische Parameter), Klassen mit Einfachvererbung,
  Kontrollfluss (`wenn`/`solange`/`für`), Fehlerbehandlung (`versuche`/`fange`/`endlich`),
  Listen-/Wörterbuch-Literale inkl. List-Comprehensions, String-Interpolation, Module (`lade`), REPL.
