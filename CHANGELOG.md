# Änderungsprotokoll

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Hinzugefügt
- Bit-Operatoren `&`, `|`, `^`, `~` und Schiebeoperatoren `<<`, `>>` für Ganzzahlen; `&`, `|`, `^` auch für Mengen
  (Schnitt, Vereinigung, symmetrische Differenz). Verbund-Zuweisungen `&=`, `|=`, `^=`, `<<=`, `>>=`.
- Zahlliterale `0xFF`, `0b101`, `0o17`; `_` als Trenner zwischen Ziffern (`1_000`).
- Null-Koaleszenz `a ?? b`: wertet `b` nur aus, wenn `a` gleich `nichts` ist (`0` und `falsch` bleiben erhalten).
- Zeilenumbrüche innerhalb von `( … )` (Aufrufe, Parameterlisten, Klammerausdrücke) sowie ein abschließendes
  Komma in Aufrufen und Parameterlisten.
- Lambda-Kurzform `funktion(x) -> ausdruck`, auch benannt (`funktion verdopple(x) -> x * 2`) und in Klassen.
- `abbilden`, `filtere` und `reduziere` als Builtins und als verkettbare Listen-Methoden
  (`liste.abbilden(f).filtere(g)`).
- `schluessel=` (auch `schlüssel=`) bei `sortiere`, `max` und `min`; `umgekehrt=` bei `sortiere`.
  `liste.sortiere()` nimmt beide Argumente ebenfalls.
- CLI-Optionen: `--version` (`-V`), `--hilfe` (`-h`, `--help`), `-c "code"` (Code direkt ausführen; Argumente
  über `kommandozeilen_argumente()`), `--pruefen datei.deu` (nur Syntaxprüfung, nichts wird ausgeführt).
- REPL-Befehl `hilfe` zeigt eine Übersicht der Befehle.
- `py -m deutsch` startet das Programm als Modul, mit denselben Optionen wie `main.py`.
- CI: Tests auf Windows und Linux für Python 3.10 bis 3.14; die Beispiele werden über die CLI ausgeführt,
  nach der Paket-Installation werden Version und Aufruf geprüft.
- Entpacken mit `*` und `**`: `f(*liste, **wb)` in Aufrufen (auch bei `neu K(…)` und Methoden), `[*a, *b]` in Listen,
  `{**a, **b}` in Wörterbüchern und `{*a, *b}` in Mengen.
- `**kwargs`-Parameter: `funktion f(a, **optionen)` sammelt überzählige Keyword-Argumente in einem Wörterbuch.
- Destrukturierende Zuweisung an bestehende Variablen: `[a, b] = [b, a]`, auch an Attribute und Indizes
  (`[k.x, liste[0]] = [1, 2]`).
- Rest- und verschachtelte Muster `[kopf, *rest]` und `[a, [b, c]]` bei `sei`, Zuweisung und `für`
  (auch in Comprehensions).
- Kettenzuweisung `a = b = 0`, auch an Attribute und Indizes. `sei a = b = 0` ist ein Syntaxfehler mit Hinweis.

### Geändert
- Der REPL-Banner zeigt die Versionsnummer aus `deutsch/__init__.py` statt des festen Texts „Deutsch 2.0“.

### Behoben
- Zeilennummern bei Fehlern in `{…}`-Interpolationen waren falsch; gemeldet wird jetzt die absolute Zeile des `{`.
- `"{1 2}"` wird als Syntaxfehler gemeldet, statt den Rest des Ausdrucks stillschweigend zu ignorieren.
- REPL: Bei offener `(` oder `[` wartet sie auf Folgezeilen (bisher nur bei `{`).

## [2.7.1]

### Geändert
- `nicht` bindet wie in Python schwächer als Vergleiche: `nicht a == b` ist jetzt `nicht (a == b)`.
  `x == nicht y` ist ein Syntaxfehler — Klammern setzen: `x == (nicht y)`.
- Zuweisung an einen nicht deklarierten Namen wirft `NameError` (mit „meintest du …?“, wenn ein
  ähnlicher Name bekannt ist), statt still eine Variable anzulegen. Neue Variablen werden mit `sei` angelegt.
- `lade` löst relative Pfade ab dem Ordner der ladenden Datei auf, nicht mehr nur ab dem Ordner des Hauptskripts.
- Strg+C bricht während einer laufenden Eingabe nur diese ab („Unterbrochen.“) statt die REPL zu beenden.
  Am Prompt `>>>` beendet Strg+C die REPL weiterhin.

### Behoben
- `abbrechen`/`weiter` in einer Funktion beendeten still die Schleife des Aufrufers; jetzt Fehler
  „'abbrechen' außerhalb einer Schleife“. Auf oberster Ebene erschienen interne Signalnamen; jetzt derselbe
  deutsche Fehler (ebenso `zurück` außerhalb einer Funktion).
