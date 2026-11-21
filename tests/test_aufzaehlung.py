# -*- coding: utf-8 -*-
"""Tests für Aufzählungstypen ('aufzaehlung Farbe { rot, gruen }')."""
import contextlib
import io
import os
import sys
import tempfile
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT_WURZEL)

from deutsch import linter
from deutsch.interpreter import Interpreter
from deutsch.lexer import Lexer
from deutsch.parser import Parser
from tests.test_main import starte_pruefen


def parse(code):
    return Parser(Lexer(code).tokenisieren()).parse()


def ausgabe(code, ladepfad=None):
    """Führt code aus und gibt die Zeilen von stdout zurück."""
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter(ladepfad=ladepfad).ausfuehren(parse(code))
    return puffer.getvalue().splitlines()


def fehlerart(rumpf, vorspann='aufzaehlung Farbe { rot, gruen, blau }\n'):
    """Art des Fehlers, den rumpf wirft (per fange)."""
    return ausgabe(vorspann + f'versuche {{ {rumpf} }} fange f {{ drucke(f) }}')


FARBE = 'aufzaehlung Farbe { rot, gruen, blau }\n'


class TestSyntax(unittest.TestCase):
    def test_beide_schreibweisen_und_mehrzeilig_mit_komma_am_ende(self):
        code = ('aufzählung Status {\n  offen = 1,\n  fertig = 2,\n}\n'
                'aufzaehlung Q { a, b, }\ndrucke(Status.fertig.wert, Q.b.wert)')
        self.assertEqual(ausgabe(code), ['2 1'])

    def test_umbrueche_ueberall(self):
        self.assertEqual(ausgabe('aufzaehlung F {\n\n a\n ,\n b\n\n}\ndrucke(F.b.wert)'), ['1'])

    def test_wert_ist_beliebiger_ausdruck_einmal_ausgewertet(self):
        code = ('sei n = 0\nfunktion z() { n += 1\n zurück n }\n'
                'aufzaehlung A { x = z(), y = 2 * 5 }\ndrucke(A.x.wert, A.x.wert, A.y.wert, n)')
        self.assertEqual(ausgabe(code), ['1 1 10 1'])

    def test_syntaxfehler(self):
        for code, teil in [('aufzaehlung F { }', 'mindestens ein Mitglied'),
                           ('aufzaehlung F { a, a }', 'doppelt'),
                           ('aufzaehlung F { a = 1, b }', 'alle mit oder alle ohne Wert'),
                           ('aufzaehlung F { a, b = 1 }', 'alle mit oder alle ohne Wert'),
                           ('aufzaehlung F { a b }', 'erwartet')]:
            with self.subTest(code=code):
                with self.assertRaises(SyntaxError) as e:
                    parse(code)
                self.assertIn(teil, str(e.exception))


class TestWerte(unittest.TestCase):
    def test_drucke_und_verkettung(self):
        self.assertEqual(ausgabe(FARBE + 'drucke(Farbe.rot)\ndrucke("x: " + Farbe.blau)'),
                         ['Farbe.rot', 'x: Farbe.blau'])

    def test_name_wert_ab_null(self):
        self.assertEqual(ausgabe(FARBE + 'drucke(Farbe.gruen.name, Farbe.rot.wert, Farbe.blau.wert)'),
                         ['gruen 0 2'])

    def test_gleichheit_identitaet(self):
        code = FARBE + ('aufzaehlung Q { rot = 0, b = 1 }\n'
                        'drucke(Farbe.rot == Farbe.rot, Farbe.rot != Farbe.gruen, Farbe.rot == Q.rot)\n'
                        'drucke(Farbe.rot != Q.rot, Farbe.rot.wert == Q.rot.wert)')
        self.assertEqual(ausgabe(code), ['wahr wahr falsch', 'wahr wahr'])

    def test_wert_nicht_gleich_mitglied(self):
        code = 'aufzaehlung S { offen = 1 }\ndrucke(S.offen == 1)'
        self.assertEqual(ausgabe(code), ['falsch'])

    def test_gleiche_werte_verschiedene_mitglieder(self):
        code = 'aufzaehlung S { a = 1, b = 1 }\ndrucke(S.a == S.b, S.a.wert == S.b.wert)'
        self.assertEqual(ausgabe(code), ['falsch wahr'])

    def test_fuer_reihenfolge_und_in(self):
        code = FARBE + ('für f in Farbe { drucke(f) }\n'
                        'drucke(Farbe.gruen in Farbe)')
        self.assertEqual(ausgabe(code), ['Farbe.rot', 'Farbe.gruen', 'Farbe.blau', 'wahr'])

    def test_passe_fall(self):
        code = FARBE + ('funktion n(f) { passe f { fall Farbe.rot: { zurück "R" } fall Farbe.gruen: { zurück "G" }'
                        ' sonst: { zurück "?" } } }\ndrucke(n(Farbe.rot), n(Farbe.gruen), n(Farbe.blau))')
        self.assertEqual(ausgabe(code), ['R G ?'])

    def test_schluessel_und_mengen(self):
        code = FARBE + ('sei w = {Farbe.rot: 1, Farbe.gruen: 2}\ndrucke(w[Farbe.gruen])\n'
                        'drucke(laenge(menge([Farbe.rot, Farbe.rot, Farbe.blau])))')
        self.assertEqual(ausgabe(code), ['2', '2'])

    def test_typ(self):
        self.assertEqual(ausgabe(FARBE + 'drucke(typ(Farbe.rot) == "Farbe", typ(Farbe))'),
                         ['wahr Aufzaehlung(Farbe)'])

    def test_neu_bindbar_wie_klassen(self):
        self.assertEqual(ausgabe(FARBE + 'aufzaehlung Farbe { x }\ndrucke(Farbe.x)'), ['Farbe.x'])


