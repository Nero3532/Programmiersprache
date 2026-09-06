# Deutsch

Eine Programmiersprache mit deutschen Schlüsselwörtern. Interpretiert (Baum-Interpreter), geschrieben in Python.

```
sei name = "Welt"
drucke("Hallo, {name}!")

funktion fakultaet(n) {
    wenn n <= 1 {
        zurück 1
    }
    zurück n * fakultaet(n - 1)
}
drucke(fakultaet(5))
```

## Verwendung

Benötigt Python 3.10+.

```
python main.py              # interaktive REPL
python main.py datei.deu    # Datei ausführen
```

Alternativ installierbar:

```
pip install -e .
deutsch                     # interaktive REPL
deutsch datei.deu           # Datei ausführen
```

## Sprachüberblick

### Variablen & Typen

```
sei x = 5                    # Ganzzahl
sei y = 3.14                 # Kommazahl
sei s = "Text"                # Zeichenkette
sei b = wahr                  # Wahrheitswert (wahr/falsch)
sei n = nichts                 # Nichts (null)
sei liste = [1, 2, 3]
sei dict = {"a": 1, "b": 2}

sei alter: Ganzzahl = 25      # optionaler, zur Laufzeit geprüfter Typ-Hinweis

sei [a, b, c] = [1, 2, 3]     # Destrukturierung

konstante PI = 3.14159        # unveränderlich — Neuzuweisung wirft TypeError
```

`sei` deklariert, `=` weist nur zu: eine Zuweisung an einen unbekannten Namen (`x = 5` ohne
vorheriges `sei x = ...`) wirft einen `NameError`, damit ein Tippfehler keine stille neue
Variable anlegt. Zuweisungen greifen auf die nächste umschließende Deklaration zu — eine
Funktion kann also eine äußere Variable beschreiben, ohne sie neu zu deklarieren.

Verfügbare Typ-Hinweise: `Ganzzahl`, `Kommazahl` (akzeptiert auch Ganzzahl), `Zeichenkette`,
`Wahrheitswert`, `Liste`, `Woerterbuch`/`Wörterbuch`, `Menge`, `Nichts`, `Funktion`, oder ein
selbstdefinierter Klassenname. Ein unbekannter Typ-Hinweis wirft einen Fehler.

### Operatoren

Arithmetisch: `+ - * / % ** //` (Potenz, Ganzzahldivision), Verbund-Zuweisung: `+= -= *= /= %= **= //=`
Vergleich: `== != < > <= >=` — auch verkettet: `1 < x < 10` (jeder Operand nur einmal ausgewertet)
Logisch: `und oder nicht`
Mitgliedschaft: `in`, `nicht in`
Ternär: `dann_wert wenn bedingung sonst sonst_wert`

### Kontrollfluss

```
wenn bedingung { ... } sonst wenn andere { ... } sonst { ... }
solange bedingung { ... }
für x in liste { ... }
für [i, wert] in aufzaehlen(liste) { ... }    # Destrukturierung, auch in Comprehensions
passe wert {
    fall 1, 2: { ... }
    fall 3: { ... }
    sonst: { ... }
}
```
`abbrechen` (break) und `weiter` (continue) funktionieren in Schleifen, auch aus einem `fall`-Block heraus.

### Funktionen

```
funktion addiere(a: Ganzzahl, b: Ganzzahl = 10) -> Ganzzahl {
    zurück a + b
}

sei quadrat = funktion(x) { zurück x * x }   # anonyme Funktion / Lambda

funktion summe(*zahlen) {                     # variadische Parameter
    sei s = 0
    für z in zahlen { s += z }
    zurück s
}

addiere(b=5, a=3)          # Keyword-Argumente, beliebige Reihenfolge
addiere(3, b=5)             # gemischt — positional muss vor Keyword stehen
```

### Klassen

