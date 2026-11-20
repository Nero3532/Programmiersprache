# -*- coding: utf-8 -*-
"""Tests für das Iterator-Protokoll: __iter__/__naechstes__, IterationsEnde, naechstes, lazy bereich."""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.interpreter import Interpreter
from deutsch.lexer import Lexer
from deutsch.parser import Parser


def ausgabe(code):
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter().ausfuehren(Parser(Lexer(code).tokenisieren()).parse())
    return puffer.getvalue().splitlines()


Z = '''klasse Z {
    funktion __init__(dies, n) { dies.n = n
        dies.i = 0 }
    funktion __iter__(dies) { zurück dies }
    funktion __naechstes__(dies) {
        wenn dies.i >= dies.n { werfe IterationsEnde() }
        dies.i += 1
        zurück dies.i
    }
}
'''


class TestIteratoren(unittest.TestCase):
    def test_fuer(self):
        self.assertEqual(ausgabe(Z + 'für x in neu Z(3) { drucke(x) }'), ['1', '2', '3'])

    def test_comprehension(self):
        self.assertEqual(ausgabe(Z + 'drucke([x * 2 für x in neu Z(3)])'), ['[2, 4, 6]'])

    def test_entpacken_zuweisung(self):
        self.assertEqual(ausgabe(Z + 'sei [a, *r] = neu Z(4)\ndrucke(a)\ndrucke(r)'), ['1', '[2, 3, 4]'])

    def test_spread_liste_menge_summe(self):
        code = Z + 'drucke([*neu Z(2)])\ndrucke(liste(neu Z(3)))\ndrucke(summe(neu Z(3)))\ndrucke(menge(neu Z(2)))'
        self.assertEqual(ausgabe(code), ['[1, 2]', '[1, 2, 3]', '6', '{1, 2}'])

    def test_hoeherer_ordnung_und_sammlungen(self):
        code = Z + ('drucke(abbilden(neu Z(3), funktion(x) { zurück x * 10 }))\n'
                    'drucke(alle(neu Z(3)))\ndrucke(einige(neu Z(0)))\n'
                    'drucke(aufzaehlen(neu Z(2)))\ndrucke(zippe(neu Z(2), ["a", "b"]))\n'
                    'drucke(sortiere(neu Z(3)))')
        self.assertEqual(ausgabe(code), ['[10, 20, 30]', 'wahr', 'falsch', '[[0, 1], [1, 2]]',
                                         '[[1, a], [2, b]]', '[1, 2, 3]'])

    def test_iter_liefert_liste(self):
        code = ('klasse S { funktion __iter__(dies) { zurück [7, 8] } }\n'
                'für x in neu S() { drucke(x) }\ndrucke(liste(neu S()))')
        self.assertEqual(ausgabe(code), ['7', '8', '[7, 8]'])

    def test_iter_ohne_naechstes_fehler(self):
        code = ('klasse K { funktion __iter__(dies) { zurück neu K() } }\n'
                'versuche { für x in neu K() { } } fange (TypFehler) f { drucke("TF") }')
        self.assertEqual(ausgabe(code), ['TF'])

    def test_nicht_iterierbar_bleibt(self):
        code = 'klasse K { }\nversuche { für x in neu K() { } } fange (TypFehler) f { drucke(f) }'
        self.assertIn('nicht iterierbar', ausgabe(code)[0])

    def test_iterationsende_fangbar(self):
        code = 'versuche { werfe IterationsEnde() } fange (IterationsEnde) f { drucke("ende") }'
        self.assertEqual(ausgabe(code), ['ende'])

    def test_naechstes_manuell(self):
        code = Z + ('sei z = neu Z(1)\ndrucke(naechstes(z))\n'
                    'versuche { naechstes(z) } fange (IterationsEnde) f { drucke("ende") }\n'
                    'drucke(nächstes(neu Z(2)))')
        self.assertEqual(ausgabe(code), ['1', 'ende', '1'])

    def test_naechstes_kein_iterator(self):
        code = 'versuche { naechstes([1]) } fange (TypFehler) f { drucke("TF") }'
        self.assertEqual(ausgabe(code), ['TF'])

    def test_fehler_im_naechstes_wird_nicht_verschluckt(self):
        code = ('klasse K { funktion __iter__(dies) { zurück dies }\n'
                '  funktion __naechstes__(dies) { werfe WertFehler("kaputt") } }\n'
                'versuche { für x in neu K() { } } fange (WertFehler) f { drucke("WF") }')
        self.assertEqual(ausgabe(code), ['WF'])

    def test_bereich_bleibt_liste(self):
        self.assertEqual(ausgabe('drucke(bereich(3) == [0, 1, 2])\ndrucke(typ(bereich(3)))'), ['wahr', 'Liste'])

    def test_bereich_lazy_in_fuer(self):
        code = 'für i in bereich(10 ** 12) { drucke(i)\n abbrechen }'
        self.assertEqual(ausgabe(code), ['0'])

    def test_bereich_lazy_in_comprehension_und_schritte(self):
        code = 'drucke([i für i in bereich(1, 10, 4)])\ndrucke([i für i in bereich(2)])'
        self.assertEqual(ausgabe(code), ['[1, 5, 9]', '[0, 1]'])

    def test_bereich_ueberschrieben(self):
        code = 'funktion bereich(n) { zurück ["x"] }\nfür i in bereich(5) { drucke(i) }'
        self.assertEqual(ausgabe(code), ['x'])

    def test_bereich_argumentzahl(self):
        code = 'versuche { für i in bereich() { } } fange (TypFehler) f { drucke("TF") }'
        self.assertEqual(ausgabe(code), ['TF'])


if __name__ == '__main__':
    unittest.main()
