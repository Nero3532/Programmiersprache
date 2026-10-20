# -*- coding: utf-8 -*-
"""
Tests für die deutschen Fehlerarten (TypFehler, WertFehler, … Fehler):
Fehlerkopf der CLI, typisiertes 'fange (...)' mit deutschen und englischen Namen, Vererbung,
unbekannte Namen und das Neuerzeugen von Fehlern mit deutscher Meldung bei erhaltener Klasse.

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT_WURZEL)

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import (FEHLERARTEN, AusnahmeFehler, Interpreter, SchluesselFehler,
                                 _meldung_deutsch, fehlerart_name)
from main import _fehler_anzeigen


def lauf(code: str, interpreter: Interpreter = None):
    """Tokenisiert, parst und führt Code aus. Gibt (ergebnis, interpreter) zurück."""
    if interpreter is None:
        interpreter = Interpreter()
    baum = Parser(Lexer(code).tokenisieren()).parse()
    return interpreter.ausfuehren(baum), interpreter


def interpreter_mit_wirf(ausnahme: BaseException) -> Interpreter:
    """Interpreter mit der Funktion wirf(), die ausnahme auslöst (für Fehlerarten, die der
    Sprachkern selbst nicht erzeugt, z. B. UnicodeDecodeError oder ImportError)."""
    interpreter = Interpreter()

    def wirf():
        raise ausnahme

    interpreter.global_umgebung.setze('wirf', wirf)
    return interpreter


def starte_code(code: str):
    """Führt 'py -m deutsch -c code' als Unterprozess aus. Gibt (exitcode, stdout, stderr) zurück."""
    ergebnis = subprocess.run(
        [sys.executable, '-m', 'deutsch', '-c', code],
        stdin=subprocess.DEVNULL, capture_output=True, cwd=PROJEKT_WURZEL, timeout=120)

    def text(daten: bytes) -> str:
        return daten.decode('utf-8', errors='replace').replace('\r\n', '\n')

    return ergebnis.returncode, text(ergebnis.stdout), text(ergebnis.stderr)


# (deutscher Name, englischer Name, Skriptcode, der genau diese Fehlerart im Sprachkern auslöst)
FEHLERKOEPFE = [
    ('TypFehler', 'TypeError', 'drucke(-nichts)'),
    ('WertFehler', 'ValueError', 'ganzzahl("x")'),
    ('NamensFehler', 'NameError', 'drucke(gibt_es_nicht)'),
    ('IndexFehler', 'IndexError', 'sei l = [1]\ndrucke(l[5])'),
    ('SchluesselFehler', 'KeyError', 'sei d = {}\ndrucke(d["x"])'),
    ('AttributFehler', 'AttributeError', 'drucke("a".gibt_es_nicht)'),
    ('DateiFehler', 'FileNotFoundError', 'datei_lesen("gibt_es_nicht.txt")'),
    ('SyntaxFehler', 'SyntaxError', 'drucke(1 +)'),
    ('LaufzeitFehler', 'RuntimeError', 'abbrechen'),
    ('RekursionsFehler', 'RecursionError', 'funktion e(n) { zurück e(n + 1) }\ne(0)'),
    ('ZusicherungsFehler', 'AssertionError', 'pruefe 1 == 2, "kaputt"'),
    ('EingabeEndeFehler', 'EOFError', 'eingabe("x")'),
    ('DivisionDurchNullFehler', 'ZeroDivisionError', 'drucke(1 / 0)'),
    ('UeberlaufFehler', 'OverflowError', 'drucke(2 ** 10000.0)'),
]


class TestFehlerkopfInDerCli(unittest.TestCase):
    def test_jede_fehlerart_zeigt_den_deutschen_namen(self):
        for deutsch, englisch, code in FEHLERKOEPFE:
            with self.subTest(fehlerart=deutsch):
                exitcode, _, fehler = starte_code(code)
                self.assertEqual(exitcode, 1)
                self.assertRegex(fehler, rf'(?m)^\[{deutsch}\] ')
                self.assertNotIn(f'[{englisch}]', fehler)
                self.assertNotIn('Traceback', fehler)

    def test_kopf_mit_zeile_und_meldung(self):
        _, _, fehler = starte_code('drucke(1 / 0)')
        self.assertIn('[DivisionDurchNullFehler] Zeile 1: Division durch Null', fehler)

    def test_rekursion_hat_eigenen_kopf_statt_fehler(self):
        _, _, fehler = starte_code('funktion e(n) { zurück e(n + 1) }\ne(0)')
        self.assertIn('[RekursionsFehler] Maximale Rekursionstiefe überschritten', fehler)
        self.assertNotIn('[Fehler]', fehler)

    def test_geworfener_wert_heisst_ausnahmefehler(self):
        _, _, fehler = starte_code('werfe "boom"')
        self.assertIn('[AusnahmeFehler] Zeile 1: boom', fehler)

    def test_fehler_in_der_repl_nutzt_deutschen_namen(self):
        ergebnis = subprocess.run(
            [sys.executable, '-m', 'deutsch'], input='drucke(1 / 0)\nbeenden\n'.encode('utf-8'),
            capture_output=True, cwd=PROJEKT_WURZEL, timeout=120)
        self.assertIn('[DivisionDurchNullFehler]', ergebnis.stdout.decode('utf-8', errors='replace'))


class TestFehlerartName(unittest.TestCase):
    def test_zuordnung_aller_arten(self):
        erwartet = {
            'TypFehler': TypeError, 'WertFehler': ValueError, 'NamensFehler': NameError,
            'IndexFehler': IndexError, 'SchluesselFehler': KeyError, 'AttributFehler': AttributeError,
            'DateiFehler': OSError, 'SyntaxFehler': SyntaxError, 'LaufzeitFehler': RuntimeError,
            'RekursionsFehler': RecursionError, 'ZusicherungsFehler': AssertionError,
            'ImportFehler': ImportError, 'EingabeEndeFehler': EOFError,
            'DivisionDurchNullFehler': ZeroDivisionError, 'UeberlaufFehler': OverflowError,
            'Fehler': Exception,
        }
        self.assertEqual(FEHLERARTEN, erwartet)
        for name, klasse in erwartet.items():
            if name != 'Fehler':
                with self.subTest(fehlerart=name):
                    self.assertEqual(fehlerart_name(klasse('x')), name)

    def test_speziellste_art_gewinnt(self):
        self.assertEqual(fehlerart_name(FileNotFoundError('x')), 'DateiFehler')
        self.assertEqual(fehlerart_name(PermissionError('x')), 'DateiFehler')
        self.assertEqual(fehlerart_name(IsADirectoryError('x')), 'DateiFehler')
        self.assertEqual(fehlerart_name(UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte')),
                         'WertFehler')
        self.assertEqual(fehlerart_name(UnicodeEncodeError('ascii', 'ä', 0, 1, 'ordinal')), 'WertFehler')
        self.assertEqual(fehlerart_name(RecursionError('x')), 'RekursionsFehler')  # nicht LaufzeitFehler
        self.assertEqual(fehlerart_name(NotImplementedError('x')), 'LaufzeitFehler')
        self.assertEqual(fehlerart_name(ModuleNotFoundError('x')), 'ImportFehler')
        self.assertEqual(fehlerart_name(IndentationError('x')), 'SyntaxFehler')
        self.assertEqual(fehlerart_name(SchluesselFehler('x')), 'SchluesselFehler')

    def test_unbekannter_python_typ_heisst_fehler(self):
        self.assertEqual(fehlerart_name(StopIteration('x')), 'Fehler')
        self.assertEqual(fehlerart_name(Exception('x')), 'Fehler')
        self.assertEqual(fehlerart_name(MemoryError()), 'Fehler')

    def test_fehler_anzeigen_nutzt_deutschen_namen(self):
        self.assertTrue(_fehler_anzeigen(ZeroDivisionError('Zeile 1: Division durch Null'), '1 / 0')
                        .splitlines()[-1].startswith('[DivisionDurchNullFehler] '))
        self.assertTrue(_fehler_anzeigen(StopIteration('x')).startswith('[Fehler] x'))
        self.assertTrue(_fehler_anzeigen(AusnahmeFehler(5)).startswith('[AusnahmeFehler] 5'))


class TestFangeMitDeutschenNamen(unittest.TestCase):
    CODE = 'sei gefangen = falsch\nversuche { wirf() } fange (NAMEN) e { gefangen = wahr }\ngefangen'

    def _faengt(self, namen: str, ausnahme: BaseException) -> bool:
        return lauf(self.CODE.replace('NAMEN', namen), interpreter_mit_wirf(ausnahme))[0]

    def test_jede_deutsche_art_faengt_ihre_python_klasse(self):
        ausnahmen = {
            'TypFehler': TypeError('t'), 'WertFehler': ValueError('t'), 'NamensFehler': NameError('t'),
            'IndexFehler': IndexError('t'), 'SchluesselFehler': KeyError('t'),
            'AttributFehler': AttributeError('t'), 'DateiFehler': OSError('t'),
            'SyntaxFehler': SyntaxError('t'), 'LaufzeitFehler': RuntimeError('t'),
            'RekursionsFehler': RecursionError('t'), 'ZusicherungsFehler': AssertionError('t'),
            'ImportFehler': ImportError('t'), 'EingabeEndeFehler': EOFError('t'),
            'DivisionDurchNullFehler': ZeroDivisionError('t'), 'UeberlaufFehler': OverflowError('t'),
        }
        for name, ausnahme in ausnahmen.items():
            with self.subTest(fehlerart=name):
                self.assertTrue(self._faengt(name, ausnahme))

    def test_jede_deutsche_art_laesst_andere_durch(self):
        for name, klasse in FEHLERARTEN.items():
            if name in ('Fehler', 'LaufzeitFehler'):
                continue
            with self.subTest(fehlerart=name):
                # StopIteration ist mit keiner deutschen Art verwandt (außer dem Oberbegriff)
                with self.assertRaises(StopIteration):
                    self._faengt(name, StopIteration('t'))

    def test_deutsche_art_im_echten_skript(self):
        code = 'sei m = ""\nversuche {{ {fehler} }} fange ({art}) e {{ m = e }}\nm'
        for art, fehler, teil in [
            ('DivisionDurchNullFehler', '1 / 0', 'Division durch Null'),
            ('NamensFehler', 'gibt_es_nicht', 'Unbekannte Variable'),
            ('IndexFehler', '[1][5]', 'außerhalb des Bereichs'),
            ('SchluesselFehler', '{}["a"]', 'nicht im Wörterbuch'),
            ('DateiFehler', 'datei_lesen("gibt_es_nicht.txt")', 'nicht gefunden'),
            ('WertFehler', 'ganzzahl("x")', 'nicht in Ganzzahl umwandeln'),
            ('TypFehler', '-nichts', 'nicht unterstützt'),
            ('ZusicherungsFehler', 'pruefe falsch, "kaputt"', 'kaputt'),
            ('UeberlaufFehler', '2 ** 10000.0', 'zu groß'),
        ]:
            with self.subTest(fehlerart=art):
                self.assertIn(teil, lauf(code.format(fehler=fehler, art=art))[0])

    def test_liste_mit_mehreren_arten(self):
        self.assertTrue(self._faengt('TypFehler, DivisionDurchNullFehler', ZeroDivisionError('t')))
        self.assertTrue(self._faengt('DivisionDurchNullFehler, TypFehler', TypeError('t')))
        with self.assertRaises(IndexError):
            self._faengt('TypFehler, WertFehler', IndexError('t'))

    def test_fehler_ohne_name_in_der_klammer_bleibt_unveraendert(self):
        ergebnis, _ = lauf('sei m = ""\nversuche { 1 / 0 } fange e { m = e }\nm')
        self.assertIn('Division durch Null', ergebnis)


class TestVererbung(unittest.TestCase):
    CODE = TestFangeMitDeutschenNamen.CODE

    def _faengt(self, namen: str, ausnahme: BaseException) -> bool:
        return lauf(self.CODE.replace('NAMEN', namen), interpreter_mit_wirf(ausnahme))[0]

    def test_wertfehler_faengt_unicode_fehler(self):
        self.assertTrue(self._faengt('WertFehler', UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte')))
        self.assertTrue(self._faengt('WertFehler', UnicodeEncodeError('ascii', 'ä', 0, 1, 'ordinal not in range')))

    def test_dateifehler_faengt_unterarten(self):
        self.assertTrue(self._faengt('DateiFehler', FileNotFoundError('t')))
        self.assertTrue(self._faengt('DateiFehler', PermissionError('t')))
        self.assertTrue(self._faengt('DateiFehler', IsADirectoryError('t')))
        ergebnis, _ = lauf('sei m = ""\nversuche { datei_lesen("gibt_es_nicht.txt") } fange (DateiFehler) e { m = e }\nm')
        self.assertIn('Datei nicht gefunden', ergebnis)

    def test_laufzeitfehler_faengt_rekursion_wie_bisher_runtimeerror(self):
        self.assertTrue(self._faengt('LaufzeitFehler', RecursionError('t')))
        self.assertTrue(self._faengt('LaufzeitFehler', NotImplementedError('t')))
        self.assertTrue(self._faengt('RuntimeError', RecursionError('t')))

    def test_rekursionsfehler_faengt_nicht_jeden_laufzeitfehler(self):
        with self.assertRaises(RuntimeError):
            self._faengt('RekursionsFehler', RuntimeError('t'))

    def test_syntaxfehler_faengt_einrueckungsfehler(self):
        self.assertTrue(self._faengt('SyntaxFehler', IndentationError('t')))

    def test_importfehler_faengt_modulnotfound(self):
        self.assertTrue(self._faengt('ImportFehler', ModuleNotFoundError('t')))

    def test_schluesselfehler_faengt_python_keyerror_und_umgekehrt(self):
        self.assertTrue(self._faengt('SchluesselFehler', KeyError('t')))
        self.assertTrue(self._faengt('SchluesselFehler', SchluesselFehler('t')))
        self.assertTrue(self._faengt('KeyError', SchluesselFehler('t')))

    def test_oberbegriff_fehler_faengt_alles(self):
        for ausnahme in (TypeError('t'), ValueError('t'), KeyError('t'), OSError('t'), ZeroDivisionError('t'),
                         RecursionError('t'), EOFError('t'), StopIteration('t'), MemoryError(), SyntaxError('t')):
            with self.subTest(ausnahme=type(ausnahme).__name__):
                self.assertTrue(self._faengt('Fehler', ausnahme))

    def test_oberbegriff_fehler_faengt_geworfene_werte(self):
        ergebnis, _ = lauf('sei m = nichts\nversuche { werfe 42 } fange (Fehler) e { m = e }\nm')
        self.assertEqual(ergebnis, 42)

    def test_geworfener_wert_wird_von_spezieller_art_nicht_gefangen(self):
        with self.assertRaises(AusnahmeFehler):
            lauf('versuche { werfe 42 } fange (WertFehler) e { e }')

    def test_nicht_passende_art_propagiert_und_endlich_laeuft(self):
        code = ('sei lief = falsch\n'
                'versuche {\n'
                '    versuche { 1 / 0 } fange (WertFehler) e { e } endlich { lief = wahr }\n'
                '} fange (DivisionDurchNullFehler) g { g }\n'
                'lief')
        self.assertTrue(lauf(code)[0])


class TestEnglischeNamenBleibenGueltig(unittest.TestCase):
    def test_englische_namen_wie_bisher(self):
        for englisch, code in [
            ('ZeroDivisionError', '1 / 0'), ('Exception', '1 / 0'), ('ArithmeticError', '1 / 0'),
            ('KeyError', '{}["a"]'), ('LookupError', '[1][5]'), ('IndexError', '[1][5]'),
            ('NameError', 'gibt_es_nicht'), ('FileNotFoundError', 'datei_lesen("gibt_es_nicht.txt")'),
            ('OSError', 'datei_lesen("gibt_es_nicht.txt")'), ('ValueError', 'ganzzahl("x")'),
            ('TypeError', '-nichts'), ('AssertionError', 'pruefe falsch'),
            ('AttributeError', '"a".gibt_es_nicht'),
        ]:
            with self.subTest(name=englisch):
                lauf(f'versuche {{ {code} }} fange ({englisch}) e {{ e }}')  # darf nicht werfen

    def test_englischer_und_deutscher_name_gemischt(self):
        lauf('versuche { 1 / 0 } fange (TypeError, DivisionDurchNullFehler) e { e }')
        lauf('versuche { -nichts } fange (DivisionDurchNullFehler, TypeError) e { e }')

    def test_englischer_name_passt_nicht(self):
        with self.assertRaises(ZeroDivisionError):
            lauf('versuche { 1 / 0 } fange (TypeError) e { e }')

    def test_ausnahmefehler_und_unicode_namen_bleiben_gueltig(self):
        ergebnis, _ = lauf('sei m = nichts\nversuche { werfe 7 } fange (AusnahmeFehler) e { m = e }\nm')
        self.assertEqual(ergebnis, 7)
        interpreter = interpreter_mit_wirf(UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte'))
        lauf('versuche { wirf() } fange (UnicodeDecodeError) e { e }', interpreter)


class TestUnbekannteFehlerart(unittest.TestCase):
    def test_unbekannter_name_loest_deutschen_fehler_aus(self):
        with self.assertRaises(NameError) as ctx:
            lauf('versuche { 1 / 0 } fange (Quatsch) e { e }')
        meldung = str(ctx.exception)
        self.assertIn("Unbekannte Fehlerart 'Quatsch'", meldung)
        self.assertIn('Zeile 1', meldung)
        self.assertIn('WertFehler', meldung)  # nennt die bekannten Arten

    def test_tippfehler_bekommt_vorschlag(self):
        with self.assertRaises(NameError) as ctx:
            lauf('versuche { 1 / 0 } fange (WertFehlr) e { e }')
        self.assertIn("meintest du 'WertFehler'?", str(ctx.exception))

    def test_unbekannter_name_wird_nicht_still_ignoriert_auch_wenn_ein_anderer_passt(self):
        with self.assertRaises(NameError):
            lauf('versuche { 1 / 0 } fange (DivisionDurchNullFehler, Quatsch) e { e }')

    def test_unbekannter_name_ohne_ausgeloesten_fehler_bleibt_folgenlos(self):
        ergebnis, _ = lauf('sei x = 1\nversuche { x = 2 } fange (Quatsch) e { x = 3 }\nx')
        self.assertEqual(ergebnis, 2)

    def test_endlich_laeuft_auch_bei_unbekanntem_namen(self):
        interpreter = Interpreter()
        with self.assertRaises(NameError):
            lauf('sei lief = falsch\nversuche { 1 / 0 } fange (Quatsch) e { e } endlich { lief = wahr }',
                 interpreter)
        self.assertTrue(interpreter.global_umgebung.hole('lief'))

    def test_cli_zeigt_namensfehler(self):
        _, _, fehler = starte_code('versuche { 1 / 0 } fange (Quatsch) e { drucke(e) }')
        self.assertIn("[NamensFehler] Zeile 1: Unbekannte Fehlerart 'Quatsch'", fehler)


UNICODE_DEKODIEREN = UnicodeDecodeError('utf-8', b'ab\xff', 2, 3, 'invalid start byte')
UNICODE_KODIEREN = UnicodeEncodeError('ascii', 'abä', 2, 3, 'ordinal not in range(128)')


class TestFehlerNeuerzeugung(unittest.TestCase):
    """Nach dem Anreichern mit der Zeile bleibt die Klasse für 'fange' erkennbar, die Meldung ist deutsch."""

    def _gefangen(self, ausnahme, namen):
        code = f'sei m = ""\nversuche {{ wirf() }} fange ({namen}) e {{ m = e }}\nm'
        return lauf(code, interpreter_mit_wirf(ausnahme))[0]

    def test_unicodedecodeerror_bleibt_nach_dem_namen_fangbar(self):
        for namen in ('UnicodeDecodeError', 'UnicodeError', 'ValueError', 'WertFehler', 'Fehler'):
            with self.subTest(fange=namen):
                self.assertIn('Zeile 2: ', self._gefangen(UNICODE_DEKODIEREN, namen))

    def test_unicodeencodeerror_bleibt_nach_dem_namen_fangbar(self):
        for namen in ('UnicodeEncodeError', 'UnicodeError', 'ValueError', 'WertFehler', 'Fehler'):
            with self.subTest(fange=namen):
                self.assertIn('Zeile 2: ', self._gefangen(UNICODE_KODIEREN, namen))

    def test_unicodedecodeerror_wird_nicht_von_unicodeencodeerror_gefangen(self):
        with self.assertRaises(UnicodeDecodeError):
            self._gefangen(UNICODE_DEKODIEREN, 'UnicodeEncodeError')

    def test_dekodierfehler_meldung_deutsch_mit_kodierung_und_position(self):
        meldung = self._gefangen(UNICODE_DEKODIEREN, 'UnicodeDecodeError')
        self.assertIn("'utf-8'", meldung)
        self.assertIn('Position 2', meldung)
        self.assertIn('0xff', meldung)
        self.assertIn('ungültiges Startbyte', meldung)
        for englisch in ('invalid start byte', "can't decode", 'codec', 'position 2:'):
            self.assertNotIn(englisch, meldung)

    def test_kodierfehler_meldung_deutsch_mit_kodierung_und_position(self):
        meldung = self._gefangen(UNICODE_KODIEREN, 'UnicodeEncodeError')
        self.assertIn("'ascii'", meldung)
        self.assertIn('Position 2', meldung)
        self.assertIn('U+00E4', meldung)
        self.assertIn("'ä'", meldung)
        for englisch in ('ordinal not in range', "can't encode", 'codec'):
            self.assertNotIn(englisch, meldung)

    def test_unicode_fehler_bereich_mehrerer_bytes(self):
        fehler = UnicodeDecodeError('utf-8', b'a\xe4\xb8', 1, 3, 'unexpected end of data')
        meldung = self._gefangen(fehler, 'UnicodeDecodeError')
        self.assertIn('Position 1–2', meldung)
        self.assertIn('Daten enden unerwartet', meldung)

    def test_nicht_gefangen_bleibt_originalklasse_mit_zeile_und_datei(self):
        for ausnahme in (UNICODE_DEKODIEREN, UNICODE_KODIEREN):
            with self.subTest(klasse=type(ausnahme).__name__):
                with self.assertRaises(type(ausnahme)) as ctx:
                    lauf('wirf()', interpreter_mit_wirf(ausnahme))
                self.assertEqual(ctx.exception.zeile, 1)
                self.assertIsNone(ctx.exception.datei)
                self.assertTrue(str(ctx.exception).startswith('Zeile 1: '))

    def test_cli_kopf_fuer_unicode_fehler_ist_wertfehler(self):
        interpreter = interpreter_mit_wirf(UNICODE_DEKODIEREN)
        try:
            lauf('wirf()', interpreter)
        except Exception as e:
            text = _fehler_anzeigen(e, 'wirf()')
        self.assertIn('[WertFehler] Zeile 1: Text lässt sich nicht als', text)

    def test_keyerror_bleibt_keyerror_ohne_anfuehrungszeichen(self):
        with self.assertRaises(KeyError) as ctx:
            lauf('wirf()', interpreter_mit_wirf(KeyError('x')))
        self.assertEqual(str(ctx.exception), "Zeile 1: 'x'")  # str(KeyError) setzt den Text selbst in '...'; nicht doppelt
        self.assertEqual(fehlerart_name(ctx.exception), 'SchluesselFehler')

    def test_oserror_klasse_bleibt_erhalten(self):
        with self.assertRaises(PermissionError) as ctx:
            lauf('wirf()', interpreter_mit_wirf(PermissionError(13, 'Permission denied')))
        self.assertEqual(fehlerart_name(ctx.exception), 'DateiFehler')
        self.assertTrue(str(ctx.exception).startswith('Zeile 1: '))

    def test_gewoehnliche_fehler_unveraendert(self):
        with self.assertRaises(ValueError) as ctx:
            lauf('wirf()', interpreter_mit_wirf(ValueError('Text')))
        self.assertEqual(str(ctx.exception), 'Zeile 1: Text')
        self.assertIs(type(ctx.exception), ValueError)

    def test_ausnahmefehler_behaelt_wert(self):
        ergebnis, _ = lauf('sei m = nichts\nversuche { werfe [1, 2] } fange e { m = e }\nm')
        self.assertEqual(ergebnis, [1, 2])

    def test_englische_python_meldungen_werden_deutsch(self):
        for ausnahme, erwartet in [
            (OverflowError(34, 'Result too large'), 'Ergebnis ist zu groß'),
            (OverflowError('int too large to convert to float'), 'Ganzzahl ist zu groß'),
            (ZeroDivisionError('division by zero'), 'Division durch Null'),
            (ZeroDivisionError('integer division or modulo by zero'), 'Division durch Null'),
            (RecursionError('maximum recursion depth exceeded while calling a Python object'),
             'Maximale Rekursionstiefe überschritten'),
            (ValueError("invalid literal for int() with base 10: 'a'"), "Kann 'a' nicht in Ganzzahl umwandeln"),
            (TypeError("unhashable type: 'list'"), "Typ 'Liste' ist nicht hashbar"),
            (TypeError("cannot use 'list' as a dict key (unhashable type: 'list')"), "Typ 'Liste' ist nicht hashbar"),
        ]:
            with self.subTest(meldung=str(ausnahme)):
                self.assertIn(erwartet, _meldung_deutsch(ausnahme))

    def test_ueberlauf_unabhaengig_vom_wortlaut_deutsch(self):
        # Linux meldet Gleitkomma-Überlauf als errno-Tupel, Windows als 'Result too large'
        for ausnahme in (OverflowError(34, 'Numerical result out of range'),
                         OverflowError(34, 'Result too large')):
            with self.subTest(meldung=str(ausnahme)):
                self.assertEqual(_meldung_deutsch(ausnahme), 'Ergebnis ist zu groß für eine Kommazahl')

    def test_deutsche_meldungen_bleiben_unveraendert(self):
        for ausnahme in (ZeroDivisionError('Ganzzahldivision durch Null'),
                         OverflowError("'exponential' ergibt für 1000 eine zu große Zahl"),
                         ValueError('Kann \'x\' nicht in Ganzzahl umwandeln'),
                         TypeError('Operator + nicht unterstützt')):
            with self.subTest(meldung=str(ausnahme)):
                self.assertEqual(_meldung_deutsch(ausnahme), str(ausnahme))

    def test_ueberlauf_im_skript_ist_deutsch(self):
        for code in ('2 ** 10000.0', '10 ** 500 / 1', '10 ** 400 * 1.0'):
            with self.subTest(code=code):
                with self.assertRaises(OverflowError) as ctx:
                    lauf(code)
                for englisch in ('too large to convert', 'Result too large', 'too large for a float'):
                    self.assertNotIn(englisch, str(ctx.exception))
                self.assertIn('zu groß', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
