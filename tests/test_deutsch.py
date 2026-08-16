# -*- coding: utf-8 -*-
"""
Automatisierte Tests für den Deutsch-Interpreter.

Ausführen mit:
    python -m unittest discover -s tests -v
oder (falls installiert):
    pytest tests/
"""
import contextlib
import glob
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEISPIELE_ORDNER = os.path.join(PROJEKT_WURZEL, 'beispiele')


def lauf(code: str, interpreter: Interpreter = None, ladepfad: str = None):
    """Tokenisiert, parst und führt Code aus. Gibt (ergebnis, interpreter) zurück."""
    if interpreter is None:
        interpreter = Interpreter(ladepfad=ladepfad)
    tokens = Lexer(code).tokenisieren()
    baum = Parser(tokens).parse()
    ergebnis = interpreter.ausfuehren(baum)
    return ergebnis, interpreter


def ausgabe_erfassen(code: str, interpreter: Interpreter = None) -> str:
    """Führt Code aus und gibt die auf stdout gedruckte Ausgabe zurück."""
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        lauf(code, interpreter)
    return puffer.getvalue()


class TestBeispielSkripte(unittest.TestCase):
    """Smoke-Test: jede Datei in beispiele/ muss ohne Fehler durchlaufen."""

    def test_alle_beispiele_laufen_fehlerfrei(self):
        dateien = sorted(glob.glob(os.path.join(BEISPIELE_ORDNER, '*.deu')))
        self.assertGreater(len(dateien), 0, 'Keine .deu-Dateien in beispiele/ gefunden')
        for pfad in dateien:
            with self.subTest(datei=os.path.basename(pfad)):
                with open(pfad, 'r', encoding='utf-8') as f:
                    quelltext = f.read()
                with contextlib.redirect_stdout(io.StringIO()):
                    lauf(quelltext, ladepfad=BEISPIELE_ORDNER)


