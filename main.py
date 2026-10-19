#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deutsch 2.0 – Einstiegspunkt
Verwendung:
    python main.py              → interaktive REPL
    python main.py datei.deu    → Datei ausführen

Copyright (C) 2026  txtblock93@gmail.com
Lizenziert unter der GNU General Public License v3.0 oder später.
Siehe LICENSE-Datei für den vollständigen Text.
"""
import sys
import os
import re
import threading


def _konsole_auf_utf8():
    """UTF-8 Ausgabe auf Windows erzwingen."""
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, 'reconfigure'):
            try:
                strom.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass


# REPL-Verlauf (optional – auf Windows ohne pyreadline3 nicht verfügbar)
try:
    import readline
    readline.parse_and_bind('tab: complete')
    _READLINE = True
except ImportError:
    try:
        import pyreadline3 as readline  # type: ignore
        _READLINE = True
    except ImportError:
        _READLINE = False

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter

BANNER = """\
╔══════════════════════════════════════════════════════════╗
║  Deutsch 2.0  –  Eine Programmiersprache auf Deutsch     ║
╠══════════════════════════════════════════════════════════╣
║  'beenden' zum Verlassen | '{' öffnet mehrzeilige Blöcke ║
╚══════════════════════════════════════════════════════════╝"""

# --------------------------------------------------------------------------
# Großer Stack für tiefe Rekursion
#
# Ein Deutsch-Funktionsaufruf braucht ca. 11 Python-Frames. Das Rekursionslimit
# zählt Python-Frames, und bei Python < 3.11 verbraucht jeder davon auch C-Stack.
# Darum läuft die Ausführung in einem Thread mit großem Stack; das Limit wird
# aus der tatsächlich erhaltenen Stackgröße abgeleitet (großzügig gerechnet),
# damit ein Überlauf immer als RecursionError endet und nie als Absturz.
# --------------------------------------------------------------------------
_STACK_STUFEN_MB = (128, 64, 32, 16)        # Windows reserviert den Stack sofort als Commit-Speicher
_STACK_BYTES_PRO_FRAME = 2048               # großzügig geschätzt (real ca. 0,3-1 KB)
_LIMIT_OHNE_THREAD = 10000                  # wie früher, falls kein Thread startet
_STOPP_WARTEZEIT = 1.0                      # Sekunden, die ein Strg+C auf das Ende wartet


def _thread_starten(ziel):
    """Startet ziel in einem Thread mit dem größten möglichen Stack und setzt das
    dazu passende Rekursionslimit. Gibt den Thread zurück, oder None, wenn
    keine Stackgröße ging."""
    alter_stack = threading.stack_size()
    try:
        for mb in _STACK_STUFEN_MB:
            groesse = mb * 1024 * 1024
            try:
                threading.stack_size(groesse)
            except (ValueError, RuntimeError):  # Plattform lehnt diese Größe ab
                continue
            sys.setrecursionlimit(groesse // _STACK_BYTES_PRO_FRAME)
            thread = threading.Thread(target=ziel, name='deutsch-ausfuehrung', daemon=True)
            try:
                thread.start()
            except RuntimeError:  # Stack nicht reservierbar -> kleinere Stufe
                continue
            return thread
        return None
    finally:
        try:
            threading.stack_size(alter_stack)
        except (ValueError, RuntimeError):
            pass


def _thread_unterbrechen(thread, fertig) -> bool:
    """Löst im Thread ein KeyboardInterrupt aus (Strg+C) und wartet kurz.
    Gibt True zurück, wenn der Thread danach beendet ist."""
    # ctypes erst hier laden (kostet beim Start ~60 ms). Der Thread rechnet
    # eventuell in einer Endlosschleife und hält die GIL; mit kurzem
    # Umschaltintervall kommt dieser Thread trotzdem schnell zum Zug.
    altes_intervall = sys.getswitchinterval()
    try:
        sys.setswitchinterval(1e-5)
        import ctypes
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread.ident), ctypes.py_object(KeyboardInterrupt))
    except Exception:
        pass
    finally:
        sys.setswitchinterval(altes_intervall)
    return fertig.wait(_STOPP_WARTEZEIT)


def im_grossen_stack(funktion, *args):
    """Führt funktion(*args) in einem Thread mit großem Stack aus und gibt das
    Ergebnis zurück. Ausnahmen (auch SystemExit, KeyboardInterrupt) werden im
    aufrufenden Thread erneut ausgelöst."""
    ergebnis = {}
    fertig = threading.Event()  # zuverlässiger als Thread.is_alive() nach Strg+C

    def arbeit():
        try:
            ergebnis['wert'] = funktion(*args)
        except BaseException as e:
            ergebnis['fehler'] = e
        finally:
            fertig.set()

    altes_limit = sys.getrecursionlimit()
    thread = _thread_starten(arbeit)
    if thread is None:
        sys.setrecursionlimit(_LIMIT_OHNE_THREAD)
        return funktion(*args)

    try:
        try:
            # Mit Zeitlimit warten: ein blockierendes Warten ließe sich unter
            # Windows nicht per Strg+C unterbrechen.
            while not fertig.wait(0.1):
                pass
        except KeyboardInterrupt:
            if not _thread_unterbrechen(thread, fertig):
                # Thread steckt fest (z. B. in eingabe()): Prozess beenden,
                # der Daemon-Thread wird dabei verworfen.
                raise SystemExit(130)
            raise
    finally:
        sys.setrecursionlimit(altes_limit)

    if 'fehler' in ergebnis:
        raise ergebnis['fehler']
    return ergebnis.get('wert')


# --------------------------------------------------------------------------
# REPL: Erkennen unvollständiger Eingabe
# --------------------------------------------------------------------------

def _eingabe_abtasten(text: str):
    """Tastet Quelltext ab und gibt (saldo, in_dreifach_string) zurück.

    saldo = Anzahl '{' minus Anzahl '}' außerhalb von Zeichenketten und
    '#'-Kommentaren. Zeichenketten sind "...", '...', \"\"\"...\"\"\" und '''...''';
    eine einfache Zeichenkette endet spätestens am Zeilenende (wie im Lexer),
    damit eine vergessene Anführungszeichen-Paarung die REPL nicht festhält.
    """
    saldo = 0
    quote = None      # aktuelles Begrenzer-Zeichen oder None
    dreifach = False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if quote is None:
            if c == '#':
                while i < n and text[i] != '\n':
                    i += 1
                continue
            if c in ('"', "'"):
                quote = c
                dreifach = text.startswith(c * 3, i)
                i += 3 if dreifach else 1
                continue
            if c == '{':
                saldo += 1
            elif c == '}':
                saldo -= 1
            i += 1
            continue

        # innerhalb einer Zeichenkette
        if c == '\\':
            i += 2
            continue
        if dreifach:
            if text.startswith(quote * 3, i):
                quote = None
                i += 3
                continue
        elif c == quote or c == '\n':
            quote = None
        i += 1
    return saldo, quote is not None and dreifach


def klammer_saldo(quelltext: str) -> int:
    """Offene '{' minus geschlossene '}', ohne Zeichenketten und Kommentare."""
    return _eingabe_abtasten(quelltext)[0]


def eingabe_unvollstaendig(quelltext: str) -> bool:
    """True, wenn die REPL weitere Zeilen lesen soll: ein '{'-Block ist noch
    offen oder eine mehrzeilige \"\"\"-Zeichenkette nicht geschlossen."""
    saldo, offene_zeichenkette = _eingabe_abtasten(quelltext)
    return saldo > 0 or offene_zeichenkette


