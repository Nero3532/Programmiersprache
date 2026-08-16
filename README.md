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
```

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
```

### Fehlerbehandlung

```
versuche {
    werfe "Etwas ist schiefgelaufen"   # beliebiger Wert werfbar, nicht nur Strings
} fange fehler {
    drucke(fehler)
} endlich {
    drucke("Immer ausgeführt")
}
```

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
```

## Eingebaute Funktionen

**Allgemein:** `drucke`, `eingabe`, `laenge`/`länge`, `typ`, `ganzzahl`, `kommazahl`, `zeichenkette`,
`wahrheitswert`, `bereich`, `sortiere`, `anhaengen`/`anhängen`, `entferne`, `umkehren`, `verbinde`,
`max`, `min`, `abs`, `runde`, `liste`, `woerterbuch`/`wörterbuch`

**Mathe:** `pi`, `e` (Konstanten), `wurzel`, `sinus`, `kosinus`, `tangens`, `logarithmus`, `exponential`,
`boden`, `decke`

**Zufall:** `zufall()` (Kommazahl in [0,1)), `zufallszahl(min, max)` (Ganzzahl, beide Enden
eingeschlossen), `mische(liste)` (mischt in-place)

**Funktional:** `summe`, `alle`, `einige`, `aufzaehlen`, `zippe`

**Datei-I/O:** `datei_lesen`, `datei_schreiben`, `datei_anhaengen`/`datei_anhängen`

**JSON:** `json_lesen`, `json_schreiben` (Mengen werden beim Schreiben automatisch zu sortierten
Listen konvertiert)

**Regex:** `passt_zu(muster, text)`, `regex_ersetze(muster, ersatz, text)`, `regex_finde(muster, text)`
(erster Treffer oder `nichts`), `regex_finde_alle(muster, text)` — nutzt Pythons `re`-Syntax

**Mengen:** `menge` (Umwandlung/leere Menge)

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
