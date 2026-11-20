# -*- coding: utf-8 -*-
"""Tests für Dekoratoren (@name, @ausdruck(args), @m.deko) und Optional-Chaining (?.)."""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch import linter
from deutsch.interpreter import Interpreter
from deutsch.lexer import Lexer
from deutsch.parser import Parser


def parse(code):
    return Parser(Lexer(code).tokenisieren()).parse()


def ausgabe(code):
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter().ausfuehren(parse(code))
    return puffer.getvalue().splitlines()


# Dekorator, der die Rückgabe verdoppelt
DOPPELT = 'funktion doppelt(f) -> funktion(x) -> f(x) * 2\n'


class TestDekoratoren(unittest.TestCase):
    def test_ohne_argumente(self):
        self.assertEqual(ausgabe(DOPPELT + '@doppelt\nfunktion f(x) { zurück x + 1 }\ndrucke(f(3))'), ['8'])

    def test_mit_argumenten(self):
        c = ('funktion mal(n) -> funktion(f) -> funktion(x) -> f(x) * n\n'
             '@mal(10)\nfunktion f(x) -> x + 1\ndrucke(f(1))')
        self.assertEqual(ausgabe(c), ['20'])

    def test_punktpfad(self):
        c = ('klasse M { statisch funktion deko(f) -> funktion(x) -> f(x) + 100 }\n'
             '@M.deko\nfunktion f(x) -> x\ndrucke(f(1))')
        self.assertEqual(ausgabe(c), ['101'])

    def test_gestapelt_von_unten_nach_oben(self):
        c = ('funktion plus1(f) -> funktion(x) -> f(x) + 1\n'
             '@doppelt\n@plus1\nfunktion f(x) -> x\ndrucke(f(5))')   # doppelt(plus1(f)) = (5+1)*2
        self.assertEqual(ausgabe(DOPPELT + c), ['12'])
        c2 = c.replace('@doppelt\n@plus1', '@plus1\n@doppelt')        # plus1(doppelt(f)) = 5*2+1
        self.assertEqual(ausgabe(DOPPELT + c2), ['11'])

    def test_ausdruecke_werden_von_oben_nach_unten_ausgewertet(self):
        c = ('funktion m(n) { drucke("auswerten {n}")\n zurück funktion(f) -> f }\n'
             '@m(1)\n@m(2)\nfunktion f() -> 0')
        self.assertEqual(ausgabe(c), ['auswerten 1', 'auswerten 2'])

    def test_lambda_builtin_instanz_als_dekorator(self):
        self.assertEqual(ausgabe('@(funktion(f) -> "L")\nfunktion f() -> 0\ndrucke(f)'), ['L'])
        self.assertEqual(ausgabe('@typ\nfunktion f() -> 0\ndrucke(f)'), ['Funktion'])  # Builtin
        c = ('klasse D { funktion __aufruf__(dies, f) -> "inst" }\nsei d = neu D()\n'
             '@d\nfunktion f() -> 0\ndrucke(f)')
        self.assertEqual(ausgabe(c), ['inst'])

    def test_rueckgabe_ersetzt_funktion(self):
        self.assertEqual(ausgabe('@(funktion(f) -> 42)\nfunktion f() -> 0\ndrucke(f)'), ['42'])

    def test_methode_und_statisch(self):
        c = (DOPPELT + 'klasse K {\n'
             '  @doppelt\n  statisch funktion s(x) -> x + 2\n'
             '  funktion n(dies) -> 1\n}\n'
             'sei k = neu K()\ndrucke(K.s(1))\ndrucke(k.n())')
        self.assertEqual(ausgabe(c), ['6', '1'])
        # Methode: der Wrapper bekommt die Instanz als erstes Argument
        c2 = ('funktion deko(f) -> funktion(a, b) -> f(a, b) * 2\n'
              'klasse K { @deko\n funktion m(dies, x) -> x + 1 }\ndrucke((neu K()).m(4))')
        self.assertEqual(ausgabe(c2), ['10'])

    def test_kurzform_und_blockform(self):
        self.assertEqual(ausgabe(DOPPELT + '@doppelt\nfunktion f(x) -> x\ndrucke(f(4))'), ['8'])

    def test_memo_beispiel(self):
        c = ('funktion merke(f) {\n'
             '  sei speicher = {}\n'
             '  funktion h(n) {\n'
             '    wenn nicht (n in speicher) { speicher[n] = f(n) }\n'
             '    zurück speicher[n]\n'
             '  }\n'
             '  zurück h\n'
             '}\n'
             'sei aufrufe = [0]\n'
             '@merke\n'
             'funktion quadrat(n) { aufrufe[0] += 1\n zurück n * n }\n'
             'drucke(quadrat(4))\ndrucke(quadrat(4))\ndrucke(aufrufe[0])')
        self.assertEqual(ausgabe(c), ['16', '16', '1'])

    def test_leerzeilen_zwischen_dekorator_und_funktion(self):
        self.assertEqual(ausgabe(DOPPELT + '@doppelt\n\nfunktion f(x) -> x\ndrucke(f(2))'), ['4'])

    def test_fehler(self):
        with self.assertRaisesRegex(SyntaxError, "muss 'funktion' folgen"):
            parse('@x\nsei a = 1')
        with self.assertRaisesRegex(SyntaxError, "muss 'funktion' folgen"):
            parse('@x\n')
        with self.assertRaisesRegex(SyntaxError, "muss 'funktion' folgen"):
            parse('@x\nklasse K { }')
        with self.assertRaisesRegex(SyntaxError, "neue Zeile"):
            parse('@x funktion f() -> 1')
        with self.assertRaisesRegex(SyntaxError, "muss 'funktion' folgen"):
            parse('klasse K { @x\n sei a = 1 }')
        with self.assertRaisesRegex(SyntaxError, "muss 'funktion' folgen"):
            parse('@x\nstatisch funktion f() -> 1')   # 'statisch' nur in Klassen
        with self.assertRaises(TypeError):
            ausgabe('@5\nfunktion f() -> 1')           # nicht aufrufbar
        with self.assertRaises(NameError):
            ausgabe('@gibtesnicht\nfunktion f() -> 1')

    def test_linter(self):
        c = DOPPELT + '@doppelt\nfunktion f(x) -> x\nklasse K { @doppelt\n funktion m(dies, x) -> x }\n'
        self.assertEqual(linter.pruefe(parse(c)), [])
        funde = linter.pruefe(parse('@gibtesnicht\nfunktion f() -> 1'))
        self.assertTrue(any("unbekannter Name 'gibtesnicht'" in t for _, t in funde))