class TestOperatoren(unittest.TestCase):
    def test_potenz(self):
        self.assertEqual(ausgabe_erfassen('drucke(2 ** 10)'), '1024\n')
        self.assertEqual(ausgabe_erfassen('drucke(-2 ** 2)'), '-4\n')
        self.assertEqual(ausgabe_erfassen('drucke(2 ** 2 ** 3)'), '256\n')  # rechtsassoziativ

    def test_ganzzahldivision(self):
        self.assertEqual(ausgabe_erfassen('drucke(7 // 2)'), '3\n')
        self.assertEqual(ausgabe_erfassen('drucke(-7 // 2)'), '-4\n')

    def test_division_durch_null(self):
        with self.assertRaises(ZeroDivisionError):
            lauf('1 / 0')
        with self.assertRaises(ZeroDivisionError):
            lauf('1 // 0')

    def test_nicht_in(self):
        self.assertEqual(ausgabe_erfassen('drucke(5 nicht in [1,2,3])'), 'wahr\n')
        self.assertEqual(ausgabe_erfassen('drucke(2 nicht in [1,2,3])'), 'falsch\n')

    def test_operator_typfehler_deutsch(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('5 < "text"')
        self.assertIn('nicht unterstützt', str(ctx.exception))

    def test_sortiere_numerisch(self):
        ergebnis, _ = lauf('sortiere([10, 2, 33, 1])')
        self.assertEqual(ergebnis, [1, 2, 10, 33])


class TestSlicing(unittest.TestCase):
    def test_listen_slicing(self):
        self.assertEqual(ausgabe_erfassen('drucke([0,1,2,3,4][1:3])'), '[1, 2]\n')
        self.assertEqual(ausgabe_erfassen('drucke([0,1,2,3,4][::-1])'), '[4, 3, 2, 1, 0]\n')

    def test_string_slicing(self):
        self.assertEqual(ausgabe_erfassen('drucke("abcdef"[1:3])'), 'bc\n')

    def test_slice_zuweisung_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei l = [1,2,3]\nl[0:1] = [9]')


class TestLambda(unittest.TestCase):
    def test_anonyme_funktion(self):
        self.assertEqual(ausgabe_erfassen(
            'sei f = funktion(x) { zurück x * x }\ndrucke(f(5))'
        ), '25\n')

    def test_lambda_als_argument(self):
        code = '''
        funktion wende_an(f, wert) { zurück f(wert) }
        drucke(wende_an(funktion(x) { zurück x + 1 }, 10))
        '''
        self.assertEqual(ausgabe_erfassen(code), '11\n')


class TestPasse(unittest.TestCase):
    def test_mehrfachwert_und_sonst(self):
        code = '''
        funktion typ_von_tag(t) {
            passe t {
                fall "Sa", "So": { zurück "Wochenende" }
                sonst: { zurück "Werktag" }
            }
        }
        drucke(typ_von_tag("Sa"))
        drucke(typ_von_tag("Mi"))
        '''
        self.assertEqual(ausgabe_erfassen(code), 'Wochenende\nWerktag\n')

    def test_abbrechen_in_fall_propagiert_zur_schleife(self):
        code = '''
        für i in bereich(5) {
            passe i {
                fall 3: { abbrechen }
                sonst: { drucke(i) }
            }
        }
        '''
        self.assertEqual(ausgabe_erfassen(code), '0\n1\n2\n')


class TestMehrfachvererbung(unittest.TestCase):
    def test_diamant_vererbung(self):
        code = '''
        klasse Basis { funktion wer(dies) { zurück "Basis" } }
        klasse Links(Basis) { }
        klasse Rechts(Basis) { }
        klasse Unten(Links, Rechts) { }
        drucke(neu Unten().wer())
        '''
        self.assertEqual(ausgabe_erfassen(code), 'Basis\n')


class TestTypHinweise(unittest.TestCase):
    def test_korrekter_typ_geht_durch(self):
        ergebnis, _ = lauf(
            'funktion addiere(a: Ganzzahl, b: Ganzzahl) -> Ganzzahl { zurück a + b }\n'
            'addiere(2, 3)'
        )
        self.assertEqual(ergebnis, 5)

    def test_falscher_typ_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a: Ganzzahl) { zurück a }\nf("text")')

    def test_kommazahl_akzeptiert_ganzzahl(self):
        ergebnis, _ = lauf('sei n: Kommazahl = 5')
        self.assertEqual(ergebnis, 5)

    def test_unbekannter_typ_hinweis_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei x: Gannzahl = 5')

    def test_impliziter_none_return_wird_geprueft(self):
        with self.assertRaises(TypeError):
            lauf('funktion f() -> Ganzzahl { sei x = 1 }\nf()')


class TestWerfe(unittest.TestCase):
    def test_string_werfen_und_fangen(self):
        code = '''
        versuche { werfe "kaputt" } fange f { drucke(f) }
        '''
        self.assertEqual(ausgabe_erfassen(code), 'kaputt\n')

    def test_beliebigen_wert_werfen(self):
        code = '''
        versuche { werfe 42 } fange f { drucke(typ(f)) }
        '''
        self.assertEqual(ausgabe_erfassen(code), 'Ganzzahl\n')

    def test_unbehandeltes_werfe_propagiert(self):
        from deutsch.interpreter import AusnahmeFehler
        with self.assertRaises(AusnahmeFehler):
            lauf('werfe "uncaught"')


class TestMathe(unittest.TestCase):
    def test_grundfunktionen(self):
        ergebnis, _ = lauf('wurzel(16)')
        self.assertEqual(ergebnis, 4.0)

    def test_konstanten(self):
        import math
        ergebnis, _ = lauf('pi')
        self.assertAlmostEqual(ergebnis, math.pi)

    def test_wurzel_negativ_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('wurzel(-1)')


class TestDateiIO(unittest.TestCase):
    def test_schreiben_lesen_anhaengen(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('datei_schreiben("x.txt", "Hallo")', interpreter)
            lauf('datei_anhaengen("x.txt", " Welt")', interpreter)
            ergebnis, _ = lauf('datei_lesen("x.txt")', interpreter)
            self.assertEqual(ergebnis, 'Hallo Welt')

    def test_fehlende_datei_wirft_deutschen_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError) as ctx:
                lauf('datei_lesen("nicht_da.txt")', interpreter)
            self.assertIn('nicht gefunden', str(ctx.exception))


