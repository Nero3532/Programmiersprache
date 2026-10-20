# -*- coding: utf-8 -*-
"""
Automatisierte Tests für den Deutsch-Interpreter.

Ausführen mit:
    python -m unittest discover -s tests -v
oder (falls installiert):
    pytest tests/
"""
import contextlib
import glob
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEISPIELE_ORDNER = os.path.join(PROJEKT_WURZEL, 'beispiele')


def lauf(code: str, interpreter: Interpreter = None, ladepfad: str = None):
    """Tokenisiert, parst und führt Code aus. Gibt (ergebnis, interpreter) zurück."""
    if interpreter is None:
        interpreter = Interpreter(ladepfad=ladepfad)
    tokens = Lexer(code).tokenisieren()
    baum = Parser(tokens).parse()
    ergebnis = interpreter.ausfuehren(baum)
    return ergebnis, interpreter


def ausgabe_erfassen(code: str, interpreter: Interpreter = None) -> str:
    """Führt Code aus und gibt die auf stdout gedruckte Ausgabe zurück."""
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        lauf(code, interpreter)
    return puffer.getvalue()


class TestBeispielSkripte(unittest.TestCase):
    """Smoke-Test: jede Datei in beispiele/ muss ohne Fehler durchlaufen."""

    def test_alle_beispiele_laufen_fehlerfrei(self):
        dateien = sorted(glob.glob(os.path.join(BEISPIELE_ORDNER, '*.deu')))
        self.assertGreater(len(dateien), 0, 'Keine .deu-Dateien in beispiele/ gefunden')
        for pfad in dateien:
            with self.subTest(datei=os.path.basename(pfad)):
                with open(pfad, 'r', encoding='utf-8') as f:
                    quelltext = f.read()
                with contextlib.redirect_stdout(io.StringIO()):
                    lauf(quelltext, ladepfad=BEISPIELE_ORDNER)


class TestOperatoren(unittest.TestCase):
    def test_potenz(self):
        self.assertEqual(ausgabe_erfassen('drucke(2 ** 10)'), '1024\n')
        self.assertEqual(ausgabe_erfassen('drucke(-2 ** 2)'), '-4\n')
        self.assertEqual(ausgabe_erfassen('drucke(2 ** 2 ** 3)'), '256\n')  # rechtsassoziativ

    def test_ganzzahldivision(self):
        self.assertEqual(ausgabe_erfassen('drucke(7 // 2)'), '3\n')
        self.assertEqual(ausgabe_erfassen('drucke(-7 // 2)'), '-4\n')

    def test_division_durch_null(self):
        with self.assertRaises(ZeroDivisionError):
            lauf('1 / 0')
        with self.assertRaises(ZeroDivisionError):
            lauf('1 // 0')

    def test_nicht_in(self):
        self.assertEqual(ausgabe_erfassen('drucke(5 nicht in [1,2,3])'), 'wahr\n')
        self.assertEqual(ausgabe_erfassen('drucke(2 nicht in [1,2,3])'), 'falsch\n')

    def test_operator_typfehler_deutsch(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('5 < "text"')
        self.assertIn('nicht unterstützt', str(ctx.exception))

    def test_sortiere_numerisch(self):
        ergebnis, _ = lauf('sortiere([10, 2, 33, 1])')
        self.assertEqual(ergebnis, [1, 2, 10, 33])


class TestSlicing(unittest.TestCase):
    def test_listen_slicing(self):
        self.assertEqual(ausgabe_erfassen('drucke([0,1,2,3,4][1:3])'), '[1, 2]\n')
        self.assertEqual(ausgabe_erfassen('drucke([0,1,2,3,4][::-1])'), '[4, 3, 2, 1, 0]\n')

    def test_string_slicing(self):
        self.assertEqual(ausgabe_erfassen('drucke("abcdef"[1:3])'), 'bc\n')

    def test_slice_zuweisung_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei l = [1,2,3]\nl[0:1] = [9]')


class TestLambda(unittest.TestCase):
    def test_anonyme_funktion(self):
        self.assertEqual(ausgabe_erfassen(
            'sei f = funktion(x) { zurück x * x }\ndrucke(f(5))'
        ), '25\n')

    def test_lambda_als_argument(self):
        code = '''
        funktion wende_an(f, wert) { zurück f(wert) }
        drucke(wende_an(funktion(x) { zurück x + 1 }, 10))
        '''
        self.assertEqual(ausgabe_erfassen(code), '11\n')


class TestPasse(unittest.TestCase):
    def test_mehrfachwert_und_sonst(self):
        code = '''
        funktion typ_von_tag(t) {
            passe t {
                fall "Sa", "So": { zurück "Wochenende" }
                sonst: { zurück "Werktag" }
            }
        }
        drucke(typ_von_tag("Sa"))
        drucke(typ_von_tag("Mi"))
        '''
        self.assertEqual(ausgabe_erfassen(code), 'Wochenende\nWerktag\n')

    def test_abbrechen_in_fall_propagiert_zur_schleife(self):
        code = '''
        für i in bereich(5) {
            passe i {
                fall 3: { abbrechen }
                sonst: { drucke(i) }
            }
        }
        '''
        self.assertEqual(ausgabe_erfassen(code), '0\n1\n2\n')


class TestMehrfachvererbung(unittest.TestCase):
    def test_diamant_vererbung(self):
        code = '''
        klasse Basis { funktion wer(dies) { zurück "Basis" } }
        klasse Links(Basis) { }
        klasse Rechts(Basis) { }
        klasse Unten(Links, Rechts) { }
        drucke(neu Unten().wer())
        '''
        self.assertEqual(ausgabe_erfassen(code), 'Basis\n')


class TestTypHinweise(unittest.TestCase):
    def test_korrekter_typ_geht_durch(self):
        ergebnis, _ = lauf(
            'funktion addiere(a: Ganzzahl, b: Ganzzahl) -> Ganzzahl { zurück a + b }\n'
            'addiere(2, 3)'
        )
        self.assertEqual(ergebnis, 5)

    def test_falscher_typ_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a: Ganzzahl) { zurück a }\nf("text")')

    def test_kommazahl_akzeptiert_ganzzahl(self):
        ergebnis, _ = lauf('sei n: Kommazahl = 5')
        self.assertEqual(ergebnis, 5)

    def test_unbekannter_typ_hinweis_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei x: Gannzahl = 5')

    def test_impliziter_none_return_wird_geprueft(self):
        with self.assertRaises(TypeError):
            lauf('funktion f() -> Ganzzahl { sei x = 1 }\nf()')


class TestWerfe(unittest.TestCase):
    def test_string_werfen_und_fangen(self):
        code = '''
        versuche { werfe "kaputt" } fange f { drucke(f) }
        '''
        self.assertEqual(ausgabe_erfassen(code), 'kaputt\n')

    def test_beliebigen_wert_werfen(self):
        code = '''
        versuche { werfe 42 } fange f { drucke(typ(f)) }
        '''
        self.assertEqual(ausgabe_erfassen(code), 'Ganzzahl\n')

    def test_unbehandeltes_werfe_propagiert(self):
        from deutsch.interpreter import AusnahmeFehler
        with self.assertRaises(AusnahmeFehler):
            lauf('werfe "uncaught"')


class TestMathe(unittest.TestCase):
    def test_grundfunktionen(self):
        ergebnis, _ = lauf('wurzel(16)')
        self.assertEqual(ergebnis, 4.0)

    def test_konstanten(self):
        import math
        ergebnis, _ = lauf('pi')
        self.assertAlmostEqual(ergebnis, math.pi)

    def test_wurzel_negativ_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('wurzel(-1)')


class TestDateiIO(unittest.TestCase):
    def test_schreiben_lesen_anhaengen(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('datei_schreiben("x.txt", "Hallo")', interpreter)
            lauf('datei_anhaengen("x.txt", " Welt")', interpreter)
            ergebnis, _ = lauf('datei_lesen("x.txt")', interpreter)
            self.assertEqual(ergebnis, 'Hallo Welt')

    def test_fehlende_datei_wirft_deutschen_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError) as ctx:
                lauf('datei_lesen("nicht_da.txt")', interpreter)
            self.assertIn('nicht gefunden', str(ctx.exception))


