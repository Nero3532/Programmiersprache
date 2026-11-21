# -*- coding: utf-8 -*-
"""
Regressionstests für eingebaute Funktionen und Methoden des Deutsch-Interpreters,
die bisher ohne Tests waren. Je Funktion: Normalfall sowie Grenz- und Fehlerfall.

Ausführen mit:
    py -m unittest discover -s tests -p test_builtins.py -v
"""
import math
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter


def auswerten(code: str):
    """Tokenisiert, parst und führt Code aus. Gibt den Wert der letzten Anweisung zurück."""
    tokens = Lexer(code).tokenisieren()
    baum = Parser(tokens).parse()
    return Interpreter().ausfuehren(baum)


class TestVerbinde(unittest.TestCase):
    def test_mit_trenner(self):
        self.assertEqual(auswerten('verbinde([1, 2, 3], ", ")'), '1, 2, 3')

    def test_ohne_trenner(self):
        self.assertEqual(auswerten('verbinde(["a", "b"])'), 'ab')

    def test_leere_liste(self):
        self.assertEqual(auswerten('verbinde([])'), '')

    def test_elemente_werden_zu_text(self):
        self.assertEqual(auswerten('verbinde([wahr, nichts], "-")'), 'wahr-nichts')

    def test_fehler_bei_nicht_liste(self):
        with self.assertRaises(TypeError):
            auswerten('verbinde(5)')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('verbinde()')
        with self.assertRaises(TypeError):
            auswerten('verbinde([1], ",", 3)')


