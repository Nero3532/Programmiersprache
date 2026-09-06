# -*- coding: utf-8 -*-
"""
Language Server für Deutsch – spricht LSP über stdin/stdout.

Bewusst ohne externe Abhängigkeiten (kein pygls): das Protokoll ist JSON-RPC mit
Content-Length-Rahmen, und die eigentliche Arbeit macht ohnehin der vorhandene
Lexer/Parser. So bleibt das Projekt installationsfrei.

Start:  deutsch --lsp
"""
import json
import re
import sys

from .lexer import Lexer, SCHLUESSELWOERTER
from .parser import Parser
from . import ast_knoten as ast
from .interpreter import Interpreter, DeutschNamensraum

# LSP-Konstanten (Auszug, damit keine Bibliothek nötig ist)
FEHLER = 1                       # DiagnosticSeverity.Error
K_METHODE, K_FUNKTION, K_VARIABLE = 2, 3, 6
K_MODUL = 9
K_KLASSE, K_SCHLUESSELWORT, K_KONSTANTE = 7, 14, 21
S_KLASSE, S_METHODE, S_FUNKTION, S_VARIABLE, S_KONSTANTE = 5, 6, 12, 13, 14

_ZEILE_MUSTER = re.compile(r'Zeile (\d+): ?')
_WORT_MUSTER = re.compile(r'[A-Za-zÄÖÜäöüß_][A-Za-zÄÖÜäöüß0-9_]*')


# ------------------------------------------------------------------ Protokoll

def nachricht_lesen(strom):
    """Liest eine LSP-Nachricht (Header + JSON-Rumpf). None am Ende des Stroms."""
    kopfzeilen = {}
    while True:
        zeile = strom.readline()
        if not zeile:
            return None
        zeile = zeile.decode('ascii', errors='replace').strip()
        if not zeile:
            break
        if ':' in zeile:
            name, _, wert = zeile.partition(':')
            kopfzeilen[name.strip().lower()] = wert.strip()
    laenge = int(kopfzeilen.get('content-length', 0))
    if laenge <= 0:
        return None
    return json.loads(strom.read(laenge).decode('utf-8'))


def nachricht_senden(strom, objekt):
    rumpf = json.dumps(objekt, ensure_ascii=False).encode('utf-8')
    strom.write(f'Content-Length: {len(rumpf)}\r\n\r\n'.encode('ascii'))
    strom.write(rumpf)
    strom.flush()


# ------------------------------------------------------------------ Analyse

def zeilen_bereich(text: str, zeile: int) -> dict:
    """LSP-Bereich über den Inhalt einer 1-basierten Zeile (ohne Einrückung)."""
    zeilen = text.split('\n')
    i = max(0, min(zeile - 1, len(zeilen) - 1)) if zeilen else 0
    inhalt = zeilen[i] if zeilen else ''
    start = len(inhalt) - len(inhalt.lstrip())
    ende = len(inhalt.rstrip())
    if ende <= start:
        start, ende = 0, max(1, len(inhalt))
    return {'start': {'line': i, 'character': start},
            'end': {'line': i, 'character': ende}}


def diagnosen(text: str) -> list:
    """Syntaxfehler als LSP-Diagnosen. Der Code wird nur gelesen, nie ausgeführt."""
    try:
        Parser(Lexer(text).tokenisieren()).parse()
    except SyntaxError as fehler:
        meldung = str(fehler)
        treffer = _ZEILE_MUSTER.search(meldung)
        zeile = int(treffer.group(1)) if treffer else 1
        return [{
            'range': zeilen_bereich(text, zeile),
            'severity': FEHLER,
            'source': 'deutsch',
            'message': _ZEILE_MUSTER.sub('', meldung, count=1),
        }]
    except Exception as fehler:                      # defekter Lexer-Zustand o. Ä.
        return [{
            'range': zeilen_bereich(text, 1),
            'severity': FEHLER,
            'source': 'deutsch',
            'message': str(fehler),
        }]
    return []


def _knoten_zeile(knoten, standard=1) -> int:
    return getattr(knoten, 'zeile', None) or standard