```
klasse Tier {
    funktion __init__(dies, name) { dies.name = name }
    funktion sprich(dies) { zurück "..." }
}
klasse Hund(Tier) {
    funktion sprich(dies) { zurück dies.name + ": Wau!" }
}
klasse Zwitter(Hund, EineAndereKlasse) { }   # Mehrfachvererbung (links-nach-rechts DFS)
neu Hund(name="Rex")                          # Keyword-Argumente auch bei neu

klasse Zaehler {
    sei anzahl = 0                            # Klassenattribut, geteilt von allen Instanzen
    konstante MAX = 1000                      # Klassenkonstante — Neuzuweisung wirft TypeError
    funktion __init__(dies) { Zaehler.anzahl += 1 }
    statisch funktion aktuelle_anzahl() { zurück Zaehler.anzahl }   # kein 'dies' → statisch
}
neu Zaehler(); neu Zaehler()
drucke(Zaehler.anzahl)                        # 2 — über Klasse zugreifbar
drucke(Zaehler.aktuelle_anzahl())             # 2 — auch über Klasse aufrufbar (ohne Instanz)
```
Statische Methoden sind normale `funktion`-Definitionen im Klassenkörper mit `statisch`-Präfix,
die kein `dies` deklarieren; sie sind sowohl über die Klasse (`Klasse.methode()`) als auch über
eine Instanz (`instanz.methode()`, ohne automatische `dies`-Bindung) aufrufbar. Klassenattribute
werden vererbt (links-nach-rechts, wie Methoden).

Eine Klassen-`konstante` ist auch gegen Überdecken pro Instanz geschützt: `instanz.MAX = 1` und
`dies.MAX = 1` werfen ebenfalls `TypeError`, ebenso in erbenden Klassen. Nicht-konstante
Klassenattribute (`sei` im Klassenkörper) bleiben überschreibbar.

**Operator-Überladung:** Klassen können `+ - * / // % **` und `== != < > <= >=` selbst definieren
über `__addiere__`, `__subtrahiere__`, `__multipliziere__`, `__dividiere__`, `__ganzdividiere__`,
`__modulo__`, `__potenziere__`, `__gleich__`, `__ungleich__`, `__kleiner__`, `__groesser__`,
`__kleinergleich__`, `__groessergleich__` (jeweils `(dies, andere)`). Nur der linke Operand wird
geprüft (kein `__radd__`-Äquivalent), jeder Operator braucht seine eigene Methode.

`__gleich__` gilt nicht nur für `==`, sondern überall, wo auf Gleichheit geprüft wird: `passe`/`fall`,
der `in`-Operator auf Listen sowie `liste.enthält()`, `liste.index_von()` und `liste.zaehle()` — der
gesuchte Wert ist dabei der linke Operand. Mengen und Wörterbücher bleiben hash-basiert, dafür wäre
zusätzlich eine `__hash__`-Überladung nötig.

### Fehlerbehandlung

```
versuche {
    werfe "Etwas ist schiefgelaufen"   # beliebiger Wert werfbar, nicht nur Strings
} fange fehler {
    drucke(fehler)
} endlich {
    drucke("Immer ausgeführt")
}

pruefe 1 + 1 == 2                       # AssertionError bei Fehlschlag
pruefe x > 0, "x muss positiv sein"     # optionale eigene Meldung

versuche {
    sei d = {}
    d["fehlt"]
} fange (SchluesselFehler, IndexError) f {   # nur diese Fehlerarten fangen, Rest propagiert weiter
    drucke(f)
}
```
Typ-Namen beim typisierten `fange` sind die intern verwendeten (teils englischen) Klassennamen,
wie sie auch in der Fehleranzeige erscheinen (`TypeError`, `ValueError`, `SchluesselFehler`,
`AusnahmeFehler`, …). Auch Basisklassen matchen — `fange (KeyError) f` fängt auch `SchluesselFehler`.
Ohne Typ-Liste (`fange f { ... }`) bleibt das bisherige Verhalten: alles wird gefangen.

### Listen/Strings: Indexing & Slicing

```
sei l = [0,1,2,3,4,5]
l[1:3]      # [1, 2]
l[::-1]     # umgekehrt
l[::2]      # jedes zweite Element
```
Slice-*Zuweisung* (`l[1:3] = [...]`) wird nicht unterstützt.

### Mengen