class TestFehlermeldungen(unittest.TestCase):
    def test_schluesselfehler_ohne_doppelte_anfuehrungszeichen(self):
        with self.assertRaises(KeyError) as ctx:
            lauf('sei d = {"a": 1}\nd["fehlt"]')
        self.assertNotIn('\\', str(ctx.exception))
        self.assertIn("Schlüssel 'fehlt'", str(ctx.exception))

    def test_index_typfehler_deutsch(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('sei l = [1,2,3]\nl["x"]')
        self.assertIn('Index-Typ', str(ctx.exception))

    def test_case_sensitive_schluesselwoerter(self):
        # 'Wenn' (groß) ist kein Schlüsselwort mehr, muss als Bezeichner nutzbar sein
        ergebnis, _ = lauf('sei Wenn = 5\nWenn')
        self.assertEqual(ergebnis, 5)

    def test_wissenschaftliche_notation(self):
        ergebnis, _ = lauf('1.0e10')
        self.assertEqual(ergebnis, 1.0e10)


class TestStacktrace(unittest.TestCase):
    def test_aufruf_stack_wird_gefuellt_bei_unbehandeltem_fehler(self):
        interpreter = Interpreter()
        code = '''
        funktion innen() { werfe "boom" }
        funktion aussen() { zurück innen() }
        aussen()
        '''
        with self.assertRaises(Exception):
            lauf(code, interpreter)
        self.assertEqual(len(interpreter._letzter_aufruf_stack), 2)
        # Gespeichert in Aufrufreihenfolge (äußerste zuerst) – main.py dreht für die Anzeige um
        namen = [n for n, _ in interpreter._letzter_aufruf_stack]
        self.assertEqual(namen, ['aussen', 'innen'])

    def test_leerer_stack_ohne_funktionsaufruf(self):
        interpreter = Interpreter()
        with self.assertRaises(ZeroDivisionError):
            lauf('1 / 0', interpreter)
        self.assertEqual(interpreter._letzter_aufruf_stack, [])


class TestVergleichsKette(unittest.TestCase):
    def test_verkettung_ausserhalb_des_bereichs(self):
        ergebnis, _ = lauf('sei x = 50\n1 < x < 10')
        self.assertFalse(ergebnis)

    def test_verkettung_innerhalb_des_bereichs(self):
        ergebnis, _ = lauf('1 < 5 < 10 < 20')
        self.assertTrue(ergebnis)

    def test_kurzschluss(self):
        ergebnis, _ = lauf('10 < 5 < 20')
        self.assertFalse(ergebnis)


class TestTernaerAusdruck(unittest.TestCase):
    def test_einfacher_ternaer(self):
        self.assertEqual(
            ausgabe_erfassen('drucke("erwachsen" wenn 20 >= 18 sonst "kind")'),
            'erwachsen\n'
        )

    def test_verkettung_rechtsassoziativ(self):
        ergebnis, _ = lauf('5 wenn falsch sonst 10 wenn wahr sonst 15')
        self.assertEqual(ergebnis, 10)

    def test_koexistenz_mit_listen_comprehension_filter(self):
        # Regression: das 'wenn'-Filter einer Comprehension darf nicht vom
        # Ternär-Lookahead in _ausdruck() verschluckt werden.
        ergebnis, _ = lauf('[x*x für x in [1,2,3,4] wenn x % 2 == 0]')
        self.assertEqual(ergebnis, [4, 16])

    def test_ternaer_als_comprehension_wert(self):
        ergebnis, _ = lauf('[x wenn x > 2 sonst -x für x in [1,2,3,4]]')
        self.assertEqual(ergebnis, [-1, -2, 3, 4])


class TestDestrukturierung(unittest.TestCase):
    def test_einfache_destrukturierung(self):
        _, interpreter = lauf('sei [a, b, c] = [1, 2, 3]')
        self.assertEqual(interpreter.global_umgebung.hole('a'), 1)
        self.assertEqual(interpreter.global_umgebung.hole('b'), 2)
        self.assertEqual(interpreter.global_umgebung.hole('c'), 3)

    def test_falsche_anzahl_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei [p, q] = [1, 2, 3]')


class TestFormatSpec(unittest.TestCase):
    def test_nachkommastellen(self):
        self.assertEqual(
            ausgabe_erfassen('drucke("Pi = {3.14159265:.2f}")'),
            'Pi = 3.14\n'
        )

    def test_slice_in_interpolation_kollidiert_nicht_mit_format_spec(self):
        # Regression: der ':' in einem Slice-Ausdruck darf nicht als
        # Format-Spec-Trenner missverstanden werden.
        self.assertEqual(
            ausgabe_erfassen('drucke("{[1,2,3,4,5][1:3]}")'),
            '[2, 3]\n'
        )

    def test_ungueltiges_format_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('sei text = "abc"\n"{text:d}"')


class TestMengen(unittest.TestCase):
    def test_mengen_literal_und_operationen(self):
        ergebnis, _ = lauf('{1,2,3}.vereinigung({2,3,4})')
        self.assertEqual(ergebnis, {1, 2, 3, 4})
        ergebnis, _ = lauf('{1,2,3}.schnittmenge({2,3,4})')
        self.assertEqual(ergebnis, {2, 3})
        ergebnis, _ = lauf('{1,2,3}.differenz({2,3,4})')
        self.assertEqual(ergebnis, {1})

    def test_leere_geschweifte_klammern_sind_woerterbuch(self):
        ergebnis, _ = lauf('{}')
        self.assertEqual(ergebnis, {})
        self.assertIsInstance(ergebnis, dict)

    def test_menge_builtin_dedupliziert(self):
        ergebnis, _ = lauf('menge([1,1,2,2,3])')
        self.assertEqual(ergebnis, {1, 2, 3})

    def test_unhashbares_element_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('{[1,2], 3}')

    def test_vereinigung_mit_nicht_menge_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('{1,2}.vereinigung([1,2])')

    def test_typ_hinweis_menge(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(s: Menge) { zurück s }\nf([1,2])')


class TestDiagnostik(unittest.TestCase):
    def test_tippfehler_schlaegt_aehnlichen_namen_vor(self):
        with self.assertRaises(NameError) as ctx:
            lauf('sei zaehler = 5\nzahler')
        self.assertIn("meintest du 'zaehler'", str(ctx.exception))

    def test_voellig_unbekannter_name_ohne_vorschlag(self):
        with self.assertRaises(NameError) as ctx:
            lauf('voelligUnbekannterXyzName123')
        self.assertNotIn('meintest du', str(ctx.exception))


class TestZufall(unittest.TestCase):
    def test_zufall_im_bereich(self):
        ergebnis, _ = lauf('zufall()')
        self.assertGreaterEqual(ergebnis, 0)
        self.assertLess(ergebnis, 1)

    def test_zufallszahl_einzelwert(self):
        ergebnis, _ = lauf('zufallszahl(5, 5)')
        self.assertEqual(ergebnis, 5)

    def test_zufallszahl_lo_groesser_hi_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('zufallszahl(10, 1)')

    def test_mische_behaelt_alle_elemente(self):
        _, interpreter = lauf('sei l = [1,2,3,4,5]\nmische(l)')
        self.assertEqual(sorted(interpreter.global_umgebung.hole('l')), [1, 2, 3, 4, 5])


class TestFunktionaleHelfer(unittest.TestCase):
    def test_summe(self):
        ergebnis, _ = lauf('summe([1,2,3,4])')
        self.assertEqual(ergebnis, 10)
        ergebnis, _ = lauf('summe(1,2,3)')
        self.assertEqual(ergebnis, 6)

    def test_alle_und_einige(self):
        self.assertTrue(lauf('alle([wahr, wahr])')[0])
        self.assertFalse(lauf('alle([wahr, falsch])')[0])
        self.assertTrue(lauf('einige([falsch, wahr])')[0])
        self.assertFalse(lauf('einige([falsch, falsch])')[0])

    def test_aufzaehlen(self):
        ergebnis, _ = lauf('aufzaehlen(["a","b"])')
        self.assertEqual(ergebnis, [[0, 'a'], [1, 'b']])

    def test_zippe(self):
        ergebnis, _ = lauf('zippe([1,2,3], ["a","b","c"])')
        self.assertEqual(ergebnis, [[1, 'a'], [2, 'b'], [3, 'c']])

    def test_zippe_mit_menge_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('zippe({1,2}, [3,4])')


class TestBodenDecke(unittest.TestCase):
    def test_boden_und_decke(self):
        self.assertEqual(lauf('boden(3.7)')[0], 3)
        self.assertEqual(lauf('decke(3.2)')[0], 4)


class TestJson(unittest.TestCase):
    def test_schreiben_und_lesen_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('json_schreiben("d.json", {"name": "Anna", "zahlen": [1,2,3]})', interpreter)
            ergebnis, _ = lauf('json_lesen("d.json")', interpreter)
            self.assertEqual(ergebnis, {'name': 'Anna', 'zahlen': [1, 2, 3]})

    def test_menge_wird_zu_sortierter_liste_konvertiert(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('json_schreiben("m.json", {"werte": {3,1,2}})', interpreter)
            ergebnis, _ = lauf('json_lesen("m.json")', interpreter)
            self.assertEqual(ergebnis, {'werte': [1, 2, 3]})

    def test_ungueltiges_json_wirft_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'kaputt.json'), 'w', encoding='utf-8') as f:
                f.write('{nicht gueltig')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ValueError):
                lauf('json_lesen("kaputt.json")', interpreter)