def symbole(text: str) -> list:
    """Gliederung des Dokuments: Funktionen, Klassen samt Methoden, Top-Level-Namen."""
    try:
        baum = Parser(Lexer(text).tokenisieren()).parse()
    except Exception:
        return []

    def eintrag(name, art, zeile, kinder=None):
        bereich = zeilen_bereich(text, zeile)
        knoten = {'name': name, 'kind': art, 'range': bereich, 'selectionRange': bereich}
        if kinder:
            knoten['children'] = kinder
        return knoten

    ergebnis = []
    for anweisung in baum.anweisungen:
        zeile = _knoten_zeile(anweisung)
        if isinstance(anweisung, ast.FunktionDefinition) and anweisung.name:
            ergebnis.append(eintrag(anweisung.name, S_FUNKTION, zeile))
        elif isinstance(anweisung, ast.KlassenDefinition):
            kinder = [
                eintrag(m.name, S_METHODE, _knoten_zeile(m, zeile))
                for m in list(anweisung.methoden) + list(anweisung.statische_methoden)
                if m.name
            ]
            kinder += [
                eintrag(a.name, S_KONSTANTE if a.ist_konstante else S_VARIABLE,
                        _knoten_zeile(a, zeile))
                for a in anweisung.klassenattribute
                if isinstance(a, ast.VariableDeklaration)
            ]
            ergebnis.append(eintrag(anweisung.name, S_KLASSE, zeile, kinder))
        elif isinstance(anweisung, ast.VariableDeklaration):
            art = S_KONSTANTE if anweisung.ist_konstante else S_VARIABLE
            ergebnis.append(eintrag(anweisung.name, art, zeile))
    return ergebnis


def _wort_an_position(text: str, zeile: int, spalte: int) -> str:
    """Das Wort unter dem Cursor (0-basierte LSP-Koordinaten)."""
    zeilen = text.split('\n')
    if not 0 <= zeile < len(zeilen):
        return ''
    inhalt = zeilen[zeile]
    for treffer in _WORT_MUSTER.finditer(inhalt):
        if treffer.start() <= spalte <= treffer.end():
            return treffer.group(0)
    return ''


class Wissen:
    """Namen und Kurzbeschreibungen für Vervollständigung und Hover."""

    def __init__(self):
        interpreter = Interpreter()
        global_ = interpreter.global_umgebung.variablen
        self.module = {
            name: sorted(wert.bindungen)
            for name, wert in global_.items()
            if isinstance(wert, DeutschNamensraum)
        }
        self.eingebaute = sorted(
            name for name, wert in global_.items()
            if callable(wert) and not isinstance(wert, DeutschNamensraum)
        )
        self.konstanten = sorted(
            name for name, wert in global_.items()
            if not callable(wert) and not isinstance(wert, DeutschNamensraum)
        )
        # Fuer Hover: welches Modul stellt welchen Namen bereit
        self._modul_von = {}
        for modulname, mitglieder in self.module.items():
            for mitglied in mitglieder:
                self._modul_von.setdefault(mitglied, []).append(modulname)
        methoden = set()
        for tabelle in (interpreter._listen_methoden, interpreter._string_methoden,
                        interpreter._woerterbuch_methoden, interpreter._menge_methoden):
            methoden.update(tabelle)
        self.methoden = sorted(methoden)
        self.schluesselwoerter = sorted(SCHLUESSELWOERTER)
        self.typnamen = ['Ganzzahl', 'Kommazahl', 'Zeichenkette', 'Wahrheitswert',
                         'Liste', 'Woerterbuch', 'Wörterbuch', 'Menge', 'Bereich',
                         'Nichts', 'Funktion']
        self._methoden_besitzer = {}
        for typ, tabelle in (('Liste', interpreter._listen_methoden),
                             ('Zeichenkette', interpreter._string_methoden),
                             ('Wörterbuch', interpreter._woerterbuch_methoden),
                             ('Menge', interpreter._menge_methoden)):
            for name, methode in tabelle.items():
                self._methoden_besitzer.setdefault(name, []).append((typ, methode))

    def beschreibung(self, name: str) -> str | None:
        if name in self.module:
            mitglieder = ', '.join(self.module[name])
            return f'`{name}` – Modul der Standardbibliothek\n\n{mitglieder}'
        if name in self.schluesselwoerter:
            return f'`{name}` – Schlüsselwort der Sprache Deutsch'
        if name in self.eingebaute:
            return f'`{name}(…)` – eingebaute Funktion'
        if name in self.konstanten:
            return f'`{name}` – eingebaute Konstante'
        if name in self.typnamen:
            return f'`{name}` – Typ-Hinweis'
        module = self._modul_von.get(name)
        if module:
            zeilen = [f'`{m}.{name}(…)` – Funktion aus der Standardbibliothek' for m in module]
            return '\n\n'.join(zeilen)
        eintraege = self._methoden_besitzer.get(name)
        if eintraege:
            zeilen = [
                f'`{typ}.{name}({", ".join(_parameternamen(m))})` – eingebaute Methode'
                for typ, m in eintraege
            ]
            return '\n\n'.join(zeilen)
        return None


