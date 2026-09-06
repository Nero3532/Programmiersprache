# Änderungsprotokoll

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Hinzugefügt
- **Language Server** (`deutsch --lsp`, alternativ `deutsch-lsp`): Diagnosen, Gliederung,
  Vervollständigung, Hover und Sprung zur Definition. Die Diagnosen zeigen die bestehenden
  deutschen Syntaxfehler inline im Editor; der Code wird dafür nur gelesen, nie ausgeführt.
  Implementiert ohne externe Abhängigkeiten – das Protokoll (JSON-RPC über stdio) steckt in
  `deutsch/lsp.py`, die Analyse macht der vorhandene Lexer/Parser.
- **tree-sitter-Grammatik** unter `editor/tree-sitter-deutsch/` für Syntaxhervorhebung,
  Faltung und Navigation, samt Abfragen (`highlights`, `locals`, `folds`) und Korpus-Tests.
  Ein CI-Job erzeugt den Parser, prüft das eingecheckte `src/` auf Aktualität, fährt die
  Korpus-Tests und parst alle Beispielskripte.
- **VS-Code-Erweiterung** unter `editor/vscode-deutsch/`: TextMate-Grammatik für die
  Hervorhebung (VS Code nutzt kein tree-sitter) und ein Client, der den Language Server
  startet. Die Hervorhebung wird über Zusicherungen in `test/hervorhebung.deu` geprüft,
  ein CI-Job testet sie und baut das Paket.
- **Faule Bereiche**: `bereich(...)` liefert eine Folge, die ihre Elemente erst beim
  Durchlaufen erzeugt. `bereich(10000000)` belegt 48 Byte statt mehrerer hundert Megabyte,
  `laenge` und `in` arbeiten in konstanter Zeit, ein Schnitt bleibt faul. Neuer Typ `Bereich`
  (auch als Typ-Hinweis) mit den Methoden `laenge`/`länge`, `enthält`, `liste`, `erste`,
  `letzte`.
- **Verschachtelte Abstraktionen** sowie **Mengen- und Wörterbuch-Abstraktionen**:
  `[x * y für x in a für y in b]`, `{x % 3 für x in bereich(10)}`,
  `{wort: länge(wort) für wort in woerter}`. Jede Klausel kann ein eigenes `wenn`-Filter
  tragen, spätere Klauseln sehen die Variablen früherer. Literale (`{}`, `{1, 2}`,
  `{"a": 1}`) bleiben unverändert Literale.
- `deutsch --version` / `-V`.
- `neu modul.Klasse(...)` — Klassen aus einem per `lade "..." als modul` geladenen Namensraum
  lassen sich direkt instanziieren (bisher ein Syntaxfehler, der nur über den Umweg
  `sei K = modul.Klasse` umgangen werden konnte). Keyword-Argumente und Verkettung
  (`neu modul.Klasse(x=1).methode()`) funktionieren wie bei lokalen Klassen.

### Behoben
- Eingebaute Instanzmethoden von Liste/Zeichenkette/Wörterbuch/Menge prüfen ihre Argumentanzahl
  selbst. Vorher zeigte ein falscher Aufruf Python-Interna
  (`Interpreter._listen_methoden_aufbauen.<locals>.<lambda>() missing 1 required positional
  argument: 'wert'`), jetzt z. B. `'Liste.einfuegen' erwartet 2 Argument(e), bekam 1`.
- Keine rohen englischen Python-Meldungen mehr bei: unärem `-` auf Nicht-Zahlen, `%` und `**`
  durch Null, Slice-Schrittweite `0`, unhashbaren Wörterbuch-Schlüsseln und Mengen-Elementen,
  `für`/List-Comprehension über nicht-iterierbare Werte, `lade` auf fehlende/unlesbare Dateien,
  `json_schreiben` in ein fehlendes Verzeichnis, `zahl()` auf ungültigen Zeichenketten sowie
  Typfehlern in `abs`, `runde`, `bereich`, `aufzaehlen`, `logarithmus`, `max`/`min`, `entferne`,
  `teile`, `ersetze`, `wiederhole`, `beginnt_mit`/`endet_mit`, `enthält` und `hole`.
- `entferne` auf einer leeren Liste und mit ungültigem Index meldet dies auf Deutsch statt
  `pop from empty list` bzw. `pop index out of range`.
- Index-Zuweisung auf eine Zeichenkette meldet jetzt `Zeichenketten sind unveränderlich` statt
  irreführend `Ungültiger Index-Typ`.
