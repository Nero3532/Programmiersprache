# -*- coding: utf-8 -*-
"""Tests für Sammlungs-Dunder: __laenge__, __hole__, __setze__, __enthaelt__, __aufruf__."""
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


LEER = 'klasse K { funktion __init__(dies) { dies.d = {} } }\nsei k = neu K()\n'


class TestDunderHooks(unittest.TestCase):
    def test_laenge(self):
        c = ('klasse K { funktion __laenge__(dies) { zurück 3 } }\n'
             'drucke(laenge(neu K()))\ndrucke(länge(neu K()))')
        self.assertEqual(ausgabe(c), ['3', '3'])

    def test_laenge_fehlt_und_falscher_typ(self):
        with self.assertRaisesRegex(TypeError, "nicht unterstützt"):
            ausgabe(LEER + 'laenge(k)')
        for rueck in ('"x"', '-1', 'wahr', '1.5'):
            c = f'klasse K {{ funktion __laenge__(dies) {{ zurück {rueck} }} }}\nlaenge(neu K())'
            with self.assertRaisesRegex(TypeError, "Ganzzahl"):
                ausgabe(c)

    def test_hole_setze_verbund_slice(self):
        c = '''
        klasse K {
            funktion __init__(dies) { dies.l = [1, 2, 3, 4] }
            funktion __hole__(dies, s) { zurück dies.l[s] }
            funktion __setze__(dies, s, w) { dies.l[s] = w }
        }
        sei k = neu K()
        k[1] = 20
        k[2] += 5
        drucke(k.l)
        '''
        self.assertEqual(ausgabe(c), ['[1, 20, 8, 4]'])

    def test_teilbereich(self):
        c = '''
        klasse K {
            funktion __hole__(dies, s) { zurück s }
            funktion __setze__(dies, s, w) { dies.t = s }
        }
        sei k = neu K()
        sei t = k[1:3]
        drucke(t)
        drucke(typ(t))
        drucke([t.anfang, t.ende, t.schritt])
        drucke(k[::2].schritt)
        k[:2] = 0
        drucke(k.t)
        '''
        self.assertEqual(ausgabe(c), ['Teilbereich(1, 3, nichts)', 'Teilbereich',
                                      '[1, 3, nichts]', '2', 'Teilbereich(nichts, 2, nichts)'])

    def test_hole_setze_fehlen(self):
        with self.assertRaisesRegex(TypeError, "__hole__"):
            ausgabe(LEER + 'k[0]')
        with self.assertRaisesRegex(TypeError, "__hole__"):
            ausgabe(LEER + 'k[0:1]')
        with self.assertRaisesRegex(TypeError, "__setze__"):
            ausgabe(LEER + 'k[0] = 1')

    def test_enthaelt(self):
        c = ('klasse K { funktion __enthaelt__(dies, w) { zurück w == 1 } }\n'
             'sei k = neu K()\ndrucke(1 in k)\ndrucke(2 in k)\ndrucke(2 nicht in k)\ndrucke(1 nicht in k)')
        self.assertEqual(ausgabe(c), ['wahr', 'falsch', 'wahr', 'falsch'])

    def test_enthaelt_fehlt_und_falscher_typ(self):
        with self.assertRaisesRegex(TypeError, "nicht unterstützt"):
            ausgabe(LEER + '1 in k')
        with self.assertRaisesRegex(TypeError, "Wahrheitswert"):
            ausgabe('klasse K { funktion __enthaelt__(dies, w) { zurück 1 } }\n1 in neu K()')

    def test_aufruf(self):
        c = '''
        klasse K {
            funktion __aufruf__(dies, a, b = 10, *rest, **opt) { zurück [a, b, rest, opt] }
        }
        sei k = neu K()
        sei t = [7, 8, 9]
        drucke(k(1))
        drucke(k(1, b = 2))
        drucke(k(*t))
        drucke(k(1, 2, 3, z = 4))
        '''
        self.assertEqual(ausgabe(c), ['[1, 10, [], {}]', '[1, 2, [], {}]',
                                      '[7, 8, [9], {}]', '[1, 2, [3], {z: 4}]'])

    def test_aufruf_fehlt(self):
        with self.assertRaisesRegex(TypeError, "nicht aufrufbar"):
            ausgabe(LEER + 'k(1)')

    def test_vererbung(self):
        c = '''
        klasse B {
            funktion __laenge__(dies) { zurück 2 }
            funktion __hole__(dies, s) { zurück s * 2 }
            funktion __setze__(dies, s, w) { dies.x = [s, w] }
            funktion __enthaelt__(dies, w) { zurück wahr }
            funktion __aufruf__(dies, a) { zurück a + 1 }
        }
        klasse A(B) { }
        sei a = neu A()
        a[1] = 5
        drucke([laenge(a), a[4], a.x, 0 in a, a(1)])
        '''
        self.assertEqual(ausgabe(c), ['[2, 8, [1, 5], wahr, 2]'])

    def test_text_nutzt_drucke(self):
        self.assertEqual(ausgabe('klasse K { funktion __text__(dies) { zurück "hallo" } }\ndrucke(neu K())'),
                         ['hallo'])

    def test_sammlung_und_linter(self):
        c = '''
        klasse Stapel {
            funktion __init__(dies) { dies.l = [] }
            funktion __laenge__(dies) { zurück laenge(dies.l) }
            funktion __hole__(dies, i) { zurück dies.l[i] }
            funktion __setze__(dies, i, w) { dies.l[i] = w }
            funktion __enthaelt__(dies, w) { zurück w in dies.l }
            funktion __aufruf__(dies, *werte) { für w in werte { dies.l.anhängen(w) }; zurück dies }
        }
        sei s = neu Stapel()
        s(1, 2, 3)
        s[0] += 10
        drucke([laenge(s), s[0], s[2], 2 in s, 9 nicht in s])
        '''
        self.assertEqual(ausgabe(c), ['[3, 11, 3, wahr, wahr]'])
        self.assertEqual(linter.pruefe(parse(c)), [])


if __name__ == '__main__':
    unittest.main()