class TestKommandozeilenArgumente(unittest.TestCase):
    def test_argumente_werden_durchgereicht(self):
        interpreter = Interpreter(argumente=['eins', 'zwei'])
        ergebnis, _ = lauf('kommandozeilen_argumente()', interpreter)
        self.assertEqual(ergebnis, ['eins', 'zwei'])

    def test_keine_argumente_ist_leere_liste(self):
        ergebnis, _ = lauf('kommandozeilen_argumente()')
        self.assertEqual(ergebnis, [])


class TestRegex(unittest.TestCase):
    def test_passt_zu(self):
        self.assertTrue(lauf(r'passt_zu("^\d+$", "12345")')[0])
        self.assertFalse(lauf(r'passt_zu("^\d+$", "abc")')[0])

    def test_regex_ersetze(self):
        ergebnis, _ = lauf(r'regex_ersetze("\s+", " ", "hallo    welt")')
        self.assertEqual(ergebnis, 'hallo welt')

    def test_regex_finde(self):
        ergebnis, _ = lauf(r'regex_finde("\d+", "abc123def")')
        self.assertEqual(ergebnis, '123')
        ergebnis, _ = lauf(r'regex_finde("\d+", "keine zahlen")')
        self.assertIsNone(ergebnis)

    def test_regex_finde_alle(self):
        ergebnis, _ = lauf(r'regex_finde_alle("\d+", "a1b22c333")')
        self.assertEqual(ergebnis, ['1', '22', '333'])

    def test_ungueltiges_muster_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('passt_zu("[", "x")')


