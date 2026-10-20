# -*- coding: utf-8 -*-
"""
Tests für die Stdlib-Erweiterungen aus P2 Runde 4: Dateien/Pfade, Text-Methoden,
Listen/Wörterbücher, Mathe (Arkusfunktionen, kaufmännisches runde) und Zeit,
dazu die übersetzten Fehlermeldungen. Je Funktion: Normalfall sowie Fehlerfall.

Ausführen mit:
    py -m unittest discover -s tests -p test_stdlib_p2.py -v
"""
import datetime as dt
import math
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter


def auswerten(code: str, ladepfad=None, **variablen):
    """Tokenisiert, parst und führt Code aus. Gibt den Wert der letzten Anweisung zurück.
    Keyword-Argumente werden als globale Variablen gesetzt (z. B. unendlich=math.inf)."""
    tokens = Lexer(code).tokenisieren()
    baum = Parser(tokens).parse()
    interpreter = Interpreter(ladepfad=ladepfad)
    for name, wert in variablen.items():
        interpreter.global_umgebung.setze(name, wert)
    return interpreter.ausfuehren(baum)


class DateiTestBasis(unittest.TestCase):
    """Legt für jeden Test einen eigenen Ordner an, relative Pfade im Code beziehen sich darauf."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ordner = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def datei(self, name, inhalt=''):
        pfad = os.path.join(self.ordner, name)
        with open(pfad, 'w', encoding='utf-8', newline='') as f:
            f.write(inhalt)
        return pfad

    def hier(self, code):
        return auswerten(code, ladepfad=self.ordner)


class TestPfadVerbinden(unittest.TestCase):
    def test_verbindet_teile(self):
        self.assertEqual(auswerten('pfad_verbinden("a", "b", "c.txt")'), os.path.join('a', 'b', 'c.txt'))

    def test_ein_teil(self):
        self.assertEqual(auswerten('pfad_verbinden("a.txt")'), 'a.txt')

    def test_fehler_ohne_argumente(self):
        with self.assertRaisesRegex(TypeError, "'pfad_verbinden' erwartet mindestens 1 Argument"):
            auswerten('pfad_verbinden()')


class TestDateiname(unittest.TestCase):
    def test_letzter_teil_des_pfads(self):
        self.assertEqual(auswerten('dateiname("ordner/datei.txt")'), 'datei.txt')
        self.assertEqual(auswerten('dateiname("datei.txt")'), 'datei.txt')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('dateiname()')
        with self.assertRaises(TypeError):
            auswerten('dateiname("a", "b")')


class TestOrdnername(unittest.TestCase):
    def test_pfad_des_enthaltenden_ordners(self):
        self.assertEqual(auswerten('ordnername("a/b/c.txt")'), 'a/b')

    def test_ohne_ordneranteil_ist_leer(self):
        self.assertEqual(auswerten('ordnername("c.txt")'), '')

    def test_passt_zu_pfad_verbinden_und_dateiname(self):
        self.assertEqual(
            auswerten('pfad_verbinden(ordnername("a/b/c.txt"), dateiname("a/b/c.txt"))'),
            os.path.join('a/b', 'c.txt'),
        )

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('ordnername()')


class TestEndung(unittest.TestCase):
    def test_mit_punkt(self):
        self.assertEqual(auswerten('endung("bild.png")'), '.png')

    def test_nur_letzte_endung(self):
        self.assertEqual(auswerten('endung("archiv.tar.gz")'), '.gz')

    def test_ohne_endung_ist_leer(self):
        self.assertEqual(auswerten('endung("readme")'), '')
        self.assertEqual(auswerten('endung(".bashrc")'), '')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('endung()')


class TestIstDateiIstOrdner(DateiTestBasis):
    def setUp(self):
        super().setUp()
        self.datei('a.txt', 'x')
        os.mkdir(os.path.join(self.ordner, 'ordner'))

    def test_ist_datei(self):
        self.assertIs(self.hier('ist_datei("a.txt")'), True)
        self.assertIs(self.hier('ist_datei("ordner")'), False)
        self.assertIs(self.hier('ist_datei("gibt_es_nicht.txt")'), False)

    def test_ist_ordner(self):
        self.assertIs(self.hier('ist_ordner("ordner")'), True)
        self.assertIs(self.hier('ist_ordner("a.txt")'), False)
        self.assertIs(self.hier('ist_ordner("gibt_es_nicht")'), False)

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            self.hier('ist_datei()')
        with self.assertRaises(TypeError):
            self.hier('ist_ordner("a", "b")')


class TestDateiLoeschen(DateiTestBasis):
    def test_loescht_datei(self):
        pfad = self.datei('weg.txt', 'x')
        self.assertIsNone(self.hier('datei_loeschen("weg.txt")'))
        self.assertFalse(os.path.exists(pfad))

    def test_umlaut_schreibweise_ist_gleichwertig(self):
        pfad = self.datei('weg.txt', 'x')
        self.hier('datei_löschen("weg.txt")')
        self.assertFalse(os.path.exists(pfad))

    def test_ordner_wird_nicht_geloescht(self):
        ordner = os.path.join(self.ordner, 'ordner')
        os.mkdir(ordner)
        with self.assertRaisesRegex(IsADirectoryError, 'ist ein Ordner, keine Datei'):
            self.hier('datei_loeschen("ordner")')
        self.assertTrue(os.path.isdir(ordner))

    def test_fehlende_datei_wirft_deutschen_fehler(self):
        with self.assertRaisesRegex(FileNotFoundError, "Datei nicht gefunden: 'nicht_da.txt'"):
            self.hier('datei_loeschen("nicht_da.txt")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            self.hier('datei_loeschen()')


class TestUmbenennen(DateiTestBasis):
    def test_benennt_datei_um(self):
        alt = self.datei('alt.txt', 'inhalt')
        self.assertIsNone(self.hier('umbenennen("alt.txt", "neu.txt")'))
        self.assertFalse(os.path.exists(alt))
        with open(os.path.join(self.ordner, 'neu.txt'), encoding='utf-8') as f:
            self.assertEqual(f.read(), 'inhalt')

    def test_benennt_ordner_um(self):
        os.mkdir(os.path.join(self.ordner, 'alt'))
        self.hier('umbenennen("alt", "neu")')
        self.assertTrue(os.path.isdir(os.path.join(self.ordner, 'neu')))
        self.assertFalse(os.path.exists(os.path.join(self.ordner, 'alt')))

    def test_vorhandenes_ziel_wird_nicht_ueberschrieben(self):
        self.datei('alt.txt', 'neu')
        self.datei('ziel.txt', 'bleibt')
        with self.assertRaisesRegex(FileExistsError, "'ziel.txt' existiert bereits"):
            self.hier('umbenennen("alt.txt", "ziel.txt")')
        with open(os.path.join(self.ordner, 'ziel.txt'), encoding='utf-8') as f:
            self.assertEqual(f.read(), 'bleibt')

    def test_fehlende_quelle_wirft_deutschen_fehler(self):
        with self.assertRaisesRegex(FileNotFoundError, "Datei oder Ordner nicht gefunden: 'nicht_da.txt'"):
            self.hier('umbenennen("nicht_da.txt", "x.txt")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            self.hier('umbenennen("a.txt")')


class TestZeilenLesen(DateiTestBasis):
    def test_liefert_zeilen_ohne_umbruch(self):
        self.datei('t.txt', 'eins\nzwei\n')
        self.assertEqual(self.hier('zeilen_lesen("t.txt")'), ['eins', 'zwei'])

    def test_windows_umbrueche_und_leerzeilen(self):
        self.datei('t.txt', 'a\r\nb\n\nc')
        self.assertEqual(self.hier('zeilen_lesen("t.txt")'), ['a', 'b', '', 'c'])

    def test_leere_datei_ergibt_leere_liste(self):
        self.datei('leer.txt', '')
        self.assertEqual(self.hier('zeilen_lesen("leer.txt")'), [])

    def test_fehlende_datei_wirft_deutschen_fehler(self):
        with self.assertRaisesRegex(FileNotFoundError, "Datei nicht gefunden"):
            self.hier('zeilen_lesen("nicht_da.txt")')

    def test_ordner_wird_abgelehnt(self):
        os.mkdir(os.path.join(self.ordner, 'ordner'))
        with self.assertRaisesRegex(IsADirectoryError, 'ist ein Ordner'):
            self.hier('zeilen_lesen("ordner")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            self.hier('zeilen_lesen()')


class TestDateiLesenUnveraendert(DateiTestBasis):
    """datei_lesen nutzt jetzt denselben Helfer wie zeilen_lesen; die Meldungen bleiben gleich."""

    def test_fehlende_datei(self):
        with self.assertRaisesRegex(FileNotFoundError, "Datei nicht gefunden: 'nicht_da.txt'"):
            self.hier('datei_lesen("nicht_da.txt")')

    def test_ordner(self):
        os.mkdir(os.path.join(self.ordner, 'ordner'))
        with self.assertRaisesRegex(IsADirectoryError, "'ordner' ist ein Ordner, keine Datei"):
            self.hier('datei_lesen("ordner")')


class TestLinksAuffuellen(unittest.TestCase):
    def test_fuellt_links_auf(self):
        self.assertEqual(auswerten('"7".links_auffuellen(3, "0")'), '007')

    def test_standardzeichen_ist_leerzeichen(self):
        self.assertEqual(auswerten('"7".links_auffuellen(3)'), '  7')

    def test_breite_kleiner_als_text_laesst_ihn_stehen(self):
        self.assertEqual(auswerten('"abcd".links_auffuellen(2, "0")'), 'abcd')

    def test_umlaut_schreibweise_ist_gleichwertig(self):
        self.assertEqual(auswerten('"7".links_auffüllen(3, "0")'), '007')

    def test_zeichen_als_keyword(self):
        self.assertEqual(auswerten('"7".links_auffuellen(3, zeichen="0")'), '007')

    def test_fehler_bei_mehrzeichigem_fuellzeichen(self):
        with self.assertRaisesRegex(ValueError, 'genau 1 Zeichen'):
            auswerten('"7".links_auffuellen(3, "00")')
        with self.assertRaises(ValueError):
            auswerten('"7".links_auffuellen(3, "")')

    def test_fehler_bei_nicht_ganzzahliger_breite(self):
        with self.assertRaisesRegex(TypeError, 'Ganzzahl als Breite'):
            auswerten('"7".links_auffuellen("3")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('"7".links_auffuellen()')
        with self.assertRaises(TypeError):
            auswerten('"7".links_auffuellen(3, "0", "x")')

    def test_fehler_bei_unbekanntem_keyword(self):
        with self.assertRaisesRegex(TypeError, "kein Parameter 'x'"):
            auswerten('"7".links_auffuellen(3, zeichen="0", x=1)')

    def test_fehler_bei_doppeltem_zeichen(self):
        with self.assertRaisesRegex(TypeError, 'mehrfach angegeben'):
            auswerten('"7".links_auffuellen(3, "0", zeichen="0")')


class TestRechtsAuffuellen(unittest.TestCase):
    def test_fuellt_rechts_auf(self):
        self.assertEqual(auswerten('"7".rechts_auffuellen(3, "0")'), '700')

    def test_umlaut_schreibweise_ist_gleichwertig(self):
        self.assertEqual(auswerten('"7".rechts_auffüllen(3, "0")'), '700')

    def test_standardzeichen_ist_leerzeichen(self):
        self.assertEqual(auswerten('"7".rechts_auffuellen(2)'), '7 ')

    def test_fehler_bei_mehrzeichigem_fuellzeichen(self):
        with self.assertRaisesRegex(ValueError, 'genau 1 Zeichen'):
            auswerten('"7".rechts_auffuellen(3, "ab")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('"7".rechts_auffuellen()')


class TestZentrieren(unittest.TestCase):
    def test_zentriert_mit_zeichen(self):
        self.assertEqual(auswerten('"ab".zentrieren(6, "*")'), '**ab**')

    def test_standardzeichen_ist_leerzeichen(self):
        self.assertEqual(auswerten('"ab".zentrieren(4)'), ' ab ')

    def test_zeichen_als_keyword(self):
        self.assertEqual(auswerten('"ab".zentrieren(6, zeichen="*")'), '**ab**')

    def test_fehler_bei_mehrzeichigem_fuellzeichen(self):
        with self.assertRaisesRegex(ValueError, 'genau 1 Zeichen'):
            auswerten('"ab".zentrieren(6, "--")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('"ab".zentrieren()')


class TestErsetzeMitAnzahl(unittest.TestCase):
    def test_ohne_anzahl_ersetzt_alle(self):
        self.assertEqual(auswerten('"aaaa".ersetze("a", "b")'), 'bbbb')

    def test_mit_anzahl(self):
        self.assertEqual(auswerten('"aaaa".ersetze("a", "b", 2)'), 'bbaa')

    def test_anzahl_null_ersetzt_nichts(self):
        self.assertEqual(auswerten('"aaaa".ersetze("a", "b", 0)'), 'aaaa')

    def test_anzahl_groesser_als_vorkommen(self):
        self.assertEqual(auswerten('"aaa".ersetze("a", "b", 10)'), 'bbb')

    def test_negative_anzahl_wirft_wertfehler(self):
        with self.assertRaisesRegex(ValueError, "Anzahl von 0 oder mehr"):
            auswerten('"aaa".ersetze("a", "b", -1)')

    def test_anzahl_kein_ganzzahl(self):
        with self.assertRaisesRegex(TypeError, 'Ganzzahl als Anzahl'):
            auswerten('"aaa".ersetze("a", "b", "2")')

    def test_fehler_bei_nicht_text_als_suchwert(self):
        with self.assertRaisesRegex(TypeError, 'Zeichenketten als erstes und zweites Argument'):
            auswerten('"abc".ersetze(1, "x")')

    def test_fehler_bei_falscher_argumentzahl_ohne_lambda_namen(self):
        with self.assertRaisesRegex(TypeError, "'ersetze' erwartet 2–3 Argumente, bekam 1") as ctx:
            auswerten('"abc".ersetze("a")')
        self.assertNotIn('lambda', str(ctx.exception))


class TestEindeutig(unittest.TestCase):
    def test_entfernt_dubletten_in_reihenfolge(self):
        self.assertEqual(auswerten('eindeutig([3, 1, 3, 2, 1])'), [3, 1, 2])

    def test_listen_methode(self):
        self.assertEqual(auswerten('[1, 1, 2].eindeutig()'), [1, 2])

    def test_unhashbare_werte(self):
        self.assertEqual(auswerten('eindeutig([[1], [1], [2]])'), [[1], [2]])

    def test_leere_liste(self):
        self.assertEqual(auswerten('eindeutig([])'), [])

    def test_originalliste_bleibt_unveraendert(self):
        self.assertEqual(auswerten('sei l = [1, 1]\nl.eindeutig()\nl'), [1, 1])

    def test_fehler_bei_nicht_liste(self):
        with self.assertRaisesRegex(TypeError, "'eindeutig' erwartet eine Liste"):
            auswerten('eindeutig("abc")')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('eindeutig([1], 2)')


class TestGruppiere(unittest.TestCase):
    def test_gruppiert_nach_schluessel(self):
        self.assertEqual(auswerten('gruppiere([1, 2, 3, 4], funktion(x) -> x % 2)'), {1: [1, 3], 0: [2, 4]})

    def test_schluessel_in_erster_fundreihenfolge(self):
        self.assertEqual(auswerten('sei g = gruppiere([3, 4, 5], funktion(x) -> x % 2)\ng.schluessel()'), [1, 0])

    def test_leere_sammlung(self):
        self.assertEqual(auswerten('gruppiere([], funktion(x) -> x)'), {})

    def test_fehler_wenn_zweites_argument_keine_funktion_ist(self):
        with self.assertRaisesRegex(TypeError, "'gruppiere' erwartet als 2. Argument eine Funktion"):
            auswerten('gruppiere([1], 5)')

    def test_fehler_bei_unhashbarem_schluessel(self):
        with self.assertRaisesRegex(TypeError, 'unveränderlichen Wert, bekam Liste'):
            auswerten('gruppiere([1], funktion(x) -> [x])')

    def test_fehler_bei_falscher_parameterzahl_der_funktion(self):
        with self.assertRaisesRegex(TypeError, 'erwartet genau 2 Argumente'):
            auswerten('gruppiere([1], funktion(a, b) -> a)')

    def test_fehler_bei_falscher_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('gruppiere([1])')


class TestZusammenfuehren(unittest.TestCase):
    def test_spaetere_gewinnen(self):
        self.assertEqual(auswerten('zusammenfuehren({"a": 1, "b": 2}, {"b": 3})'), {'a': 1, 'b': 3})

    def test_mehr_als_zwei(self):
        self.assertEqual(auswerten('zusammenfuehren({"a": 1}, {"a": 2}, {"a": 3, "c": 4})'), {'a': 3, 'c': 4})

    def test_umlaut_schreibweise_ist_gleichwertig(self):
        self.assertEqual(auswerten('zusammenführen({"a": 1}, {"a": 2})'), {'a': 2})

    def test_woerterbuch_methode(self):
        self.assertEqual(auswerten('{"a": 1}.zusammenfuehren({"b": 2})'), {'a': 1, 'b': 2})

    def test_woerterbuch_methode_umlaut(self):
        self.assertEqual(auswerten('{"a": 1}.zusammenführen({"a": 5}, {"b": 2})'), {'a': 5, 'b': 2})

    def test_eingaben_bleiben_unveraendert(self):
        self.assertEqual(auswerten('sei a = {"x": 1}\nsei b = zusammenfuehren(a, {"y": 2})\na'), {'x': 1})

    def test_fehler_bei_nicht_woerterbuch(self):
        with self.assertRaisesRegex(TypeError, "'zusammenführen' erwartet Wörterbücher, bekam Liste"):
            auswerten('zusammenführen({"a": 1}, [1])')

    def test_fehler_ohne_argumente(self):
        with self.assertRaises(TypeError):
            auswerten('zusammenfuehren()')


class TestListenMaxMin(unittest.TestCase):
    def test_max_und_min(self):
        self.assertEqual(auswerten('[3, 1, 2].max()'), 3)
        self.assertEqual(auswerten('[3, 1, 2].min()'), 1)

    def test_mit_schluessel(self):
        self.assertEqual(auswerten('["aa", "b", "ccc"].max(schluessel=funktion(s) -> s.laenge())'), 'ccc')
        self.assertEqual(auswerten('["aa", "b", "ccc"].min(schluessel=funktion(s) -> s.laenge())'), 'b')

    def test_gleichstand_gewinnt_der_erste(self):
        self.assertEqual(auswerten('["ab", "cd"].max(schluessel=funktion(s) -> s.laenge())'), 'ab')

    def test_leere_liste_wirft_wertfehler(self):
        with self.assertRaisesRegex(ValueError, "'max' erwartet eine nicht-leere Liste"):
            auswerten('[].max()')
        with self.assertRaises(ValueError):
            auswerten('[].min()')

    def test_positionsargument_wird_abgelehnt(self):
        with self.assertRaisesRegex(TypeError, 'keine Positionsargumente'):
            auswerten('[1, 2].max(3)')

    def test_umgekehrt_gibt_es_nur_bei_sortiere(self):
        with self.assertRaisesRegex(TypeError, "'max' hat kein Parameter 'umgekehrt'"):
            auswerten('[1, 2].max(umgekehrt=wahr)')

    def test_nicht_vergleichbare_typen(self):
        with self.assertRaisesRegex(TypeError, "'max' kann Werte dieser Typen nicht vergleichen"):
            auswerten('[1, "a"].max()')


class TestArkusfunktionen(unittest.TestCase):
    def test_arcsin(self):
        self.assertAlmostEqual(auswerten('arcsin(1)'), math.pi / 2)
        self.assertAlmostEqual(auswerten('arcsin(0)'), 0.0)

    def test_arccos(self):
        self.assertAlmostEqual(auswerten('arccos(1)'), 0.0)
        self.assertAlmostEqual(auswerten('arccos(-1)'), math.pi)

    def test_arctan(self):
        self.assertAlmostEqual(auswerten('arctan(1)'), math.pi / 4)
        self.assertAlmostEqual(auswerten('arctan(0)'), 0.0)

    def test_arctan2_beruecksichtigt_quadranten(self):
        self.assertAlmostEqual(auswerten('arctan2(1, 1)'), math.pi / 4)
        self.assertAlmostEqual(auswerten('arctan2(-1, -1)'), -3 * math.pi / 4)
        self.assertAlmostEqual(auswerten('arctan2(0, -1)'), math.pi)

    def test_arcsin_und_arccos_ausserhalb_des_bereichs(self):
        with self.assertRaisesRegex(ValueError, "'arcsin' nicht definiert für 2"):
            auswerten('arcsin(2)')
        with self.assertRaisesRegex(ValueError, "'arccos' nicht definiert für -1.5"):
            auswerten('arccos(-1.5)')

    def test_nicht_zahl_wirft_typfehler(self):
        with self.assertRaisesRegex(TypeError, "'arcsin' erwartet eine Zahl, bekam Zeichenkette"):
            auswerten('arcsin("a")')
        with self.assertRaisesRegex(TypeError, "'arctan' erwartet eine Zahl, bekam Nichts"):
            auswerten('arctan(nichts)')
        with self.assertRaisesRegex(TypeError, "'arctan2' erwartet zwei Zahlen"):
            auswerten('arctan2("a", 1)')

    def test_falsche_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('arctan2(1)')
        with self.assertRaises(TypeError):
            auswerten('arccos()')


class TestRundeKaufmaennisch(unittest.TestCase):
    def test_halbe_werden_vom_nullpunkt_weg_gerundet(self):
        self.assertEqual(auswerten('runde(2.5)'), 3)
        self.assertEqual(auswerten('runde(-2.5)'), -3)
        self.assertEqual(auswerten('runde(0.5)'), 1)

    def test_dezimaldarstellung_statt_binaerfehler(self):
        self.assertEqual(auswerten('runde(2.675, 2)'), 2.68)
        self.assertEqual(auswerten('runde(1.005, 2)'), 1.01)

    def test_ohne_stellen_und_stellen_null_ergeben_ganzzahl(self):
        for code in ('runde(2.4)', 'runde(2.4, 0)'):
            with self.subTest(code=code):
                ergebnis = auswerten(code)
                self.assertEqual(ergebnis, 2)
                self.assertIsInstance(ergebnis, int)

    def test_mit_stellen_ergibt_kommazahl(self):
        ergebnis = auswerten('runde(2.675, 2)')
        self.assertIsInstance(ergebnis, float)

    def test_negative_stellen(self):
        ergebnis = auswerten('runde(1234.5678, -2)')
        self.assertEqual(ergebnis, 1200)
        self.assertIsInstance(ergebnis, int)
        self.assertEqual(auswerten('runde(1250, -2)'), 1300)
        self.assertEqual(auswerten('runde(-1250, -2)'), -1300)

    def test_negativer_rundungsrest_ergibt_keine_minus_null(self):
        ergebnis = auswerten('runde(-0.001, 2)')
        self.assertEqual(ergebnis, 0.0)
        self.assertEqual(math.copysign(1.0, ergebnis), 1.0)

    def test_grosse_stellenzahl_ist_schnell_und_exakt(self):
        self.assertEqual(auswerten('runde(2.5, 1000000000)'), 2.5)

    def test_grosse_zahl_mit_stellen(self):
        self.assertEqual(auswerten('runde(gross, 2)', gross=1e300), 1e300)

    def test_zeichenkette_wirft_typfehler_mit_und_ohne_stellen(self):
        with self.assertRaisesRegex(TypeError, "'runde' erwartet eine Zahl, bekam Zeichenkette"):
            auswerten('runde("3.7")')
        with self.assertRaisesRegex(TypeError, "'runde' erwartet eine Zahl, bekam Zeichenkette"):
            auswerten('runde("3.7", 1)')

    def test_nichts_wirft_typfehler_mit_und_ohne_stellen(self):
        with self.assertRaisesRegex(TypeError, "'runde' erwartet eine Zahl, bekam Nichts"):
            auswerten('runde(nichts)')
        with self.assertRaisesRegex(TypeError, "'runde' erwartet eine Zahl, bekam Nichts"):
            auswerten('runde(nichts, 2)')

    def test_stellen_muessen_ganzzahl_sein(self):
        with self.assertRaisesRegex(TypeError, 'Ganzzahl als Stellenzahl'):
            auswerten('runde(2.5, "1")')
        with self.assertRaisesRegex(TypeError, 'Ganzzahl als Stellenzahl'):
            auswerten('runde(2.5, 1.5)')

    def test_nicht_endliche_zahl_wirft_wertfehler(self):
        with self.assertRaisesRegex(ValueError, 'endliche Zahl'):
            auswerten('runde(unendlich)', unendlich=math.inf)
        with self.assertRaisesRegex(ValueError, 'endliche Zahl'):
            auswerten('runde(keine_zahl, 2)', keine_zahl=math.nan)

    def test_falsche_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('runde()')
        with self.assertRaises(TypeError):
            auswerten('runde(1, 2, 3)')


class TestWarte(unittest.TestCase):
    def test_wartet_die_angegebene_zeit(self):
        with mock.patch('time.sleep') as schlaf:
            self.assertIsNone(auswerten('warte(0.5)'))
        schlaf.assert_called_once_with(0.5)

    def test_null_sekunden_ist_erlaubt(self):
        with mock.patch('time.sleep') as schlaf:
            auswerten('warte(0)')
        schlaf.assert_called_once_with(0)

    def test_negative_zeit_wirft_wertfehler(self):
        with mock.patch('time.sleep') as schlaf:
            with self.assertRaisesRegex(ValueError, 'bekam -1'):
                auswerten('warte(-1)')
        schlaf.assert_not_called()

    def test_nicht_zahl_wirft_typfehler(self):
        with mock.patch('time.sleep'):
            with self.assertRaisesRegex(TypeError, "'warte' erwartet eine Zahl, bekam Zeichenkette"):
                auswerten('warte("1")')
            with self.assertRaisesRegex(TypeError, "'warte' erwartet eine Zahl, bekam Nichts"):
                auswerten('warte(nichts)')

    def test_nan_wirft_wertfehler(self):
        with mock.patch('time.sleep') as schlaf:
            with self.assertRaises(ValueError):
                auswerten('warte(zahl)', zahl=math.nan)
        schlaf.assert_not_called()

    def test_falsche_argumentzahl(self):
        with mock.patch('time.sleep'):
            with self.assertRaises(TypeError):
                auswerten('warte()')


class TestDatumLesen(unittest.TestCase):
    def test_liest_text_als_zeitstempel(self):
        erwartet = dt.datetime(2024, 3, 15, 10, 30).timestamp()
        self.assertEqual(auswerten('datum_lesen("2024-03-15 10:30", "%Y-%m-%d %H:%M")'), erwartet)

    def test_gegenstueck_zu_datum_formatieren(self):
        code = 'datum_formatieren(datum_lesen("15.03.2024 08:05", "%d.%m.%Y %H:%M"), "%d.%m.%Y %H:%M")'
        self.assertEqual(auswerten(code), '15.03.2024 08:05')

    def test_ergebnis_ist_kommazahl(self):
        self.assertIsInstance(auswerten('datum_lesen("2024-01-01", "%Y-%m-%d")'), float)

    def test_unpassender_text_wirft_deutschen_wertfehler(self):
        with self.assertRaisesRegex(ValueError, "'gestern' passt nicht zum Format '%Y-%m-%d'"):
            auswerten('datum_lesen("gestern", "%Y-%m-%d")')

    def test_falsche_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('datum_lesen("2024-01-01")')


class TestDatumFormatieren(unittest.TestCase):
    def wertfehler(self, code, **variablen):
        """Führt code aus, erwartet einen ValueError und gibt dessen Text ohne das 'Zeile N: ' zurück."""
        with self.assertRaises(ValueError) as ctx:
            auswerten(code, **variablen)
        return re.sub(r'^Zeile \d+: ', '', str(ctx.exception))

    def test_formatiert_zeitstempel(self):
        self.assertEqual(auswerten('datum_formatieren(0, "%Y")'), '1970')
        stempel = dt.datetime(2024, 3, 15, 10, 30).timestamp()
        self.assertEqual(auswerten('datum_formatieren(stempel, "%d.%m.%Y %H:%M")', stempel=stempel),
                         '15.03.2024 10:30')

    def test_ganzzahl_und_kommazahl_als_zeitstempel(self):
        self.assertEqual(auswerten('datum_formatieren(86400, "%Y")'), '1970')
        self.assertEqual(auswerten('datum_formatieren(86400.5, "%Y")'), '1970')

    def test_nicht_zahl_wirft_deutschen_wertfehler(self):
        faelle = {'"x"': 'Zeichenkette', 'nichts': 'Nichts', '[1]': 'Liste'}
        for wert, typname in faelle.items():
            with self.subTest(wert=wert):
                text = self.wertfehler(f'datum_formatieren({wert}, "%Y")')
                self.assertEqual(
                    text, f"'datum_formatieren' erwartet als Zeitstempel eine Zahl, bekam {typname}")
                self.assertNotIn('argument must be', text)

    def test_unendlich_und_nan_wirft_deutschen_wertfehler(self):
        for wert, text in [(math.inf, 'inf'), (-math.inf, '-inf'), (math.nan, 'nan')]:
            with self.subTest(wert=text):
                self.assertEqual(
                    self.wertfehler('datum_formatieren(stempel, "%Y")', stempel=wert),
                    f"'datum_formatieren' erwartet als Zeitstempel eine endliche Zahl, bekam {text}")

    def test_zeitstempel_ausserhalb_des_datumsbereichs(self):
        for code in ('datum_formatieren(1e20, "%Y")', 'datum_formatieren(-1e20, "%Y")',
                     'datum_formatieren(10 ** 30, "%Y")', 'datum_formatieren(1e12, "%Y")'):
            with self.subTest(code=code):
                text = self.wertfehler(code)
                self.assertTrue(text.startswith('Zeitstempel '), text)
                self.assertTrue(text.endswith(' liegt außerhalb des darstellbaren Datumsbereichs'), text)
                self.assertNotIn('out of range', text)

    def test_ungueltiges_format_wirft_deutschen_wertfehler(self):
        # Ob ein Format ungültig ist, hängt von der Plattform ab: hier fällt strftime sicher aus
        with mock.patch('deutsch.interpreter.datetime') as datum_klasse:
            datum_klasse.fromtimestamp.return_value.strftime.side_effect = ValueError('Invalid format string')
            text = self.wertfehler('datum_formatieren(0, "%Q")')
        self.assertEqual(text, "Ungültiges Datumsformat '%Q'")

    def test_falsche_argumentzahl(self):
        with self.assertRaises(TypeError):
            auswerten('datum_formatieren(0)')


class TestUebersetzteFehlermeldungen(unittest.TestCase):
    def test_abs_nicht_zahl(self):
        with self.assertRaisesRegex(TypeError, "'abs' erwartet eine Zahl, bekam Zeichenkette"):
            auswerten('abs("x")')

    def test_logarithmus_basis_eins(self):
        with self.assertRaisesRegex(ZeroDivisionError, "'logarithmus' ist mit Basis 1 nicht definiert"):
            auswerten('logarithmus(8, 1)')

    def test_logarithmus_nicht_zahl_nennt_das_richtige_argument(self):
        with self.assertRaisesRegex(TypeError, "'logarithmus' erwartet eine Zahl, bekam Zeichenkette"):
            auswerten('logarithmus(8, "a")')

    def test_exponential_ueberlauf(self):
        with self.assertRaisesRegex(OverflowError, "'exponential' ergibt für 1000 eine zu große Zahl"):
            auswerten('exponential(1000)')

    def test_ersetze_falsche_argumentzahl(self):
        with self.assertRaisesRegex(TypeError, "'ersetze' erwartet 2–3 Argumente"):
            auswerten('"abc".ersetze("a")')

    def test_runde_nichts(self):
        with self.assertRaisesRegex(TypeError, "'runde' erwartet eine Zahl, bekam Nichts"):
            auswerten('runde(nichts)')


if __name__ == '__main__':
    unittest.main()
