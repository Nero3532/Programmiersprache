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

sys.setrecursionlimit(10000)

# UTF-8 Ausgabe auf Windows erzwingen
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
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
║  'beenden' zum Verlassen  |  '{' öffnet mehrzeilige Blöcke ║
╚══════════════════════════════════════════════════════════╝"""


def _fehler_anzeigen(fehler: Exception, quelltext: str = '', dateiname: str = '<repl>', aufruf_stack=None):
    """Gibt Fehler mit Zeilenkontext und optionaler Aufruf-Kette aus."""
    msg = str(fehler)

    # Zeilennummer aus Fehlermeldung extrahieren
    m = re.search(r'Zeile (\d+)', msg)
    zeile_nr = int(m.group(1)) if m else None

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
    try:
        tokens = Lexer(quelltext).tokenisieren()
        baum = Parser(tokens).parse()
        ergebnis = interpreter.ausfuehren(baum)
        return ergebnis, None
    except SyntaxError as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))
    except NameError as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))
    except TypeError as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))
    except AttributeError as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))
    except IndexError as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))
    except KeyError as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))
    except ZeroDivisionError as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))
    except RecursionError:
        return None, '[Fehler] Maximale Rekursionstiefe überschritten'
    except Exception as e:
        return None, _fehler_anzeigen(e, quelltext, dateiname, getattr(interpreter, '_letzter_aufruf_stack', None))


def datei_starten(pfad: str, argumente: list = None):
    if not os.path.exists(pfad):
        print(f'Fehler: Datei nicht gefunden: {pfad!r}', file=sys.stderr)
        sys.exit(1)

    with open(pfad, 'r', encoding='utf-8') as f:
        quelltext = f.read()

    ladepfad = os.path.dirname(os.path.abspath(pfad))
    interpreter = Interpreter(ladepfad=ladepfad, argumente=argumente or [])

    _, fehler = _ausfuehren(quelltext, interpreter, dateiname=pfad)
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

        # Mehrzeilige Eingabe: weiterlesen bis { } ausgeglichen
        quelltext = zeile
        while quelltext.count('{') > quelltext.count('}'):
            try:
                mehr = input('... ')
                quelltext += '\n' + mehr
            except (EOFError, KeyboardInterrupt):
                print()
                quelltext = ''
                break

        if not quelltext.strip():
            continue

        ergebnis, fehler = _ausfuehren(quelltext, interpreter)
        if fehler:
            print(fehler)
        elif ergebnis is not None:
            print(interpreter._zu_text(ergebnis))


def main():
    if len(sys.argv) > 1:
        datei_starten(sys.argv[1], sys.argv[2:])
    else:
        repl()


if __name__ == '__main__':
    main()
