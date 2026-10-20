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
python main.py datei.deu a b        # Argumente: kommandozeilen_argumente() → ["a", "b"]
python main.py -c "drucke(1 + 2)"   # Code direkt ausführen
python main.py --pruefen datei.deu  # nur auf Syntaxfehler prüfen, nichts ausführen
python main.py --version            # Version (auch -V)
python main.py --hilfe              # alle Optionen (auch -h, --help)
```

Alternativ installierbar:

```
pip install -e .
deutsch                     # interaktive REPL
deutsch datei.deu           # Datei ausführen
```

Als Modul, mit denselben Optionen wie `main.py` (unter Linux/macOS `python3 -m deutsch`):

```
py -m deutsch -c "drucke(2 ** 10)"
```

In der REPL zeigt `hilfe` die Befehle, `beenden` verlässt sie.

## Sprachüberblick

### Variablen & Typen

```
sei x = 5                    # Ganzzahl
sei y = 3.14                 # Kommazahl
sei s = "Text"                # Zeichenkette
sei b = wahr                  # Wahrheitswert (wahr/falsch)
sei n = nichts                 # Nichts (null)
sei hex = 0xFF                # Zahlliterale: 0x Hex, 0b Binär, 0o Oktal
sei million = 1_000_000       # Unterstriche zwischen Ziffern
sei liste = [1, 2, 3]
sei dict = {"a": 1, "b": 2}

sei alter: Ganzzahl = 25      # optionaler, zur Laufzeit geprüfter Typ-Hinweis

sei [a, b, c] = [1, 2, 3]     # Destrukturierung
sei [kopf, *rest] = [1, 2, 3] # Rest-Muster: rest ist [2, 3]
sei [x, [y, z]] = [1, [2, 3]] # verschachtelte Muster

konstante PI = 3.14159        # unveränderlich — Neuzuweisung wirft TypeError
```

Neue Variablen entstehen nur durch `sei`; eine Zuweisung an einen nicht deklarierten Namen wirft `NameError`.
Typ-Hinweise werden bei jeder Zuweisung und bei `+=` geprüft, nicht nur bei der Deklaration.

Verfügbare Typ-Hinweise: `Ganzzahl`, `Kommazahl` (akzeptiert auch Ganzzahl), `Zeichenkette`,
`Wahrheitswert`, `Liste`, `Woerterbuch`/`Wörterbuch`, `Menge`, `Nichts`, `Funktion`, oder ein
selbstdefinierter Klassenname. Ein unbekannter Typ-Hinweis wirft einen Fehler.

Destrukturierende Zuweisung funktioniert auch ohne `sei`, an Variablen, Attribute und Indizes. Die rechte
Seite wird vollständig ausgewertet, bevor zugewiesen wird. Ohne `*rest` muss die Anzahl passen. Muster gelten
auch für `für`-Schleifen und Comprehensions. Kettenzuweisung `a = b = 0` setzt bestehende Ziele auf denselben
Wert; `sei a = b = 0` ist ein Syntaxfehler.

```
sei a = 1
sei b = 2
[a, b] = [b, a]               # Tausch: a ist 2, b ist 1
a = b = 0                     # Kettenzuweisung
```

### Operatoren

Arithmetisch: `+ - * / % ** //` (Potenz, Ganzzahldivision), Verbund-Zuweisung: `+= -= *= /= %= **= //=`
Vergleich: `== != < > <= >=` — auch verkettet: `1 < x < 10` (jeder Operand nur einmal ausgewertet)
Logisch: `und oder nicht`
Bitweise: `& | ^ ~` und Schieben `<< >>` für Ganzzahlen; Verbund-Zuweisung `&= |= ^= <<= >>=`
Mitgliedschaft: `in`, `nicht in`
Null-Koaleszenz: `a ?? b` (liefert `b` nur, wenn `a` gleich `nichts` ist)
Ternär: `dann_wert wenn bedingung sonst sonst_wert`

