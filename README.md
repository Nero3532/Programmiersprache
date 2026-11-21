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
python main.py --pruefen datei.deu  # auf Syntaxfehler und Hinweise prüfen, nichts ausführen
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

### `--pruefen`: Prüfung ohne Ausführung

`python main.py --pruefen datei.deu` führt Lexer, Parser und einen Linter aus, das Programm läuft nicht. Der Linter meldet drei Hinweise (lieber auslassen als falsch melden):

- **unbekannter Name**: Name wird gelesen, aber nirgends angelegt; bei Tippfehlern mit Vorschlag
- **unbenutzte Variable**: `sei`-Variable in einer Funktion oder Methode wird nie gelesen (Namen mit `_` am Anfang und Konstanten ausgenommen)
- **unerreichbarer Code**: Anweisung direkt nach `zurück`, `abbrechen`, `weiter` oder `werfe` im selben Block

Ausgabe je Hinweis `Datei:Zeile: Hinweis: Text`, am Ende eine Zusammenfassung. Exitcode `0`, außer bei einem Syntaxfehler (dann Exitcode `1`, Meldung auf stderr).

```
$ python main.py --pruefen beispiel.deu
beispiel.deu:2: Hinweis: unbekannter Name 'anzal' – meintest du 'anzahl'?
beispiel.deu:4: Hinweis: Variable 'x' wird angelegt, aber nie gelesen
beispiel.deu:6: Hinweis: unerreichbarer Code
beispiel.deu: keine Syntaxfehler, 3 Hinweise
```

Dazu passende `beispiel.deu`:

```
sei anzahl = 1
drucke(anzal)
funktion f() {
    sei x = 2
    zurück 1
    drucke(3)
}
```

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

konstante PI = 3.14159        # unveränderlich — Neuzuweisung wirft TypFehler
```

Neue Variablen entstehen nur durch `sei`; eine Zuweisung an einen nicht deklarierten Namen wirft `NamensFehler`.
Typ-Hinweise werden bei jeder Zuweisung und bei `+=` geprüft, nicht nur bei der Deklaration. Das gilt auch für
Parameter: Ein Parameter mit Typ-Hinweis wird bei Neuzuweisung im Funktionskörper geprüft. Bei `*args: T` und
`**kw: T` prüft der Hinweis jedes Element bzw. jeden Wert einzeln.

Verfügbare Typ-Hinweise: `Ganzzahl`, `Kommazahl` (akzeptiert auch Ganzzahl), `Zeichenkette`,
`Wahrheitswert`, `Liste`, `Woerterbuch`/`Wörterbuch`, `Menge`, `Nichts`, `Funktion`, oder ein
selbstdefinierter Klassenname, auch als Punktpfad `modul.Klasse` (siehe Abschnitt Module). Ein unbekannter
Typ-Hinweis wirft einen Fehler.

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
Null-Koaleszenz: `a ?? b` (liefert `b` nur, wenn `a` gleich `nichts` ist), Verbund-Zuweisung `a ??= b`
Optional-Chaining: `a?.b` und `a?.m()` ergeben `nichts`, wenn `a` gleich `nichts` ist; dann wird die ganze Kette übersprungen
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

#### Mustervergleich in `passe` / `fall`

```
passe wert {
    fall sei [kopf, *rest]: { ... }      # Liste mit Rest: rest ist die Restliste
    fall sei {"typ": t, "r": r}: { ... } # Wörterbuch: Schlüssel prüfen und binden
    fall Ganzzahl n: { ... }             # Typmuster: nur wenn Typ passt
    fall Ganzzahl n wenn n > 5: { ... } # Wächter: zusätzliche Bedingung nach "wenn"
    fall _: { ... }                      # Platzhalter: passt auf alles, bindet nichts
    sonst: { ... }
}
```

- `sei` vor dem Muster bindet Namen. Die Bindungen sind nur im zugehörigen Arm sichtbar.
- Ohne `sei` bleibt `fall [a, b]` ein Vergleich: Namen werden nicht gebunden, `fall [1, 2]` prüft Gleichheit.
- Ein einzelner Name ohne `sei` ist ebenfalls ein Wertvergleich; `fall sei x` bindet alles.
- Mehrere Alternativen mit Komma: `fall 1, 2, 3: { ... }` (mit `sei` müssen alle Alternativen dieselben Namen binden).
- `passe` ist auch ein Ausdruck: der Wert des Arms ist das Ergebnis. Passt kein Arm und fehlt `sonst`, gibt es einen `WertFehler` (fangbar mit `fange`).

```
sei r = passe 2 { fall 1: { "eins" } fall 2: { "zwei" } }
drucke(r)                                   # zwei
sei [kopf, *rest] = [1, 2, 3]
passe [1, 2, 3] { fall sei [kopf, *rest]: { drucke(rest) } }   # [2, 3]
```

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

`abbilden`, `filtere` und `reduziere` nehmen Listen, Mengen (in sortierter Reihenfolge), Wörterbücher (Schlüssel) und Zeichenketten;
`abbilden` und `filtere` liefern immer eine Liste. Die Methodenform gibt es für Listen. `sortiere`, `max` und
`min` nehmen `schluessel=f` (auch `schlüssel=`), `sortiere` zusätzlich `umgekehrt=wahr`.

#### Dekoratoren

Eine Zeile `@ausdruck` vor `funktion` (auch vor Methoden und `statisch funktion`) gibt die Funktion an einen
Dekorator weiter; die Rückgabe ersetzt die Funktion. Mit Argumenten (`@name(args)`) und Punktpfad (`@m.name`) geht es auch.
Mehrere Dekoratoren werden wie in Python angewendet: Ausdrücke von oben nach unten ausgewertet, angewendet von unten nach oben.

```
funktion memo(f) {
    sei cache = {}
    zurück funktion(x) {
        wenn x nicht in cache { cache[x] = f(x) }
        zurück cache[x]
    }
}