class TestDatumZeit(unittest.TestCase):
    def test_jetzt_ist_positiv(self):
        ergebnis, _ = lauf('jetzt()')
        self.assertGreater(ergebnis, 0)

    def test_datum_formatieren(self):
        ergebnis, _ = lauf('datum_formatieren(0, "%Y")')
        self.assertEqual(ergebnis, '1970')

    def test_ungueltiger_zeitstempel_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('datum_formatieren("keine_zahl", "%Y")')


class TestIndexUndZaehlen(unittest.TestCase):
    def test_liste_index_von_und_zaehle(self):
        ergebnis, _ = lauf('[1,2,3,2,1].index_von(3)')
        self.assertEqual(ergebnis, 2)
        ergebnis, _ = lauf('[1,2,3,2,1].zaehle(1)')
        self.assertEqual(ergebnis, 2)

    def test_liste_index_von_nicht_gefunden_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('[1,2,3].index_von(99)')

    def test_string_index_von_und_zaehle(self):
        ergebnis, _ = lauf('"hallo welt hallo".index_von("welt")')
        self.assertEqual(ergebnis, 6)
        ergebnis, _ = lauf('"hallo welt hallo".zaehle("hallo")')
        self.assertEqual(ergebnis, 2)

    def test_string_index_von_nicht_gefunden_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('"abc".index_von("xyz")')

    def test_string_index_von_falscher_typ_wirft_deutschen_fehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('"abc".index_von(5)')
        self.assertNotIn('must be str', str(ctx.exception))

    def test_string_zaehle_falscher_typ_wirft_deutschen_fehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('"abc".zaehle(5)')
        self.assertNotIn('must be str', str(ctx.exception))