```
0xFF & 0b1010                 # 10
1 << 4                        # 16
sei name = nichts
drucke(name ?? "Gast")        # Gast
```

Vorrang (schwach → stark): Ternär `wenn … sonst` · `??` · `oder` · `und` · `nicht` · Vergleiche und `in` ·
`|` · `^` · `&` · `<< >>` · `+ -` · `* / % //` · unär `- ~` · `**`.
Wie in Python binden `& | ^` stärker als Vergleiche: `x & 1 == 0` ist `(x & 1) == 0`.

`nicht` bindet schwächer als Vergleiche (wie in Python): `nicht a == b` ist `nicht (a == b)`. Steht `nicht`
als Operand, etwa in `a == nicht b`, ist das ein Syntaxfehler; dann Klammern setzen: `a == (nicht b)`.

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
Außerhalb einer Schleife ist beides ein Fehler, auch innerhalb einer Funktion, die aus einer Schleife aufgerufen wird.

### Funktionen

```
funktion addiere(a: Ganzzahl, b: Ganzzahl = 10) -> Ganzzahl {
    zurück a + b
}

sei quadrat = funktion(x) { zurück x * x }   # anonyme Funktion / Lambda
sei kubik = funktion(x) -> x * x * x          # Kurzform: '-> ausdruck' statt '{ zurück … }'
funktion verdopple(x) -> x * 2                # Kurzform auch benannt

funktion summe(*zahlen) {                     # variadische Parameter
    sei s = 0
    für z in zahlen { s += z }
    zurück s
}

# **optionen sammelt überzählige Keyword-Argumente
funktion anzeigen(a, **optionen) { zurück [a, optionen] }

addiere(b=5, a=3)          # Keyword-Argumente, beliebige Reihenfolge
addiere(3, b=5)             # gemischt — positional muss vor Keyword stehen
anzeigen(1, x = 2)           # [1, {x: 2}]
sei werte = [3, 5]
addiere(*werte)              # 8
addiere(**{"a": 3, "b": 5})  # 8
```

`*liste` und `**wb` entpacken beim Aufruf (auch bei `neu K(…)` und Methoden). In der Parameterliste sammelt
`*name` überzählige Positionsargumente und `**name` überzählige Keyword-Argumente in einem Wörterbuch;
`**name` muss der letzte Parameter sein.

Der Ausdruck nach `->` reicht so weit wie möglich (wie Pythons `lambda`). Innerhalb von `( … )` dürfen
Aufrufe, Parameterlisten und Klammerausdrücke über mehrere Zeilen gehen, auch mit einem abschließenden Komma.

```
abbilden([1, 2, 3], funktion(x) -> x * 10)          # [10, 20, 30]
filtere([1, 2, 3, 4], funktion(x) -> x % 2 == 0)    # [2, 4]
reduziere([1, 2, 3, 4], funktion(a, b) -> a + b)    # 10 (Startwert optional als 3. Argument)
[3, 1, 2].filtere(funktion(x) -> x > 1).abbilden(funktion(x) -> x * 2)   # [6, 4]
sortiere(["bb", "a", "ccc"], schluessel=laenge)     # [a, bb, ccc]
```

`abbilden`, `filtere` und `reduziere` nehmen Listen, Mengen (in sortierter Reihenfolge) und Zeichenketten;
`abbilden` und `filtere` liefern immer eine Liste. Die Methodenform gibt es für Listen. `sortiere`, `max` und
`min` nehmen `schluessel=f` (auch `schlüssel=`), `sortiere` zusätzlich `umgekehrt=wahr`.

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