class TestFehlermeldungen(unittest.TestCase):
    def test_schluesselfehler_ohne_doppelte_anfuehrungszeichen(self):
        with self.assertRaises(KeyError) as ctx:
            lauf('sei d = {"a": 1}\nd["fehlt"]')
        self.assertNotIn('\\', str(ctx.exception))
        self.assertIn("Schlüssel 'fehlt'", str(ctx.exception))

    def test_index_typfehler_deutsch(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('sei l = [1,2,3]\nl["x"]')
        self.assertIn('Index-Typ', str(ctx.exception))

    def test_case_sensitive_schluesselwoerter(self):
        # 'Wenn' (groß) ist kein Schlüsselwort mehr, muss als Bezeichner nutzbar sein
        ergebnis, _ = lauf('sei Wenn = 5\nWenn')
        self.assertEqual(ergebnis, 5)

    def test_wissenschaftliche_notation(self):
        ergebnis, _ = lauf('1.0e10')
        self.assertEqual(ergebnis, 1.0e10)


class TestStacktrace(unittest.TestCase):
    def test_aufruf_stack_wird_gefuellt_bei_unbehandeltem_fehler(self):
        interpreter = Interpreter()
        code = '''
        funktion innen() { werfe "boom" }
        funktion aussen() { zurück innen() }
        aussen()
        '''
        with self.assertRaises(Exception):
            lauf(code, interpreter)
        self.assertEqual(len(interpreter._letzter_aufruf_stack), 2)
        # Gespeichert in Aufrufreihenfolge (äußerste zuerst) – main.py dreht für die Anzeige um
        namen = [eintrag.name for eintrag in interpreter._letzter_aufruf_stack]
        self.assertEqual(namen, ['aussen', 'innen'])

    def test_leerer_stack_ohne_funktionsaufruf(self):
        interpreter = Interpreter()
        with self.assertRaises(ZeroDivisionError):
            lauf('1 / 0', interpreter)
        self.assertEqual(interpreter._letzter_aufruf_stack, [])


class TestVergleichsKette(unittest.TestCase):
    def test_verkettung_ausserhalb_des_bereichs(self):
        ergebnis, _ = lauf('sei x = 50\n1 < x < 10')
        self.assertFalse(ergebnis)

    def test_verkettung_innerhalb_des_bereichs(self):
        ergebnis, _ = lauf('1 < 5 < 10 < 20')
        self.assertTrue(ergebnis)

    def test_kurzschluss(self):
        ergebnis, _ = lauf('10 < 5 < 20')
        self.assertFalse(ergebnis)


class TestTernaerAusdruck(unittest.TestCase):
    def test_einfacher_ternaer(self):
        self.assertEqual(
            ausgabe_erfassen('drucke("erwachsen" wenn 20 >= 18 sonst "kind")'),
            'erwachsen\n'
        )

    def test_verkettung_rechtsassoziativ(self):
        ergebnis, _ = lauf('5 wenn falsch sonst 10 wenn wahr sonst 15')
        self.assertEqual(ergebnis, 10)

    def test_koexistenz_mit_listen_comprehension_filter(self):
        # Regression: das 'wenn'-Filter einer Comprehension darf nicht vom
        # Ternär-Lookahead in _ausdruck() verschluckt werden.
        ergebnis, _ = lauf('[x*x für x in [1,2,3,4] wenn x % 2 == 0]')
        self.assertEqual(ergebnis, [4, 16])

    def test_ternaer_als_comprehension_wert(self):
        ergebnis, _ = lauf('[x wenn x > 2 sonst -x für x in [1,2,3,4]]')
        self.assertEqual(ergebnis, [-1, -2, 3, 4])


class TestDestrukturierung(unittest.TestCase):
    def test_einfache_destrukturierung(self):
        _, interpreter = lauf('sei [a, b, c] = [1, 2, 3]')
        self.assertEqual(interpreter.global_umgebung.hole('a'), 1)
        self.assertEqual(interpreter.global_umgebung.hole('b'), 2)
        self.assertEqual(interpreter.global_umgebung.hole('c'), 3)

    def test_falsche_anzahl_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei [p, q] = [1, 2, 3]')


class TestFormatSpec(unittest.TestCase):
    def test_nachkommastellen(self):
        self.assertEqual(
            ausgabe_erfassen('drucke("Pi = {3.14159265:.2f}")'),
            'Pi = 3.14\n'
        )

    def test_slice_in_interpolation_kollidiert_nicht_mit_format_spec(self):
        # Regression: der ':' in einem Slice-Ausdruck darf nicht als
        # Format-Spec-Trenner missverstanden werden.
        self.assertEqual(
            ausgabe_erfassen('drucke("{[1,2,3,4,5][1:3]}")'),
            '[2, 3]\n'
        )

    def test_ungueltiges_format_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('sei text = "abc"\n"{text:d}"')


class TestMengen(unittest.TestCase):
    def test_mengen_literal_und_operationen(self):
        ergebnis, _ = lauf('{1,2,3}.vereinigung({2,3,4})')
        self.assertEqual(ergebnis, {1, 2, 3, 4})
        ergebnis, _ = lauf('{1,2,3}.schnittmenge({2,3,4})')
        self.assertEqual(ergebnis, {2, 3})
        ergebnis, _ = lauf('{1,2,3}.differenz({2,3,4})')
        self.assertEqual(ergebnis, {1})

    def test_leere_geschweifte_klammern_sind_woerterbuch(self):
        ergebnis, _ = lauf('{}')
        self.assertEqual(ergebnis, {})
        self.assertIsInstance(ergebnis, dict)

    def test_menge_builtin_dedupliziert(self):
        ergebnis, _ = lauf('menge([1,1,2,2,3])')
        self.assertEqual(ergebnis, {1, 2, 3})

    def test_unhashbares_element_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('{[1,2], 3}')

    def test_vereinigung_mit_nicht_menge_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('{1,2}.vereinigung([1,2])')

    def test_typ_hinweis_menge(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(s: Menge) { zurück s }\nf([1,2])')


class TestDiagnostik(unittest.TestCase):
    def test_tippfehler_schlaegt_aehnlichen_namen_vor(self):
        with self.assertRaises(NameError) as ctx:
            lauf('sei zaehler = 5\nzahler')
        self.assertIn("meintest du 'zaehler'", str(ctx.exception))

    def test_voellig_unbekannter_name_ohne_vorschlag(self):
        with self.assertRaises(NameError) as ctx:
            lauf('voelligUnbekannterXyzName123')
        self.assertNotIn('meintest du', str(ctx.exception))


class TestZufall(unittest.TestCase):
    def test_zufall_im_bereich(self):
        ergebnis, _ = lauf('zufall()')
        self.assertGreaterEqual(ergebnis, 0)
        self.assertLess(ergebnis, 1)

    def test_zufallszahl_einzelwert(self):
        ergebnis, _ = lauf('zufallszahl(5, 5)')
        self.assertEqual(ergebnis, 5)

    def test_zufallszahl_lo_groesser_hi_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('zufallszahl(10, 1)')

    def test_mische_behaelt_alle_elemente(self):
        _, interpreter = lauf('sei l = [1,2,3,4,5]\nmische(l)')
        self.assertEqual(sorted(interpreter.global_umgebung.hole('l')), [1, 2, 3, 4, 5])


class TestFunktionaleHelfer(unittest.TestCase):
    def test_summe(self):
        ergebnis, _ = lauf('summe([1,2,3,4])')
        self.assertEqual(ergebnis, 10)
        ergebnis, _ = lauf('summe(1,2,3)')
        self.assertEqual(ergebnis, 6)

    def test_alle_und_einige(self):
        self.assertTrue(lauf('alle([wahr, wahr])')[0])
        self.assertFalse(lauf('alle([wahr, falsch])')[0])
        self.assertTrue(lauf('einige([falsch, wahr])')[0])
        self.assertFalse(lauf('einige([falsch, falsch])')[0])

    def test_aufzaehlen(self):
        ergebnis, _ = lauf('aufzaehlen(["a","b"])')
        self.assertEqual(ergebnis, [[0, 'a'], [1, 'b']])

    def test_zippe(self):
        ergebnis, _ = lauf('zippe([1,2,3], ["a","b","c"])')
        self.assertEqual(ergebnis, [[1, 'a'], [2, 'b'], [3, 'c']])

    def test_zippe_mit_menge_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('zippe({1,2}, [3,4])')


class TestBodenDecke(unittest.TestCase):
    def test_boden_und_decke(self):
        self.assertEqual(lauf('boden(3.7)')[0], 3)
        self.assertEqual(lauf('decke(3.2)')[0], 4)


class TestJson(unittest.TestCase):
    def test_schreiben_und_lesen_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('json_schreiben("d.json", {"name": "Anna", "zahlen": [1,2,3]})', interpreter)
            ergebnis, _ = lauf('json_lesen("d.json")', interpreter)
            self.assertEqual(ergebnis, {'name': 'Anna', 'zahlen': [1, 2, 3]})

    def test_menge_wird_zu_sortierter_liste_konvertiert(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('json_schreiben("m.json", {"werte": {3,1,2}})', interpreter)
            ergebnis, _ = lauf('json_lesen("m.json")', interpreter)
            self.assertEqual(ergebnis, {'werte': [1, 2, 3]})

    def test_ungueltiges_json_wirft_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'kaputt.json'), 'w', encoding='utf-8') as f:
                f.write('{nicht gueltig')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ValueError):
                lauf('json_lesen("kaputt.json")', interpreter)


class TestKommandozeilenArgumente(unittest.TestCase):
    def test_argumente_werden_durchgereicht(self):
        interpreter = Interpreter(argumente=['eins', 'zwei'])
        ergebnis, _ = lauf('kommandozeilen_argumente()', interpreter)
        self.assertEqual(ergebnis, ['eins', 'zwei'])

    def test_keine_argumente_ist_leere_liste(self):
        ergebnis, _ = lauf('kommandozeilen_argumente()')
        self.assertEqual(ergebnis, [])


class TestRegex(unittest.TestCase):
    def test_passt_zu(self):
        self.assertTrue(lauf(r'passt_zu("^\d+$", "12345")')[0])
        self.assertFalse(lauf(r'passt_zu("^\d+$", "abc")')[0])

    def test_regex_ersetze(self):
        ergebnis, _ = lauf(r'regex_ersetze("\s+", " ", "hallo    welt")')
        self.assertEqual(ergebnis, 'hallo welt')

    def test_regex_finde(self):
        ergebnis, _ = lauf(r'regex_finde("\d+", "abc123def")')
        self.assertEqual(ergebnis, '123')
        ergebnis, _ = lauf(r'regex_finde("\d+", "keine zahlen")')
        self.assertIsNone(ergebnis)

    def test_regex_finde_alle(self):
        ergebnis, _ = lauf(r'regex_finde_alle("\d+", "a1b22c333")')
        self.assertEqual(ergebnis, ['1', '22', '333'])

    def test_ungueltiges_muster_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('passt_zu("[", "x")')


class TestDatumZeit(unittest.TestCase):
    def test_jetzt_ist_positiv(self):
        ergebnis, _ = lauf('jetzt()')
        self.assertGreater(ergebnis, 0)

    def test_datum_formatieren(self):
        ergebnis, _ = lauf('datum_formatieren(0, "%Y")')
        self.assertEqual(ergebnis, '1970')

    def test_ungueltiger_zeitstempel_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('datum_formatieren("keine_zahl", "%Y")')