def _anzeigename(datei: str, ladepfad: str | None) -> str:
    """Pfad relativ zum Ordner des Hauptskripts (mit '/'), außerhalb davon der volle Pfad.
    Dieselbe Schreibweise wie in den Meldungen des Interpreters."""
    if not ladepfad:
        return datei
    try:
        relativ = os.path.relpath(datei, ladepfad)
    except ValueError:  # z. B. anderes Laufwerk unter Windows
        return datei
    if relativ == os.pardir or relativ.startswith(os.pardir + os.sep):
        return datei
    return relativ.replace(os.sep, '/')


def _quelltext_lesen(pfad: str):
    """Quelltext einer Datei, oder None, wenn sie nicht lesbar ist."""
    try:
        with open(pfad, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return None


def _fehler_anzeigen(fehler: Exception, quelltext: str = '', dateiname: str = '<repl>',
                     aufruf_stack=None, ladepfad: str | None = None):
    """Gibt Fehler mit Zeilenkontext und optionaler Aufruf-Kette aus.

    Stammt der Fehler aus einer per 'lade' geladenen Datei (Attribut 'datei'), zeigen
    Name und Zeilenkontext diese Datei statt des Hauptskripts."""
    msg = str(fehler)

    # Zeile bevorzugt aus dem Attribut des Interpreters; die Meldung nur als Ersatz
    zeile_nr = getattr(fehler, 'zeile', None)
    if zeile_nr is None:
        m = re.search(r'Zeile (\d+)', msg)
        zeile_nr = int(m.group(1)) if m else None

    datei = getattr(fehler, 'datei', None)  # None = Hauptskript oder REPL
    if datei:
        dateiname = _anzeigename(datei, ladepfad)
        quelltext = _quelltext_lesen(datei) or ''

    linien = quelltext.split('\n') if quelltext else []

    ausgabe = [f'[{type(fehler).__name__}] {msg}']

    if zeile_nr and 0 < zeile_nr <= len(linien):
        zeile_text = linien[zeile_nr - 1]
        ausgabe.insert(0, f'  {dateiname}, Zeile {zeile_nr}:')
        ausgabe.insert(1, f'    {zeile_text}')
        ausgabe.insert(2, f'    {"^" * max(1, len(zeile_text.strip()))}')

    if aufruf_stack:
        for name, zeile in reversed(aufruf_stack):
            ausgabe.append(f"  in Funktion '{name}' (Zeile {zeile})")

    return '\n'.join(ausgabe)


def _ausfuehren(quelltext: str, interpreter: Interpreter, dateiname: str = '<repl>'):
    """Führt Quelltext aus. Gibt (ergebnis, fehler_text) zurück."""
    ladepfad = getattr(interpreter, '_ladepfad', None)
    try:
        tokens = Lexer(quelltext).tokenisieren()
        baum = Parser(tokens).parse()
        ergebnis = interpreter.ausfuehren(baum)
        return ergebnis, None
    except RecursionError:
        return None, '[Fehler] Maximale Rekursionstiefe überschritten'
    except Exception as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname,
                                      getattr(interpreter, '_letzter_aufruf_stack', None), ladepfad)


