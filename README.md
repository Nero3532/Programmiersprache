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
```

Verfügbare Typ-Hinweise: `Ganzzahl`, `Kommazahl` (akzeptiert auch Ganzzahl), `Zeichenkette`,
`Wahrheitswert`, `Liste`, `Woerterbuch`/`Wörterbuch`, `Nichts`, `Funktion`, oder ein
selbstdefinierter Klassenname. Ein unbekannter Typ-Hinweis wirft einen Fehler.

### Operatoren

Arithmetisch: `+ - * / % ** //` (Potenz, Ganzzahldivision), Verbund-Zuweisung: `+= -= *= /= %= **= //=`
Vergleich: `== != < > <= >=`
Logisch: `und oder nicht`
Mitgliedschaft: `in`, `nicht in`

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

### Module

```
lade "andere_datei.deu"
```

## Eingebaute Funktionen

**Allgemein:** `drucke`, `eingabe`, `laenge`/`länge`, `typ`, `ganzzahl`, `kommazahl`, `zeichenkette`,
`wahrheitswert`, `bereich`, `sortiere`, `anhaengen`/`anhängen`, `entferne`, `umkehren`, `verbinde`,
`max`, `min`, `abs`, `runde`, `liste`, `woerterbuch`/`wörterbuch`

**Mathe:** `pi`, `e` (Konstanten), `wurzel`, `sinus`, `kosinus`, `tangens`, `logarithmus`, `exponential`

**Datei-I/O:** `datei_lesen`, `datei_schreiben`, `datei_anhaengen`/`datei_anhängen`

Listen, Zeichenketten und Wörterbücher haben zusätzlich Methoden (`liste.laenge()`, `text.gross()`,
`dict.schluessel()`, …) — siehe [beispiele/alle_features.deu](beispiele/alle_features.deu) für eine
vollständige Demonstration.

## Bekannte Einschränkungen

- Kein Bytecode-Compiler — reiner Baum-Interpreter (bewusste Design-Entscheidung, siehe unten).
- Mehrfachvererbung nutzt einfache links-nach-rechts-Tiefensuche, keine echte C3-Linearisierung.
- Variadische Parameter (`*args`) werden nicht einzeln typgeprüft.
- `(-8) ** 0.5` liefert eine Python-`complex`-Zahl ohne dedizierte Formatierung.
- Rekursionslimit ist auf 10000 gesetzt (`sys.setrecursionlimit`), tief rekursive Deutsch-Programme
  können trotzdem an das Python-Stacklimit stoßen.

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