class TestIndexUndZaehlen(unittest.TestCase):
    def test_liste_index_von_und_zaehle(self):
        ergebnis, _ = lauf('[1,2,3,2,1].index_von(3)')
        self.assertEqual(ergebnis, 2)
        ergebnis, _ = lauf('[1,2,3,2,1].zaehle(1)')
        self.assertEqual(ergebnis, 2)

    def test_liste_index_von_nicht_gefunden_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('[1,2,3].index_von(99)')

    def test_string_index_von_und_zaehle(self):
        ergebnis, _ = lauf('"hallo welt hallo".index_von("welt")')
        self.assertEqual(ergebnis, 6)
        ergebnis, _ = lauf('"hallo welt hallo".zaehle("hallo")')
        self.assertEqual(ergebnis, 2)

    def test_string_index_von_nicht_gefunden_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('"abc".index_von("xyz")')

    def test_string_index_von_falscher_typ_wirft_deutschen_fehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('"abc".index_von(5)')
        self.assertNotIn('must be str', str(ctx.exception))

    def test_string_zaehle_falscher_typ_wirft_deutschen_fehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('"abc".zaehle(5)')
        self.assertNotIn('must be str', str(ctx.exception))


class TestStatistik(unittest.TestCase):
    def test_mittelwert_median(self):
        self.assertEqual(lauf('mittelwert([1,2,3,4,5])')[0], 3)
        self.assertEqual(lauf('median([1,2,3,4,5])')[0], 3)

    def test_stdabweichung(self):
        ergebnis, _ = lauf('stdabweichung([2,4,4,4,5,5,7,9])')
        self.assertAlmostEqual(ergebnis, 2.0)

    def test_leere_liste_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('mittelwert([])')
        with self.assertRaises(ValueError):
            lauf('median([])')
        with self.assertRaises(ValueError):
            lauf('stdabweichung([])')


class TestTiefeKopie(unittest.TestCase):
    def test_verschachtelte_strukturen_werden_unabhaengig(self):
        code = '''
        sei original = {"zahlen": [1,2,3], "verschachtelt": {"a": [1,2]}}
        sei kopie = tiefe_kopie(original)
        kopie["zahlen"].anhaengen(99)
        kopie["verschachtelt"]["a"].anhaengen(99)
        '''
        _, interpreter = lauf(code)
        original = interpreter.global_umgebung.hole('original')
        kopie = interpreter.global_umgebung.hole('kopie')
        self.assertEqual(original['zahlen'], [1, 2, 3])
        self.assertEqual(kopie['zahlen'], [1, 2, 3, 99])
        self.assertEqual(original['verschachtelt']['a'], [1, 2])
        self.assertEqual(kopie['verschachtelt']['a'], [1, 2, 99])


class TestUmgebungsvariable(unittest.TestCase):
    def test_fehlend_ohne_standard_ist_nichts(self):
        ergebnis, _ = lauf('umgebungsvariable("GARANTIERT_NICHT_GESETZT_XYZ")')
        self.assertIsNone(ergebnis)

    def test_fehlend_mit_standard(self):
        ergebnis, _ = lauf('umgebungsvariable("GARANTIERT_NICHT_GESETZT_XYZ", "standard")')
        self.assertEqual(ergebnis, 'standard')


class TestDateisystemHelfer(unittest.TestCase):
    def test_pfad_existiert(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            self.assertTrue(lauf('pfad_existiert(".")', interpreter)[0])
            self.assertFalse(lauf('pfad_existiert("nicht_da_xyz")', interpreter)[0])

    def test_ordner_erstellen_und_dateien_auflisten(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('ordner_erstellen("neu")', interpreter)
            lauf('datei_schreiben("neu/a.txt", "x")', interpreter)
            ergebnis, _ = lauf('dateien_auflisten("neu")', interpreter)
            self.assertEqual(ergebnis, ['a.txt'])

    def test_dateien_auflisten_fehlender_ordner_wirft_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError):
                lauf('dateien_auflisten("nicht_da_xyz")', interpreter)

    def test_ordner_erstellen_auf_existierender_datei_wirft_deutschen_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('datei_schreiben("x.txt", "a")', interpreter)
            with self.assertRaises(FileExistsError) as ctx:
                lauf('ordner_erstellen("x.txt")', interpreter)
            self.assertIn('existiert bereits als Datei', str(ctx.exception))


class TestHashingKodierung(unittest.TestCase):
    def test_hash_sha256_laenge(self):
        ergebnis, _ = lauf('hash_sha256("hallo")')
        self.assertEqual(len(ergebnis), 64)

    def test_base64_roundtrip_mit_umlauten(self):
        code = 'sei k = base64_kodieren("Hallo Welt äöü")\nbase64_dekodieren(k)'
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, 'Hallo Welt äöü')

    def test_ungueltiges_base64_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('base64_dekodieren("!!!nicht_gueltig!!!")')


class TestSchleifenDestrukturierung(unittest.TestCase):
    def test_fuer_schleife(self):
        code = '''
        sei ausgabe = []
        für [i, wert] in aufzaehlen(["a","b"]) {
            ausgabe.anhaengen([i, wert])
        }
        ausgabe
        '''
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, [[0, 'a'], [1, 'b']])

    def test_listen_comprehension(self):
        ergebnis, _ = lauf('[x*y für [x, y] in zippe([1,2,3], [10,20,30])]')
        self.assertEqual(ergebnis, [10, 40, 90])

    def test_normale_fuer_schleife_weiterhin_ok(self):
        ergebnis, _ = lauf('sei s = 0\nfür x in [1,2,3] { s += x }\ns')
        self.assertEqual(ergebnis, 6)

    def test_falsche_anzahl_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('für [a, b] in [[1,2,3]] { a }')

    def test_woerterbuch_paare_destrukturierung(self):
        code = '''
        sei d = {"a": 1, "b": 2}
        sei ausgabe = []
        für [schluessel, wert] in d.paare() {
            ausgabe.anhaengen(schluessel)
        }
        sortiere(ausgabe)
        '''
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, ['a', 'b'])

    def test_woerterbuch_direkt_destrukturieren_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei d = {"a": 1}\nfür [k, v] in d { k }')


class TestKeywordArgumente(unittest.TestCase):
    def test_reine_keyword_argumente(self):
        code = 'funktion f(a, b) { zurück a + b }\nf(a=1, b=2)'
        self.assertEqual(lauf(code)[0], 3)

    def test_gemischt_positional_und_keyword(self):
        code = 'funktion f(a, b, c=10) { zurück a + b + c }\nf(1, c=100, b=2)'
        self.assertEqual(lauf(code)[0], 103)

    def test_neu_instanz_mit_keyword_argumenten(self):
        code = '''
        klasse Punkt {
            funktion __init__(dies, x, y=0) { dies.x = x; dies.y = y }
        }
        neu Punkt(x=5, y=9).y
        '''
        self.assertEqual(lauf(code)[0], 9)

    def test_unbekanntes_keyword_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a) { zurück a }\nf(b=1)')

    def test_doppelter_wert_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a) { zurück a }\nf(1, a=2)')

    def test_fehlendes_pflichtargument_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a, b) { zurück a }\nf(a=1)')

    def test_keyword_auf_variadic_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(*a) { zurück a }\nf(a=[1,2])')

    def test_positional_nach_keyword_ist_syntaxfehler(self):
        with self.assertRaises(SyntaxError):
            lauf('funktion f(a, b) { zurück a }\nf(a=1, 2)')

    def test_doppeltes_keyword_ist_syntaxfehler(self):
        with self.assertRaises(SyntaxError):
            lauf('funktion f(a) { zurück a }\nf(a=1, a=2)')


