# Entwurf P3b (sprache-architekt, 2026-11-20)

Nutzer-Entscheidungen: Iterator-Ende per `werfe IterationsEnde()`; Muster binden nur mit `sei`; `passe` als Ausdruck über Blöcke (letzter Wert); Generatoren `ergib` diese Runde als letzter Schritt.
Reihenfolge (interpreter.py nie zwei Schreiber): 1. Iterator-Protokoll (S/M, sonnet/medium) → 2. Mustervergleich (M, sonnet/high) → 3. Generatoren (M, sonnet/high; opus nur nach 2 Fehlversuchen).
Dunder-Hooks `__laenge__`/`__hole__`/`__setze__`/`__enthaelt__`/`__aufruf__` existieren (Commit 7950a82) — deren Hook-Helfer nutzen, nicht doppeln.

## 1) Iterator-Protokoll
- `klasse Z { funktion __iter__(dies) { zurück dies } funktion __naechstes__(dies) { wenn dies.i >= dies.n { werfe IterationsEnde() } dies.i += 1; zurück dies.i } }` → `für x in neu Z(3)`, `[x*2 für x in z]`, `sei [a, *r] = z`, `abbilden(z, f)`, `*z`, `liste(z)`. `__iter__` darf auch Liste/Zeichenkette/Generator liefern (dann kein `__naechstes__` nötig).
- `_iteriere()` erweitern: DeutschInstanz mit `__iter__` → aufrufen; Ergebnis mit `__naechstes__` → Python-Generator `while True: try x = __naechstes__() except _IterationsEndeFehler: return; yield x`.
- `IterationsEnde` als neuer FEHLERARTEN-Eintrag mit eigener Python-Basis `_IterationsEndeFehler(Exception)` — NICHT StopIteration (PEP 479 macht daraus in Generatoren RuntimeError).
- Abnehmer mit `isinstance(…, (list, set))` bekommen Rückfall `list(self._iteriere(w))` nur für Instanz/Generator: `_hof_elemente`, `_muster_zerlegen`, `_entpackte_elemente`/`_ENTPACKBAR`, `liste`, `menge`, `summe`, `alle`, `einige`, `aufzaehlen`, `zippe`, `sortiere`.
- Builtin `naechstes`/`nächstes(x)`: `__naechstes__` bzw. `next()`, StopIteration → IterationsEnde.
- `bereich` bleibt Liste. Schneller Pfad in `für`/ListenAusdruck: iterable ist Aufruf des Namens `bereich`, Wert ist wirklich das Builtin, ohne `*`/kwargs → direkt `range()`; gemeinsamer Helfer `_bereich_range(args)` auch für `_eb_bereich`.
- Tests: Instanz in für/Comprehension/Entpacken/abbilden/`*`; `__iter__` gibt Liste; IterationsEnde fangbar; `naechstes` am Ende; `bereich(3) == [0,1,2]`; `für i in bereich(10**12) { abbrechen }` endet sofort.