class TestOptionalChaining(unittest.TestCase):
    K = ('klasse K { funktion __init__(dies) { dies.b = 5\n dies.n = nichts }\n'
         ' funktion m(dies, x) -> x * 2 }\n')

    def test_nichts_und_nicht_nichts(self):
        self.assertEqual(ausgabe('sei a = nichts\ndrucke(a?.b)'), ['nichts'])
        self.assertEqual(ausgabe(self.K + 'sei a = neu K()\ndrucke(a?.b)'), ['5'])

    def test_methodenaufruf(self):
        self.assertEqual(ausgabe(self.K + 'sei a = neu K()\ndrucke(a?.m(4))'), ['8'])
        # Argumente werden bei nichts nicht ausgewertet
        c = 'funktion boom() { drucke("boom")\n zurück 1 }\nsei a = nichts\ndrucke(a?.m(boom()))'
        self.assertEqual(ausgabe(c), ['nichts'])

    def test_kette_kurzschluss(self):
        self.assertEqual(ausgabe('sei a = nichts\ndrucke(a?.b.c)\ndrucke(a?.b.c.d(1)[0])'),
                         ['nichts', 'nichts'])
        self.assertEqual(ausgabe(self.K + 'sei a = neu K()\ndrucke(a?.n?.x)'), ['nichts'])
        # normales '.' schützt nicht
        with self.assertRaises(AttributeError):
            ausgabe(self.K + 'sei a = neu K()\ndrucke(a?.n.x)')

    def test_fehlendes_attribut_bleibt_fehler(self):
        with self.assertRaises(AttributeError):
            ausgabe(self.K + 'sei a = neu K()\ndrucke(a?.fehlt)')

    def test_mit_koaleszenz(self):
        self.assertEqual(ausgabe('sei a = nichts\ndrucke(a?.b ?? "x")'), ['x'])
        self.assertEqual(ausgabe(self.K + 'sei a = neu K()\ndrucke(a?.b ?? "x")'), ['5'])

    def test_kurzschluss_nur_in_eigener_kette(self):
        self.assertEqual(ausgabe('sei a = nichts\nsei l = [a?.b, 1]\ndrucke(l)'), ['[nichts, 1]'])
        self.assertEqual(ausgabe('sei a = nichts\ndrucke("{a?.b}")'), ['nichts'])

    def test_fehler(self):
        with self.assertRaisesRegex(SyntaxError, r"\?\."):
            parse('sei a = 1 ? 2')
        with self.assertRaises(SyntaxError):
            parse('sei a = nichts\na?.b = 1')
        with self.assertRaises(SyntaxError):
            parse('sei a = nichts\na?.')

    def test_linter(self):
        self.assertEqual(linter.pruefe(parse('sei a = nichts\ndrucke(a?.b)')), [])


if __name__ == '__main__':
    unittest.main()