- Zeilennummern nach mehrzeiligen (`"""`) Zeichenketten: der Lexer zählte jeden Zeilenumbruch
  im String doppelt, wodurch alle folgenden Fehlermeldungen auf eine zu hohe Zeile zeigten und
  die Quelltext-Anzeige ausfiel, sobald diese Zeile hinter dem Dateiende lag.
- `max` und `min` akzeptieren jetzt auch Mengen (wie `summe`, `alle`, `einige`, `ggt`, `kgv`).
  Vorher gab `max({3, 1, 2})` die Menge selbst zurück statt `3`.
- `runde` mit negativer Stellenzahl rundet auf Zehner/Hunderter/…: `runde(1234, -2)` ergibt
  `1200` statt bisher `1234`. Positive Stellen und der Standardfall bleiben unverändert.
- Anonyme Funktionen heißen in Argument-Fehlermeldungen `<anonym>` statt `'None'`
  (`'<anonym>': Pflichtargument(e) fehlen: x`), benannte behalten ihren Namen.
- Grammatik in der Fehlermeldung `hat kein Parameter` → `hat keinen Parameter`.
- Unerwartete Token im Klassenkörper werden gemeldet statt still übersprungen: ein Tippfehler
  wie `klasse A { tippfehler }` verschwand bisher spurlos, jetzt gibt es einen `SyntaxError`
  mit Zeilenangabe.
- `__gleich__` wirkt jetzt überall, wo auf Gleichheit geprüft wird: `passe`/`fall`, der
  `in`-Operator auf Listen und die wertbasierten Listenmethoden `enthält`, `index_von`
  und `zaehle`. Bisher galt die Überladung nur für den `==`-Operator, sodass `a == b` wahr
  sein konnte, `passe a { fall b: ... }` aber nicht traf. Der gesuchte Wert ist dabei der
  linke Operand. Mengen und Wörterbücher bleiben hash-basiert – dafür wäre zusätzlich eine
  `__hash__`-Überladung nötig.
- 67 neue Regressionstests (216 gesamt).

### Geändert
- `datum_formatieren` mit einem Zeitstempel falschen Typs wirft `TypeError` statt `ValueError`
  (konsistent mit `wurzel`, `sinus`, `boden`); ein numerischer Zeitstempel außerhalb des gültigen
  Bereichs wirft weiterhin `ValueError`.
- `bereich` und `aufzaehlen` akzeptieren keine Zahlen mehr in Zeichenketten-Form
  (`bereich("5")`) – Argumente müssen Zahlen sein.
- `bereich(...)` gibt keine **Liste** mehr zurück, sondern einen faulen `Bereich`.
  Schleifen, Abstraktionen und die eingebauten Funktionen sind unverändert; wer das
  Ergebnis als Liste braucht (Listenmethoden, Veränderung, Ausgabe als `[…]`), schreibt
  `liste(bereich(...))`. `typ(bereich(3))` liefert jetzt `'Bereich'`, `drucke(bereich(3))`
  gibt `bereich(0, 3)` aus.
- Eine Klassen-`konstante` lässt sich nicht mehr pro Instanz überdecken: `instanz.MAX = 1`
  und `dies.MAX = 1` werfen jetzt `TypeError` statt still ein Instanzattribut anzulegen, das
  die Konstante beim Lesen verdeckte. Das gilt auch für geerbte Konstanten – und `Kind.MAX = 1`
  auf einer geerbten Konstante wird ebenfalls abgewiesen (bisher legte es still ein
  überdeckendes Klassenattribut an). Die Meldung nennt die deklarierende Klasse. Nicht-konstante
  Klassenattribute (`sei` im Klassenkörper) bleiben pro Klasse und pro Instanz überschreibbar.
- Zuweisung an einen nicht deklarierten Namen ist jetzt ein Fehler statt einer stillen
  Neuanlage: `zaehler = 5` ohne vorheriges `sei zaehler = ...` wirft
  `Variable 'zaehler' wurde nicht deklariert (benutze 'sei')`, bei ähnlichem vorhandenem
  Namen mit Vorschlag. Damit greift die Meldung, die `Umgebung.weise_zu` schon immer
  enthielt, aber nie erreicht wurde. Unverändert bleiben: Zuweisung an bestehende Variablen
  (auch aus einem inneren Geltungsbereich heraus), Schleifen- und `fange`-Variablen sowie
  Attribut- und Index-Zuweisungen (`obj.neu = 1`, `liste[0] = 1`).

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
