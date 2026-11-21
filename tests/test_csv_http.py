# -*- coding: utf-8 -*-
"""
Tests für csv_lesen/csv_schreiben, http_holen (nur gegen einen lokalen Server, kein Internet),
json_parsen/json_text und das Keyword kodierung= der Datei-Funktionen.

Ausführen mit:
    py -m unittest discover -s tests -p test_csv_http.py -v
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter


def auswerten(code: str, ladepfad=None, **variablen):
    tokens = Lexer(code).tokenisieren()
    baum = Parser(tokens).parse()
    interpreter = Interpreter(ladepfad=ladepfad)
    for name, wert in variablen.items():
        interpreter.global_umgebung.setze(name, wert)
    return interpreter.ausfuehren(baum)


class DateiBasis(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ordner = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def pfad(self, name):
        return os.path.join(self.ordner, name)

    def schreibe(self, name, inhalt, kodierung='utf-8'):
        with open(self.pfad(name), 'w', encoding=kodierung, newline='') as f:
            f.write(inhalt)

    def lies(self, name, kodierung='utf-8'):
        with open(self.pfad(name), 'r', encoding=kodierung, newline='') as f:
            return f.read()

    def hier(self, code, **v):
        return auswerten(code, ladepfad=self.ordner, **v)


class TestCsvLesen(DateiBasis):
    def test_mit_kopfzeile_liefert_woerterbuecher(self):
        self.schreibe('a.csv', 'name,alter\nAnna,30\nBen,25\n')
        self.assertEqual(self.hier('csv_lesen("a.csv")'),
                         [{'name': 'Anna', 'alter': '30'}, {'name': 'Ben', 'alter': '25'}])

    def test_ohne_kopfzeile_liefert_listen(self):
        self.schreibe('a.csv', 'name,alter\nAnna,30\n')
        self.assertEqual(self.hier('csv_lesen("a.csv", kopfzeile=falsch)'),
                         [['name', 'alter'], ['Anna', '30']])

    def test_semikolon_positional_und_keyword(self):
        self.schreibe('a.csv', 'a;b\n1;2\n')
        erwartet = [{'a': '1', 'b': '2'}]
        self.assertEqual(self.hier('csv_lesen("a.csv", ";")'), erwartet)
        self.assertEqual(self.hier('csv_lesen("a.csv", trennzeichen=";")'), erwartet)

    def test_anfuehrungszeichen_und_zeilenumbruch_im_feld(self):
        self.schreibe('a.csv', 'text,x\r\n"Hallo, ""Welt""\nzweite Zeile",1\r\n')
        self.assertEqual(self.hier('csv_lesen("a.csv")'),
                         [{'text': 'Hallo, "Welt"\nzweite Zeile', 'x': '1'}])

    def test_umlaute(self):
        self.schreibe('a.csv', 'ort\nMünchen\nÄrger\n')
        self.assertEqual(self.hier('csv_lesen("a.csv", kopfzeile=falsch)'), [['ort'], ['München'], ['Ärger']])

    def test_leere_zeilen_uebersprungen_kurze_zeile_aufgefuellt(self):
        self.schreibe('a.csv', 'a,b\n\n1\n')
        self.assertEqual(self.hier('csv_lesen("a.csv")'), [{'a': '1', 'b': ''}])

    def test_leere_datei(self):
        self.schreibe('a.csv', '')
        self.assertEqual(self.hier('csv_lesen("a.csv")'), [])

    def test_latin1(self):
        self.schreibe('a.csv', 'ort\nKöln\n', 'latin-1')
        self.assertEqual(self.hier('csv_lesen("a.csv", kodierung="latin-1")'), [{'ort': 'Köln'}])

    def test_fehler(self):
        self.schreibe('a.csv', 'a,b\n1,2,3\n')
        with self.assertRaisesRegex(ValueError, 'Zeile 2 hat mehr Felder'):
            self.hier('csv_lesen("a.csv")')
        with self.assertRaisesRegex(FileNotFoundError, 'Datei nicht gefunden'):
            self.hier('csv_lesen("fehlt.csv")')
        with self.assertRaisesRegex(ValueError, 'genau ein Zeichen'):
            self.hier('csv_lesen("a.csv", ";;")')
        with self.assertRaisesRegex(TypeError, 'Zeichenkette'):
            self.hier('csv_lesen("a.csv", 5)')
        with self.assertRaisesRegex(TypeError, "kein Parameter 'x'"):
            self.hier('csv_lesen("a.csv", x=1)')
        with self.assertRaisesRegex(TypeError, 'mindestens 1 Argument'):
            self.hier('csv_lesen()')
        with self.assertRaisesRegex(ValueError, 'Unbekannte Kodierung'):
            self.hier('csv_lesen("a.csv", kodierung="quatsch")')

    def test_falsche_kodierung_der_datei(self):
        self.schreibe('a.csv', 'ort\nKöln\n', 'latin-1')
        with self.assertRaisesRegex(ValueError, 'keine gültige UTF-8-Textdatei'):
            self.hier('csv_lesen("a.csv")')


class TestCsvSchreiben(DateiBasis):
    def test_woerterbuecher_rundum(self):
        zeilen = [{'name': 'Anna', 'ort': 'München'}, {'name': 'Ben', 'ort': 'Köln'}]
        self.hier('csv_schreiben("a.csv", z)', z=zeilen)
        self.assertEqual(self.lies('a.csv'), 'name,ort\nAnna,München\nBen,Köln\n')
        self.assertEqual(self.hier('csv_lesen("a.csv")'), zeilen)

    def test_fehlende_felder_leer_und_nichts_leer(self):
        self.hier('csv_schreiben("a.csv", z)', z=[{'a': 1, 'b': 2}, {'a': 3}, {'a': None, 'b': 'x'}])
        self.assertEqual(self.lies('a.csv'), 'a,b\n1,2\n3,\n,x\n')

    def test_listen_semikolon_und_quoting(self):
        z = [['a;b', 'say "hi"', 'zwei\nZeilen'], ['1', '2', '3']]
        self.hier('csv_schreiben("a.csv", z, trennzeichen=";")', z=z)
        self.assertEqual(self.hier('csv_lesen("a.csv", ";", falsch)'), z)

    def test_latin1(self):
        self.hier('csv_schreiben("a.csv", z, kodierung="latin-1")', z=[['Köln']])
        with open(self.pfad('a.csv'), 'rb') as f:
            self.assertEqual(f.read(), 'Köln\n'.encode('latin-1'))

    def test_fehler_ohne_halbe_datei(self):
        self.schreibe('a.csv', 'alt\n')
        with self.assertRaisesRegex(TypeError, 'nicht als Feld'):
            self.hier('csv_schreiben("a.csv", z)', z=[['ok'], [['verschachtelt']]])
        with self.assertRaisesRegex(ValueError, "Schlüssel 'c' fehlt"):
            self.hier('csv_schreiben("a.csv", z)', z=[{'a': 1}, {'c': 2}])
        with self.assertRaisesRegex(ValueError, 'nicht als ASCII speichern'):
            self.hier('csv_schreiben("a.csv", z, kodierung="ascii")', z=[['Köln']])
        with self.assertRaisesRegex(TypeError, 'Wörterbüchern oder .* Listen'):
            self.hier('csv_schreiben("a.csv", z)', z=[{'a': 1}, ['b']])
        with self.assertRaisesRegex(TypeError, 'Liste von Zeilen'):
            self.hier('csv_schreiben("a.csv", 5)')
        with self.assertRaisesRegex(ValueError, 'genau ein Zeichen'):
            self.hier('csv_schreiben("a.csv", z, trennzeichen="")', z=[['a']])
        self.assertEqual(self.lies('a.csv'), 'alt\n')  # nichts überschrieben

    def test_leere_liste_und_fehlende_argumente(self):
        self.hier('csv_schreiben("a.csv", [])')
        self.assertEqual(self.lies('a.csv'), '')
        with self.assertRaisesRegex(TypeError, 'mindestens 2 Argument'):
            self.hier('csv_schreiben("a.csv")')


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        status, typ, body = 200, 'text/plain; charset=utf-8', 'Grüße'.encode('utf-8')
        if self.path == '/latin':
            typ, body = 'text/plain; charset=iso-8859-1', 'Grüße'.encode('latin-1')
        elif self.path == '/ohne':
            typ = 'text/plain'
        elif self.path == '/nf':
            status, body = 404, b'weg'
        elif self.path == '/kaputt':
            typ, body = 'text/plain; charset=gibtesnicht', b'x'
        elif self.path == '/json':
            typ, body = 'application/json', b'{"a": [1, 2]}'
        elif self.path == '/zu_ok':
            self.send_response(302)
            self.send_header('Location', '/ok')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        elif self.path == '/zu_ftp':
            self.send_response(302)
            self.send_header('Location', 'ftp://127.0.0.1:1/x')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        elif self.path == '/schleife':
            self.send_response(302)
            self.send_header('Location', '/schleife')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        elif self.path == '/zu_file':
            self.send_response(302)
            self.send_header('Location', 'file:///etc/passwd')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        elif self.path == '/kurz':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', '100')
            self.end_headers()
            self.wfile.write(b'nur wenig')
            self.close_connection = True
            return
        elif self.path == '/langsam':
            time.sleep(1.5)
        self.send_response(status)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass


class TestHttpHolen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        cls.server.daemon_threads = True
        cls.basis = f'http://127.0.0.1:{cls.server.server_address[1]}'
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def holen(self, pfad, extra=''):
        return auswerten(f'http_holen(u{extra})', u=self.basis + pfad)

    def test_200_utf8(self):
        self.assertEqual(self.holen('/ok'), 'Grüße')

    def test_ohne_charset_ist_utf8(self):
        self.assertEqual(self.holen('/ohne'), 'Grüße')

    def test_zeichensatz_aus_header(self):
        self.assertEqual(self.holen('/latin'), 'Grüße')

    def test_unbekannter_zeichensatz(self):
        with self.assertRaisesRegex(ValueError, 'unbekannte Kodierung'):
            self.holen('/kaputt')

    def test_404(self):
        with self.assertRaisesRegex(OSError, 'HTTP-Fehler 404'):
            self.holen('/nf')

    def test_zeitueberschreitung(self):
        with self.assertRaisesRegex(TimeoutError, 'Zeitüberschreitung'):
            self.holen('/langsam', ', zeitlimit=0.3')

    def test_zeitlimit_positional_reicht_aus(self):
        self.assertEqual(self.holen('/ok', ', 5'), 'Grüße')

    def test_mit_json_parsen(self):
        self.assertEqual(auswerten('json_parsen(http_holen(u))', u=self.basis + '/json'), {'a': [1, 2]})

    def test_weiterleitung_auf_http_folgt(self):
        self.assertEqual(self.holen('/zu_ok'), 'Grüße')

    def test_weiterleitung_auf_ftp_verboten(self):
        with self.assertRaisesRegex(ValueError, "Weiterleitung auf nicht erlaubtes Schema 'ftp'"):
            self.holen('/zu_ftp')

    def test_weiterleitung_auf_file_verboten(self):
        with self.assertRaisesRegex(ValueError, "Weiterleitung auf nicht erlaubtes Schema 'file'"):
            self.holen('/zu_file')

    def test_unvollstaendige_antwort(self):
        with self.assertRaisesRegex(OSError, 'Unvollständige Antwort'):
            self.holen('/kurz')

    def test_weiterleitungsschleife(self):
        with self.assertRaisesRegex(OSError, 'zyklische Weiterleitungen'):
            self.holen('/schleife')

    def test_nicht_erlaubtes_schema(self):
        for url in ('file:///etc/passwd', 'ftp://127.0.0.1/x', 'javascript:1', 'abc', ''):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, 'nur http:// und https://'):
                    auswerten('http_holen(u)', u=url)

    def test_ungueltige_url_und_netzfehler(self):
        with self.assertRaisesRegex(ValueError, 'Ungültige URL'):
            auswerten('http_holen(u)', u='http://[kaputt/')
        with self.assertRaisesRegex(OSError, 'Netzwerkfehler'):
            # Port 1 auf localhost: Verbindung wird abgelehnt
            auswerten('http_holen("http://127.0.0.1:1/")')

    def test_falsche_argumente(self):
        with self.assertRaisesRegex(TypeError, 'zeitlimit'):
            auswerten('http_holen("http://127.0.0.1/", zeitlimit="x")')
        with self.assertRaisesRegex(ValueError, 'größer als 0'):
            auswerten('http_holen("http://127.0.0.1/", zeitlimit=0)')
        with self.assertRaisesRegex(TypeError, 'mindestens 1 Argument'):
            auswerten('http_holen()')


class TestQaFunde(DateiBasis):
    def test_csv_excel_bom_ohne_bom_im_schluessel(self):
        self.schreibe('a.csv', '﻿name,alter\nAnna,30\n')
        self.assertEqual(self.hier('csv_lesen("a.csv")'), [{'name': 'Anna', 'alter': '30'}])

    def test_bom_bei_datei_zeilen_json_lesen_schreiben_ohne_bom(self):
        self.schreibe('t.txt', '﻿A\nB\n')
        self.assertEqual(self.hier('datei_lesen("t.txt")'), 'A\nB\n')
        self.assertEqual(self.hier('zeilen_lesen("t.txt")'), ['A', 'B'])
        self.schreibe('j.json', '﻿{"a": 1}')
        self.assertEqual(self.hier('json_lesen("j.json")'), {'a': 1})
        self.hier('datei_schreiben("o.txt", "x")')
        with open(self.pfad('o.txt'), 'rb') as f:
            self.assertEqual(f.read(), b'x')

    def test_csv_doppelte_spaltennamen(self):
        self.schreibe('a.csv', 'a,b,a\n1,2,3\n')
        with self.assertRaisesRegex(ValueError, "Spaltenname 'a' kommt mehrfach"):
            self.hier('csv_lesen("a.csv")')
        self.assertEqual(self.hier('csv_lesen("a.csv", kopfzeile=falsch)'), [['a', 'b', 'a'], ['1', '2', '3']])

    def test_csv_offenes_anfuehrungszeichen(self):
        self.schreibe('a.csv', 'a,b\n1,"2\n')
        with self.assertRaisesRegex(ValueError, r'nicht geschlossenes Anführungszeichen.*Zeile \d+'):
            self.hier('csv_lesen("a.csv")')

    def test_null_hoch_negativ_deutsch(self):
        for code in ('0 ** -1', '0.0 ** -1', 'sei a = 0\na ** -1'):
            with self.subTest(code=code):
                with self.assertRaisesRegex(ZeroDivisionError, 'Null kann nicht mit negativem Exponenten'):
                    auswerten(code)


class TestJsonText(unittest.TestCase):
    def test_parsen(self):
        self.assertEqual(auswerten('json_parsen(t)', t='{"a": [1, 2.5, null, true], "b": "ü"}'),
                         {'a': [1, 2.5, None, True], 'b': 'ü'})

    def test_text_und_rundum(self):
        wert = {'a': [1, None, True], 'b': 'Grüße'}
        text = auswerten('json_text(w)', w=wert)
        self.assertIn('Grüße', text)  # kein \u-Escape
        self.assertEqual(auswerten('json_parsen(t)', t=text), wert)

    def test_menge_wird_sortierte_liste(self):
        self.assertEqual(auswerten('json_parsen(json_text(m))', m={3, 1, 2}), [1, 2, 3])

    def test_fehler(self):
        with self.assertRaisesRegex(ValueError, r'Ungültiges JSON \(Zeichen'):
            auswerten('json_parsen(t)', t='{kaputt')
        with self.assertRaisesRegex(TypeError, 'Zeichenkette'):
            auswerten('json_parsen(5)')
        with self.assertRaisesRegex(TypeError, "kann nicht als JSON"):
            auswerten('json_text(f)', f=object())
        with self.assertRaisesRegex(TypeError, 'erwartet 1 Argument'):
            auswerten('json_text()')
        with self.assertRaises(RecursionError):
            auswerten('json_parsen(t)', t='[' * 100000 + ']' * 100000)


class TestKodierung(DateiBasis):
    def test_lesen_schreiben_anhaengen_zeilen_latin1(self):
        self.hier('datei_schreiben("t.txt", "Köln\\n", kodierung="latin-1")')
        with open(self.pfad('t.txt'), 'rb') as f:
            self.assertEqual(f.read().strip(), b'K\xf6ln')  # Zeilenende je nach System
        self.hier('datei_anhaengen("t.txt", "Zürich\\n", kodierung="latin-1")')
        self.assertEqual(self.hier('datei_lesen("t.txt", kodierung="latin-1")'), 'Köln\nZürich\n')
        self.assertEqual(self.hier('zeilen_lesen("t.txt", kodierung="latin-1")'), ['Köln', 'Zürich'])
        self.hier('datei_anhängen("t.txt", "x", kodierung="latin-1")')

    def test_standard_bleibt_utf8(self):
        self.hier('datei_schreiben("t.txt", "Köln")')
        self.assertEqual(self.lies('t.txt'), 'Köln')

    def test_falsche_kodierung_beim_lesen(self):
        self.schreibe('t.txt', 'Köln', 'latin-1')
        with self.assertRaisesRegex(ValueError, 'keine gültige UTF-8-Textdatei'):
            self.hier('datei_lesen("t.txt")')
        with self.assertRaisesRegex(ValueError, 'keine gültige ASCII-Textdatei'):
            self.hier('datei_lesen("t.txt", kodierung="ascii")')

    def test_unbekannte_kodierung(self):
        for code in ('datei_lesen("t.txt", kodierung="quatsch")',
                     'datei_schreiben("t.txt", "x", kodierung="quatsch")',
                     'datei_anhaengen("t.txt", "x", kodierung="quatsch")',
                     'zeilen_lesen("t.txt", kodierung="quatsch")',
                     'datei_lesen("t.txt", kodierung="rot13")'):
            with self.subTest(code=code):
                with self.assertRaisesRegex(ValueError, 'Unbekannte Kodierung|keine Text-Kodierung'):
                    self.hier(code)
        self.assertFalse(os.path.exists(self.pfad('t.txt')))

    def test_zeichen_nicht_kodierbar(self):
        with self.assertRaisesRegex(ValueError, 'nicht als LATIN-1 speichern'):
            self.hier('datei_schreiben("t.txt", "日本", kodierung="latin-1")')

    def test_falsche_keywords_und_typen(self):
        with self.assertRaisesRegex(TypeError, "kein Parameter 'x'"):
            self.hier('datei_lesen("t.txt", x=1)')
        with self.assertRaisesRegex(TypeError, 'kodierung'):
            self.hier('datei_lesen("t.txt", kodierung=5)')


if __name__ == '__main__':
    unittest.main()