class TestZyklischesLaden(unittest.TestCase):
    def test_zyklus_wird_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'a.deu'), 'w', encoding='utf-8') as f:
                f.write('lade "b.deu"\n')
            with open(os.path.join(tmp, 'b.deu'), 'w', encoding='utf-8') as f:
                f.write('lade "a.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ImportError):
                lauf('lade "a.deu"', interpreter)

    def test_wiederholtes_nicht_zyklisches_laden_funktioniert(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'c.deu'), 'w', encoding='utf-8') as f:
                f.write('funktion h() { zurück 42 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "c.deu"', interpreter)
            ergebnis, _ = lauf('lade "c.deu"\nh()', interpreter)
            self.assertEqual(ergebnis, 42)

    def test_direkte_selbstreferenz_wird_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'self.deu'), 'w', encoding='utf-8') as f:
                f.write('lade "self.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ImportError):
                lauf('lade "self.deu"', interpreter)


class TestOperatorUeberladung(unittest.TestCase):
    def test_addiere_ueberladung(self):
        code = '''
        klasse Vektor {
            funktion __init__(dies, x, y) { dies.x = x; dies.y = y }
            funktion __addiere__(dies, andere) { zurück neu Vektor(dies.x + andere.x, dies.y + andere.y) }
        }
        sei ergebnis = neu Vektor(1,2) + neu Vektor(3,4)
        [ergebnis.x, ergebnis.y]
        '''
        self.assertEqual(lauf(code)[0], [4, 6])

    def test_gleich_ueberladung(self):
        code = '''
        klasse Punkt {
            funktion __init__(dies, x) { dies.x = x }
            funktion __gleich__(dies, andere) { zurück dies.x == andere.x }
        }
        neu Punkt(5) == neu Punkt(5)
        '''
        self.assertTrue(lauf(code)[0])

    def test_ohne_ueberladung_normaler_fehler(self):
        code = '''
        klasse A { funktion __init__(dies) { } }
        neu A() - neu A()
        '''
        with self.assertRaises(TypeError):
            lauf(code)

    def test_verbund_zuweisung_nutzt_ueberladung(self):
        code = '''
        klasse Vektor {
            funktion __init__(dies, x) { dies.x = x }
            funktion __addiere__(dies, andere) { zurück neu Vektor(dies.x + andere.x) }
        }
        sei v = neu Vektor(5)
        v += neu Vektor(3)
        v.x
        '''
        self.assertEqual(lauf(code)[0], 8)

    def test_normale_zahlen_unveraendert(self):
        self.assertEqual(lauf('5 + 3')[0], 8)


class TestMengenVergleiche(unittest.TestCase):
    def test_teilmenge_und_obermenge(self):
        self.assertTrue(lauf('{1,2}.teilmenge_von({1,2,3})')[0])
        self.assertFalse(lauf('{1,2,3}.teilmenge_von({1,2})')[0])
        self.assertTrue(lauf('{1,2,3}.obermenge_von({1,2})')[0])

    def test_symmetrische_differenz(self):
        ergebnis, _ = lauf('{1,2,3}.symmetrische_differenz({2,3,4})')
        self.assertEqual(ergebnis, {1, 4})


class TestListeErweitern(unittest.TestCase):
    def test_einfuegen(self):
        _, interpreter = lauf('sei l = [1,2,3]\nl.einfuegen(1, 99)')
        self.assertEqual(interpreter.global_umgebung.hole('l'), [1, 99, 2, 3])

    def test_erweitere(self):
        _, interpreter = lauf('sei l = [1,2]\nl.erweitere([3,4])')
        self.assertEqual(interpreter.global_umgebung.hole('l'), [1, 2, 3, 4])

    def test_erweitere_falscher_typ_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei l = [1,2]\nl.erweitere("abc")')


class TestMatheUtilities(unittest.TestCase):
    def test_ggt_kgv(self):
        self.assertEqual(lauf('ggt(12, 18)')[0], 6)
        self.assertEqual(lauf('ggt([12, 18, 24])')[0], 6)
        self.assertEqual(lauf('kgv(4, 6)')[0], 12)

    def test_vorzeichen(self):
        self.assertEqual(lauf('vorzeichen(-5)')[0], -1)
        self.assertEqual(lauf('vorzeichen(0)')[0], 0)
        self.assertEqual(lauf('vorzeichen(3.5)')[0], 1)


class TestStringPraedikate(unittest.TestCase):
    def test_praedikate(self):
        self.assertTrue(lauf('"123".ist_ziffer()')[0])
        self.assertFalse(lauf('"abc".ist_ziffer()')[0])
        self.assertTrue(lauf('"abc".ist_buchstabe()')[0])
        self.assertTrue(lauf('"   ".ist_leerraum()')[0])


class TestPruefeAnweisung(unittest.TestCase):
    def test_erfolgreiche_pruefung_gibt_keinen_fehler(self):
        lauf('pruefe wahr')
        lauf('pruefe 1 + 1 == 2, "sollte nicht passieren"')

    def test_fehlgeschlagene_pruefung_mit_meldung(self):
        with self.assertRaises(AssertionError) as ctx:
            lauf('pruefe falsch, "eigene Meldung"')
        self.assertIn('eigene Meldung', str(ctx.exception))

    def test_fehlgeschlagene_pruefung_ohne_meldung(self):
        with self.assertRaises(AssertionError) as ctx:
            lauf('pruefe 1 == 2')
        self.assertIn('fehlgeschlagen', str(ctx.exception))


class TestKonstanten(unittest.TestCase):
    def test_lesen(self):
        self.assertEqual(lauf('konstante PI = 3.14\nPI')[0], 3.14)

    def test_neuzuweisung_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('konstante x = 1\nx = 2')

    def test_verbund_zuweisung_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('konstante x = 1\nx += 1')

    def test_redeklaration_im_selben_scope_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('konstante x = 1\nkonstante x = 2')

    def test_verschachtelter_scope_schattet_korrekt(self):
        code = '''
        konstante x = 1
        funktion f() {
            konstante x = 2
            zurück x
        }
        [f(), x]
        '''
        self.assertEqual(lauf(code)[0], [2, 1])

    def test_sei_bleibt_unveraendert(self):
        self.assertEqual(lauf('sei x = 1\nx = 2\nx')[0], 2)


class TestTypisiertesFangen(unittest.TestCase):
    def test_nicht_passender_typ_propagiert(self):
        with self.assertRaises(ZeroDivisionError):
            lauf('versuche { 1/0 } fange (TypeError) f { f }')

    def test_passender_typ_faengt(self):
        ergebnis, _ = lauf('versuche { 1/0 } fange (ZeroDivisionError, TypeError) f { f }\n')
        # kein Fehler mehr -> Skript laeuft durch

    def test_endlich_laeuft_auch_bei_nicht_passendem_typ(self):
        code = '''
        sei lief = falsch
        versuche {
            versuche { 1/0 } fange (TypeError) f { f } endlich { lief = wahr }
        } fange g { g }
        lief
        '''
        self.assertTrue(lauf(code)[0])

    def test_basisklasse_faengt_abgeleiteten_fehler(self):
        code = '''
        sei d = {"a": 1}
        versuche { d["fehlt"] } fange (KeyError) f { f }
        '''
        lauf(code)  # darf nicht werfen

    def test_ausnahmefehler_nach_name_fangbar(self):
        code = 'sei erfasst = nichts\nversuche { werfe 42 } fange (AusnahmeFehler) f { erfasst = f }\nerfasst'
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, 42)


