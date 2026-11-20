# -*- coding: utf-8 -*-
"""Tests für den Linter (deutsch/linter.py) und 'main.py --pruefen'."""
import glob
import os
import sys
import tempfile
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT_WURZEL)

from deutsch import linter
from deutsch.lexer import Lexer
from deutsch.parser import Parser
from tests.test_main import starte_pruefen


def hinweise(code: str):
    return linter.pruefe(Parser(Lexer(code).tokenisieren()).parse())


def texte(code: str, stichwort: str):
    return [(z, t) for z, t in hinweise(code) if stichwort in t]


class TestUnbekannterName(unittest.TestCase):
    def test_treffer_mit_vorschlag_und_zeile(self):
        r = texte('sei anzahl = 1\ndrucke(anzal)\n', 'unbekannter Name')
        self.assertEqual(r, [(2, "unbekannter Name 'anzal' – meintest du 'anzahl'?")])

    def test_vorschlag_programmname_zuerst_kein_irrefuehrender(self):
        self.assertEqual(texte('sei zaehler = 1\ndrucke(zaehlr)\n', 'unbekannter Name'),
                         [(2, "unbekannter Name 'zaehlr' – meintest du 'zaehler'?")])
        r = texte('funktion f(x) { zurück x }\ndrucke(zaehlr)\n', 'unbekannter Name')
        self.assertEqual(r, [(2, "unbekannter Name 'zaehlr'")])
        self.assertEqual(texte('drucke(zaehlr)\n', 'unbekannter Name'), [(1, "unbekannter Name 'zaehlr'")])

    def test_selbst_ist_der_methodenparameter(self):
        code = 'klasse K { funktion __init__(selbst) { selbst.x = 1 }\n funktion g(selbst) { zurück selbst.x } }\n'
        self.assertEqual(hinweise(code), [])
        self.assertEqual(len(texte('drucke(selbst)\n', 'unbekannter Name')), 1)

    def test_treffer_ohne_vorschlag(self):
        self.assertEqual(texte('drucke(qqqqqq)\n', 'unbekannter Name'),
                         [(1, "unbekannter Name 'qqqqqq'")])

    def test_gebundene_namen_sind_bekannt(self):
        code = '''
sei a = 1
konstante K = 2
sei [x, *rest] = [1, 2, 3]
funktion f(p, q = 1, *mehr, **opt) { zurück p + q + K + x + a + laenge(mehr) + laenge(opt) }
klasse T { funktion m(selbst) { zurück selbst.wert } }
für i in bereich(3) { drucke(i) }
für [u, v] in [[1, 2]] { drucke(u + v) }
versuche { drucke(rest) } fange (WertFehler) e { drucke(e) }
drucke(f(1), T, [n für n in bereich(2)])
'''
        self.assertEqual(texte(code, 'unbekannter Name'), [])

    def test_closure_attribut_keyword_methode_sind_keine_freien_namen(self):
        code = '''
funktion zaehler() {
    sei n = 0
    zurück funktion() { n += 1
        zurück n }
}
klasse A { funktion __init__(selbst) { selbst.x = 1 }
    funktion g(selbst, wert) { zurück selbst.x + wert } }
sei a = neu A()
drucke(sortiere([3, 1], umgekehrt = wahr), a.g(wert = 2), "abc".gross(), "{a.x}")
'''
        self.assertEqual(texte(code, 'unbekannter Name'), [])

    def test_lade_ohne_als_schaltet_regel_ab_mit_als_nicht(self):
        self.assertEqual(texte('lade "m.deu"\ndrucke(foo)\n', 'unbekannter Name'), [])
        self.assertEqual(len(texte('lade "m.deu" als m\ndrucke(foo)\n', 'unbekannter Name')), 1)

    def test_fehlerarten_sind_bekannt(self):
        self.assertEqual(texte('werfe neu WertFehler("x")\n', 'unbekannter Name'), [])


class TestUnbenutzteVariable(unittest.TestCase):
    def test_treffer_in_funktion_und_methode(self):
        code = 'funktion f() {\n    sei a = 1\n}\nklasse K { funktion m(selbst) {\n    sei b = 2\n} }\n'
        self.assertEqual([z for z, _ in texte(code, 'nie gelesen')], [2, 5])

    def test_gelesen_ist_kein_treffer(self):
        code = 'funktion f() {\n    sei a = 1\n    zurück a\n}\n'
        self.assertEqual(texte(code, 'nie gelesen'), [])

    def test_unterstrich_oberste_ebene_konstante_und_closure(self):
        code = '''
sei oben = 1
funktion f() {
    sei _ignoriert = 1
    konstante K = 2
    sei n = 0
    zurück funktion() -> n
}
'''
        self.assertEqual(texte(code, 'nie gelesen'), [])

    def test_zuweisung_allein_ist_kein_lesen(self):
        self.assertEqual(len(texte('funktion f() {\n    sei a = 1\n    a = 2\n}\n', 'nie gelesen')), 1)

    def test_interpolation_zaehlt_als_lesen(self):
        self.assertEqual(texte('funktion f() {\n    sei a = 1\n    drucke("{a}")\n}\n', 'nie gelesen'), [])


class TestUnerreichbar(unittest.TestCase):
    def test_treffer_nach_jedem_sprung(self):
        for sprung in ('zurück 1', 'werfe "x"'):
            r = texte(f'funktion f() {{\n    {sprung}\n    drucke(1)\n}}\n', 'unerreichbar')
            self.assertEqual(r, [(3, 'unerreichbarer Code')], sprung)
        for sprung in ('abbrechen', 'weiter'):
            r = texte(f'solange wahr {{\n    {sprung}\n    drucke(1)\n}}\n', 'unerreichbar')
            self.assertEqual(r, [(3, 'unerreichbarer Code')], sprung)

    def test_kein_treffer(self):
        code = '''
funktion f(x) {
    wenn x { zurück 1 }
    drucke(2)
    zurück 3
}
solange wahr { wenn falsch { abbrechen }
    weiter }
'''
        self.assertEqual(texte(code, 'unerreichbar'), [])


class TestPruefenCli(unittest.TestCase):
    def test_ausgabe_sortiert_exitcode_null(self):
        code = 'funktion f() {\n    sei a = 1\n    zurück 2\n    drucke(1)\n}\ndrucke(zzzzz)\n'
        rc, aus, fehler = starte_pruefen(code)
        zeilen = aus.strip().splitlines()
        self.assertEqual(rc, 0)
        self.assertRegex(zeilen[0], r'test\.deu:2: Hinweis: Variable')
        self.assertRegex(zeilen[1], r'test\.deu:4: Hinweis: unerreichbar')
        self.assertRegex(zeilen[2], r'test\.deu:6: Hinweis: unbekannter Name')
        self.assertTrue(zeilen[3].endswith(': keine Syntaxfehler, 3 Hinweise'))

    def test_syntaxfehler_exitcode_eins_ohne_hinweise(self):
        rc, aus, _ = starte_pruefen('sei = 2\n')
        self.assertEqual((rc, aus), (1, ''))


class TestBeispiele(unittest.TestCase):
    def test_beispiele_ohne_namens_und_unerreichbar_hinweise(self):
        for pfad in glob.glob(os.path.join(PROJEKT_WURZEL, 'beispiele', '*.deu')):
            with open(pfad, encoding='utf-8') as f:
                r = hinweise(f.read())
            schlecht = [h for h in r if 'unbekannter Name' in h[1] or 'unerreichbar' in h[1]]
            self.assertEqual(schlecht, [], os.path.basename(pfad))


if __name__ == '__main__':
    unittest.main()
