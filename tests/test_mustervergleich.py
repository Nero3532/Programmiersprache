# -*- coding: utf-8 -*-
"""Tests für den Mustervergleich: Typmuster, 'sei'-Muster, Wächter, Alternativen, 'passe' als Ausdruck."""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.interpreter import Interpreter
from deutsch.lexer import Lexer
from deutsch.linter import pruefe
from deutsch.parser import Parser


def ausgabe(code):
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter().ausfuehren(Parser(Lexer(code).tokenisieren()).parse())
    return puffer.getvalue().splitlines()


def fehler(code):
    """Fehlertext (Python-Typ: Meldung) oder None, wenn der Code läuft."""
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            Interpreter().ausfuehren(Parser(Lexer(code).tokenisieren()).parse())
        except Exception as e:
            return f'{type(e).__name__}: {e}'
    return None


def warnungen(code):
    return pruefe(Parser(Lexer(code).tokenisieren()).parse())


class TestTypmuster(unittest.TestCase):
    def test_primitive(self):
        code = '''funktion f(x) { passe x {
            fall Ganzzahl n: { zurück "int " + zeichenkette(n) }
            fall Zeichenkette s: { zurück "str " + s }
            fall Liste l: { zurück "liste" }
            sonst: { zurück "?" }
        } }
        drucke(f(3)); drucke(f("a")); drucke(f([1])); drucke(f(nichts))'''
        self.assertEqual(ausgabe(code), ['int 3', 'str a', 'liste', '?'])

    def test_ganzzahl_passt_nicht_auf_wahr(self):
        code = 'passe wahr { fall Ganzzahl n: { drucke("int") } fall Wahrheitswert w: { drucke("bool") } }'
        self.assertEqual(ausgabe(code), ['bool'])

    def test_klasse_mit_vererbung(self):
        code = '''klasse Tier { }
        klasse Hund(Tier) { }
        klasse Stein { }
        für x in [neu Hund(), neu Tier(), neu Stein()] {
            passe x { fall Hund h: { drucke("hund") } fall Tier t: { drucke("tier") } sonst: { drucke("sonst") } }
        }'''
        self.assertEqual(ausgabe(code), ['hund', 'tier', 'sonst'])

    def test_aufzaehlung(self):
        code = '''aufzählung Farbe { rot, gruen }
        passe Farbe.rot { fall Farbe f: { drucke("farbe") } }
        passe 1 { fall Farbe f: { drucke("farbe") } sonst: { drucke("nein") } }'''
        self.assertEqual(ausgabe(code), ['farbe', 'nein'])

    def test_wertfehler_aus_fange(self):
        code = '''versuche { ganzzahl("x") } fange e {
            passe e { fall TypFehler f: { drucke("typ") } fall WertFehler f: { drucke("wert") } }
        }'''
        self.assertEqual(ausgabe(code), ['wert'])

    def test_eigene_fehlerklasse(self):
        code = '''klasse MeinFehler(Fehler) { }
        versuche { werfe neu MeinFehler() } fange e {
            passe e { fall WertFehler f: { drucke("wert") } fall MeinFehler m: { drucke("mein") } }
        }'''
        self.assertEqual(ausgabe(code), ['mein'])

    def test_unbekannter_typ(self):
        self.assertIn('Unbekannter Typ im Muster', fehler('passe 1 { fall Gibtsnicht g: { } }'))

    def test_einzelner_name_bleibt_wertvergleich(self):
        code = ('sei x = 5\npasse 5 { fall x: { drucke("gleich") } }\n'
                'passe 6 { fall x: { drucke("gleich") } sonst: { drucke("anders") } }')
        self.assertEqual(ausgabe(code), ['gleich', 'anders'])

    def test_platzhalter(self):
        self.assertEqual(ausgabe('passe 42 { fall 1: { drucke("a") } fall _: { drucke("alles") } }'), ['alles'])


