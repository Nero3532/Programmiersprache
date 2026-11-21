# -*- coding: utf-8 -*-
"""Formatierer v1: zeilenbasiert, erhält Kommentare, ändert nur Einrückung und Leerraum.

Die Zeichenketten-/Klammer-Abtastung kommt aus main.py (wie die REPL); main wird
erst beim Aufruf importiert, weil main.py selbst diesen Formatierer lädt.
"""
import os
import sys

EINRUECKUNG = '    '


def formatiere(text: str) -> str:
    """Formatiert Quelltext mit LF-Zeilenenden; gibt den neuen Text zurück."""
    import main
    zeilen = text.split('\n')
    aus = []
    tiefe = 0
    leer = 0
    i = 0
    while i < len(zeilen):
        inhalt = zeilen[i].lstrip(' \t')
        if not inhalt.strip():
            leer += 1
            if leer <= 2:
                aus.append('')
            i += 1
            continue
        leer = 0
        saldo, offen, _ = main._eingabe_abtasten(inhalt)
        ende = i
        while offen and ende + 1 < len(zeilen):   # mehrzeilige """-Zeichenkette
            ende += 1
            saldo, offen, _ = main._eingabe_abtasten('\n'.join([inhalt] + zeilen[i + 1:ende + 1]))
        stufe = max(tiefe - (1 if inhalt[0] in ')]}' else 0), 0)
        if ende == i:
            aus.append(EINRUECKUNG * stufe + inhalt.rstrip())
        else:   # Anfangszeile behält Zeilenende (liegt in der Zeichenkette), Inhalt unverändert
            aus.append(EINRUECKUNG * stufe + inhalt)
            aus.extend(zeilen[i + 1:ende])
            aus.append(zeilen[ende].rstrip() if not offen else zeilen[ende])
        tiefe = max(tiefe + saldo, 0)
        i = ende + 1
    while aus and aus[-1] == '':
        aus.pop()
    return '\n'.join(aus) + '\n' if aus else ''


def _kommentare(text: str) -> list:
    """Kommentartexte (ohne Zeilenendleerraum) in Reihenfolge."""
    import main
    gefunden = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ('"', "'"):
            ende = main._zeichenkette_ende(text, i)
            i = n if ende is None else ende
        elif c == '#':
            j = text.find('\n', i)
            j = n if j < 0 else j
            gefunden.append(text[i:j].rstrip())
            i = j
        else:
            i += 1
    return gefunden


def _struktur(k):
    """Struktur-Darstellung eines AST ohne Zeilennummern."""
    from deutsch.ast_knoten import Knoten
    if isinstance(k, Knoten):
        namen = {n for t in type(k).__mro__ for n in getattr(t, '__slots__', ()) if 'zeile' not in n}
        return (type(k).__name__, tuple((n, _struktur(getattr(k, n, None))) for n in sorted(namen)))
    if isinstance(k, (list, tuple)):
        return tuple(_struktur(x) for x in k)
    if isinstance(k, dict):
        return tuple(sorted((repr(a), _struktur(b)) for a, b in k.items()))
    return k if k is None or isinstance(k, (bool, int, float, str)) else repr(k)


def _parsen(text: str):
    from deutsch.lexer import Lexer
    from deutsch.parser import Parser
    return Parser(Lexer(text).tokenisieren()).parse()


def _formatieren_pruefen(original: str):
    """Gibt (neuer_text, None) oder (None, Fehlertext) zurück. Prüft Parsebarkeit, AST und Kommentare."""
    neu = formatiere(original)
    try:
        gleich = _struktur(_parsen(neu)) == _struktur(_parsen(original))
    except Exception as e:
        return None, f'formatierte Fassung nicht parsbar ({e})'
    if not gleich:
        return None, 'formatierte Fassung hat anderen Syntaxbaum'
    if _kommentare(neu) != _kommentare(original):
        return None, 'Kommentare wären verändert'
    return neu, None


def datei_formatieren(pfad: str) -> int:
    """CLI: formatiert die Datei an Ort und Stelle; Rückgabe = Exitcode."""
    import main
    if not os.path.exists(pfad):
        print(f'Fehler: Datei nicht gefunden: {pfad!r}', file=sys.stderr)
        return 1
    with open(pfad, 'rb') as f:
        roh = f.read()
    try:
        text = roh.decode('utf-8')
    except UnicodeDecodeError:
        print(f'{pfad}: keine gültige UTF-8-Datei, nichts geändert', file=sys.stderr)
        return 1
    crlf = b'\r\n' in roh
    original = text.replace('\r\n', '\n')

    fehler, _ = main.im_grossen_stack(main._pruefen, original, pfad)
    if fehler:
        print(fehler, file=sys.stderr)
        return 1
    neu, grund = main.im_grossen_stack(_formatieren_pruefen, original)
    if grund:
        print(f'{pfad}: Formatieren abgebrochen, Datei unverändert: {grund}', file=sys.stderr)
        return 1
    ausgabe = (neu.replace('\n', '\r\n') if crlf else neu).encode('utf-8')
    if ausgabe == roh:
        print(f'{pfad}: bereits formatiert')
        return 0
    with open(pfad, 'wb') as f:
        f.write(ausgabe)
    print(f'{pfad}: formatiert')
    return 0