```
sei m1 = {1, 2, 3}
sei m2 = {2, 3, 4}
m1.vereinigung(m2)     # {1, 2, 3, 4}
m1.schnittmenge(m2)    # {2, 3}
m1.differenz(m2)       # {1}
menge([1, 1, 2, 2])    # {1, 2} – Umwandlung/Deduplizierung, menge() ohne Argument = leere Menge
```
`{}` bleibt (wie in Python) ein leeres *Wörterbuch*, nicht eine leere Menge.

### Abstraktionen (Comprehensions)

```
[x * x für x in bereich(1, 6)]                    # Liste
[x für x in bereich(20) wenn x % 2 == 0]          # mit Filter
[a + b für [a, b] in paare]                        # mit Destrukturierung

[x * y für x in [1,2,3] für y in [10,20]]          # verschachtelt, links nach rechts
[y für x in [3] für y in bereich(x)]               # spätere Klausel sieht frühere Variable

{x % 3 für x in bereich(10)}                       # Menge
{wort: länge(wort) für wort in woerter}            # Wörterbuch
```

Jede Klausel kann ein eigenes `wenn`-Filter tragen. `{}` bleibt ein leeres *Wörterbuch* —
eine Abstraktion wird daraus erst durch das `für`.

### String-Interpolation mit Format-Spezifizierer

```
drucke("Pi = {pi:.2f}")        # Pi = 3.14
drucke("Zahl = {42:5d}")       # Zahl =    42
```
Nutzt Pythons `format()`-Minisprache. Ein `:` innerhalb von Klammern (Slices, Funktionsaufrufe,
Dict-/Mengen-Literale) wird korrekt nicht als Format-Trenner missverstanden:
`"{liste[1:3]}"` bleibt ein Slice-Ausdruck.

### Module

```
lade "andere_datei.deu"

lade "andere_datei.deu" als modul   # Namensraum statt globaler Vermischung
modul.funktion()
modul.KONSTANTE
neu modul.Klasse(...)               # Klassen aus dem Namensraum instanziieren
```
Ohne `als` landen alle Top-Level-Definitionen der geladenen Datei im globalen Scope (wie bisher).
Mit `als name` läuft die Datei in einem isolierten Scope; ihre Top-Level-Bindungen werden stattdessen
unter `name.attribut` erreichbar, ohne den aufrufenden Scope zu verändern.

Zyklische Importe (A lädt B, B lädt A) werden erkannt und werfen einen klaren `ImportError`
statt in eine Endlosschleife zu laufen. Mehrfaches (nicht-zyklisches) Laden derselben Datei ist
erlaubt und führt sie erneut aus.

## Eingebaute Funktionen

**Allgemein:** `drucke`, `eingabe`, `laenge`/`länge`, `typ`, `ganzzahl`, `kommazahl`, `zeichenkette`,
`wahrheitswert`, `bereich`, `sortiere`, `anhaengen`/`anhängen`, `entferne`, `umkehren`, `verbinde`,
`max`, `min`, `abs`, `runde`, `liste`, `woerterbuch`/`wörterbuch`

**Mathe:** `pi`, `e` (Konstanten), `wurzel`, `sinus`, `kosinus`, `tangens`, `logarithmus`, `exponential`,
`boden`, `decke`, `ggt`, `kgv`, `vorzeichen`

**Zufall:** `zufall()` (Kommazahl in [0,1)), `zufallszahl(min, max)` (Ganzzahl, beide Enden
eingeschlossen), `mische(liste)` (mischt in-place)

**Funktional:** `summe`, `alle`, `einige`, `aufzaehlen`, `zippe`

**Datei-I/O:** `datei_lesen`, `datei_schreiben`, `datei_anhaengen`/`datei_anhängen`

**JSON:** `json_lesen`, `json_schreiben` (Mengen werden beim Schreiben automatisch zu sortierten
Listen konvertiert)

**Regex:** `passt_zu(muster, text)`, `regex_ersetze(muster, ersatz, text)`, `regex_finde(muster, text)`
(erster Treffer oder `nichts`), `regex_finde_alle(muster, text)` — nutzt Pythons `re`-Syntax