funktion zaehlt(f) {
    sei aufrufe = 0
    zurück funktion(x) {
        aufrufe += 1
        drucke("Aufruf {aufrufe}")
        zurück f(x)
    }
}

@memo
funktion quadrat(x) -> x * x
@zaehlt
funktion verdopple(x) -> x * 2

quadrat(4)     # 16
quadrat(4)     # 16 (aus dem Cache)
verdopple(3)   # Aufruf 1, dann 6
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
    konstante MAX = 1000                      # Klassenkonstante — Neuzuweisung wirft TypFehler
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

**Operator-Überladung:** Klassen können `+ - * / // % **`, `& | ^ << >>` und `== != < > <= >=` selbst definieren
über `__addiere__`, `__subtrahiere__`, `__multipliziere__`, `__dividiere__`, `__ganzdividiere__`,
`__modulo__`, `__potenziere__`, `__bitund__`, `__bitoder__`, `__bitxoder__`, `__links__`, `__rechts__`,
`__gleich__`, `__ungleich__`, `__kleiner__`, `__groesser__`, `__kleinergleich__`, `__groessergleich__`
(jeweils `(dies, andere)`); unäres `~` über `__bitnicht__(dies)`. Nur der linke Operand wird
geprüft (kein `__radd__`-Äquivalent), jeder Operator braucht seine eigene Methode.

**Sammlungs-Hooks:** Klassen verhalten sich wie eingebaute Sammlungen über `__laenge__(dies)`,
`__hole__(dies, schluessel)` und `__setze__(dies, schluessel, wert)` (für `länge`, `x[i]` und `x[i] = w`),
`__enthaelt__(dies, wert)` (für `in` / `nicht in`) sowie `__aufruf__(dies, ...)` (für `x(...)`).
Slices kommen als `Teilbereich`-Objekt an (`.anfang`, `.ende`, `.schritt`; nicht angegebene Teile sind `nichts`).
Fehlt ein Hook, gibt es eine deutsche Meldung; falsche Rückgabetypen werden ebenfalls gemeldet.

```
klasse Stapel {
    funktion __init__(dies, werte) { dies.daten = werte }
    funktion __laenge__(dies) { zurück länge(dies.daten) }
    funktion __hole__(dies, s) {
        wenn typ(s) == "Teilbereich" { zurück neu Stapel(dies.daten[s.anfang:s.ende]) }
        zurück dies.daten[s]
    }
    funktion __setze__(dies, s, w) { dies.daten[s] = w }
    funktion __enthaelt__(dies, w) { zurück w in dies.daten }
    funktion __aufruf__(dies, x) { zurück dies.daten[x] + 1 }
}
sei l = neu Stapel([10, 20, 30, 40])
drucke(länge(l), l[2], länge(l[1:3]), 30 in l, l(2))   # 4 30 2 wahr 31
l[0] = 7
drucke(l.daten)                                        # [7, 20, 30, 40]
```

### Eigene Iteratoren

Eine Klasse mit `__iter__` ist in `für`, Comprehensions, Entpacken, `liste`, `menge`, `summe`, `abbilden` & Co. iterierbar.
`__iter__` liefert entweder eine Sammlung oder ein Objekt mit `__naechstes__`. Das Ende meldet `__naechstes__`
mit `werfe IterationsEnde()`; `naechstes(it)` ruft `__naechstes__` direkt auf.