- Typ-Hinweise von `sei`-Variablen wurden bei Neuzuweisung und `+=` nicht geprüft; jetzt werden sie bei jeder Zuweisung geprüft.
- Rekursion brach schon nach ca. 900 Aufrufen ab; jetzt läuft die Ausführung in einem Thread mit großem Stack (ca. 5900 Aufrufe).
- REPL: `{` in einer Zeichenkette oder einem Kommentar ließ die REPL weiterlesen, Eingaben gingen verloren.
- Zeilennummern nach mehrzeiligen `"""`-Zeichenketten waren falsch.
- Tippfehler im Klassenkörper (z. B. `funtion`) wurden still übersprungen; jetzt Syntaxfehler mit Vorschlag („meintest du …?“).
- `lade`: deutsche Meldung bei fehlender Datei; Fehler in geladenen Dateien nennen Dateiname und richtige Zeile;
  `neu modul.Klasse(...)` funktioniert.
- Englische Python-Fehlertexte übersetzt: `%` durch Null, unäres Minus auf Nicht-Zahl, `zahl()`, `max`/`min`
  mit gemischten Typen, `entferne` auf leerer Liste, EOF bei `eingabe`, Iteration über Nicht-Iterierbares,
  `json_lesen`, `json_schreiben`, `datei_lesen`/`datei_schreiben`/`datei_anhängen`.
- `json_schreiben` prüft den Wert, bevor die Datei angelegt wird: nicht speicherbare Werte und zirkuläre
  Verweise werden auf Deutsch gemeldet, und die Datei wird dabei nicht überschrieben.
- 182 neue Regressionstests (331 gesamt).

## [2.7.0]

### Hinzugefügt
- `konstante X = wert` — unveränderliche Bindungen; Neuzuweisung (auch per Verbund-Zuweisung) und
  Redeklaration im selben Geltungsbereich werfen `TypeError`. Verschachtelte Scopes können weiterhin
  schatten (eigene lokale Konstante mit gleichem Namen).
- Typisiertes `fange (Typ1, Typ2) name { ... }` — fängt nur passende Fehlerarten (inkl. Basisklassen,
  z. B. fängt `KeyError` auch `SchluesselFehler`); nicht passende Fehler propagieren weiter,
  `endlich` läuft trotzdem. Ohne Typ-Liste unverändertes Verhalten (alles fangen).
- `lade "datei.deu" als name` — lädt in einen isolierten Scope statt in den globalen; Bindungen über
  `name.attribut` erreichbar statt den aufrufenden Scope zu verändern.
- Statische Klassenattribute (`sei`/`konstante` direkt im Klassenkörper, geteilt über alle Instanzen
  und per `Klasse.attribut` lesbar/schreibbar) und statische Methoden (`statisch funktion ...`, kein
  `dies`, aufrufbar über Klasse oder Instanz ohne automatische Bindung). Werden vererbt.
- 19 neue Regressionstests (149 gesamt).

## [2.6.0]

### Hinzugefügt
- `pruefe bedingung[, meldung]` — Assertion-Anweisung, wirft `AssertionError` bei Fehlschlag.
- Mengen: `teilmenge_von`, `obermenge_von`, `symmetrische_differenz`.
- Liste: `einfuegen(index, wert)`, `erweitere(andere_liste)`.
- Mathe: `ggt`, `kgv`, `vorzeichen`.
- Zeichenkette: `ist_ziffer`, `ist_buchstabe`, `ist_leerraum`.
- 11 neue Regressionstests (130 gesamt).

## [2.5.0]

### Hinzugefügt
- Destrukturierung in `für`-Schleifen und List-Comprehensions: `für [i, wert] in aufzaehlen(liste) { ... }`,
  `[x*y für [x, y] in zippe(a, b)]`.
- Keyword-Argumente bei Funktionsaufrufen und `neu Klasse(...)`: `f(b=2, a=1)`, gemischt mit
  positionalen Argumenten (die vor Keyword-Argumenten stehen müssen).
- Zyklische `lade`-Importe werden erkannt und werfen einen klaren `ImportError` statt einer
  Endlosschleife/Rekursionsfehler; mehrfaches nicht-zyklisches Laden bleibt erlaubt.
- Operator-Überladung für Klassen: `__addiere__`, `__subtrahiere__`, `__multipliziere__`,
  `__dividiere__`, `__ganzdividiere__`, `__modulo__`, `__potenziere__`, `__gleich__`, `__ungleich__`,
  `__kleiner__`, `__groesser__`, `__kleinergleich__`, `__groessergleich__` — nur linker Operand,
  jeder Operator einzeln definierbar.
- 18 neue Regressionstests (114 gesamt).

### Behoben
- Doppelte Keyword-Argumente (`f(a=1, a=2)`) wurden stillschweigend akzeptiert (letzter Wert
  gewinnt) statt wie in Python als Fehler abgelehnt zu werden.
- 5 weitere Regressionstests (119 gesamt).

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

### Behoben
- `zeichenkette.index_von()`/`.zaehle()` leckten rohe englische `TypeError`-Meldungen bei falschem
  Argumenttyp (z. B. `"abc".index_von(5)`).
- `ordner_erstellen()` leckte eine rohe (teils englische, teils Windows-lokalisierte) Meldung, wenn
  der Zielpfad bereits als Datei existierte; `dateien_auflisten()` übersetzte `PermissionError` nicht.
- 3 neue Regressionstests dafür (96 gesamt).

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
