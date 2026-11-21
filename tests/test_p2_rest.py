# -*- coding: utf-8 -*-
"""P2-Reste: Wörterbuch in abbilden/filtere/reduziere/gruppiere, Typ-Hinweise bei *args/**kw,
Ortsanreicherung per Attribut, Bit-Operator-Überladung, ??=.

Ausführen mit:  py -m unittest discover -s tests -p test_p2_rest.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter


def lauf(code: str):
    return Interpreter().ausfuehren(Parser(Lexer(code).tokenisieren()).parse())


class WoerterbuchSammlung(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(lauf('abbilden({"a": 1, "b": 2}, funktion(k) -> k + "!")'), ['a!', 'b!'])
        self.assertEqual(lauf('filtere({"a": 1, "bb": 2}, funktion(k) -> länge(k) > 1)'), ['bb'])
        self.assertEqual(lauf('reduziere({"a": 1, "b": 2}, funktion(x, k) -> x + k, "")'), 'ab')
        self.assertEqual(lauf('gruppiere({"a": 1, "bb": 2, "c": 3}, funktion(k) -> länge(k))'), {1: ['a', 'c'], 2: ['bb']})

    def test_fehler(self):
        with self.assertRaisesRegex(TypeError, 'Liste, Menge, Wörterbuch'):
            lauf('abbilden(5, funktion(x) -> x)')


class VariadischeTypHinweise(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(lauf('funktion f(*a: Ganzzahl, **kw: Zeichenkette) { zurück [a, kw] }\nf(1, 2, x="y")'),
                         [[1, 2], {'x': 'y'}])

    def test_args_fehler(self):
        with self.assertRaisesRegex(TypeError, "Parameter 'a': erwartet Typ 'Ganzzahl'"):
            lauf('funktion f(*a: Ganzzahl) { zurück a }\nf(1, "x")')

    def test_kwargs_fehler(self):
        with self.assertRaisesRegex(TypeError, "Parameter 'kw': erwartet Typ 'Zeichenkette'"):
            lauf('funktion f(**kw: Zeichenkette) { zurück kw }\nf(x=1)')


class OrtAnreicherung(unittest.TestCase):
    def test_meldung_mit_zeile_bekommt_ort(self):
        with self.assertRaises(Exception) as ctx:
            lauf('sei a = 1\nwerfe "Zeile kaputt"')
        self.assertTrue(str(ctx.exception).startswith('Zeile 2: '), str(ctx.exception))

    def test_nicht_doppelt(self):
        with self.assertRaises(Exception) as ctx:
            lauf('funktion f() {\n  werfe "boom"\n}\nf()')
        self.assertEqual(str(ctx.exception).count('Zeile'), 1)


BIT_KLASSE = '''
klasse B {
    funktion __init__(dies, w) { dies.w = w }
    funktion __bitund__(dies, o) { zurück neu B(dies.w + 1) }
    funktion __bitoder__(dies, o) { zurück neu B(dies.w + 2) }
    funktion __bitxoder__(dies, o) { zurück neu B(dies.w + 3) }
    funktion __links__(dies, o) { zurück neu B(dies.w + 4) }
    funktion __rechts__(dies, o) { zurück neu B(dies.w + 5) }
    funktion __bitnicht__(dies) { zurück neu B(dies.w + 6) }
}
sei b = neu B(0)
'''


class BitUeberladung(unittest.TestCase):
    def test_normal(self):
        for ausdruck, erwartet in [('b & b', 1), ('b | b', 2), ('b ^ b', 3), ('b << 1', 4), ('b >> 1', 5), ('~b', 6)]:
            with self.subTest(ausdruck):
                self.assertEqual(lauf(BIT_KLASSE + f'({ausdruck}).w'), erwartet)

    def test_verbund(self):
        self.assertEqual(lauf(BIT_KLASSE + 'b &= b\nb.w'), 1)

    def test_fehler_ohne_methode(self):
        with self.assertRaises(TypeError):
            lauf('klasse K { funktion __init__(dies) { } }\nneu K() & 1')
        with self.assertRaises(TypeError):
            lauf('klasse K { funktion __init__(dies) { } }\n~neu K()')


class FrageFrageGleich(unittest.TestCase):
    def test_nichts_wird_gesetzt(self):
        self.assertEqual(lauf('sei x = nichts\nx ??= 5\nx'), 5)

    def test_wert_bleibt_und_rechts_nicht_ausgewertet(self):
        self.assertEqual(lauf('sei x = 0\nx ??= 1 // 0\nx'), 0)

    def test_index_ziel(self):
        self.assertEqual(lauf('sei l = [nichts, 2]\nl[0] ??= 9\nl[1] ??= 9\nl'), [9, 2])

    def test_fehler_undeklariert(self):
        with self.assertRaises(NameError):
            lauf('y ??= 1')


if __name__ == '__main__':
    unittest.main()