class TestStatistik(unittest.TestCase):
    def test_mittelwert_median(self):
        self.assertEqual(lauf('mittelwert([1,2,3,4,5])')[0], 3)
        self.assertEqual(lauf('median([1,2,3,4,5])')[0], 3)

    def test_stdabweichung(self):
        ergebnis, _ = lauf('stdabweichung([2,4,4,4,5,5,7,9])')
        self.assertAlmostEqual(ergebnis, 2.0)

    def test_leere_liste_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('mittelwert([])')
        with self.assertRaises(ValueError):
            lauf('median([])')
        with self.assertRaises(ValueError):
            lauf('stdabweichung([])')


class TestTiefeKopie(unittest.TestCase):
    def test_verschachtelte_strukturen_werden_unabhaengig(self):
        code = '''
        sei original = {"zahlen": [1,2,3], "verschachtelt": {"a": [1,2]}}
        sei kopie = tiefe_kopie(original)
        kopie["zahlen"].anhaengen(99)
        kopie["verschachtelt"]["a"].anhaengen(99)
        '''
        _, interpreter = lauf(code)
        original = interpreter.global_umgebung.hole('original')
        kopie = interpreter.global_umgebung.hole('kopie')
        self.assertEqual(original['zahlen'], [1, 2, 3])
        self.assertEqual(kopie['zahlen'], [1, 2, 3, 99])
        self.assertEqual(original['verschachtelt']['a'], [1, 2])
        self.assertEqual(kopie['verschachtelt']['a'], [1, 2, 99])


class TestUmgebungsvariable(unittest.TestCase):
    def test_fehlend_ohne_standard_ist_nichts(self):
        ergebnis, _ = lauf('umgebungsvariable("GARANTIERT_NICHT_GESETZT_XYZ")')
        self.assertIsNone(ergebnis)

    def test_fehlend_mit_standard(self):
        ergebnis, _ = lauf('umgebungsvariable("GARANTIERT_NICHT_GESETZT_XYZ", "standard")')
        self.assertEqual(ergebnis, 'standard')


class TestDateisystemHelfer(unittest.TestCase):
    def test_pfad_existiert(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            self.assertTrue(lauf('pfad_existiert(".")', interpreter)[0])
            self.assertFalse(lauf('pfad_existiert("nicht_da_xyz")', interpreter)[0])

    def test_ordner_erstellen_und_dateien_auflisten(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('ordner_erstellen("neu")', interpreter)
            lauf('datei_schreiben("neu/a.txt", "x")', interpreter)
            ergebnis, _ = lauf('dateien_auflisten("neu")', interpreter)
            self.assertEqual(ergebnis, ['a.txt'])

    def test_dateien_auflisten_fehlender_ordner_wirft_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(FileNotFoundError):
                lauf('dateien_auflisten("nicht_da_xyz")', interpreter)

    def test_ordner_erstellen_auf_existierender_datei_wirft_deutschen_fehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            interpreter = Interpreter(ladepfad=tmp)
            lauf('datei_schreiben("x.txt", "a")', interpreter)
            with self.assertRaises(FileExistsError) as ctx:
                lauf('ordner_erstellen("x.txt")', interpreter)
            self.assertIn('existiert bereits als Datei', str(ctx.exception))


class TestHashingKodierung(unittest.TestCase):
    def test_hash_sha256_laenge(self):
        ergebnis, _ = lauf('hash_sha256("hallo")')
        self.assertEqual(len(ergebnis), 64)

    def test_base64_roundtrip_mit_umlauten(self):
        code = 'sei k = base64_kodieren("Hallo Welt äöü")\nbase64_dekodieren(k)'
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, 'Hallo Welt äöü')

    def test_ungueltiges_base64_wirft_fehler(self):
        with self.assertRaises(ValueError):
            lauf('base64_dekodieren("!!!nicht_gueltig!!!")')


if __name__ == '__main__':
    unittest.main()