**Mengen:** `menge` (Umwandlung/leere Menge); Instanzmethoden zusätzlich `teilmenge_von`,
`obermenge_von`, `symmetrische_differenz`

**Statistik:** `mittelwert`, `median`, `stdabweichung` (Populations-Standardabweichung, nicht
Stichprobe — definiert auch für einelementige Listen)

**Datum/Zeit:** `jetzt()` (Unix-Epoch-Sekunden), `datum_formatieren(zeitstempel, format)`
(Python-`strftime`-Direktiven, z. B. `"%Y-%m-%d"`)

**Kopieren:** `tiefe_kopie(wert)` — rekursive Kopie verschachtelter Listen/Wörterbücher/Mengen/
Instanzen (im Unterschied zum flachen `.kopiere()`); bei selbstreferenziellen Strukturen
(`l.anhängen(l)`) `RecursionError` statt Endlosschleife

**Hashing/Kodierung:** `hash_sha256`, `base64_kodieren`, `base64_dekodieren`

**Dateisystem:** `pfad_existiert`, `dateien_auflisten`, `ordner_erstellen`

**System:** `kommandozeilen_argumente()` — Argumente hinter dem Skriptnamen
(`deutsch skript.deu a b` → `["a", "b"]`), `umgebungsvariable(name)`/`umgebungsvariable(name, standard)`

Listen, Zeichenketten, Wörterbücher und Mengen haben zusätzlich Methoden (`liste.laenge()`, `text.gross()`,
`dict.schluessel()`, `menge.vereinigung()`, …) — siehe [beispiele/alle_features.deu](beispiele/alle_features.deu)
für eine vollständige Demonstration.

## Editor-Unterstützung

```
python main.py --lsp        # Language Server (LSP über stdio)
```

Der Language Server liefert Syntaxfehler als Inline-Diagnosen, eine Gliederung mit Klassen und
Methoden, kontextabhängige Vervollständigung (nach einem `.` nur Methoden), Kurzinfos zu
eingebauten Funktionen und Sprung zur Definition. Er wertet den Code nur syntaktisch aus und
führt ihn nie aus.

Unter [editor/](editor/) liegen zwei Grammatiken für die Syntaxhervorhebung:

- [`vscode-deutsch/`](editor/vscode-deutsch) — VS-Code-Erweiterung (TextMate-Grammatik plus
  Anbindung des Language Servers). Ausprobieren mit
  `cd editor/vscode-deutsch && npm install && code --extensionDevelopmentPath=.`
- [`tree-sitter-deutsch/`](editor/tree-sitter-deutsch) — tree-sitter-Grammatik für Neovim,
  Helix, Zed, Emacs und GitHub, samt Abfragen für Hervorhebung, Faltung und Geltungsbereiche.

## Bekannte Einschränkungen

- Kein Bytecode-Compiler — reiner Baum-Interpreter (bewusste Design-Entscheidung, siehe unten).
- Mehrfachvererbung nutzt einfache links-nach-rechts-Tiefensuche, keine echte C3-Linearisierung.
- Variadische Parameter (`*args`) werden nicht einzeln typgeprüft.
- `(-8) ** 0.5` liefert eine Python-`complex`-Zahl ohne dedizierte Formatierung.
- Rekursionslimit ist auf 10000 gesetzt (`sys.setrecursionlimit`), tief rekursive Deutsch-Programme
  können trotzdem an das Python-Stacklimit stoßen.
- Die Version in `pyproject.toml` wird manuell parallel zu `deutsch/__init__.py`s `__version__`
  gepflegt (kein dynamisches Versioning-Setup).

## Projektstruktur

```
main.py              REPL / Datei-Runner / Fehleranzeige
deutsch/
  lexer.py            Tokenisierung
  parser.py            rekursiver Abstiegs-Parser
  ast_knoten.py         AST-Knotenklassen
  interpreter.py         Baum-Interpreter (Visitor-Pattern)
  umgebung.py            lexikalischer Geltungsbereich
beispiele/            Beispielskripte (.deu)
```

## Lizenz

GNU General Public License v3.0 oder später — siehe [LICENSE](LICENSE).