## 2) Mustervergleich
- Nur hinter `fall`, eigener `_muster_lesen` in parser.py (statt `_ausdruck`): Muster := Wert | `_` | `Typ name` | `sei [m, *rest]` | `sei {"k": m}`. Komma = Alternativen (gibt es schon). Danach optional `wenn bedingung`, dann `:` und Block.
- Werte mit `_koaleszenz()` lesen (ohne Ternär) → `wenn` ist Guard; Ternär als Wert nur in Klammern (einzige Bruchstelle, kommt in Tests/Beispielen nicht vor).
- Typmuster: `fall Ganzzahl n:`, `fall Punkt p:`, `fall WertFehler f:`, `fall Farbe f:` — Bezeichner/Punktpfad gefolgt von Bezeichner. Einzelner Bezeichner `fall x:` bleibt Wertvergleich. `fall Farbe.rot:` geht schon.
- `|` ist keine Alternative (bleibt Bit-Oder).
- Bindung NUR mit `sei` (Nutzer): `fall sei [a, *rest] wenn a > 0:`, `fall sei {"typ": t}:` — Namen binden, Literale/Punktpfade vergleichen. Ohne `sei` bleibt `fall [a, b]:` Vergleich wie heute.
- `passe` als Ausdruck (Nutzer): in `_primaer` erlauben; Wert = letzte Ausdrucksanweisung des Arm-Blocks. Kein Treffer im Ausdruck → WertFehler „kein 'fall' passt"; als Anweisung `nichts` wie heute.
- Interpreter `_muster_passt(m, wert, paare, u) -> bool` (wirft nicht): Wert `==`; `_` immer; Typmuster über Tabelle `primitive` aus `_pruefe_typ` (in Klassenkonstante ziehen) bzw. `_eb_ist_instanz` für Klassen/Vererbung/Aufzählungen/DeutschFehler; Liste über `_muster_teile(...) -> teile|None` (aus `_muster_zerlegen` auslagern, beide nutzen es); Wörterbuch: muss Wörterbuch sein und alle Schlüssel haben (mehr erlaubt), Teilmuster rekursiv.
- Scope: je Arm neue `Umgebung(u)`; Bindungen und Guard dort; Guard falsch → Scope verwerfen, nächster Arm.
- AST: `faelle` → `[(muster_liste, waechter|None, block)]`; neue Knoten `TypMuster`, `WoerterbuchMuster`; `Muster` mit Knoten-Zielen und `sei`-Flag wiederverwenden. Linter `_gebunden` kennt Arm-Bindungen. Alternativen mit Bindung nur bei gleicher Namensmenge, sonst Parserfehler. Prüfen, ob `__gleich__` beim Wertvergleich greift.
- Tests: Guard wahr/falsch, sieht Bindung; `sei [a, *rest]` leer/kurz/lang; Wörterbuch mit fehlendem Schlüssel; `Ganzzahl` passt nicht auf `wahr`; Klasse mit Vererbung; WertFehler aus fange und eigene Fehlerklasse; Bindung außerhalb des Arms unsichtbar; passe als Ausdruck mit/ohne Treffer; alte passe-Tests grün; Linter ohne Fehlwarnung.

## 3) Generatoren `ergib`
- Ohne Thread, ohne Greenlet (Abhängigkeit verboten; Thread je Generator bricht Stack/Rekursionslimit/Strg+C).
- `ergib ausdruck` nur als Anweisung (kein `sende`). Parser setzt `FunktionDefinition.ist_generator`, wenn `ergib` im eigenen Körper (nicht in inneren funktion/lambda/klasse). Neues Schlüsselwort `ergib` (kommt in Tests/Beispielen nicht als Name vor).
- `_funktion_aufrufen` nach Parameterbindung: `DeutschGenerator(self._gen_block(koerper, fn_u))` zurückgeben. Typname `Generator`.
- `_gen_*`-Besucher mit `yield from` nur für Block, Wenn, Solange, Für, Passe, Versuche, Ergib; alle anderen Anweisungen normal über `_besuche_anweisung`. `zurück` beendet den Generator.
- `DeutschGenerator.__next__` setzt bei jeder Fortsetzung `_aufruf_stack`, `_aktuelle_datei`, Zeile und setzt sie zurück (wie in `_funktion_aufrufen`). fange-Prüfung aus Versuche in einen Helfer ziehen (nicht doppeln). Bei Abbruch läuft `endlich` erst über `close()`/GC.
- Tests: unendlich + abbrechen; `ergib` in wenn/solange/für/passe/versuche (jeder Anweisungstyp einmal); `zurück`; `endlich`; richtige Fehlerzeile im Körper; Strg+C im Generator (test_main); Generator in abbilden/liste/Entpacken.
- Restrisiko: `_gen_*` kopiert Kontrollfluss — Tests müssen jeden Anweisungstyp mit `ergib` abdecken.