def datei_starten(pfad: str, argumente: list = None):
    if not os.path.exists(pfad):
        print(f'Fehler: Datei nicht gefunden: {pfad!r}', file=sys.stderr)
        sys.exit(1)

    with open(pfad, 'r', encoding='utf-8') as f:
        quelltext = f.read()

    ladepfad = os.path.dirname(os.path.abspath(pfad))
    interpreter = Interpreter(ladepfad=ladepfad, argumente=argumente or [])

    _, fehler = im_grossen_stack(_ausfuehren, quelltext, interpreter, pfad)
    if fehler:
        print(fehler, file=sys.stderr)
        sys.exit(1)


def repl():
    print(BANNER)
    if _READLINE:
        print('(REPL-Verlauf aktiv – Pfeiltasten für Verlauf)')
    print()

    interpreter = Interpreter()

    while True:
        try:
            zeile = input('>>> ')
        except (EOFError, KeyboardInterrupt):
            print('\nAuf Wiedersehen!')
            break

        if zeile.strip() in ('beenden', 'exit', 'quit'):
            print('Auf Wiedersehen!')
            break

        if not zeile.strip():
            continue

        # Mehrzeilige Eingabe: weiterlesen bis { } ausgeglichen (Zeichenketten
        # und Kommentare zählen nicht mit)
        quelltext = zeile
        while eingabe_unvollstaendig(quelltext):
            try:
                mehr = input('... ')
                quelltext += '\n' + mehr
            except (EOFError, KeyboardInterrupt):
                print()
                quelltext = ''
                break

        if not quelltext.strip():
            continue

        try:
            ergebnis, fehler = im_grossen_stack(_ausfuehren, quelltext, interpreter)
        except KeyboardInterrupt:
            print('\nUnterbrochen.')
            continue
        if fehler:
            print(fehler)
        elif ergebnis is not None:
            print(interpreter._zu_text(ergebnis))


def main():
    _konsole_auf_utf8()
    if len(sys.argv) > 1:
        datei_starten(sys.argv[1], sys.argv[2:])
    else:
        repl()


if __name__ == '__main__':
    main()