class TestSeiMuster(unittest.TestCase):
    LISTE = '''funktion f(x) { zurück passe x {
        fall sei []: { "leer" }
        fall sei [a]: { "eins " + zeichenkette(a) }
        fall sei [a, *rest]: { "viele " + zeichenkette(a) + " " + zeichenkette(rest) }
        sonst: { "kein" }
    } }
    '''

    def test_liste_leer_kurz_lang(self):
        code = self.LISTE + 'drucke(f([])); drucke(f([7])); drucke(f([1, 2, 3])); drucke(f("x"))'
        self.assertEqual(ausgabe(code), ['leer', 'eins 7', 'viele 1 [2, 3]', 'kein'])

    def test_literal_vergleicht_name_bindet(self):
        code = '''funktion f(x) { zurück passe x { fall sei [0, b]: { "null " + zeichenkette(b) } fall sei [a, b]: { "sonst" } } }
        drucke(f([0, 5])); drucke(f([1, 5]))'''
        self.assertEqual(ausgabe(code), ['null 5', 'sonst'])

    def test_name_im_muster_bindet_neu(self):
        code = 'sei k = 7\npasse [2, 9] { fall sei [k, z]: { drucke(k); drucke(z) } }'
        self.assertEqual(ausgabe(code), ['2', '9'])

    def test_punktpfad_vergleicht(self):
        code = '''aufzählung F { rot, gruen }
        für x in [[F.rot, 1], [F.gruen, 2]] {
            passe x { fall sei [F.rot, n]: { drucke("rot " + zeichenkette(n)) } sonst: { drucke("andere") } }
        }'''
        self.assertEqual(ausgabe(code), ['rot 1', 'andere'])

    def test_verschachtelt_und_typ_im_muster(self):
        code = 'passe [1, [2, "x"]] { fall sei [a, [Ganzzahl b, Zeichenkette c]]: { drucke(a + b); drucke(c) } }'
        self.assertEqual(ausgabe(code), ['3', 'x'])

    def test_woerterbuch(self):
        code = '''funktion f(x) { zurück passe x {
            fall sei {"typ": "kreis", "r": r}: { "kreis " + zeichenkette(r) }
            fall sei {"typ": t}: { "typ " + t }
            sonst: { "kein" }
        } }
        drucke(f({"typ": "kreis", "r": 2, "extra": 1})); drucke(f({"typ": "quadrat"}))
        drucke(f({"r": 1})); drucke(f([1]))'''
        self.assertEqual(ausgabe(code), ['kreis 2', 'typ quadrat', 'kein', 'kein'])

    def test_sei_name_bindet_alles(self):
        code = 'passe 5 { fall sei x wenn x > 9: { drucke("gross") } fall sei x: { drucke(x) } }'
        self.assertEqual(ausgabe(code), ['5'])

    def test_ohne_sei_kein_binden(self):
        # ohne 'sei' ist '[a, b]' ein Wertvergleich; 'a' ist hier unbekannt
        self.assertIn('NameError', fehler('passe [1, 2] { fall [a, b]: { } }'))
        self.assertEqual(ausgabe('passe [1, 2] { fall [1, 2]: { drucke("ja") } }'), ['ja'])

    def test_instanz_wird_nicht_verbraucht(self):
        code = '''klasse Z { funktion __init__(dies) { dies.i = 0 }
            funktion __iter__(dies) { zurück dies }
            funktion __naechstes__(dies) { dies.i += 1
                wenn dies.i > 2 { werfe IterationsEnde() }
                zurück dies.i } }
        sei z = neu Z()
        passe z { fall sei [a, b]: { drucke("liste") } sonst: { drucke("kein") } }
        drucke(z.i)'''
        self.assertEqual(ausgabe(code), ['kein', '0'])

    def test_mehrere_sterne_parserfehler(self):
        self.assertIn('höchstens ein', fehler('passe [1] { fall sei [*a, *b]: { } }'))


class TestWaechter(unittest.TestCase):
    def test_wahr_sieht_bindung(self):
        code = 'passe [5, 1] { fall sei [a, b] wenn a > b: { drucke("gross") } sonst: { drucke("klein") } }'
        self.assertEqual(ausgabe(code), ['gross'])

    def test_falsch_naechster_arm(self):
        code = ('passe [1, 5] { fall sei [a, b] wenn a > b: { drucke("gross") } '
                'fall sei [a, b]: { drucke("zweiter " + zeichenkette(b)) } }')
        self.assertEqual(ausgabe(code), ['zweiter 5'])

    def test_wert_mit_waechter(self):
        code = 'sei n = 3\npasse 3 { fall 3 wenn n > 5: { drucke("a") } fall 3 wenn n < 5: { drucke("b") } }'
        self.assertEqual(ausgabe(code), ['b'])

    def test_typ_mit_waechter(self):
        code = 'passe 4 { fall Ganzzahl n wenn n % 2 == 1: { drucke("ungerade") } fall Ganzzahl n: { drucke("gerade") } }'
        self.assertEqual(ausgabe(code), ['gerade'])

    def test_ternaer_nur_in_klammern(self):
        code = 'passe 1 { fall (2 wenn wahr sonst 3): { drucke("a") } fall 1: { drucke("b") } }'
        self.assertEqual(ausgabe(code), ['b'])