class TestTypHinweise(unittest.TestCase):
    def test_ok_und_typfehler(self):
        code = FARBE + ('aufzaehlung Q { a }\n'
                        'sei f: Farbe = Farbe.rot\n'
                        'funktion g(x: Farbe) -> Farbe { zurück x }\n'
                        'drucke(g(Farbe.blau))\n'
                        'versuche { g(Q.a) } fange (TypFehler) e { drucke("param") }\n'
                        'versuche { g(0) } fange (TypFehler) e { drucke("zahl") }\n'
                        'versuche { sei h: Farbe = Q.a } fange (TypFehler) e { drucke("sei") }\n'
                        'funktion r() -> Farbe { zurück Q.a }\n'
                        'versuche { r() } fange (TypFehler) e { drucke("rueck") }')
        self.assertEqual(ausgabe(code), ['Farbe.blau', 'param', 'zahl', 'sei', 'rueck'])


class TestFehler(unittest.TestCase):
    def test_unbekanntes_mitglied(self):
        code = FARBE + 'versuche { Farbe.lila } fange (AttributFehler) f { drucke(f) }'
        self.assertEqual(ausgabe(code), ["Zeile 2: Aufzählung 'Farbe' hat kein Mitglied 'lila'"])

    def test_zuweisung_ist_typfehler(self):
        for rumpf in ('Farbe.rot.wert = 5', 'Farbe.rot.name = "x"', 'Farbe.lila = 1', 'Farbe.rot = 1'):
            with self.subTest(rumpf=rumpf):
                code = FARBE + f'versuche {{ {rumpf} }} fange (TypFehler) f {{ drucke("tf") }}'
                self.assertEqual(ausgabe(code), ['tf'])

    def test_kleiner_ist_typfehler(self):
        code = FARBE + 'versuche { Farbe.rot < Farbe.gruen } fange (TypFehler) f { drucke("tf") }'
        self.assertEqual(ausgabe(code), ['tf'])


class TestModul(unittest.TestCase):
    def test_lade_als(self):
        with tempfile.TemporaryDirectory() as ordner:
            with open(os.path.join(ordner, 'm.deu'), 'w', encoding='utf-8') as f:
                f.write(FARBE)
            code = ('lade "m.deu" als m\nsei f: m.Farbe = m.Farbe.rot\n'
                    'drucke(f, f == m.Farbe.rot)')
            self.assertEqual(ausgabe(code, ladepfad=ordner), ['Farbe.rot wahr'])


class TestLinter(unittest.TestCase):
    def test_keine_fehlwarnung(self):
        code = FARBE + 'funktion f() { sei x = Farbe.rot\n zurück x }\ndrucke(f(), Farbe.blau.wert)\n'
        self.assertEqual(linter.pruefe(parse(code)), [])
        rc, aus, fehler = starte_pruefen(code)
        self.assertEqual(rc, 0, aus + fehler)
        self.assertNotIn('unbekannter Name', aus + fehler)


if __name__ == '__main__':
    unittest.main()
