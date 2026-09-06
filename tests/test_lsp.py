# -*- coding: utf-8 -*-
"""
Tests für den Language Server.

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lsp import (Server, diagnosen, symbole, zeilen_bereich,
                         nachricht_lesen, nachricht_senden, _wort_an_position,
                         S_KLASSE, S_METHODE, S_FUNKTION, S_VARIABLE, S_KONSTANTE)

URI = 'file:///test.deu'

QUELLE = '''konstante MAX = 10

funktion verdopple(x) {
    zurück x * 2
}

klasse Zaehler {
    konstante GRENZE = 5
    sei anzahl = 0
    funktion __init__(dies) { dies.n = 0 }
    statisch funktion neu_start() { zurück 0 }
}

sei ergebnis = verdopple(MAX)
'''


def _rahmen(objekt) -> bytes:
    rumpf = json.dumps(objekt, ensure_ascii=False).encode('utf-8')
    return f'Content-Length: {len(rumpf)}\r\n\r\n'.encode('ascii') + rumpf


def _entrahmen(rohdaten: bytes) -> list:
    strom, ergebnis = io.BytesIO(rohdaten), []
    while True:
        laenge = None
        while True:
            zeile = strom.readline()
            if not zeile:
                return ergebnis
            zeile = zeile.decode('ascii').strip()
            if not zeile:
                break
            if zeile.lower().startswith('content-length'):
                laenge = int(zeile.split(':')[1])
        if not laenge:
            return ergebnis
        ergebnis.append(json.loads(strom.read(laenge).decode('utf-8')))


def fahre(nachrichten: list) -> list:
    """Schickt Nachrichten durch einen Server und gibt dessen Antworten zurück."""
    eingang = io.BytesIO(b''.join(_rahmen(n) for n in nachrichten))
    ausgang = io.BytesIO()
    Server(eingang, ausgang).laufen()
    return _entrahmen(ausgang.getvalue())


def oeffnen(text: str, uri: str = URI) -> dict:
    return {'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
            'params': {'textDocument': {'uri': uri, 'languageId': 'deutsch',
                                        'version': 1, 'text': text}}}


def anfrage(id_: int, methode: str, parameter: dict) -> dict:
    return {'jsonrpc': '2.0', 'id': id_, 'method': methode, 'params': parameter}


def bei(zeile: int, spalte: int, uri: str = URI) -> dict:
    return {'textDocument': {'uri': uri}, 'position': {'line': zeile, 'character': spalte}}


def ergebnisse(antworten: list) -> dict:
    return {a['id']: a.get('result') for a in antworten if 'id' in a}


def meldungen(antworten: list, methode: str) -> list:
    return [a['params'] for a in antworten if a.get('method') == methode]


class TestProtokollrahmen(unittest.TestCase):
    def test_senden_und_lesen_sind_umkehrbar(self):
        strom = io.BytesIO()
        nachricht_senden(strom, {'jsonrpc': '2.0', 'id': 1, 'result': {'text': 'mit Ümläuten'}})
        strom.seek(0)
        self.assertEqual(nachricht_lesen(strom)['result']['text'], 'mit Ümläuten')

    def test_leerer_strom_liefert_none(self):
        self.assertIsNone(nachricht_lesen(io.BytesIO(b'')))

    def test_content_length_zaehlt_bytes_nicht_zeichen(self):
        strom = io.BytesIO()
        nachricht_senden(strom, {'wert': 'äöü'})          # 6 Bytes in UTF-8, 3 Zeichen
        kopf = strom.getvalue().split(b'\r\n')[0].decode()
        laenge = int(kopf.split(':')[1])
        self.assertEqual(laenge, len(strom.getvalue().split(b'\r\n\r\n', 1)[1]))


class TestDiagnosen(unittest.TestCase):
    def test_fehlerfreies_dokument_hat_keine_diagnosen(self):
        self.assertEqual(diagnosen(QUELLE), [])

    def test_syntaxfehler_wird_gemeldet(self):
        d = diagnosen('sei x = 1\nklasse A { tippfehler }\n')
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]['severity'], 1)
        self.assertEqual(d[0]['source'], 'deutsch')
        self.assertEqual(d[0]['range']['start']['line'], 1)      # 0-basiert: zweite Zeile
        self.assertIn("Klasse 'A'", d[0]['message'])

    def test_zeilenpraefix_wird_aus_der_meldung_entfernt(self):
        d = diagnosen('sei x = ')
        self.assertNotIn('Zeile', d[0]['message'])

    def test_zeile_nach_mehrzeiligem_string_stimmt(self):
        text = 'sei t = """A\nB\nC"""\nklasse X { kaputt }\n'
        d = diagnosen(text)
        self.assertEqual(d[0]['range']['start']['line'], 3)

    def test_diagnose_fuehrt_den_code_nicht_aus(self):
        with tempfile.TemporaryDirectory() as tmp:
            beweis = os.path.join(tmp, 'beweis.txt').replace('\\', '/')
            diagnosen(f'datei_schreiben("{beweis}", "geschrieben")')
            self.assertFalse(os.path.exists(beweis),
                             'Diagnose darf den Code niemals ausführen')

    def test_bereich_deckt_den_zeileninhalt_ohne_einrueckung_ab(self):
        bereich = zeilen_bereich('sei x = 1\n    kaputt\n', 2)
        self.assertEqual(bereich['start'], {'line': 1, 'character': 4})
        self.assertEqual(bereich['end'], {'line': 1, 'character': 10})


class TestGliederung(unittest.TestCase):
    def setUp(self):
        self.symbole = symbole(QUELLE)
        self.nach_name = {s['name']: s for s in self.symbole}

    def test_top_level_symbole(self):
        self.assertEqual(self.nach_name['MAX']['kind'], S_KONSTANTE)
        self.assertEqual(self.nach_name['verdopple']['kind'], S_FUNKTION)
        self.assertEqual(self.nach_name['Zaehler']['kind'], S_KLASSE)
        self.assertEqual(self.nach_name['ergebnis']['kind'], S_VARIABLE)

    def test_zeilen_sind_korrekt(self):
        self.assertEqual(self.nach_name['verdopple']['range']['start']['line'], 2)
        self.assertEqual(self.nach_name['Zaehler']['range']['start']['line'], 6)

    def test_klassenmitglieder_als_kinder_mit_eigener_zeile(self):
        kinder = {k['name']: k for k in self.nach_name['Zaehler']['children']}
        self.assertEqual(kinder['__init__']['kind'], S_METHODE)
        self.assertEqual(kinder['neu_start']['kind'], S_METHODE)
        self.assertEqual(kinder['GRENZE']['kind'], S_KONSTANTE)
        self.assertEqual(kinder['anzahl']['kind'], S_VARIABLE)
        self.assertEqual(kinder['__init__']['range']['start']['line'], 9)
        self.assertEqual(kinder['GRENZE']['range']['start']['line'], 7)

    def test_kaputtes_dokument_liefert_leere_gliederung(self):
        self.assertEqual(symbole('klasse A { kaputt }'), [])


class TestWortErkennung(unittest.TestCase):
    def test_umlaute_gehoeren_zum_wort(self):
        self.assertEqual(_wort_an_position('    zurück x', 0, 6), 'zurück')

    def test_position_ausserhalb_liefert_leer(self):
        self.assertEqual(_wort_an_position('abc', 5, 0), '')
        self.assertEqual(_wort_an_position('   ', 0, 1), '')


class TestServerLebenszyklus(unittest.TestCase):
    def test_initialize_meldet_faehigkeiten(self):
        antwort = ergebnisse(fahre([anfrage(1, 'initialize', {})]))[1]
        faehig = antwort['capabilities']
        for name in ('completionProvider', 'hoverProvider',
                     'documentSymbolProvider', 'definitionProvider'):
            self.assertIn(name, faehig)
        self.assertEqual(faehig['textDocumentSync'], 1)

    def test_shutdown_beendet_die_schleife_noch_nicht(self):
        antworten = fahre([anfrage(1, 'shutdown', {}), anfrage(2, 'initialize', {})])
        self.assertIn(2, ergebnisse(antworten), 'nach shutdown muss exit noch bedient werden')

    def test_exit_beendet_die_schleife(self):
        antworten = fahre([{'jsonrpc': '2.0', 'method': 'exit', 'params': {}},
                           anfrage(9, 'initialize', {})])
        self.assertNotIn(9, ergebnisse(antworten))

    def test_unbekannte_anfrage_wird_leer_beantwortet(self):
        antworten = fahre([anfrage(1, 'textDocument/gibtEsNicht', {})])
        self.assertIn(1, ergebnisse(antworten))
        self.assertIsNone(ergebnisse(antworten)[1])

    def test_unbekannte_benachrichtigung_wird_ignoriert(self):
        antworten = fahre([{'jsonrpc': '2.0', 'method': '$/cancelRequest', 'params': {'id': 1}},
                           anfrage(1, 'initialize', {})])
        self.assertIn(1, ergebnisse(antworten))


class TestServerDokumente(unittest.TestCase):
    def test_didopen_veroeffentlicht_diagnosen(self):
        antworten = fahre([oeffnen('klasse A { kaputt }')])
        gemeldet = meldungen(antworten, 'textDocument/publishDiagnostics')
        self.assertEqual(len(gemeldet), 1)
        self.assertEqual(gemeldet[0]['uri'], URI)
        self.assertEqual(len(gemeldet[0]['diagnostics']), 1)

    def test_didchange_aktualisiert_diagnosen(self):
        antworten = fahre([
            oeffnen('klasse A { kaputt }'),
            {'jsonrpc': '2.0', 'method': 'textDocument/didChange',
             'params': {'textDocument': {'uri': URI, 'version': 2},
                        'contentChanges': [{'text': 'sei x = 1'}]}},
        ])
        gemeldet = meldungen(antworten, 'textDocument/publishDiagnostics')
        self.assertEqual(len(gemeldet[0]['diagnostics']), 1)
        self.assertEqual(len(gemeldet[1]['diagnostics']), 0, 'Fehler muss verschwinden')

    def test_didclose_leert_die_diagnosen(self):
        antworten = fahre([
            oeffnen('klasse A { kaputt }'),
            {'jsonrpc': '2.0', 'method': 'textDocument/didClose',
             'params': {'textDocument': {'uri': URI}}},
        ])
        self.assertEqual(meldungen(antworten, 'textDocument/publishDiagnostics')[-1]['diagnostics'], [])


class TestSprachfunktionen(unittest.TestCase):
    def _erg(self, *nachrichten):
        return ergebnisse(fahre([oeffnen(QUELLE), *nachrichten]))

    def test_documentsymbol_liefert_die_gliederung(self):
        erg = self._erg(anfrage(1, 'textDocument/documentSymbol', {'textDocument': {'uri': URI}}))
        self.assertEqual([s['name'] for s in erg[1]], ['MAX', 'verdopple', 'Zaehler', 'ergebnis'])

    def test_vervollstaendigung_enthaelt_schluesselwoerter_eingebaute_und_eigene(self):
        erg = self._erg(anfrage(1, 'textDocument/completion', bei(13, 20)))
        namen = {e['label'] for e in erg[1]}
        self.assertIn('funktion', namen)          # Schlüsselwort
        self.assertIn('drucke', namen)            # eingebaute Funktion
        self.assertIn('pi', namen)                # eingebaute Konstante
        self.assertIn('Ganzzahl', namen)          # Typ-Hinweis
        self.assertIn('verdopple', namen)         # eigene Funktion
        self.assertIn('Zaehler', namen)           # eigene Klasse

    def test_vervollstaendigung_nach_punkt_nur_methoden(self):
        text = QUELLE + 'sei l = [1]\nl.\n'
        erg = ergebnisse(fahre([oeffnen(text),
                                anfrage(1, 'textDocument/completion', bei(15, 2))]))
        namen = {e['label'] for e in erg[1]}
        self.assertIn('anhaengen', namen)
        self.assertIn('laenge', namen)
        self.assertNotIn('funktion', namen, 'nach dem Punkt keine Schlüsselwörter')
        self.assertNotIn('drucke', namen, 'nach dem Punkt keine freien Funktionen')

    def test_hover_auf_schluesselwort_eingebautem_und_methode(self):
        erg = self._erg(
            anfrage(1, 'textDocument/hover', bei(3, 6)),      # zurück
            anfrage(2, 'textDocument/hover', bei(13, 18)),    # verdopple
        )
        self.assertIn('Schlüsselwort', erg[1]['contents']['value'])
        self.assertIn('Funktion in dieser Datei', erg[2]['contents']['value'])

    def test_hover_auf_eingebauter_methode_zeigt_signatur(self):
        text = 'sei l = [1]\nl.einfuegen(0, 2)\n'
        erg = ergebnisse(fahre([oeffnen(text),
                                anfrage(1, 'textDocument/hover', bei(1, 4))]))
        wert = erg[1]['contents']['value']
        self.assertIn('Liste.einfuegen(index, wert)', wert)

    def test_hover_auf_unbekanntem_wort_liefert_nichts(self):
        erg = self._erg(anfrage(1, 'textDocument/hover', bei(3, 12)))   # 'x'
        self.assertIsNone(erg[1])

    def test_definition_springt_zur_funktion(self):
        erg = self._erg(anfrage(1, 'textDocument/definition', bei(13, 18)))
        self.assertEqual(erg[1]['uri'], URI)
        self.assertEqual(erg[1]['range']['start']['line'], 2)

    def test_definition_findet_auch_klassenmethoden(self):
        text = QUELLE + 'Zaehler.neu_start()\n'
        erg = ergebnisse(fahre([oeffnen(text),
                                anfrage(1, 'textDocument/definition', bei(14, 10))]))
        self.assertEqual(erg[1]['range']['start']['line'], 10)

    def test_definition_bei_unbekanntem_namen_liefert_nichts(self):
        erg = self._erg(anfrage(1, 'textDocument/definition', bei(0, 0)))  # 'konstante'
        self.assertIsNone(erg[1])


if __name__ == '__main__':
    unittest.main()