class TestAlternativen(unittest.TestCase):
    def test_werte(self):
        self.assertEqual(ausgabe('passe 2 { fall 1, 2, 3: { drucke("klein") } }'), ['klein'])

    def test_gleiche_namen_binden(self):
        code = 'für x in [[1, 2], [3, 9]] { passe x { fall sei [a, 2], sei [a, 9]: { drucke(a) } } }'
        self.assertEqual(ausgabe(code), ['1', '3'])

    def test_unterschiedliche_namen_parserfehler(self):
        self.assertIn('dieselben Namen', fehler('passe 1 { fall sei a, sei b: { } }'))
        self.assertIn('dieselben Namen', fehler('passe 1 { fall sei [a, b], sei [a]: { } }'))


class TestScope(unittest.TestCase):
    def test_bindung_ausserhalb_unsichtbar(self):
        self.assertIn('NameError', fehler('passe [1] { fall sei [zz]: { drucke(zz) } }\ndrucke(zz)'))

    def test_bindung_falscher_arm_unsichtbar(self):
        self.assertIn('NameError', fehler('passe [1, 2] { fall sei [q]: { } fall sei [a, b]: { drucke(q) } }'))


class TestPasseAusdruck(unittest.TestCase):
    def test_wert_des_arms(self):
        code = 'sei r = passe 2 { fall 1: { "eins" } fall 2: { drucke("x")\n "zwei" } }\ndrucke(r)'
        self.assertEqual(ausgabe(code), ['x', 'zwei'])

    def test_sonst(self):
        self.assertEqual(ausgabe('drucke(passe 9 { fall 1: { "a" } sonst: { "b" } })'), ['b'])

    def test_ohne_treffer_wertfehler(self):
        self.assertIn("ValueError: Zeile 1: 'passe': kein 'fall' passt", fehler('sei r = passe 9 { fall 1: { "a" } }'))

    def test_ohne_treffer_fangbar(self):
        code = 'versuche { sei r = passe 9 { fall 1: { "a" } } } fange (WertFehler) e { drucke("fehler") }'
        self.assertEqual(ausgabe(code), ['fehler'])

    def test_anweisung_ohne_treffer_nichts(self):
        self.assertEqual(ausgabe('passe 9 { fall 1: { drucke("a") } }\ndrucke("ende")'), ['ende'])

    def test_rueckgabe_und_klammern_mit_umbruechen(self):
        code = '''funktion f(x) { zurück passe x {
            fall 1: { "a" }
            sonst: { "b" }
        } }
        drucke(f(1)); drucke(f(2))
        drucke((passe 2 {
            fall 2: { "klammer" }
        }))'''
        self.assertEqual(ausgabe(code), ['a', 'b', 'klammer'])

    def test_verschachtelt(self):
        code = 'drucke(passe 1 { fall 1: { passe 2 { fall 2: { "innen" } } } })'
        self.assertEqual(ausgabe(code), ['innen'])


class TestGleichHook(unittest.TestCase):
    def test_gleich_hook_greift_beim_wertvergleich(self):
        code = '''klasse Z { funktion __init__(dies, n) { dies.n = n }
            funktion __gleich__(dies, o) { zurück o == dies.n } }
        passe neu Z(5) { fall 5: { drucke("hook") } sonst: { drucke("kein hook") } }'''
        self.assertEqual(ausgabe(code), ['hook'])


class TestLinter(unittest.TestCase):
    def test_keine_fehlwarnung_auf_bindungen(self):
        code = '''funktion f(x) { zurück passe x {
            fall sei [a, *rest] wenn a > 0: { a + rest[0] }
            fall sei {"typ": t}: { t }
            fall Ganzzahl n: { n }
            sonst: { 0 }
        } }
        drucke(f([1, 2]))'''
        self.assertEqual(warnungen(code), [])

    def test_unbekannter_name_im_wert_wird_gemeldet(self):
        self.assertTrue(warnungen('passe 1 { fall sei [a, unbekannt.x]: { } }'))


if __name__ == '__main__':
    unittest.main()
