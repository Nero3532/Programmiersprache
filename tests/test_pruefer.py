# -*- coding: utf-8 -*-
"""
Tests für die statische Prüfung.

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import glob
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.pruefer import pruefe

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEISPIELE = os.path.join(PROJEKT_WURZEL, 'beispiele')


def befunde(code: str, ladepfad: str = None) -> list:
    return pruefe(Parser(Lexer(code).tokenisieren()).parse(), ladepfad)


def meldungen(code: str, ladepfad: str = None) -> str:
    return ' | '.join(b.meldung for b in befunde(code, ladepfad))


class TestKeineFehlalarme(unittest.TestCase):
    """Wichtigste Eigenschaft: gültiger Code darf keine Befunde erzeugen."""

    def test_alle_beispielskripte_sind_sauber(self):
        dateien = sorted(glob.glob(os.path.join(BEISPIELE, '*.deu')))
        self.assertGreater(len(dateien), 0)
        for pfad in dateien:
            with self.subTest(datei=os.path.basename(pfad)):
                with io.open(pfad, encoding='utf-8') as datei:
                    quelltext = datei.read()
                gefunden = befunde(quelltext, BEISPIELE)
                self.assertEqual(
                    [f'Z.{b.zeile}: {b.meldung}' for b in gefunden], [],
                    'gültiger Code darf keine Befunde erzeugen')

    def test_gueltige_konstrukte(self):
        for code in (
            'sei x: Kommazahl = 5',                       # Ganzzahl passt zu Kommazahl
            'sei l = [1,2]; l.anhaengen(3)',
            'funktion f(a, b = 2) { zurück a }; f(1)',
            'funktion f(*x) { zurück x }; f(1,2,3)',
            'funktion f(a, b) { zurück a }; f(*[1,2])',   # Anzahl erst zur Laufzeit klar
            'funktion a() { zurück b() }\nfunktion b() { zurück 1 }\na()',
            'klasse K { funktion __init__(dies, x) { dies.x = x } }; neu K(1)',
            'funktion g() { ergibt 1 }; liste(g())',
            'für i in bereich(3) { drucke(i) }',
            '[x für x in bereich(3) wenn x > 0]',
            'versuche { werfe "x" } fange f { drucke(f) }',
            'sei w = mathe.wurzel(4); drucke(zeit.jetzt())',
            'sei x = 1; x = 2',
        ):
            with self.subTest(code=code):
                self.assertEqual(meldungen(code), '')

    def test_unbekannter_typ_erzeugt_keinen_folgefehler(self):
        gefunden = befunde('sei s: Ganzahl = 1')
        self.assertEqual(len(gefunden), 1)
        self.assertIn('Unbekannter Typ-Hinweis', gefunden[0].meldung)


class TestNamen(unittest.TestCase):
    def test_unbekannter_name(self):
        self.assertIn('Unbekannte Variable oder Funktion', meldungen('drucke(zaehlre)'))

    def test_vorschlag_bei_tippfehler(self):
        self.assertIn("meintest du 'zaehler'", meldungen('sei zaehler = 1\ndrucke(zaehlrer)'))

    def test_zuweisung_ohne_deklaration(self):
        self.assertIn('wurde nicht deklariert', meldungen('zaehler = 5'))

    def test_zuweisung_an_konstante(self):
        self.assertIn('ist eine Konstante', meldungen('konstante K = 1\nK = 2'))

    def test_unbekannte_elternklasse(self):
        self.assertIn('Unbekannte Elternklasse', meldungen('klasse A(Fehlt) { }'))

    def test_schleifen_und_fange_variablen_sind_bekannt(self):
        self.assertEqual(meldungen('für i in [1] { drucke(i) }'), '')
        self.assertEqual(meldungen('versuche { werfe 1 } fange f { drucke(f) }'), '')

    def test_variable_aus_einem_block_gilt_nicht_ausserhalb(self):
        self.assertIn('Unbekannte Variable', meldungen('wenn wahr { sei x = 1 }\ndrucke(x)'))


class TestTypen(unittest.TestCase):
    def test_konflikt_bei_deklaration(self):
        self.assertIn("erwartet Typ 'Ganzzahl'", meldungen('sei x: Ganzzahl = "text"'))

    def test_ganzzahl_gilt_als_kommazahl(self):
        self.assertEqual(meldungen('sei x: Kommazahl = 5'), '')

    def test_rueckgabetyp(self):
        code = 'funktion f() -> Ganzzahl { zurück "x" }'
        self.assertIn('Rückgabewert', meldungen(code))

    def test_rueckgabetyp_ok(self):
        self.assertEqual(meldungen('funktion f() -> Ganzzahl { zurück 5 }'), '')

    def test_unbekannter_typ_hinweis(self):
        self.assertIn("Unbekannter Typ-Hinweis: 'Ganzahl'", meldungen('sei x: Ganzahl = 1'))

    def test_eigene_klasse_als_typ_hinweis(self):
        code = 'klasse K { }\nfunktion f(k: K) { zurück 1 }'
        self.assertEqual(meldungen(code), '')


class TestAufrufe(unittest.TestCase):
    F = 'funktion f(a, b) { zurück a }\n'

    def test_zu_wenige_argumente(self):
        self.assertIn('Pflichtargument(e) fehlen: b', meldungen(self.F + 'f(1)'))

    def test_zu_viele_argumente(self):
        self.assertIn('erwartet höchstens 2', meldungen(self.F + 'f(1,2,3)'))

    def test_unbekanntes_keyword_argument(self):
        self.assertIn("hat keinen Parameter 'c'", meldungen(self.F + 'f(1, c=2)'))

    def test_keyword_deckt_pflichtargument_ab(self):
        self.assertEqual(meldungen(self.F + 'f(1, b=2)'), '')

    def test_konstruktor(self):
        code = 'klasse P { funktion __init__(dies, x) { dies.x = x } }\nneu P()'
        self.assertIn('Pflichtargument(e) fehlen: x', meldungen(code))

    def test_entpackung_unterdrueckt_die_anzahlpruefung(self):
        self.assertEqual(meldungen(self.F + 'f(*[1,2])'), '')


class TestBibliothek(unittest.TestCase):
    def test_unbekanntes_modulmitglied(self):
        self.assertIn("hat kein Attribut 'wurzl'", meldungen('drucke(mathe.wurzl(4))'))

    def test_vorschlag_beim_modulmitglied(self):
        self.assertIn("meintest du 'wurzel'", meldungen('drucke(mathe.wurzl(4))'))

    def test_unbekannte_methode_auf_eingebautem_typ(self):
        self.assertIn("hat kein Attribut 'grosss'",
                      meldungen('sei s = "abc"\ndrucke(s.grosss())'))

    def test_methode_auf_unbekanntem_typ_wird_nicht_gemeldet(self):
        # Der Typ von 'x' ist nicht ableitbar – dann schweigt der Prüfer
        self.assertEqual(meldungen('funktion f(x) { zurück x.irgendwas() }'), '')


class TestLaden(unittest.TestCase):
    def test_lade_bringt_namen_mit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, 'hilf.deu'), 'w', encoding='utf-8') as datei:
                datei.write('funktion hilfe(a) { zurück a }\nsei WERT = 1\n')
            code = 'lade "hilf.deu"\ndrucke(hilfe(WERT))'
            self.assertEqual(meldungen(code, tmp), '')

    def test_lade_prueft_auch_die_signatur(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, 'hilf.deu'), 'w', encoding='utf-8') as datei:
                datei.write('funktion hilfe(a, b) { zurück a }\n')
            self.assertIn('Pflichtargument(e) fehlen: b',
                          meldungen('lade "hilf.deu"\nhilfe(1)', tmp))

    def test_unlesbare_datei_schaltet_namenspruefung_ab(self):
        # Lieber schweigen als raten: sonst gäbe es lauter Fehlalarme
        code = 'lade "gibt_es_nicht.deu"\ndrucke(unbekannt_xyz)'
        self.assertEqual(meldungen(code, '.'), '')

    def test_namensraum_inhalt_wird_nicht_geraten(self):
        self.assertEqual(meldungen('lade "x.deu" als m\ndrucke(m.beliebig())', '.'), '')


if __name__ == '__main__':
    unittest.main()