class TestUmkehren(unittest.TestCase):
    def test_veraendert_liste_in_place(self):
        self.assertEqual(auswerten('sei l = [1, 2, 3]\numkehren(l)\nl'), [3, 2, 1])

    def test_gibt_nichts_zurueck(self):
        self.assertIsNone(auswerten('sei l = [1, 2, 3]\numkehren(l)'))

    def test_leere_liste(self):
        self.assertEqual(auswerten('sei l = []\numkehren(l)\nl'), [])

    def test_fehler_bei_nicht_liste(self):
        with self.assertRaises(TypeError):
            auswerten('umkehren("abc")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('umkehren()')


class TestEntferne(unittest.TestCase):
    def test_ohne_index_entfernt_letztes_element(self):
        self.assertEqual(auswerten('sei l = [1, 2, 3]\nentferne(l)'), 3)
        self.assertEqual(auswerten('sei l = [1, 2, 3]\nentferne(l)\nl'), [1, 2])

    def test_mit_index_gibt_entferntes_element_zurueck(self):
        self.assertEqual(auswerten('sei l = [1, 2, 3]\nentferne(l, 0)'), 1)
        self.assertEqual(auswerten('sei l = [1, 2, 3]\nentferne(l, 0)\nl'), [2, 3])

    def test_negativer_index(self):
        self.assertEqual(auswerten('sei l = [1, 2, 3]\nentferne(l, -1)'), 3)

    def test_leere_liste_wirft_indexfehler(self):
        with self.assertRaises(IndexError):
            auswerten('sei l = []\nentferne(l)')

    def test_index_ausserhalb_wirft_indexfehler(self):
        with self.assertRaises(IndexError):
            auswerten('sei l = [1, 2, 3]\nentferne(l, 5)')

    def test_fehler_bei_nicht_liste(self):
        with self.assertRaises(TypeError):
            auswerten('entferne("abc")')

    def test_fehler_bei_nicht_ganzzahligem_index(self):
        with self.assertRaises(TypeError):
            auswerten('sei l = [1]\nentferne(l, "x")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('entferne()')


class TestMaxMin(unittest.TestCase):
    def test_max_aus_liste(self):
        self.assertEqual(auswerten('max([1, 5, 3])'), 5)

    def test_max_aus_einzelnen_argumenten(self):
        self.assertEqual(auswerten('max(1, 5, 3)'), 5)

    def test_max_gemischte_zahlen(self):
        self.assertEqual(auswerten('max(1, 2.5)'), 2.5)

    def test_max_einzelnes_argument(self):
        self.assertEqual(auswerten('max(7)'), 7)

    def test_max_zeichenketten(self):
        self.assertEqual(auswerten('max(["apfel", "birne"])'), 'birne')

    def test_max_leere_liste_wirft_wertfehler(self):
        with self.assertRaises(ValueError):
            auswerten('max([])')

    def test_max_ohne_argumente_wirft_typfehler(self):
        with self.assertRaises(TypeError):
            auswerten('max()')

    def test_max_nicht_vergleichbare_typen_wirft_typfehler(self):
        with self.assertRaisesRegex(TypeError, "'max' kann Werte dieser Typen nicht vergleichen"):
            auswerten('max(1, "a")')
        with self.assertRaises(TypeError):
            auswerten('max([nichts, 1])')

    def test_min_aus_liste(self):
        self.assertEqual(auswerten('min([3, 1, 2])'), 1)

    def test_min_aus_einzelnen_argumenten_mit_negativen_zahlen(self):
        self.assertEqual(auswerten('min(-1, -5, 0)'), -5)

    def test_min_leere_liste_wirft_wertfehler(self):
        with self.assertRaises(ValueError):
            auswerten('min([])')

    def test_min_ohne_argumente_wirft_typfehler(self):
        with self.assertRaises(TypeError):
            auswerten('min()')

    def test_min_nicht_vergleichbare_typen_wirft_typfehler(self):
        with self.assertRaises(TypeError):
            auswerten('min(1, "a")')


class TestAbs(unittest.TestCase):
    def test_positiv_negativ_null(self):
        self.assertEqual(auswerten('abs(-3)'), 3)
        self.assertEqual(auswerten('abs(-2.5)'), 2.5)
        self.assertEqual(auswerten('abs(0)'), 0)

    def test_fehler_bei_nicht_zahl(self):
        with self.assertRaises(TypeError):
            auswerten('abs("x")')
        with self.assertRaises(TypeError):
            auswerten('abs(nichts)')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('abs()')
        with self.assertRaises(TypeError):
            auswerten('abs(1, 2)')


class TestRunde(unittest.TestCase):
    def test_ohne_stellen_ergibt_ganzzahl(self):
        ergebnis = auswerten('runde(3.7)')
        self.assertEqual(ergebnis, 4)
        self.assertIsInstance(ergebnis, int)

    def test_eindeutige_faelle_ohne_stellen(self):
        self.assertEqual(auswerten('runde(2.4)'), 2)
        self.assertEqual(auswerten('runde(2.6)'), 3)

    def test_negative_zahl(self):
        self.assertEqual(auswerten('runde(-2.7)'), -3)

    def test_mit_stellen(self):
        ergebnis = auswerten('runde(3.14159, 2)')
        self.assertAlmostEqual(ergebnis, 3.14)
        self.assertIsInstance(ergebnis, float)

    def test_stellen_null_ergibt_ganzzahl(self):
        ergebnis = auswerten('runde(3.14159, 0)')
        self.assertEqual(ergebnis, 3)
        self.assertIsInstance(ergebnis, int)

    def test_ganzzahl_mit_stellen_ergibt_kommazahl(self):
        ergebnis = auswerten('runde(5, 2)')
        self.assertEqual(ergebnis, 5.0)
        self.assertIsInstance(ergebnis, float)

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('runde()')
        with self.assertRaises(TypeError):
            auswerten('runde(1, 2, 3)')

    def test_fehler_bei_nichts(self):
        with self.assertRaises(TypeError):
            auswerten('runde(nichts)')


class TestKommazahl(unittest.TestCase):
    def test_text_zu_kommazahl(self):
        self.assertEqual(auswerten('kommazahl("3.5")'), 3.5)

    def test_negativer_text(self):
        self.assertEqual(auswerten('kommazahl("-0.25")'), -0.25)

    def test_ganzzahl_wird_kommazahl(self):
        ergebnis = auswerten('kommazahl(3)')
        self.assertEqual(ergebnis, 3.0)
        self.assertIsInstance(ergebnis, float)

    def test_unlesbarer_text_wirft_wertfehler(self):
        with self.assertRaises(ValueError):
            auswerten('kommazahl("abc")')

    def test_nichts_wirft_wertfehler(self):
        with self.assertRaises(ValueError):
            auswerten('kommazahl(nichts)')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('kommazahl()')


class TestZeichenkette(unittest.TestCase):
    def test_zahlen(self):
        self.assertEqual(auswerten('zeichenkette(42)'), '42')
        self.assertEqual(auswerten('zeichenkette(2.5)'), '2.5')

    def test_wahrheitswerte_und_nichts(self):
        self.assertEqual(auswerten('zeichenkette(wahr)'), 'wahr')
        self.assertEqual(auswerten('zeichenkette(falsch)'), 'falsch')
        self.assertEqual(auswerten('zeichenkette(nichts)'), 'nichts')

    def test_liste(self):
        self.assertEqual(auswerten('zeichenkette([1, 2])'), '[1, 2]')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('zeichenkette()')
        with self.assertRaises(TypeError):
            auswerten('zeichenkette(1, 2)')


class TestWahrheitswert(unittest.TestCase):
    def test_wahre_werte(self):
        for code in ('wahrheitswert(1)', 'wahrheitswert("x")', 'wahrheitswert([0])', 'wahrheitswert(wahr)'):
            with self.subTest(code=code):
                self.assertIs(auswerten(code), True)

    def test_falsche_werte(self):
        for code in ('wahrheitswert(0)', 'wahrheitswert(0.0)', 'wahrheitswert("")',
                     'wahrheitswert([])', 'wahrheitswert(nichts)', 'wahrheitswert(falsch)'):
            with self.subTest(code=code):
                self.assertIs(auswerten(code), False)

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('wahrheitswert()')


class TestWoerterbuchKonvertierung(unittest.TestCase):
    def test_aus_paaren(self):
        self.assertEqual(auswerten('woerterbuch([["a", 1], ["b", 2]])'), {'a': 1, 'b': 2})

    def test_umlaut_schreibweise_ist_gleichwertig(self):
        self.assertEqual(auswerten('wörterbuch([["a", 1]])'), {'a': 1})
        self.assertEqual(auswerten('wörterbuch([["a", 1]])'), auswerten('woerterbuch([["a", 1]])'))

    def test_leere_liste(self):
        self.assertEqual(auswerten('woerterbuch([])'), {})

    def test_fehler_bei_nicht_liste(self):
        with self.assertRaises(TypeError):
            auswerten('woerterbuch("abc")')
        with self.assertRaises(TypeError):
            auswerten('woerterbuch({"a": 1})')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('woerterbuch()')


class TestTrigonometrie(unittest.TestCase):
    def test_sinus(self):
        self.assertAlmostEqual(auswerten('sinus(0)'), 0.0)
        self.assertAlmostEqual(auswerten('sinus(pi / 2)'), 1.0)

    def test_kosinus(self):
        self.assertAlmostEqual(auswerten('kosinus(0)'), 1.0)
        self.assertAlmostEqual(auswerten('kosinus(pi)'), -1.0)

    def test_tangens(self):
        self.assertAlmostEqual(auswerten('tangens(0)'), 0.0)
        self.assertAlmostEqual(auswerten('tangens(pi / 4)'), 1.0)

    def test_nicht_zahl_wirft_typfehler(self):
        for funktion in ('sinus', 'kosinus', 'tangens'):
            with self.subTest(funktion=funktion):
                with self.assertRaisesRegex(TypeError, f"'{funktion}' erwartet eine Zahl"):
                    auswerten(f'{funktion}("a")')
                with self.assertRaisesRegex(TypeError, f"'{funktion}' erwartet eine Zahl"):
                    auswerten(f'{funktion}(nichts)')

    def test_falsche_argumentzahl(self):
        for funktion in ('sinus', 'kosinus', 'tangens'):
            with self.subTest(funktion=funktion):
                with self.assertRaises(TypeError):
                    auswerten(f'{funktion}()')


class TestLogarithmus(unittest.TestCase):
    def test_natuerlicher_logarithmus(self):
        self.assertAlmostEqual(auswerten('logarithmus(1)'), 0.0)
        self.assertAlmostEqual(auswerten('logarithmus(e)'), 1.0)

    def test_mit_basis(self):
        self.assertAlmostEqual(auswerten('logarithmus(8, 2)'), 3.0)
        self.assertAlmostEqual(auswerten('logarithmus(100, 10)'), 2.0)

    def test_null_wirft_wertfehler(self):
        with self.assertRaisesRegex(ValueError, "'logarithmus' nicht definiert"):
            auswerten('logarithmus(0)')

    def test_negativ_wirft_wertfehler(self):
        with self.assertRaises(ValueError):
            auswerten('logarithmus(-1)')

    def test_basis_eins_wirft_null_division(self):
        with self.assertRaises(ZeroDivisionError):
            auswerten('logarithmus(8, 1)')

    def test_nicht_zahl_wirft_typfehler(self):
        with self.assertRaisesRegex(TypeError, "'logarithmus' erwartet eine Zahl"):
            auswerten('logarithmus("a")')

    def test_falsche_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('logarithmus()')
        with self.assertRaises(TypeError):
            auswerten('logarithmus(1, 2, 3)')


class TestExponential(unittest.TestCase):
    def test_normalfall(self):
        self.assertAlmostEqual(auswerten('exponential(0)'), 1.0)
        self.assertAlmostEqual(auswerten('exponential(1)'), math.e)
        self.assertAlmostEqual(auswerten('exponential(-1)'), 1 / math.e)

    def test_nicht_zahl_wirft_typfehler(self):
        with self.assertRaisesRegex(TypeError, "'exponential' erwartet eine Zahl"):
            auswerten('exponential("a")')

    def test_ueberlauf(self):
        with self.assertRaises(OverflowError):
            auswerten('exponential(1000)')

    def test_falsche_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('exponential()')


class TestEingabe(unittest.TestCase):
    def test_liest_zeile_und_zeigt_prompt(self):
        with mock.patch('builtins.input', return_value='Anna') as eingabe_mock:
            ergebnis = auswerten('eingabe("Name: ")')
        self.assertEqual(ergebnis, 'Anna')
        eingabe_mock.assert_called_once_with('Name: ')

    def test_ohne_prompt(self):
        with mock.patch('builtins.input', return_value='x') as eingabe_mock:
            auswerten('eingabe()')
        eingabe_mock.assert_called_once_with('')

    def test_prompt_wird_zu_text(self):
        with mock.patch('builtins.input', return_value='') as eingabe_mock:
            auswerten('eingabe(42)')
        eingabe_mock.assert_called_once_with('42')

    def test_ergebnis_ist_zeichenkette(self):
        with mock.patch('builtins.input', return_value='42'):
            self.assertEqual(auswerten('typ(eingabe())'), 'Zeichenkette')

    def test_dateiende_wirft_deutsche_meldung(self):
        with mock.patch('builtins.input', side_effect=EOFError):
            with self.assertRaisesRegex(EOFError, 'Eingabe nicht möglich'):
                auswerten('eingabe("x")')


class TestTextMethoden(unittest.TestCase):
    def test_gross_und_klein(self):
        self.assertEqual(auswerten('"abc".gross()'), 'ABC')
        self.assertEqual(auswerten('"ABC".klein()'), 'abc')

    def test_leerer_text(self):
        self.assertEqual(auswerten('"".gross()'), '')
        self.assertEqual(auswerten('"".klein()'), '')

    def test_teile_mit_trenner(self):
        self.assertEqual(auswerten('"a,b,c".teile(",")'), ['a', 'b', 'c'])

    def test_teile_mit_leerem_teil(self):
        self.assertEqual(auswerten('"a,,b".teile(",")'), ['a', '', 'b'])

    def test_teile_ohne_trenner_an_leerraum(self):
        self.assertEqual(auswerten('"  a  b ".teile()'), ['a', 'b'])

    def test_teile_ohne_vorkommen_des_trenners(self):
        self.assertEqual(auswerten('"abc".teile(",")'), ['abc'])

    def test_teile_leerer_text_ohne_trenner(self):
        self.assertEqual(auswerten('"".teile()'), [])

    def test_ersetze(self):
        self.assertEqual(auswerten('"aaa".ersetze("a", "b")'), 'bbb')
        self.assertEqual(auswerten('"abc".ersetze("x", "y")'), 'abc')
        self.assertEqual(auswerten('"abc".ersetze("b", "")'), 'ac')

    def test_ersetze_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('"abc".ersetze("a")')

    def test_beginnt_mit_und_endet_mit(self):
        self.assertIs(auswerten('"Hallo".beginnt_mit("Ha")'), True)
        self.assertIs(auswerten('"Hallo".beginnt_mit("lo")'), False)
        self.assertIs(auswerten('"Hallo".endet_mit("lo")'), True)
        self.assertIs(auswerten('"Hallo".endet_mit("Ha")'), False)

    def test_beginnt_mit_leerem_praefix(self):
        self.assertIs(auswerten('"Hallo".beginnt_mit("")'), True)

    def test_beginnt_mit_fehler_bei_nicht_text(self):
        with self.assertRaises(TypeError):
            auswerten('"abc".beginnt_mit(1)')


class TestWoerterbuchMethoden(unittest.TestCase):
    def test_schluessel_in_einfuegereihenfolge(self):
        self.assertEqual(auswerten('sei d = {"a": 1, "b": 2}\nd.schluessel()'), ['a', 'b'])

    def test_schluessel_umlaut_alias(self):
        self.assertEqual(auswerten('sei d = {"a": 1}\nd.schlüssel()'), ['a'])

    def test_schluessel_leeres_woerterbuch(self):
        self.assertEqual(auswerten('sei d = woerterbuch([])\nd.schluessel()'), [])

    def test_kopiere_ist_unabhaengig(self):
        self.assertEqual(auswerten('sei d = {"a": 1}\nsei c = d.kopiere()\nc.entferne("a")\nd'), {'a': 1})

    def test_kopiere_ist_flach(self):
        self.assertEqual(
            auswerten('sei d = {"l": [1]}\nsei c = d.kopiere()\nc.hole("l").anhaengen(2)\nd["l"]'),
            [1, 2],
        )

    def test_listen_kopiere_ist_unabhaengig(self):
        self.assertEqual(auswerten('sei a = [1, 2]\nsei b = a.kopiere()\nb.anhaengen(3)\na'), [1, 2])


class TestTypHinweiseEingebauterTypen(unittest.TestCase):
    def test_zeichenkette_passend(self):
        self.assertEqual(auswerten('funktion f(s: Zeichenkette) { zurück s }\nf("ja")'), 'ja')
        self.assertEqual(auswerten('sei s: Zeichenkette = "ok"\ns'), 'ok')

    def test_zeichenkette_unpassend(self):
        with self.assertRaises(TypeError):
            auswerten('funktion f(s: Zeichenkette) { zurück s }\nf(5)')
        with self.assertRaises(TypeError):
            auswerten('sei s: Zeichenkette = 5')

    def test_wahrheitswert_passend(self):
        self.assertIs(auswerten('funktion f(b: Wahrheitswert) -> Wahrheitswert { zurück b }\nf(wahr)'), True)
        self.assertIs(auswerten('sei b: Wahrheitswert = falsch\nb'), False)

    def test_wahrheitswert_unpassend(self):
        # Python-bool ist eine int-Unterklasse; die Ganzzahl 1 darf trotzdem nicht als Wahrheitswert durchgehen.
        with self.assertRaises(TypeError):
            auswerten('sei b: Wahrheitswert = 1')
        with self.assertRaises(TypeError):
            auswerten('funktion f(b: Wahrheitswert) { zurück b }\nf(0)')

    def test_nichts_passend(self):
        self.assertIsNone(auswerten('sei n: Nichts = nichts\nn'))
        self.assertIsNone(auswerten('funktion f() -> Nichts { sei x = 1 }\nf()'))

    def test_nichts_unpassend(self):
        with self.assertRaises(TypeError):
            auswerten('sei n: Nichts = 0')
        with self.assertRaises(TypeError):
            auswerten('funktion f(n: Nichts) { zurück n }\nf(1)')

    def test_woerterbuch_passend(self):
        self.assertEqual(auswerten('sei d: Woerterbuch = {"a": 1}\nd'), {'a': 1})

    def test_woerterbuch_unpassend(self):
        with self.assertRaises(TypeError):
            auswerten('sei d: Woerterbuch = [1]')

    def test_wörterbuch_passend(self):
        self.assertEqual(auswerten('sei d: Wörterbuch = {"a": 1}\nd'), {'a': 1})

    def test_wörterbuch_unpassend(self):
        with self.assertRaises(TypeError):
            auswerten('funktion f(d: Wörterbuch) { zurück d }\nf([1])')


class TestVariadischeParameter(unittest.TestCase):
    SUMME = (
        'funktion summe(*zahlen) {\n'
        '    sei s = 0\n'
        '    für z in zahlen { s += z }\n'
        '    zurück s\n'
        '}\n'
    )

    def test_ohne_argumente(self):
        self.assertEqual(auswerten(self.SUMME + 'summe()'), 0)

    def test_ein_argument(self):
        self.assertEqual(auswerten(self.SUMME + 'summe(5)'), 5)

    def test_mehrere_argumente(self):
        self.assertEqual(auswerten(self.SUMME + 'summe(1, 2, 3)'), 6)

    def test_parameter_ist_liste(self):
        self.assertEqual(auswerten('funktion sammle(*werte) { zurück werte }\nsammle(1, "a")'), [1, 'a'])
        self.assertEqual(auswerten('funktion sammle(*werte) { zurück werte }\nsammle()'), [])


if __name__ == '__main__':
    unittest.main()