```
klasse Zaehler {
    funktion __init__(dies, n) { dies.n = n
        dies.i = 0 }
    funktion __iter__(dies) { zurück dies }
    funktion __naechstes__(dies) {
        wenn dies.i >= dies.n { werfe IterationsEnde() }
        dies.i += 1
        zurück dies.i
    }
}
für x in neu Zaehler(3) { drucke(x) }      # 1 2 3
drucke(summe(neu Zaehler(4)))              # 10
```

### Generatoren

Eine Funktion mit `ergib` liefert beim Aufruf einen Generator statt eines Werts. Der Rumpf läuft erst weiter, wenn der
Generator abgefragt wird; `zurück` beendet ihn. Läuft ohne Threads im selben Thread.

```
funktion nat() { sei i = 0
    solange wahr { ergib i
        i += 1 } }
für x in nat() { wenn x > 3 { abbrechen }
    drucke(x) }                            # 0 1 2 3
funktion zwei() { ergib 1
    zurück
    ergib 2 }
drucke(liste(zwei()))                      # [1]
```

- Unendliche Generatoren nur mit `abbrechen` in `für` oder mit `naechstes(g)` abfragen, sonst läuft die Schleife ewig.
- Nutzung: `für`, `liste`, `summe`, `abbilden` & Co., Comprehensions, Entpacken (`sei [a, b] = f()`), `naechstes(g)`.
- Typname: `typ(g)` ergibt `Generator`.
- Grenzen: `ergib` nur im Rumpf einer Funktion, nicht außerhalb und nicht in einem `passe`-Ausdruck.
- Vorzeitiges Ende: `für` schließt einen Generator bei `abbrechen`, `zurück` oder Fehler sofort, sein `endlich` läuft dann. Ein bei Programmende noch angehaltener Generator oder einer, der nur in einer Listen-Comprehension abbricht, führt sein `endlich` nicht verlässlich aus.

### Aufzählungstypen

```
aufzaehlung Farbe { rot, gruen, blau }       # ohne Wert: ab 0
drucke(Farbe.gruen, Farbe.gruen.name, Farbe.gruen.wert)   # Farbe.gruen gruen 1
für f in Farbe { drucke(f.name) }                          # rot, gruen, blau
sei x: Farbe = Farbe.blau                                  # Typ-Hinweis, zur Laufzeit geprüft
funktion n(f) { passe f { fall Farbe.rot: { zurück "R" } sonst: { zurück "?" } } }
versuche { Farbe.rot = 1 } fange (TypFehler) e { drucke("nicht änderbar") }
```
Schlüsselwort auch als `aufzählung`. Mit Werten: `aufzaehlung Stufe { niedrig = 1, hoch = 10 }`; entweder alle Mitglieder mit oder alle ohne Wert.
`name` ist Text, `wert` die Zahl. Vergleich nur mit `==` und `!=`; `<` wirft `TypFehler`.
Werte sind beliebige Ausdrücke, einmal beim Anlegen ausgewertet. Mitglieder und ihre Attribute
sind unveränderlich (`TypFehler`); unbekannte Mitglieder ergeben `AttributFehler`.

### Fehlerbehandlung

```
versuche {
    werfe "Etwas ist schiefgelaufen"   # beliebiger Wert werfbar, nicht nur Strings
} fange fehler {
    drucke(fehler)
} endlich {
    drucke("Immer ausgeführt")
}

pruefe 1 + 1 == 2                       # ZusicherungsFehler bei Fehlschlag
pruefe x > 0, "x muss positiv sein"     # optionale eigene Meldung

versuche {
    sei d = {}
    d["fehlt"]
} fange (SchluesselFehler, IndexFehler) f {   # nur diese Fehlerarten fangen, Rest propagiert weiter
    drucke(f)
}
```
Die Fehlerarten haben deutsche Namen; sie stehen auch im Fehlerkopf der CLI, z. B.
`[DivisionDurchNullFehler] Zeile 1: Division durch Null`:

| Deutsch | Python | Deutsch | Python |
|---|---|---|---|
| `Fehler` | `Exception` (Oberbegriff, fängt alles) | `LaufzeitFehler` | `RuntimeError` |
| `TypFehler` | `TypeError` | `RekursionsFehler` | `RecursionError` |
| `WertFehler` | `ValueError` | `ZusicherungsFehler` | `AssertionError` |
| `NamensFehler` | `NameError` | `ImportFehler` | `ImportError` |
| `IndexFehler` | `IndexError` | `EingabeEndeFehler` | `EOFError` |
| `SchluesselFehler` | `KeyError` | `DivisionDurchNullFehler` | `ZeroDivisionError` |
| `AttributFehler` | `AttributeError` | `UeberlaufFehler` | `OverflowError` |
| `DateiFehler` | `OSError` | `SyntaxFehler` | `SyntaxError` |

`IterationsEnde` ist keine Python-Art, sondern eine eigene Basis (nicht `StopIteration`). Sie wird nur im Iterator-Protokoll
von `__naechstes__` geworfen (siehe „Eigene Iteratoren“); `fange (IterationsEnde)` fängt sie.

`fange (…)` versteht diese Namen und die englischen Python-Namen (`fange (KeyError) f`), auch gemischt.
Mit Vererbung: `fange (DateiFehler)` fängt auch `FileNotFoundError`, `fange (LaufzeitFehler)`
fängt auch `RekursionsFehler`. `fange (Fehler)` fängt alles, auch mit `werfe` geworfene Werte.
Mit `werfe` geworfene Werte, die keine Fehler sind, haben die Art `AusnahmeFehler`
(`fange (AusnahmeFehler) e { … }`) und werden von den übrigen Arten nicht gefangen. Ein unbekannter Name,
etwa ein Tippfehler, wirft einen `NamensFehler` mit Vorschlag (`meintest du 'WertFehler'?`).

Ohne Typ-Liste (`fange f { ... }`) bleibt das bisherige Verhalten: alles wird gefangen.

#### Eigene Fehlerklassen

Eigene Fehlerklassen erben von einer deutschen Fehlerart und sind unter deutschem und englischem Namen fangbar.
Sie werden mit `neu` erzeugt; Fehlerklassen können auch ohne `neu` geworfen werden, dann mit `werfe WertFehler("…")`:

```
klasse MeinFehler(WertFehler) {
    funktion __init__(dies, text, code) {
        dies.nachricht = text
        dies.code = code
    }
}

versuche {
    werfe neu MeinFehler("kaputt", 3)
} fange (MeinFehler) f {
    drucke(f.nachricht, f.art, f.zeile, f.datei, f.code)
}
```