def _parameternamen(methode) -> list:
    """Parameternamen einer eingebauten Methode ohne das führende 'obj'."""
    import inspect
    try:
        namen = list(inspect.signature(methode.fn).parameters)[1:]
    except (TypeError, ValueError):
        return []
    return [n if n != 'args' else '*args' for n in namen]


# ------------------------------------------------------------------ Server

class Server:
    def __init__(self, eingang=None, ausgang=None):
        self.eingang = eingang if eingang is not None else sys.stdin.buffer
        self.ausgang = ausgang if ausgang is not None else sys.stdout.buffer
        self.dokumente: dict[str, str] = {}
        self.wissen = Wissen()
        self.laeuft = True
        self.beendet_angefordert = False

    # ---- Versand

    def _antwort(self, id_, ergebnis):
        nachricht_senden(self.ausgang, {'jsonrpc': '2.0', 'id': id_, 'result': ergebnis})

    def _benachrichtigung(self, methode, parameter):
        nachricht_senden(self.ausgang,
                         {'jsonrpc': '2.0', 'method': methode, 'params': parameter})

    def _diagnosen_melden(self, uri):
        self._benachrichtigung('textDocument/publishDiagnostics', {
            'uri': uri,
            'diagnostics': diagnosen(self.dokumente.get(uri, '')),
        })

    # ---- Hauptschleife

    def laufen(self):
        while self.laeuft:
            nachricht = nachricht_lesen(self.eingang)
            if nachricht is None:
                break
            self.behandeln(nachricht)

    def behandeln(self, nachricht):
        methode = nachricht.get('method')
        id_ = nachricht.get('id')
        parameter = nachricht.get('params') or {}
        behandler = getattr(self, '_m_' + methode.replace('/', '_').replace('$', ''), None) \
            if methode else None
        if behandler is None:
            if id_ is not None:      # unbekannte Anfrage: leer beantworten, nie hängen lassen
                self._antwort(id_, None)
            return
        ergebnis = behandler(parameter)
        if id_ is not None:
            self._antwort(id_, ergebnis)

    # ---- Lebenszyklus

    def _m_initialize(self, parameter):
        return {
            'capabilities': {
                'textDocumentSync': 1,                     # voller Text bei jeder Änderung
                'completionProvider': {'triggerCharacters': ['.']},
                'hoverProvider': True,
                'documentSymbolProvider': True,
                'definitionProvider': True,
            },
            'serverInfo': {'name': 'deutsch-lsp'},
        }

    def _m_initialized(self, parameter):
        return None

    def _m_shutdown(self, parameter):
        # Laut Protokoll endet der Server erst bei 'exit', nicht schon hier
        self.beendet_angefordert = True
        return None

    def _m_exit(self, parameter):
        self.laeuft = False
        return None

    # ---- Dokumente

    def _m_textDocument_didOpen(self, parameter):
        dokument = parameter['textDocument']
        self.dokumente[dokument['uri']] = dokument.get('text', '')
        self._diagnosen_melden(dokument['uri'])

    def _m_textDocument_didChange(self, parameter):
        uri = parameter['textDocument']['uri']
        aenderungen = parameter.get('contentChanges') or []
        if aenderungen:
            self.dokumente[uri] = aenderungen[-1].get('text', '')
        self._diagnosen_melden(uri)

    def _m_textDocument_didSave(self, parameter):
        self._diagnosen_melden(parameter['textDocument']['uri'])

    def _m_textDocument_didClose(self, parameter):
        uri = parameter['textDocument']['uri']
        self.dokumente.pop(uri, None)
        self._benachrichtigung('textDocument/publishDiagnostics',
                               {'uri': uri, 'diagnostics': []})

    # ---- Sprachfunktionen

    def _m_textDocument_documentSymbol(self, parameter):
        return symbole(self.dokumente.get(parameter['textDocument']['uri'], ''))

    def _m_textDocument_completion(self, parameter):
        text = self.dokumente.get(parameter['textDocument']['uri'], '')
        position = parameter.get('position') or {}
        zeilen = text.split('\n')
        zeile = zeilen[position.get('line', 0)] if position.get('line', 0) < len(zeilen) else ''
        vor_cursor = zeile[:position.get('character', 0)]

        # Nach 'modul.' die Mitglieder dieses Moduls, nach jedem anderen Punkt die
        # eingebauten Instanzmethoden
        if vor_cursor.rstrip().endswith('.'):
            davor = _WORT_MUSTER.findall(vor_cursor.rstrip()[:-1])
            if davor and davor[-1] in self.wissen.module:
                modulname = davor[-1]
                return [{'label': n, 'kind': K_FUNKTION,
                         'detail': f'aus {modulname}'}
                        for n in self.wissen.module[modulname]]
            return [{'label': n, 'kind': K_METHODE,
                     'detail': 'eingebaute Methode'} for n in self.wissen.methoden]

        eintraege = [{'label': n, 'kind': K_SCHLUESSELWORT} for n in self.wissen.schluesselwoerter]
        eintraege += [{'label': n, 'kind': K_FUNKTION, 'detail': 'eingebaute Funktion'}
                      for n in self.wissen.eingebaute]
        eintraege += [{'label': n, 'kind': K_KONSTANTE, 'detail': 'eingebaute Konstante'}
                      for n in self.wissen.konstanten]
        eintraege += [{'label': n, 'kind': K_MODUL, 'detail': 'Modul der Standardbibliothek'}
                      for n in sorted(self.wissen.module)]
        eintraege += [{'label': n, 'kind': K_KLASSE, 'detail': 'Typ-Hinweis'}
                      for n in self.wissen.typnamen]
        for symbol in symbole(text):
            art = K_KLASSE if symbol['kind'] == S_KLASSE else (
                K_FUNKTION if symbol['kind'] == S_FUNKTION else K_VARIABLE)
            eintraege.append({'label': symbol['name'], 'kind': art, 'detail': 'in dieser Datei'})
        return eintraege

    def _m_textDocument_hover(self, parameter):
        text = self.dokumente.get(parameter['textDocument']['uri'], '')
        position = parameter.get('position') or {}
        wort = _wort_an_position(text, position.get('line', 0), position.get('character', 0))
        if not wort:
            return None
        beschreibung = self.wissen.beschreibung(wort)
        if beschreibung is None:
            for symbol in symbole(text):
                if symbol['name'] == wort:
                    art = {S_KLASSE: 'Klasse', S_FUNKTION: 'Funktion',
                           S_KONSTANTE: 'Konstante'}.get(symbol['kind'], 'Variable')
                    beschreibung = f'`{wort}` – {art} in dieser Datei'
                    break
        if beschreibung is None:
            return None
        return {'contents': {'kind': 'markdown', 'value': beschreibung}}

    def _m_textDocument_definition(self, parameter):
        uri = parameter['textDocument']['uri']
        text = self.dokumente.get(uri, '')
        position = parameter.get('position') or {}
        wort = _wort_an_position(text, position.get('line', 0), position.get('character', 0))
        if not wort:
            return None

        def suchen(eintraege):
            for symbol in eintraege:
                if symbol['name'] == wort:
                    return {'uri': uri, 'range': symbol['range']}
                treffer = suchen(symbol.get('children') or [])
                if treffer:
                    return treffer
            return None

        return suchen(symbole(text))


def main(argv=None):
    Server().laufen()
    return 0


if __name__ == '__main__':
    sys.exit(main())