class TestLadeAls(unittest.TestCase):
    def test_namensraum_bindungen(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('funktion addiere(a, b) { zurück a + b }\nkonstante VERSION = "1.0"\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "mod.deu" als m\nm.addiere(3, 4)', interpreter)
            self.assertEqual(ergebnis, 7)
            ergebnis, _ = lauf('m.VERSION', interpreter)
            self.assertEqual(ergebnis, '1.0')

    def test_bindungen_landen_nicht_im_globalen_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('sei geheim = 1\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "mod.deu" als m', interpreter)
            with self.assertRaises(NameError):
                lauf('geheim', interpreter)

    def test_ohne_als_weiterhin_global(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('funktion h() { zurück 1 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "mod.deu"\nh()', interpreter)
            self.assertEqual(ergebnis, 1)


class TestStatischeKlassenmitglieder(unittest.TestCase):
    def test_geteiltes_klassenattribut(self):
        code = '''
        klasse Zaehler {
            sei anzahl = 0
            funktion __init__(dies) { Zaehler.anzahl += 1 }
        }
        neu Zaehler(); neu Zaehler(); neu Zaehler()
        Zaehler.anzahl
        '''
        self.assertEqual(lauf(code)[0], 3)

    def test_statische_methode_ueber_klasse_und_instanz(self):
        code = '''
        klasse K {
            statisch funktion hallo() { zurück "hi" }
        }
        [K.hallo(), neu K().hallo()]
        '''
        self.assertEqual(lauf(code)[0], ['hi', 'hi'])

    def test_klassenkonstante_schutz(self):
        with self.assertRaises(TypeError):
            lauf('klasse K { konstante MAX = 5 }\nK.MAX = 1')

    def test_vererbung_von_statischem_attribut_und_methode(self):
        code = '''
        klasse Basis {
            sei geteilt = "x"
            statisch funktion hallo() { zurück "hi" }
        }
        klasse Kind(Basis) { }
        [Kind.geteilt, Kind.hallo()]
        '''
        self.assertEqual(lauf(code)[0], ['x', 'hi'])

    def test_unbekanntes_klassenattribut_wirft_fehler(self):
        with self.assertRaises(AttributeError):
            lauf('klasse K { }\nK.unbekannt')


class TestSchleifenSignale(unittest.TestCase):
    """'abbrechen'/'weiter'/'zurück' enden an der Funktions- bzw. Programmgrenze mit einem Fehler."""

    def test_abbrechen_in_schleife_innerhalb_funktion_funktioniert(self):
        code = '''
        funktion bis_drei() {
            für i in bereich(10) {
                wenn i == 3 { abbrechen }
                drucke(i)
            }
        }
        bis_drei()
        '''
        self.assertEqual(ausgabe_erfassen(code), '0\n1\n2\n')

    def test_weiter_in_schleife_innerhalb_funktion_funktioniert(self):
        code = '''
        funktion ohne_eins() {
            für i in bereich(3) {
                wenn i == 1 { weiter }
                drucke(i)
            }
        }
        ohne_eins()
        '''
        self.assertEqual(ausgabe_erfassen(code), '0\n2\n')

    def test_zurueck_aus_schleife_in_funktion_funktioniert(self):
        code = '''
        funktion erste_gerade(liste) {
            für x in liste {
                wenn x % 2 == 0 { zurück x }
            }
            zurück nichts
        }
        erste_gerade([1, 3, 4, 6])
        '''
        self.assertEqual(lauf(code)[0], 4)

    def test_abbrechen_in_funktion_beendet_aufrufer_schleife_nicht_still(self):
        code = (
            'funktion f() {\n'
            '    abbrechen\n'
            '}\n'
            'sei i = 0\n'
            'solange i < 3 {\n'
            '    f()\n'
            '    i += 1\n'
            '}\n'
        )
        with self.assertRaises(RuntimeError) as ctx:
            lauf(code)
        self.assertIn("'abbrechen' außerhalb einer Schleife", str(ctx.exception))
        self.assertIn('Zeile 2', str(ctx.exception))

    def test_weiter_in_funktion_wirft_fehler_mit_zeile(self):
        code = 'funktion f() { weiter }\nfür i in [1, 2] { f() }\n'
        with self.assertRaises(RuntimeError) as ctx:
            lauf(code)
        self.assertIn("'weiter' außerhalb einer Schleife", str(ctx.exception))
        self.assertIn('Zeile 1', str(ctx.exception))

    def test_abbrechen_in_methode_ohne_schleife_wirft_fehler(self):
        code = 'klasse K { funktion m(dies) { abbrechen } }\nfür i in [1] { neu K().m() }\n'
        with self.assertRaises(RuntimeError) as ctx:
            lauf(code)
        self.assertIn("'abbrechen' außerhalb einer Schleife", str(ctx.exception))

    def test_abbrechen_auf_oberster_ebene_wirft_deutschen_fehler(self):
        with self.assertRaises(RuntimeError) as ctx:
            lauf('sei x = 1\nabbrechen\n')
        self.assertIn("'abbrechen' außerhalb einer Schleife", str(ctx.exception))
        self.assertIn('Zeile 2', str(ctx.exception))

    def test_weiter_auf_oberster_ebene_wirft_deutschen_fehler(self):
        with self.assertRaises(RuntimeError) as ctx:
            lauf('wenn wahr { weiter }')
        self.assertIn("'weiter' außerhalb einer Schleife", str(ctx.exception))

    def test_zurueck_auf_oberster_ebene_wirft_deutschen_fehler(self):
        with self.assertRaises(RuntimeError) as ctx:
            lauf('sei x = 1\nzurück x\n')
        self.assertIn("'zurück' außerhalb einer Funktion", str(ctx.exception))
        self.assertIn('Zeile 2', str(ctx.exception))

    def test_zurueck_in_schleife_auf_oberster_ebene_wirft_fehler(self):
        with self.assertRaises(RuntimeError) as ctx:
            lauf('für i in [1, 2] { zurück i }')
        self.assertIn("'zurück' außerhalb einer Funktion", str(ctx.exception))

    def test_abbrechen_in_geladener_datei_beendet_lade_schleife_nicht(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('abbrechen\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(RuntimeError) as ctx:
                lauf('für i in [1, 2] { lade "mod.deu" }', interpreter)
            self.assertIn("'abbrechen' außerhalb einer Schleife", str(ctx.exception))

    def test_interpreter_bleibt_nach_signalfehler_nutzbar(self):
        interpreter = Interpreter()
        with self.assertRaises(RuntimeError):
            lauf('abbrechen', interpreter)
        ergebnis, _ = lauf('1 + 1', interpreter)
        self.assertEqual(ergebnis, 2)


class TestTypHinweisNeuzuweisung(unittest.TestCase):
    def test_passende_neuzuweisung_geht_durch(self):
        ergebnis, _ = lauf('sei x: Ganzzahl = 1\nx = 2\nx')
        self.assertEqual(ergebnis, 2)

    def test_kommazahl_akzeptiert_ganzzahl_bei_neuzuweisung(self):
        ergebnis, _ = lauf('sei k: Kommazahl = 1.5\nk = 2\nk')
        self.assertEqual(ergebnis, 2)

    def test_verbundzuweisung_mit_passendem_typ(self):
        ergebnis, _ = lauf('sei x: Ganzzahl = 1\nx += 4\nx')
        self.assertEqual(ergebnis, 5)

    def test_falscher_typ_bei_neuzuweisung_wirft_fehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('sei x: Ganzzahl = 1\nx = "text"')
        meldung = str(ctx.exception)
        self.assertIn("Variable 'x': erwartet Typ 'Ganzzahl', bekam Zeichenkette", meldung)
        self.assertIn('Zeile 2', meldung)

    def test_neuzuweisung_meldung_gleich_wie_bei_deklaration(self):
        with self.assertRaises(TypeError) as bei_deklaration:
            lauf('sei x: Ganzzahl = "text"')
        with self.assertRaises(TypeError) as bei_zuweisung:
            lauf('sei x: Ganzzahl = 1\nx = "text"')
        self.assertIn(
            "Variable 'x': erwartet Typ 'Ganzzahl', bekam Zeichenkette", str(bei_deklaration.exception)
        )
        self.assertIn(
            "Variable 'x': erwartet Typ 'Ganzzahl', bekam Zeichenkette", str(bei_zuweisung.exception)
        )

    def test_verbundzuweisung_mit_falschem_ergebnistyp_wirft_fehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('sei x: Ganzzahl = 1\nx += 0.5')
        self.assertIn("Variable 'x': erwartet Typ 'Ganzzahl', bekam Kommazahl", str(ctx.exception))

    def test_fehlgeschlagene_zuweisung_aendert_wert_nicht(self):
        interpreter = Interpreter()
        lauf('sei x: Ganzzahl = 1', interpreter)
        with self.assertRaises(TypeError):
            lauf('x = "text"', interpreter)
        self.assertEqual(lauf('x', interpreter)[0], 1)

    def test_typ_hinweis_gilt_auch_aus_funktion_heraus(self):
        code = 'sei x: Ganzzahl = 1\nfunktion f() { x = "text" }\nf()'
        with self.assertRaises(TypeError) as ctx:
            lauf(code)
        self.assertIn("Variable 'x': erwartet Typ 'Ganzzahl'", str(ctx.exception))

    def test_typ_hinweis_klassenname(self):
        code = 'klasse P { }\nsei p: P = neu P()\n'
        lauf(code + 'p = neu P()')
        with self.assertRaises(TypeError) as ctx:
            lauf(code + 'p = 5')
        self.assertIn("Variable 'p': erwartet Typ 'P', bekam Ganzzahl", str(ctx.exception))

    def test_konstante_mit_hinweis_meldet_konstante(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('konstante K: Ganzzahl = 1\nK = "text"')
        self.assertIn('Konstante', str(ctx.exception))

    def test_neue_deklaration_ohne_hinweis_hebt_hinweis_auf(self):
        ergebnis, _ = lauf('sei x: Ganzzahl = 1\nsei x = "text"\nx = "anders"\nx')
        self.assertEqual(ergebnis, 'anders')

    def test_innere_deklaration_ohne_hinweis_ueberschattet_hinweis(self):
        code = 'sei x: Ganzzahl = 1\nwenn wahr { sei x = "text"\nx = "anders" }\nx'
        self.assertEqual(lauf(code)[0], 1)

    def test_untypisierte_variable_bleibt_frei_zuweisbar(self):
        ergebnis, _ = lauf('sei x = 1\nx = "text"\nx')
        self.assertEqual(ergebnis, 'text')


class TestZuweisungOhneSei(unittest.TestCase):
    def test_unbekannter_name_mit_vorschlag(self):
        with self.assertRaises(NameError) as ctx:
            lauf('sei zaehler = 0\nzaehlr = 2')
        meldung = str(ctx.exception)
        self.assertIn("Variable 'zaehlr' ist nicht deklariert", meldung)
        self.assertIn("meintest du 'zaehler'?", meldung)
        self.assertIn("Neue Variablen mit 'sei' anlegen.", meldung)
        self.assertIn('Zeile 2', meldung)

    def test_voellig_unbekannter_name_ohne_vorschlag(self):
        with self.assertRaises(NameError) as ctx:
            lauf('voelligUnbekannterXyzName123 = 1')
        meldung = str(ctx.exception)
        self.assertIn("Variable 'voelligUnbekannterXyzName123' ist nicht deklariert", meldung)
        self.assertNotIn('meintest du', meldung)
        self.assertIn("'sei'", meldung)

    def test_verbundzuweisung_an_unbekannten_namen_wirft_namenfehler(self):
        with self.assertRaises(NameError) as ctx:
            lauf('sei zaehler = 0\nzaehlr += 1')
        self.assertIn("Variable 'zaehlr' ist nicht deklariert", str(ctx.exception))
        self.assertIn("meintest du 'zaehler'?", str(ctx.exception))

    def test_unbekannter_name_legt_keine_variable_an(self):
        interpreter = Interpreter()
        with self.assertRaises(NameError):
            lauf('neu_var = 1', interpreter)
        with self.assertRaises(NameError):
            lauf('neu_var', interpreter)

    def test_zuweisung_in_funktion_an_unbekannten_namen_wirft_fehler(self):
        with self.assertRaises(NameError):
            lauf('funktion f() { lokal = 1 }\nf()')

    def test_mit_sei_deklarierte_variable_ist_zuweisbar(self):
        self.assertEqual(lauf('sei x = 1\nx = 2\nx')[0], 2)

    def test_zuweisung_an_variable_aeusseren_scopes_bleibt_erlaubt(self):
        code = '''
        sei z = 0
        funktion f() { z = z + 1 }
        f(); f()
        wenn wahr { z = z + 10 }
        z
        '''
        self.assertEqual(lauf(code)[0], 12)

    def test_parameter_ist_zuweisbar(self):
        ergebnis, _ = lauf('funktion f(a) { a = a + 1\nzurück a }\nf(1)')
        self.assertEqual(ergebnis, 2)

    def test_fuer_variable_ist_zuweisbar(self):
        ergebnis, _ = lauf('sei s = 0\nfür i in [1, 2] { i = i * 2\ns += i }\ns')
        self.assertEqual(ergebnis, 6)

    def test_fange_name_ist_zuweisbar(self):
        code = 'sei r = nichts\nversuche { werfe "x" } fange e { e = "neu"\nr = e }\nr'
        self.assertEqual(lauf(code)[0], 'neu')

    def test_destrukturierte_namen_sind_zuweisbar(self):
        ergebnis, _ = lauf('sei [a, b] = [1, 2]\na = 5\nb += 1\n[a, b]')
        self.assertEqual(ergebnis, [5, 3])

    def test_schleifendestrukturierung_namen_sind_zuweisbar(self):
        ergebnis, _ = lauf('sei s = 0\nfür [a, b] in [[1, 2], [3, 4]] { a = a * 10\ns += a + b }\ns')
        self.assertEqual(ergebnis, 46)

    def test_funktionsname_ist_zuweisbar(self):
        ergebnis, _ = lauf('funktion f() { zurück 1 }\nf = 3\nf')
        self.assertEqual(ergebnis, 3)

    def test_klassenname_ist_zuweisbar(self):
        ergebnis, _ = lauf('klasse K { }\nK = 3\nK')
        self.assertEqual(ergebnis, 3)

    def test_lade_als_name_ist_zuweisbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('sei x = 1\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "mod.deu" als m\nm = 7\nm', interpreter)
            self.assertEqual(ergebnis, 7)

    def test_attribut_und_index_zuweisung_unveraendert(self):
        code = '''
        klasse P { funktion __init__(dies) { dies.x = 1 } }
        sei p = neu P()
        p.x = 5
        sei l = [1, 2]
        l[0] = 9
        [p.x, l]
        '''
        self.assertEqual(lauf(code)[0], [5, [9, 2]])


# ------------------------------------------------------------ Modulsystem 'lade'

def _datei_schreiben(ordner: str, name: str, inhalt: str) -> str:
    """Legt ordner/name (name darf '/' enthalten) samt Unterordnern an und gibt den Pfad zurück."""
    pfad = os.path.join(ordner, *name.split('/'))
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, 'w', encoding='utf-8') as f:
        f.write(inhalt)
    return pfad


class TestLadeRelativZurLadendenDatei(unittest.TestCase):
    def test_geladene_datei_laedt_aus_eigenem_ordner(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'hilfe.deu', 'funktion wer() { zurück "oben" }\n')   # Köder im Hauptordner
            _datei_schreiben(tmp, 'unter/hilfe.deu', 'funktion wer() { zurück "unten" }\n')
            _datei_schreiben(tmp, 'unter/mitte.deu', 'lade "hilfe.deu" als h\nfunktion frage() { zurück h.wer() }\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "unter/mitte.deu" als m\nm.frage()', interpreter)
            self.assertEqual(ergebnis, 'unten')

    def test_ohne_als_global_und_relativ_zur_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'unter/hilfe.deu', 'funktion f() { zurück 5 }\n')
            _datei_schreiben(tmp, 'unter/mitte.deu', 'lade "hilfe.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "unter/mitte.deu"\nf()', interpreter)
            self.assertEqual(ergebnis, 5)

    def test_hauptskript_bleibt_relativ_zum_ladepfad(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'a.deu', 'funktion f() { zurück 1 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "a.deu"\nf()', interpreter)
            self.assertEqual(ergebnis, 1)

    def test_oberordner_und_absoluter_pfad(self):
        with tempfile.TemporaryDirectory() as tmp:
            absolut = _datei_schreiben(tmp, 'oben.deu', 'konstante O = 7\n').replace('\\', '/')
            _datei_schreiben(tmp, 'unter/mitte.deu',
                             f'lade "../oben.deu" als o\nlade "{absolut}" als a\n'
                             'konstante SUMME = o.O + a.O\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "unter/mitte.deu" als m\nm.SUMME', interpreter)
            self.assertEqual(ergebnis, 14)

    def test_funktion_laedt_relativ_zur_definierenden_datei(self):
        # lade im Körper einer Funktion gilt ab dem Ordner der Datei, in der die Funktion steht,
        # auch wenn sie vom Hauptskript aus aufgerufen wird
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'unter/tief.deu', 'konstante T = "tief"\n')
            _datei_schreiben(tmp, 'unter/mitte.deu',
                             'funktion hole() { lade "tief.deu" als t\nzurück t.T }\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "unter/mitte.deu" als m\nm.hole()', interpreter)
            self.assertEqual(ergebnis, 'tief')

    def test_ohne_ladepfad_gilt_arbeitsordner(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'repl.deu', 'funktion f() { zurück 3 }\n')
            alt = os.getcwd()
            os.chdir(tmp)
            try:
                interpreter = Interpreter()
                ergebnis, _ = lauf('lade "repl.deu"\nf()', interpreter)
            finally:
                os.chdir(alt)
            self.assertEqual(ergebnis, 3)

    def test_nur_im_hauptordner_liegende_datei_wird_aus_unterordner_nicht_gefunden(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'nur_oben.deu', 'sei x = 1\n')
            _datei_schreiben(tmp, 'unter/mitte.deu', 'lade "nur_oben.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError) as ctx:
                lauf('lade "unter/mitte.deu"', interpreter)
            self.assertIn('nur_oben.deu', str(ctx.exception))
            self.assertIn('unter/mitte.deu, Zeile 1', str(ctx.exception))

    def test_zyklus_ueber_ordner_hinweg_wird_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'a.deu', 'lade "unter/b.deu"\n')
            _datei_schreiben(tmp, 'unter/b.deu', 'lade "../a.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ImportError) as ctx:
                lauf('lade "a.deu"', interpreter)
            self.assertIn('a.deu -> b.deu -> a.deu', str(ctx.exception))

    def test_zyklus_bei_unterschiedlicher_pfadschreibweise_wird_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'unter/a.deu', 'lade "../unter/./a.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ImportError):
                lauf('lade "unter/a.deu"', interpreter)

    def test_mehrfaches_laden_nach_fehler_ist_wieder_moeglich(self):
        # der Lade-Stack und die aktuelle Datei werden auch bei Fehlern sauber zurückgesetzt
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'unter/kaputt.deu', 'lade "gibt_es_nicht.deu"\n')
            _datei_schreiben(tmp, 'a.deu', 'funktion f() { zurück 1 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError):
                lauf('lade "unter/kaputt.deu"', interpreter)
            with self.assertRaises(FileNotFoundError):
                lauf('lade "unter/kaputt.deu"', interpreter)   # kein "Zyklus" durch Reste im Stack
            ergebnis, _ = lauf('lade "a.deu"\nf()', interpreter)
            self.assertEqual(ergebnis, 1)


class TestLadeDateiFehlt(unittest.TestCase):
    def test_fehlende_datei_meldet_pfad_und_zeile_auf_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError) as ctx:
                lauf('sei x = 1\nlade "fehlt.deu"', interpreter)
            meldung = str(ctx.exception)
            self.assertIn('Datei nicht gefunden', meldung)
            self.assertIn(os.path.join(tmp, 'fehlt.deu'), meldung)
            self.assertIn('Zeile 2', meldung)
            self.assertNotIn('Errno', meldung)
            self.assertNotIn('No such file', meldung)

    def test_fehlende_datei_mit_als_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError) as ctx:
                lauf('lade "fehlt.deu" als m', interpreter)
            self.assertIn('Datei nicht gefunden', str(ctx.exception))
            self.assertIn('Zeile 1', str(ctx.exception))

    def test_fehlende_datei_ist_mit_versuche_fangbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            code = 'sei r = ""\nversuche { lade "fehlt.deu" } fange (FileNotFoundError) e { r = e }\nr'
            ergebnis, _ = lauf(code, interpreter)
            self.assertIn('Datei nicht gefunden', ergebnis)

    def test_ordner_statt_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'ordner'))
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(IsADirectoryError) as ctx:
                lauf('lade "ordner"', interpreter)
            self.assertIn('ist ein Ordner', str(ctx.exception))
            self.assertNotIn('Errno', str(ctx.exception))

    def test_keine_utf8_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'binaer.deu'), 'wb') as f:
                f.write(b'\xff\xfe\x00\x80')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ValueError) as ctx:
                lauf('lade "binaer.deu"', interpreter)
            self.assertIn('keine gültige UTF-8-Textdatei', str(ctx.exception))
            self.assertIn('Zeile 1', str(ctx.exception))

    def test_pfad_ist_keine_zeichenkette(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('lade 5')
        self.assertIn("'lade' erwartet einen Pfad als Zeichenkette, bekam Ganzzahl", str(ctx.exception))


class TestNeuMitPunktpfad(unittest.TestCase):
    MODUL = (
        'klasse Box {\n'
        '    funktion __init__(dies, w, faktor=1) { dies.w = w * faktor }\n'
        '    funktion wert(dies) { zurück dies.w }\n'
        '}\n'
        'funktion kein_typ() { zurück 1 }\n'
    )

    def _interpreter(self, tmp):
        _datei_schreiben(tmp, 'm.deu', self.MODUL)
        interpreter = Interpreter(ladepfad=tmp)
        lauf('lade "m.deu" als m', interpreter)
        return interpreter

    def test_positionale_argumente(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = self._interpreter(tmp)
            ergebnis, _ = lauf('sei b = neu m.Box(4)\nb.wert()', interpreter)
            self.assertEqual(ergebnis, 4)

    def test_keyword_argumente_gemischt(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = self._interpreter(tmp)
            ergebnis, _ = lauf('(neu m.Box(4, faktor=3)).wert()', interpreter)
            self.assertEqual(ergebnis, 12)
            ergebnis, _ = lauf('neu m.Box(faktor=5, w=2).wert()', interpreter)
            self.assertEqual(ergebnis, 10)

    def test_mehrstufiger_pfad(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'innen.deu', self.MODUL)
            _datei_schreiben(tmp, 'aussen.deu', 'lade "innen.deu" als i\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "aussen.deu" als a\nneu a.i.Box(6, faktor=2).wert()', interpreter)
            self.assertEqual(ergebnis, 12)

    def test_instanz_traegt_klasse_aus_dem_modul(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = self._interpreter(tmp)
            ergebnis, _ = lauf('sei b = neu m.Box(1)\n[b, m.Box]', interpreter)
            self.assertIs(ergebnis[0].klasse, ergebnis[1])

    def test_einfaches_neu_unveraendert(self):
        ergebnis, _ = lauf('klasse K { funktion __init__(dies, x) { dies.x = x } }\n(neu K(3)).x')
        self.assertEqual(ergebnis, 3)

    def test_parser_baut_punktpfad(self):
        baum = Parser(Lexer('neu a.b.K(1, z=2)').tokenisieren()).parse()
        knoten = baum.anweisungen[0]
        self.assertEqual(knoten.name, 'a.b.K')
        self.assertEqual(len(knoten.argumente), 1)
        self.assertEqual([n for n, _ in knoten.keyword_argumente], ['z'])

    def test_unbekannte_klasse_im_modul(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = self._interpreter(tmp)
            with self.assertRaises(AttributeError) as ctx:
                lauf('neu m.Fehlt()', interpreter)
            self.assertIn("Namensraum 'm' hat kein Attribut 'Fehlt'", str(ctx.exception))

    def test_kein_klassenname_im_modul(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = self._interpreter(tmp)
            with self.assertRaises(TypeError) as ctx:
                lauf('neu m.kein_typ()', interpreter)
            self.assertIn("'m.kein_typ' ist keine Klasse", str(ctx.exception))

    def test_unbekanntes_modul(self):
        with self.assertRaises(NameError):
            lauf('neu nirgends.Box()')

    def test_falsche_argumente_der_modulklasse(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = self._interpreter(tmp)
            with self.assertRaises(TypeError) as ctx:
                lauf('neu m.Box()', interpreter)
            self.assertIn('Pflichtargument', str(ctx.exception))

    def test_syntaxfehler_bei_unvollstaendigem_pfad(self):
        with self.assertRaises(SyntaxError):
            lauf('neu m.()')
        with self.assertRaises(SyntaxError):
            lauf('neu m.Box')   # Klammern fehlen
        with self.assertRaises(SyntaxError):
            lauf('neu m.Box(a=1, 2)')   # positional nach keyword


class TestFehlerInGeladenenDateien(unittest.TestCase):
    def test_laufzeitfehler_nennt_datei_und_zeile(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'hilfe.deu', 'sei a = 1\nsei b = 2\nsei c = 1 / 0\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ZeroDivisionError) as ctx:
                lauf('sei x = 1\nlade "hilfe.deu"', interpreter)
            self.assertIn('hilfe.deu, Zeile 3: Division durch Null', str(ctx.exception))
            self.assertNotIn('Zeile 2', str(ctx.exception))   # nicht die Zeile des lade im Hauptskript
            self.assertEqual(ctx.exception.datei, pfad)
            self.assertEqual(ctx.exception.zeile, 3)

    def test_fehler_in_funktion_der_geladenen_datei_beim_aufruf_aus_dem_hauptskript(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'hilfe.deu', 'funktion teile(a) {\n  zurück a / 0\n}\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "hilfe.deu" als h', interpreter)
            with self.assertRaises(ZeroDivisionError) as ctx:
                lauf('sei x = 1\n\nh.teile(4)', interpreter)
            self.assertIn('hilfe.deu, Zeile 2:', str(ctx.exception))
            self.assertEqual(ctx.exception.datei, pfad)
            self.assertEqual(ctx.exception.zeile, 2)

    def test_fehler_in_methode_einer_klasse_aus_geladener_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'k.deu', 'klasse K {\n  funktion boese(dies) {\n    zurück nirgends\n  }\n}\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "k.deu" als k', interpreter)
            with self.assertRaises(NameError) as ctx:
                lauf('sei o = neu k.K()\no.boese()', interpreter)
            self.assertIn('k.deu, Zeile 3:', str(ctx.exception))

    def test_dateiname_relativ_zum_hauptordner_mit_schraegstrich(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'unter/hilfe.deu', 'sei c = 1 / 0\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ZeroDivisionError) as ctx:
                lauf('lade "unter/hilfe.deu"', interpreter)
            self.assertIn('unter/hilfe.deu, Zeile 1:', str(ctx.exception))
            self.assertEqual(ctx.exception.datei, pfad)

    def test_fehler_in_verschachtelt_geladener_datei_nennt_die_innerste(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'unter/innen.deu', '\nsei c = 1 / 0\n')
            _datei_schreiben(tmp, 'unter/mitte.deu', 'sei v = 1\nlade "innen.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ZeroDivisionError) as ctx:
                lauf('lade "unter/mitte.deu"', interpreter)
            self.assertIn('unter/innen.deu, Zeile 2:', str(ctx.exception))
            self.assertEqual(ctx.exception.datei, pfad)
            self.assertEqual(ctx.exception.zeile, 2)

    def test_syntaxfehler_nennt_datei_und_zeile(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'hilfe.deu', 'sei a = 1\nsei = 3\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(SyntaxError) as ctx:
                lauf('lade "hilfe.deu"', interpreter)
            meldung = str(ctx.exception)
            self.assertTrue(meldung.startswith('hilfe.deu, Zeile 2: '), meldung)
            self.assertNotIn('(hilfe', meldung)   # SyntaxError.__str__ darf keinen eigenen Ort anhängen
            self.assertEqual(ctx.exception.datei, pfad)
            self.assertEqual(ctx.exception.zeile, 2)

    def test_lexerfehler_nennt_datei_und_zeile(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'hilfe.deu', 'sei a = 1\n\nsei s = "offen\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(SyntaxError) as ctx:
                lauf('lade "hilfe.deu" als h', interpreter)
            self.assertIn('hilfe.deu, Zeile 3: Nicht abgeschlossene Zeichenkette', str(ctx.exception))
            self.assertEqual(ctx.exception.datei, pfad)
            self.assertEqual(ctx.exception.zeile, 3)

    def test_syntaxfehler_in_verschachtelt_geladener_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'unter/innen.deu', 'sei = 3\n')
            _datei_schreiben(tmp, 'unter/mitte.deu', 'lade "innen.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(SyntaxError) as ctx:
                lauf('lade "unter/mitte.deu"', interpreter)
            self.assertTrue(str(ctx.exception).startswith('unter/innen.deu, Zeile 1: '), str(ctx.exception))
            self.assertEqual(ctx.exception.datei, pfad)

    def test_kontrollsignal_in_geladener_datei_nennt_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'mod.deu', 'sei a = 1\nabbrechen\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(RuntimeError) as ctx:
                lauf('lade "mod.deu"', interpreter)
            self.assertIn("mod.deu, Zeile 2: 'abbrechen' außerhalb einer Schleife", str(ctx.exception))
            self.assertEqual(ctx.exception.datei, pfad)
            self.assertEqual(ctx.exception.zeile, 2)

    def test_werfe_in_geladener_datei_behaelt_wert_und_nennt_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _datei_schreiben(tmp, 'mod.deu', 'funktion los() {\n  werfe "kaputt"\n}\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "mod.deu" als m', interpreter)
            with self.assertRaises(Exception) as ctx:
                lauf('m.los()', interpreter)
            self.assertEqual(ctx.exception.wert, 'kaputt')
            self.assertIn('mod.deu, Zeile 2: kaputt', str(ctx.exception))
            self.assertEqual(ctx.exception.datei, pfad)

    def test_hauptskript_fehler_bleibt_ohne_dateiname(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'ok.deu', 'sei a = 1\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ZeroDivisionError) as ctx:
                lauf('lade "ok.deu"\nsei x = 1 / 0', interpreter)
            self.assertTrue(str(ctx.exception).startswith('Zeile 2: '), str(ctx.exception))
            self.assertIsNone(ctx.exception.datei)
            self.assertEqual(ctx.exception.zeile, 2)

    def test_fehler_im_hauptskript_nach_aufruf_geladener_funktion_hat_keinen_dateinamen(self):
        # Aufruf einer Funktion aus einer geladenen Datei darf die "aktuelle Datei" nicht verstellen
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'mod.deu', 'funktion f() { zurück 1 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "mod.deu" als m', interpreter)
            with self.assertRaises(ZeroDivisionError) as ctx:
                lauf('sei a = m.f()\nsei b = 1 / 0', interpreter)
            self.assertTrue(str(ctx.exception).startswith('Zeile 2: '), str(ctx.exception))
            self.assertIsNone(ctx.exception.datei)

    def test_aktuelle_datei_wird_nach_fehler_zurueckgesetzt(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'kaputt.deu', 'sei c = 1 / 0\n')
            _datei_schreiben(tmp, 'mod.deu', 'funktion f() { zurück 1 / 0 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ZeroDivisionError):
                lauf('lade "kaputt.deu"', interpreter)
            self.assertIsNone(interpreter._aktuelle_datei)
            lauf('lade "mod.deu" als m', interpreter)
            with self.assertRaises(ZeroDivisionError):
                lauf('m.f()', interpreter)
            self.assertIsNone(interpreter._aktuelle_datei)

    def test_gefangener_fehler_aus_geladener_datei_enthaelt_dateinamen(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'mod.deu', 'sei c = 1 / 0\n')
            interpreter = Interpreter(ladepfad=tmp)
            code = 'sei r = ""\nversuche { lade "mod.deu" } fange e { r = e }\nr'
            ergebnis, _ = lauf(code, interpreter)
            self.assertIn('mod.deu, Zeile 1: Division durch Null', ergebnis)


class TestFehlertexteDeutsch(unittest.TestCase):
    """Rohe englische Python-Meldungen dürfen bei Skript-Fehlern nicht mehr ankommen."""

    def _meldung(self, code: str, fehlertyp, interpreter: Interpreter = None) -> str:
        with self.assertRaises(fehlertyp) as ctx:
            lauf(code, interpreter)
        return str(ctx.exception)

    def test_modulo_durch_null_deutsch(self):
        meldung = self._meldung('5 % 0', ZeroDivisionError)
        self.assertIn('Division durch Null', meldung)
        self.assertNotIn('modulo', meldung)

    def test_verbund_modulo_durch_null_deutsch(self):
        meldung = self._meldung('sei x = 5\nx %= 0', ZeroDivisionError)
        self.assertIn('Division durch Null', meldung)
        self.assertNotIn('modulo', meldung)

    def test_unaeres_minus_auf_zeichenkette_deutsch(self):
        meldung = self._meldung('-"a"', TypeError)
        self.assertIn("Operator '-' nicht unterstützt für Zeichenkette", meldung)
        self.assertNotIn('unary', meldung)

    def test_unaeres_minus_auf_liste_deutsch(self):
        meldung = self._meldung('-[1, 2]', TypeError)
        self.assertIn("Operator '-' nicht unterstützt für Liste", meldung)
        self.assertNotIn('bad operand', meldung)

    def test_zahl_auf_nicht_zahl_deutsch(self):
        meldung = self._meldung('"abc".zahl()', ValueError)
        self.assertIn("Kann 'abc' nicht in Zahl umwandeln", meldung)
        self.assertNotIn('could not convert', meldung)
        self.assertEqual(lauf('"12".zahl()')[0], 12)

    def test_max_nicht_vergleichbare_typen_deutsch(self):
        meldung = self._meldung('max(1, "a")', TypeError)
        self.assertIn("'max' kann Werte dieser Typen nicht vergleichen", meldung)
        self.assertIn('Ganzzahl', meldung)
        self.assertIn('Zeichenkette', meldung)
        self.assertNotIn('not supported', meldung)

    def test_min_nicht_vergleichbare_typen_deutsch(self):
        meldung = self._meldung('min([1, "a"])', TypeError)
        self.assertIn("'min' kann Werte dieser Typen nicht vergleichen", meldung)
        self.assertNotIn('not supported', meldung)

    def test_entferne_leere_liste_methode_deutsch(self):
        meldung = self._meldung('sei l = []\nl.entferne()', IndexError)
        self.assertIn('aus einer leeren Liste entfernen', meldung)
        self.assertNotIn('pop', meldung)

    def test_entferne_leere_liste_funktion_deutsch(self):
        meldung = self._meldung('sei l = []\nentferne(l)', IndexError)
        self.assertIn('aus einer leeren Liste entfernen', meldung)
        self.assertNotIn('pop', meldung)

    def test_entferne_index_ausserhalb_deutsch(self):
        meldung = self._meldung('sei l = [1]\nentferne(l, 5)', IndexError)
        self.assertIn('Index 5 ist außerhalb des Bereichs', meldung)
        self.assertNotIn('pop index', meldung)

    def test_entferne_kein_ganzzahl_index_deutsch(self):
        meldung = self._meldung('sei l = [1]\nl.entferne("a")', TypeError)
        self.assertIn('Ganzzahl-Index', meldung)
        self.assertNotIn('invalid literal', meldung)

    def test_eingabe_bei_geschlossener_eingabe_deutsch(self):
        with mock.patch('builtins.input', side_effect=EOFError):
            meldung = self._meldung('eingabe("Name: ")', EOFError)
        self.assertIn('Dateiende erreicht', meldung)
        self.assertNotIn('EOF', meldung)

    def test_fuer_schleife_ueber_instanz_deutsch(self):
        meldung = self._meldung('klasse Hund { }\nfür x in neu Hund() { drucke(x) }', TypeError)
        self.assertIn("'Hund' ist nicht iterierbar", meldung)
        self.assertNotIn('iterable', meldung)

    def test_listenausdruck_ueber_instanz_deutsch(self):
        meldung = self._meldung('klasse Hund { }\n[x für x in neu Hund()]', TypeError)
        self.assertIn("'Hund' ist nicht iterierbar", meldung)
        self.assertNotIn('iterable', meldung)

    def test_fuer_schleife_ueber_zahl_deutsch(self):
        meldung = self._meldung('für x in 5 { drucke(x) }', TypeError)
        self.assertIn("'Ganzzahl' ist nicht iterierbar", meldung)
        self.assertNotIn('iterable', meldung)

    def test_json_ungueltig_ohne_englischen_parserfehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'kaputt.json', '{\n  "a": tru\n}')
            meldung = self._meldung('json_lesen("kaputt.json")', ValueError, Interpreter(ladepfad=tmp))
        self.assertIn("Ungültiges JSON in 'kaputt.json'", meldung)
        self.assertNotIn('Expecting', meldung)
        self.assertNotIn('line', meldung)

    def test_json_ordner_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, 'ordner'))
            meldung = self._meldung('json_lesen("ordner")', IsADirectoryError, Interpreter(ladepfad=tmp))
        self.assertIn('ist ein Ordner, keine Datei', meldung)
        self.assertNotIn('Permission denied', meldung)
        self.assertNotIn('Errno', meldung)

    def test_json_nicht_utf8_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'bin.json'), 'wb') as f:
                f.write(b'\xff\xfe\x00bad')
            meldung = self._meldung('json_lesen("bin.json")', ValueError, Interpreter(ladepfad=tmp))
        self.assertIn('keine gültige UTF-8-Textdatei', meldung)
        self.assertNotIn('decode', meldung)

    def test_json_zu_tief_verschachtelt_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _datei_schreiben(tmp, 'tief.json', '[' * 200000)
            meldung = self._meldung('json_lesen("tief.json")', RecursionError, Interpreter(ladepfad=tmp))
        self.assertIn('zu tief verschachtelt', meldung)
        self.assertNotIn('Stack overflow', meldung)
        self.assertNotIn('recursion', meldung)

    def test_json_nullzeichen_im_pfad_deutsch(self):
        meldung = self._meldung('json_lesen("a\x00b.json")', ValueError)  # echtes Nullzeichen im Pfad
        self.assertIn('ist kein gültiger Dateipfad', meldung)
        self.assertNotIn('null', meldung)

    def test_json_keine_berechtigung_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('deutsch.interpreter.open', side_effect=PermissionError(13, 'Permission denied'), create=True):
                meldung = self._meldung('json_lesen("x.json")', PermissionError, Interpreter(ladepfad=tmp))
        self.assertIn('Keine Berechtigung zum Lesen', meldung)
        self.assertNotIn('Permission denied', meldung)

    def test_json_sonstiger_os_fehler_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('deutsch.interpreter.open', side_effect=OSError(22, 'Invalid argument'), create=True):
                meldung = self._meldung('json_lesen("x.json")', OSError, Interpreter(ladepfad=tmp))
        self.assertIn("'x.json' konnte nicht gelesen werden", meldung)
        self.assertNotIn('Invalid argument', meldung)

    def test_fallback_bei_mehrargumentfehler_bleibt_fangbar(self):
        interpreter = Interpreter()

        def werfe_unicode():
            raise UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte')

        interpreter.global_umgebung.setze('werfe_unicode', werfe_unicode)
        meldung = self._meldung('werfe_unicode()', ValueError, interpreter)
        self.assertIn('Zeile 1: ', meldung)
        self.assertNotIn('arguments', meldung)
        ergebnis, _ = lauf('sei m = ""\nversuche { werfe_unicode() } fange (ValueError) f { m = f }\nm', interpreter)
        self.assertIn('Zeile 2: ', ergebnis)

    def test_datei_lesen_ordner_meldet_ordner_statt_berechtigung(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, 'ordner'))
            meldung = self._meldung('datei_lesen("ordner")', IsADirectoryError, Interpreter(ladepfad=tmp))
        self.assertIn('ist ein Ordner, keine Datei', meldung)
        self.assertNotIn('Berechtigung', meldung)

    def test_datei_lesen_sonstiger_os_fehler_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('deutsch.interpreter.open', side_effect=OSError(22, 'Invalid argument'), create=True):
                meldung = self._meldung('datei_lesen("a.txt")', OSError, Interpreter(ladepfad=tmp))
        self.assertIn("'a.txt' konnte nicht gelesen werden", meldung)
        self.assertNotIn('Invalid argument', meldung)

    def test_datei_lesen_nullzeichen_im_pfad_deutsch(self):
        meldung = self._meldung('datei_lesen("a\x00b.txt")', ValueError)  # echtes Nullzeichen im Pfad
        self.assertIn('ist kein gültiger Dateipfad', meldung)
        self.assertNotIn('null', meldung)

    def test_datei_schreiben_ordner_meldet_ordner(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, 'ordner'))
            meldung = self._meldung('datei_schreiben("ordner", "x")', IsADirectoryError, Interpreter(ladepfad=tmp))
        self.assertIn('ist ein Ordner, keine Datei', meldung)
        self.assertNotIn('Berechtigung', meldung)

    def test_datei_schreiben_sonstiger_os_fehler_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('deutsch.interpreter.open', side_effect=OSError(22, 'Invalid argument'), create=True):
                meldung = self._meldung('datei_schreiben("a.txt", "x")', OSError, Interpreter(ladepfad=tmp))
        self.assertIn("'a.txt' konnte nicht geschrieben werden", meldung)
        self.assertNotIn('Invalid argument', meldung)

    def test_datei_schreiben_nicht_utf8_speicherbar_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            interpreter.global_umgebung.setze('kaputter_text', lambda: '\ud800')  # Ersatzzeichen, nicht kodierbar
            meldung = self._meldung('datei_schreiben("a.txt", kaputter_text())', ValueError, interpreter)
        self.assertIn('als UTF-8 speichern', meldung)
        self.assertNotIn('codec', meldung)

    def test_datei_anhaengen_sonstiger_os_fehler_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('deutsch.interpreter.open', side_effect=OSError(22, 'Invalid argument'), create=True):
                meldung = self._meldung('datei_anhängen("a.txt", "x")', OSError, Interpreter(ladepfad=tmp))
        self.assertIn("'a.txt' konnte nicht geschrieben werden", meldung)
        self.assertNotIn('Invalid argument', meldung)

    def test_json_schreiben_zirkulaer_deutsch_ohne_halbe_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            meldung = self._meldung('sei l = [1]\nl.anhaengen(l)\njson_schreiben("c.json", l)',
                                    ValueError, Interpreter(ladepfad=tmp))
            self.assertFalse(os.path.exists(os.path.join(tmp, 'c.json')))
        self.assertIn('Zirkulärer Verweis', meldung)
        self.assertNotIn('Circular', meldung)

    def test_json_schreiben_schluesseltyp_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            meldung = self._meldung('klasse Hund { }\nsei h = neu Hund()\njson_schreiben("k.json", {h: 1})',
                                    TypeError, Interpreter(ladepfad=tmp))
        self.assertIn("Schlüssel vom Typ 'Hund'", meldung)
        self.assertNotIn('keys must be', meldung)

    def test_json_schreiben_zu_tief_verschachtelt_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = 'sei l = []\nfür i in bereich(3000) { l = [l] }\njson_schreiben("d.json", l)'
            meldung = self._meldung(code, RecursionError, Interpreter(ladepfad=tmp))
        self.assertIn('zu tief verschachtelt', meldung)
        self.assertNotIn('recursion', meldung)

    def test_json_schreiben_ordner_meldet_ordner(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, 'ordner'))
            meldung = self._meldung('json_schreiben("ordner", 1)', IsADirectoryError, Interpreter(ladepfad=tmp))
        self.assertIn('ist ein Ordner, keine Datei', meldung)
        self.assertNotIn('Permission denied', meldung)

    def test_json_schreiben_sonstiger_os_fehler_deutsch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('deutsch.interpreter.open', side_effect=OSError(22, 'Invalid argument'), create=True):
                meldung = self._meldung('json_schreiben("x.json", 1)', OSError, Interpreter(ladepfad=tmp))
        self.assertIn("'x.json' konnte nicht geschrieben werden", meldung)
        self.assertNotIn('Invalid argument', meldung)


if __name__ == '__main__':
    unittest.main()