- Das Fehlerobjekt (`f`) hat `nachricht`, `art`, `zeile` und `datei`; es bleibt als Zeichenkette verwendbar.
- `ist_instanz(f, WertFehler)` prüft die Art, auch über Vererbung.
- `fange (m.MeinFehler)` mit Punktpfad fängt eine Klasse aus einem geladenen Modul.
- Wird ein gefangener Fehler mit `werfe f` erneut geworfen, behält er Art, Meldung und Ort.

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
klasse Hund(modul.Tier) { }             # Basisklasse aus dem Modul
sei t: modul.Tier = neu Hund()          # Typ-Hinweis mit Punktpfad
```
Ohne `als` landen alle Top-Level-Definitionen der geladenen Datei im globalen Scope (wie bisher).
Mit `als name` läuft die Datei in einem isolierten Scope; ihre Top-Level-Bindungen werden stattdessen
unter `name.attribut` erreichbar, ohne den aufrufenden Scope zu verändern.
Relative Pfade in `lade` gelten ab dem Ordner der ladenden Datei. Basisklassen und Typ-Hinweise akzeptieren einen
Punktpfad `modul.Name`; bei Parametern und Rückgabetyp wird er dort aufgelöst, wo die Funktion definiert ist.

Zyklische Importe (A lädt B, B lädt A) werden erkannt und werfen einen klaren `ImportFehler`
statt in eine Endlosschleife zu laufen. Mehrfaches (nicht-zyklisches) Laden derselben Datei ist
erlaubt und führt sie erneut aus.

## Eingebaute Funktionen

**Allgemein:** `drucke`, `eingabe`, `laenge`/`länge`, `typ`, `ganzzahl`, `kommazahl`, `zeichenkette`,
`wahrheitswert`, `bereich`, `sortiere`, `anhaengen`/`anhängen`, `entferne`, `umkehren`, `verbinde`,
`max`, `min`, `abs`, `runde`, `liste`, `woerterbuch`/`wörterbuch`, `eindeutig`, `zusammenfuehren`/`zusammenführen`

`bereich` liefert eine Liste; direkt in `für` oder einer Comprehension läuft es lazy, ohne Liste im Speicher
(`für i in bereich(10**12) { wenn i >= 2 { abbrechen } }` startet sofort).

`runde` rundet kaufmännisch (ab ,5 vom Nullpunkt weg): `runde(2.5)` ergibt 3, `runde(2.675, 2)` ergibt 2.68.

**Mathe:** `pi`, `e` (Konstanten), `wurzel`, `sinus`, `kosinus`, `tangens`, `arcsin`, `arccos`, `arctan`,
`arctan2`, `logarithmus`, `exponential`, `boden`, `decke`, `ggt`, `kgv`, `vorzeichen`

**Zufall:** `zufall()` (Kommazahl in [0,1)), `zufallszahl(min, max)` (Ganzzahl, beide Enden
eingeschlossen), `mische(liste)` (mischt in-place)

**Funktional:** `summe`, `alle`, `einige`, `aufzaehlen`, `zippe`, `abbilden`, `filtere`, `reduziere`, `gruppiere`

**Datei-I/O:** `datei_lesen`, `datei_schreiben`, `datei_anhaengen`/`datei_anhängen`, `zeilen_lesen`,
`datei_loeschen`/`datei_löschen`, `umbenennen`

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
`datum_lesen(text, format)` ist das Gegenstück (liefert Epoch-Sekunden), `warte(sekunden)` hält die Ausführung an.

**Kopieren:** `tiefe_kopie(wert)` — rekursive Kopie verschachtelter Listen/Wörterbücher/Mengen/
Instanzen (im Unterschied zum flachen `.kopiere()`); bei selbstreferenziellen Strukturen
(`l.anhängen(l)`) `RekursionsFehler` statt Endlosschleife

**Hashing/Kodierung:** `hash_sha256`, `base64_kodieren`, `base64_dekodieren`

**Dateisystem:** `pfad_existiert`, `dateien_auflisten`, `ordner_erstellen`, `ist_datei`, `ist_ordner`,
`pfad_verbinden`, `dateiname`, `ordnername`, `endung`

**System:** `kommandozeilen_argumente()` — Argumente hinter dem Skriptnamen
(`deutsch skript.deu a b` → `["a", "b"]`), `umgebungsvariable(name)`/`umgebungsvariable(name, standard)`

Listen, Zeichenketten, Wörterbücher und Mengen haben zusätzlich Methoden (`liste.laenge()`, `text.gross()`,
`dict.schluessel()`, `menge.vereinigung()`, …) — siehe [beispiele/alle_features.deu](beispiele/alle_features.deu)
für eine vollständige Demonstration.

**Zeichenketten-Methoden:** `links_auffuellen(breite[, zeichen])` (auch `links_auffüllen`),
`rechts_auffuellen(breite[, zeichen])` (auch `rechts_auffüllen`), `zentrieren(breite[, zeichen])`,
`ersetze(alt, neu[, anzahl])`.

**Listen-Methoden:** `eindeutig()`, `max()` und `min()` (mit `schluessel=`).

**Wörterbuch-Methoden:** `zusammenfuehren(…)` (auch `zusammenführen`).

## Bekannte Einschränkungen

- Kein Bytecode-Compiler — reiner Baum-Interpreter (bewusste Design-Entscheidung, siehe unten).
- Mehrfachvererbung nutzt einfache links-nach-rechts-Tiefensuche, keine echte C3-Linearisierung.
- `(-8) ** 0.5` liefert eine Python-`complex`-Zahl ohne dedizierte Formatierung.
- Rekursionstiefe: ca. 5950 Deutsch-Aufrufe bei einfacher Rekursion (Ausführung in einem Thread mit 128-MB-Stack;
  fällt der Stack kleiner aus, sinkt die Grenze entsprechend). Darüber bricht das Programm mit einem Rekursionsfehler ab.
- Die Version in `pyproject.toml` wird manuell parallel zu `deutsch/__init__.py`s `__version__`
  gepflegt (kein dynamisches Versioning-Setup).

## Editor

Syntax-Hervorhebung für VS Code (`.deu`): siehe [editor/vscode/README.md](editor/vscode/README.md).

## Projektstruktur

```
main.py              REPL / Datei-Runner / Fehleranzeige
deutsch/
  __main__.py          Aufruf als Modul (py -m deutsch)
  lexer.py            Tokenisierung
  token_typen.py      Token-Arten
  parser.py            rekursiver Abstiegs-Parser
  ast_knoten.py         AST-Knotenklassen
  interpreter.py         Baum-Interpreter (Visitor-Pattern)
  umgebung.py            lexikalischer Geltungsbereich
beispiele/            Beispielskripte (.deu)
```

## Lizenz

GNU General Public License v3.0 oder später — siehe [LICENSE](LICENSE).