**Operator-Überladung:** Klassen können `+ - * / // % **` und `== != < > <= >=` selbst definieren
über `__addiere__`, `__subtrahiere__`, `__multipliziere__`, `__dividiere__`, `__ganzdividiere__`,
`__modulo__`, `__potenziere__`, `__gleich__`, `__ungleich__`, `__kleiner__`, `__groesser__`,
`__kleinergleich__`, `__groessergleich__` (jeweils `(dies, andere)`). Nur der linke Operand wird
geprüft (kein `__radd__`-Äquivalent), jeder Operator braucht seine eigene Methode.

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

Entpacken mit `*` (Listen, Mengen, Zeichenketten, Bereiche) und `**` (Wörterbücher) in Literalen. Das Ergebnis
ist immer eine neue Sammlung; bei Wörterbüchern gewinnt der später stehende Schlüssel.

```
sei a = [1, 2]
[*a, *a, 3]                       # [1, 2, 1, 2, 3]
{**{"x": 1}, **{"x": 2, "y": 3}}  # {"x": 2, "y": 3}
{*[1, 2], *[2, 3]}                # {1, 2, 3}
```
Wörterbuch- und Mengen-Entpacken lassen sich in einem Literal nicht mischen.

### Mengen

```
sei m1 = {1, 2, 3}
sei m2 = {2, 3, 4}
m1.vereinigung(m2)     # {1, 2, 3, 4}
m1.schnittmenge(m2)    # {2, 3}
m1.differenz(m2)       # {1}
menge([1, 1, 2, 2])    # {1, 2} – Umwandlung/Deduplizierung, menge() ohne Argument = leere Menge
```
Die Operatoren `&` (Schnitt), `|` (Vereinigung) und `^` (symmetrische Differenz) funktionieren auch auf Mengen:
`m1 & m2` ist `{2, 3}`.

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

lade "andere_datei.deu" als modul   # Namensraum statt globaler Vermischung
modul.funktion()
modul.KONSTANTE
neu modul.Klasse(1, 2)                  # Klasse aus dem Modul
```
Ohne `als` landen alle Top-Level-Definitionen der geladenen Datei im globalen Scope (wie bisher).
Mit `als name` läuft die Datei in einem isolierten Scope; ihre Top-Level-Bindungen werden stattdessen
unter `name.attribut` erreichbar, ohne den aufrufenden Scope zu verändern.
Relative Pfade in `lade` gelten ab dem Ordner der ladenden Datei.

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

**Funktional:** `summe`, `alle`, `einige`, `aufzaehlen`, `zippe`, `abbilden`, `filtere`, `reduziere`

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

## Bekannte Einschränkungen

- Kein Bytecode-Compiler — reiner Baum-Interpreter (bewusste Design-Entscheidung, siehe unten).
- Mehrfachvererbung nutzt einfache links-nach-rechts-Tiefensuche, keine echte C3-Linearisierung.
- Variadische Parameter (`*args`) werden nicht einzeln typgeprüft.
- `(-8) ** 0.5` liefert eine Python-`complex`-Zahl ohne dedizierte Formatierung.
- Rekursionstiefe: ca. 5900 Deutsch-Aufrufe (Ausführung in einem Thread mit 128-MB-Stack; fällt der Stack
  kleiner aus, sinkt die Grenze entsprechend). Darüber bricht das Programm mit einem Rekursionsfehler ab.
- Die Version in `pyproject.toml` wird manuell parallel zu `deutsch/__init__.py`s `__version__`
  gepflegt (kein dynamisches Versioning-Setup).

## Projektstruktur

```
main.py              REPL / Datei-Runner / Fehleranzeige
deutsch/
  __main__.py          Aufruf als Modul (py -m deutsch)
  lexer.py            Tokenisierung
  parser.py            rekursiver Abstiegs-Parser
  ast_knoten.py         AST-Knotenklassen
  interpreter.py         Baum-Interpreter (Visitor-Pattern)
  umgebung.py            lexikalischer Geltungsbereich
beispiele/            Beispielskripte (.deu)
```

## Lizenz

GNU General Public License v3.0 oder später — siehe [LICENSE](LICENSE).
