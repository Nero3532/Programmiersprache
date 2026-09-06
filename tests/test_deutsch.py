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


class TestEingebauteMethodenArity(unittest.TestCase):
    """Falsche Argumentanzahl bei eingebauten Instanzmethoden muss eine deutsche
    Meldung liefern statt Pythons '<lambda>() missing 1 required positional argument'."""

    def _meldung(self, code: str) -> str:
        with self.assertRaises(TypeError) as ctx:
            lauf(code)
        text = str(ctx.exception)
        self.assertNotIn('lambda', text)
        self.assertNotIn('positional argument', text)
        self.assertNotIn('Interpreter.', text)
        return text

    def test_zu_wenige_argumente(self):
        self.assertIn("'Liste.einfuegen' erwartet 2 Argument(e), bekam 1",
                      self._meldung('[1,2].einfuegen(0)'))

    def test_zu_viele_argumente(self):
        self.assertIn("'Liste.laenge' erwartet 0 Argument(e), bekam 1",
                      self._meldung('[1].laenge(9)'))

    def test_optionale_argumente_als_bereich(self):
        self.assertIn("'Wörterbuch.hole' erwartet 1–2 Argument(e), bekam 3",
                      self._meldung('{"a": 1}.hole("a", 2, 3)'))

    def test_zeichenkette_und_menge(self):
        self.assertIn("'Zeichenkette.ersetze' erwartet 2", self._meldung('"ab".ersetze("a")'))
        self.assertIn("'Menge.vereinigung' erwartet 1", self._meldung('{1}.vereinigung()'))

    def test_optionale_argumente_funktionieren_weiter(self):
        self.assertEqual(lauf('"a,b".teile(",")')[0], ['a', 'b'])
        self.assertEqual(lauf('"a b".teile()')[0], ['a', 'b'])
        self.assertEqual(lauf('{"a": 1}.hole("a")')[0], 1)
        self.assertEqual(lauf('{"a": 1}.hole("z", "ersatz")')[0], 'ersatz')
        self.assertEqual(lauf('sei l = [1,2,3]; l.entferne()')[0], 3)
        self.assertEqual(lauf('sei l = [1,2,3]; l.entferne(0)')[0], 1)


class TestKeineRohenPythonMeldungen(unittest.TestCase):
    """Laufzeitfehler dürfen keine englischen Python-Originalmeldungen durchreichen."""

    ROH = ('object ', 'must be', 'not iterable', 'could not convert', 'invalid literal',
           'unsupported operand', 'division by zero', 'unhashable', 'Errno', 'lambda')

    def _pruefe(self, code: str, erwartet: str):
        with self.assertRaises(Exception) as ctx:
            lauf(code)
        text = str(ctx.exception)
        for roh in self.ROH:
            self.assertNotIn(roh, text, f'Rohe Python-Meldung in {code!r}: {text}')
        self.assertIn(erwartet, text)

    def test_unaeres_minus_auf_zeichenkette(self):
        self._pruefe('-"a"', "Operator '-' nicht unterstützt für Zeichenkette")

    def test_modulo_durch_null(self):
        self._pruefe('5 % 0', 'Modulo durch Null')

    def test_null_hoch_negativ(self):
        self._pruefe('0 ** (0-1)', 'negativem Exponenten')

    def test_slice_schrittweite_null(self):
        self._pruefe('[1,2][::0]', 'Slice-Schrittweite darf nicht 0 sein')

    def test_unhashbarer_woerterbuch_schluessel(self):
        self._pruefe('sei d = {[1]: 2}', 'hashbar')

    def test_nicht_iterierbar_in_schleife(self):
        self._pruefe('für x in 5 { }', 'Iterierbares')

    def test_nicht_iterierbar_in_comprehension(self):
        self._pruefe('[x für x in 5]', 'Iterierbares')

    def test_zahl_aus_ungueltiger_zeichenkette(self):
        self._pruefe('"5x".zahl()', "Kann '5x' nicht in eine Zahl umwandeln")

    def test_lade_datei_fehlt(self):
        self._pruefe('lade "gibt_es_wirklich_nicht.deu"', 'Datei zum Laden nicht gefunden')

    def test_zahl_argumente_werden_geprueft(self):
        self._pruefe('abs("a")', "'abs' erwartet eine Zahl")
        self._pruefe('runde("a")', "'runde' erwartet eine Zahl")
        self._pruefe('bereich("a")', "'bereich' erwartet eine Ganzzahl")
        self._pruefe('"a".wiederhole("x")', "'wiederhole' erwartet eine Ganzzahl")

    def test_entferne_auf_leerer_liste(self):
        self._pruefe('entferne([])', 'leeren Liste')

    def test_max_mit_gemischten_typen(self):
        self._pruefe('max([1, "a"])', 'gemischter Typen')

    def test_zeichenkette_ist_unveraenderlich(self):
        self._pruefe('sei s = "abc"; s[0] = "x"', 'unveränderlich')


class TestZeilennummernBeiMehrzeiligenStrings(unittest.TestCase):
    """Zeilenumbrüche in dreifach gequoteten Zeichenketten wurden doppelt gezählt,
    wodurch alle folgenden Fehlermeldungen auf eine zu hohe Zeile zeigten."""

    def test_fehlerzeile_nach_mehrzeiligem_string(self):
        code = '''sei t = """Zeile A
Zeile B
Zeile C"""
sei x = nicht_existent'''
        with self.assertRaises(NameError) as ctx:
            lauf(code)
        self.assertIn('Zeile 4', str(ctx.exception))

    def test_mehrere_strings_verschieben_sich_nicht_kumulativ(self):
        code = '''sei a = """1
2"""
sei b = """3
4"""
sei c = nicht_existent'''
        with self.assertRaises(NameError) as ctx:
            lauf(code)
        self.assertIn('Zeile 5', str(ctx.exception))

    def test_fehlerzeile_nach_mehrzeiliger_interpolation(self):
        code = '''sei n = 1
sei t = """Wert: {n}
zweite Zeile"""
sei x = nicht_existent'''
        with self.assertRaises(NameError) as ctx:
            lauf(code)
        self.assertIn('Zeile 4', str(ctx.exception))

    def test_stringinhalt_bleibt_unveraendert(self):
        code = '''sei t = """A
B"""
laenge(t)'''
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, 3)   # 'A' + Zeilenumbruch + 'B'


class TestMaxMinMitMengen(unittest.TestCase):
    def test_max_und_min_auf_menge(self):
        self.assertEqual(lauf('max({3, 1, 2})')[0], 3)
        self.assertEqual(lauf('min({3, 1, 2})')[0], 1)

    def test_liste_und_variadische_form_unveraendert(self):
        self.assertEqual(lauf('max([3, 1, 2])')[0], 3)
        self.assertEqual(lauf('min(3, 1, 2)')[0], 1)

    def test_leere_menge_wirft_wertfehler(self):
        with self.assertRaises(ValueError):
            lauf('max(menge())')


class TestRundenMitNegativenStellen(unittest.TestCase):
    def test_negative_stellen_runden_auf_zehner_und_hunderter(self):
        self.assertEqual(lauf('runde(1234, -2)')[0], 1200)
        self.assertEqual(lauf('runde(1678, -3)')[0], 2000)
        self.assertEqual(lauf('runde(1234.5, -2)')[0], 1200)

    def test_ergebnis_ist_ganzzahl_bei_stellen_kleiner_gleich_null(self):
        self.assertEqual(lauf('typ(runde(1234.5, -2))')[0], 'Ganzzahl')
        self.assertEqual(lauf('typ(runde(3.7))')[0], 'Ganzzahl')

    def test_positive_und_null_stellen_unveraendert(self):
        self.assertEqual(lauf('runde(3.7)')[0], 4)
        self.assertEqual(lauf('runde(3.14159, 2)')[0], 3.14)
        self.assertEqual(lauf('runde(3.7, 0)')[0], 4)


class TestAnonymeFunktionenInFehlermeldungen(unittest.TestCase):
    """Anonyme Funktionen erschienen in Argument-Fehlern als 'None'."""

    ANON = 'sei f = funktion(x) { zurück x }; '

    def _meldung(self, code: str) -> str:
        with self.assertRaises(TypeError) as ctx:
            lauf(code)
        text = str(ctx.exception)
        self.assertNotIn("'None'", text)
        return text

    def test_fehlendes_pflichtargument(self):
        self.assertIn('<anonym>', self._meldung(self.ANON + 'f()'))

    def test_unbekanntes_keyword_argument(self):
        self.assertIn('<anonym>', self._meldung(self.ANON + 'f(a=1)'))

    def test_mehrfacher_wert_fuer_parameter(self):
        self.assertIn('<anonym>', self._meldung(self.ANON + 'f(1, x=2)'))

    def test_zu_viele_argumente(self):
        self.assertIn('<anonym>', self._meldung(self.ANON + 'f(1, 2)'))

    def test_benannte_funktion_behaelt_ihren_namen(self):
        self.assertIn("'g'", self._meldung('funktion g(a) { zurück a }; g()'))


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
        # Falscher Typ -> TypeError (wie bei 'wurzel'/'boden'), deutsche Meldung
        with self.assertRaises(TypeError) as ctx:
            lauf('datum_formatieren("keine_zahl", "%Y")')
        self.assertIn('erwartet eine Zahl', str(ctx.exception))
        self.assertIn('Zeichenkette', str(ctx.exception))

    def test_zeitstempel_ausserhalb_des_bereichs_wirft_wertfehler(self):
        with self.assertRaises(ValueError) as ctx:
            lauf('datum_formatieren(1e30, "%Y")')
        self.assertIn('Ungültiger Zeitstempel', str(ctx.exception))


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


class TestSchleifenDestrukturierung(unittest.TestCase):
    def test_fuer_schleife(self):
        code = '''
        sei ausgabe = []
        für [i, wert] in aufzaehlen(["a","b"]) {
            ausgabe.anhaengen([i, wert])
        }
        ausgabe
        '''
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, [[0, 'a'], [1, 'b']])

    def test_listen_comprehension(self):
        ergebnis, _ = lauf('[x*y für [x, y] in zippe([1,2,3], [10,20,30])]')
        self.assertEqual(ergebnis, [10, 40, 90])

    def test_normale_fuer_schleife_weiterhin_ok(self):
        ergebnis, _ = lauf('sei s = 0\nfür x in [1,2,3] { s += x }\ns')
        self.assertEqual(ergebnis, 6)

    def test_falsche_anzahl_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('für [a, b] in [[1,2,3]] { a }')

    def test_woerterbuch_paare_destrukturierung(self):
        code = '''
        sei d = {"a": 1, "b": 2}
        sei ausgabe = []
        für [schluessel, wert] in d.paare() {
            ausgabe.anhaengen(schluessel)
        }
        sortiere(ausgabe)
        '''
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, ['a', 'b'])

    def test_woerterbuch_direkt_destrukturieren_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei d = {"a": 1}\nfür [k, v] in d { k }')


class TestKeywordArgumente(unittest.TestCase):
    def test_reine_keyword_argumente(self):
        code = 'funktion f(a, b) { zurück a + b }\nf(a=1, b=2)'
        self.assertEqual(lauf(code)[0], 3)

    def test_gemischt_positional_und_keyword(self):
        code = 'funktion f(a, b, c=10) { zurück a + b + c }\nf(1, c=100, b=2)'
        self.assertEqual(lauf(code)[0], 103)

    def test_neu_instanz_mit_keyword_argumenten(self):
        code = '''
        klasse Punkt {
            funktion __init__(dies, x, y=0) { dies.x = x; dies.y = y }
        }
        neu Punkt(x=5, y=9).y
        '''
        self.assertEqual(lauf(code)[0], 9)

    def test_unbekanntes_keyword_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a) { zurück a }\nf(b=1)')

    def test_doppelter_wert_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a) { zurück a }\nf(1, a=2)')

    def test_fehlendes_pflichtargument_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(a, b) { zurück a }\nf(a=1)')

    def test_keyword_auf_variadic_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('funktion f(*a) { zurück a }\nf(a=[1,2])')

    def test_positional_nach_keyword_ist_syntaxfehler(self):
        with self.assertRaises(SyntaxError):
            lauf('funktion f(a, b) { zurück a }\nf(a=1, 2)')

    def test_doppeltes_keyword_ist_syntaxfehler(self):
        with self.assertRaises(SyntaxError):
            lauf('funktion f(a) { zurück a }\nf(a=1, a=2)')


class TestZyklischesLaden(unittest.TestCase):
    def test_zyklus_wird_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'a.deu'), 'w', encoding='utf-8') as f:
                f.write('lade "b.deu"\n')
            with open(os.path.join(tmp, 'b.deu'), 'w', encoding='utf-8') as f:
                f.write('lade "a.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ImportError):
                lauf('lade "a.deu"', interpreter)

    def test_wiederholtes_nicht_zyklisches_laden_funktioniert(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'c.deu'), 'w', encoding='utf-8') as f:
                f.write('funktion h() { zurück 42 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "c.deu"', interpreter)
            ergebnis, _ = lauf('lade "c.deu"\nh()', interpreter)
            self.assertEqual(ergebnis, 42)

    def test_direkte_selbstreferenz_wird_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'self.deu'), 'w', encoding='utf-8') as f:
                f.write('lade "self.deu"\n')
            interpreter = Interpreter(ladepfad=tmp)
            with self.assertRaises(ImportError):
                lauf('lade "self.deu"', interpreter)


class TestOperatorUeberladung(unittest.TestCase):
    def test_addiere_ueberladung(self):
        code = '''
        klasse Vektor {
            funktion __init__(dies, x, y) { dies.x = x; dies.y = y }
            funktion __addiere__(dies, andere) { zurück neu Vektor(dies.x + andere.x, dies.y + andere.y) }
        }
        sei ergebnis = neu Vektor(1,2) + neu Vektor(3,4)
        [ergebnis.x, ergebnis.y]
        '''
        self.assertEqual(lauf(code)[0], [4, 6])

    def test_gleich_ueberladung(self):
        code = '''
        klasse Punkt {
            funktion __init__(dies, x) { dies.x = x }
            funktion __gleich__(dies, andere) { zurück dies.x == andere.x }
        }
        neu Punkt(5) == neu Punkt(5)
        '''
        self.assertTrue(lauf(code)[0])

    def test_ohne_ueberladung_normaler_fehler(self):
        code = '''
        klasse A { funktion __init__(dies) { } }
        neu A() - neu A()
        '''
        with self.assertRaises(TypeError):
            lauf(code)

    def test_verbund_zuweisung_nutzt_ueberladung(self):
        code = '''
        klasse Vektor {
            funktion __init__(dies, x) { dies.x = x }
            funktion __addiere__(dies, andere) { zurück neu Vektor(dies.x + andere.x) }
        }
        sei v = neu Vektor(5)
        v += neu Vektor(3)
        v.x
        '''
        self.assertEqual(lauf(code)[0], 8)

    def test_normale_zahlen_unveraendert(self):
        self.assertEqual(lauf('5 + 3')[0], 8)


class TestMengenVergleiche(unittest.TestCase):
    def test_teilmenge_und_obermenge(self):
        self.assertTrue(lauf('{1,2}.teilmenge_von({1,2,3})')[0])
        self.assertFalse(lauf('{1,2,3}.teilmenge_von({1,2})')[0])
        self.assertTrue(lauf('{1,2,3}.obermenge_von({1,2})')[0])

    def test_symmetrische_differenz(self):
        ergebnis, _ = lauf('{1,2,3}.symmetrische_differenz({2,3,4})')
        self.assertEqual(ergebnis, {1, 4})


class TestListeErweitern(unittest.TestCase):
    def test_einfuegen(self):
        _, interpreter = lauf('sei l = [1,2,3]\nl.einfuegen(1, 99)')
        self.assertEqual(interpreter.global_umgebung.hole('l'), [1, 99, 2, 3])

    def test_erweitere(self):
        _, interpreter = lauf('sei l = [1,2]\nl.erweitere([3,4])')
        self.assertEqual(interpreter.global_umgebung.hole('l'), [1, 2, 3, 4])

    def test_erweitere_falscher_typ_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('sei l = [1,2]\nl.erweitere("abc")')


class TestMatheUtilities(unittest.TestCase):
    def test_ggt_kgv(self):
        self.assertEqual(lauf('ggt(12, 18)')[0], 6)
        self.assertEqual(lauf('ggt([12, 18, 24])')[0], 6)
        self.assertEqual(lauf('kgv(4, 6)')[0], 12)

    def test_vorzeichen(self):
        self.assertEqual(lauf('vorzeichen(-5)')[0], -1)
        self.assertEqual(lauf('vorzeichen(0)')[0], 0)
        self.assertEqual(lauf('vorzeichen(3.5)')[0], 1)


class TestStringPraedikate(unittest.TestCase):
    def test_praedikate(self):
        self.assertTrue(lauf('"123".ist_ziffer()')[0])
        self.assertFalse(lauf('"abc".ist_ziffer()')[0])
        self.assertTrue(lauf('"abc".ist_buchstabe()')[0])
        self.assertTrue(lauf('"   ".ist_leerraum()')[0])


class TestPruefeAnweisung(unittest.TestCase):
    def test_erfolgreiche_pruefung_gibt_keinen_fehler(self):
        lauf('pruefe wahr')
        lauf('pruefe 1 + 1 == 2, "sollte nicht passieren"')

    def test_fehlgeschlagene_pruefung_mit_meldung(self):
        with self.assertRaises(AssertionError) as ctx:
            lauf('pruefe falsch, "eigene Meldung"')
        self.assertIn('eigene Meldung', str(ctx.exception))

    def test_fehlgeschlagene_pruefung_ohne_meldung(self):
        with self.assertRaises(AssertionError) as ctx:
            lauf('pruefe 1 == 2')
        self.assertIn('fehlgeschlagen', str(ctx.exception))


class TestKonstanten(unittest.TestCase):
    def test_lesen(self):
        self.assertEqual(lauf('konstante PI = 3.14\nPI')[0], 3.14)

    def test_neuzuweisung_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('konstante x = 1\nx = 2')

    def test_verbund_zuweisung_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('konstante x = 1\nx += 1')

    def test_redeklaration_im_selben_scope_wirft_fehler(self):
        with self.assertRaises(TypeError):
            lauf('konstante x = 1\nkonstante x = 2')

    def test_verschachtelter_scope_schattet_korrekt(self):
        code = '''
        konstante x = 1
        funktion f() {
            konstante x = 2
            zurück x
        }
        [f(), x]
        '''
        self.assertEqual(lauf(code)[0], [2, 1])

    def test_sei_bleibt_unveraendert(self):
        self.assertEqual(lauf('sei x = 1\nx = 2\nx')[0], 2)


class TestTypisiertesFangen(unittest.TestCase):
    def test_nicht_passender_typ_propagiert(self):
        with self.assertRaises(ZeroDivisionError):
            lauf('versuche { 1/0 } fange (TypeError) f { f }')

    def test_passender_typ_faengt(self):
        ergebnis, _ = lauf('versuche { 1/0 } fange (ZeroDivisionError, TypeError) f { f }\n')
        # kein Fehler mehr -> Skript laeuft durch

    def test_endlich_laeuft_auch_bei_nicht_passendem_typ(self):
        code = '''
        sei lief = falsch
        versuche {
            versuche { 1/0 } fange (TypeError) f { f } endlich { lief = wahr }
        } fange g { g }
        lief
        '''
        self.assertTrue(lauf(code)[0])

    def test_basisklasse_faengt_abgeleiteten_fehler(self):
        code = '''
        sei d = {"a": 1}
        versuche { d["fehlt"] } fange (KeyError) f { f }
        '''
        lauf(code)  # darf nicht werfen

    def test_ausnahmefehler_nach_name_fangbar(self):
        code = 'sei erfasst = nichts\nversuche { werfe 42 } fange (AusnahmeFehler) f { erfasst = f }\nerfasst'
        ergebnis, _ = lauf(code)
        self.assertEqual(ergebnis, 42)


class TestLadeAls(unittest.TestCase):
    def test_namensraum_bindungen(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('funktion addiere(a, b) { zurück a + b }\nkonstante VERSION = "1.0"\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "mod.deu" als m\nm.addiere(3, 4)', interpreter)
            self.assertEqual(ergebnis, 7)
            ergebnis, _ = lauf('m.VERSION', interpreter)
            self.assertEqual(ergebnis, '1.0')

    def test_bindungen_landen_nicht_im_globalen_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('sei geheim = 1\n')
            interpreter = Interpreter(ladepfad=tmp)
            lauf('lade "mod.deu" als m', interpreter)
            with self.assertRaises(NameError):
                lauf('geheim', interpreter)

    def test_ohne_als_weiterhin_global(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
                f.write('funktion h() { zurück 1 }\n')
            interpreter = Interpreter(ladepfad=tmp)
            ergebnis, _ = lauf('lade "mod.deu"\nh()', interpreter)
            self.assertEqual(ergebnis, 1)


class TestStatischeKlassenmitglieder(unittest.TestCase):
    def test_geteiltes_klassenattribut(self):
        code = '''
        klasse Zaehler {
            sei anzahl = 0
            funktion __init__(dies) { Zaehler.anzahl += 1 }
        }
        neu Zaehler(); neu Zaehler(); neu Zaehler()
        Zaehler.anzahl
        '''
        self.assertEqual(lauf(code)[0], 3)

    def test_statische_methode_ueber_klasse_und_instanz(self):
        code = '''
        klasse K {
            statisch funktion hallo() { zurück "hi" }
        }
        [K.hallo(), neu K().hallo()]
        '''
        self.assertEqual(lauf(code)[0], ['hi', 'hi'])

    def test_klassenkonstante_schutz(self):
        with self.assertRaises(TypeError):
            lauf('klasse K { konstante MAX = 5 }\nK.MAX = 1')

    def test_vererbung_von_statischem_attribut_und_methode(self):
        code = '''
        klasse Basis {
            sei geteilt = "x"
            statisch funktion hallo() { zurück "hi" }
        }
        klasse Kind(Basis) { }
        [Kind.geteilt, Kind.hallo()]
        '''
        self.assertEqual(lauf(code)[0], ['x', 'hi'])

    def test_unbekanntes_klassenattribut_wirft_fehler(self):
        with self.assertRaises(AttributeError):
            lauf('klasse K { }\nK.unbekannt')


class TestKlassenkoerperSyntax(unittest.TestCase):
    """Unerwartete Token im Klassenkörper wurden still übersprungen – ein Tippfehler
    verschwand dadurch spurlos statt gemeldet zu werden."""

    def test_unerwartetes_token_wirft_syntaxfehler(self):
        with self.assertRaises(SyntaxError) as ctx:
            lauf('klasse A { tippfehler }')
        meldung = str(ctx.exception)
        self.assertIn("Klasse 'A'", meldung)
        self.assertIn('Zeile 1', meldung)

    def test_zeile_des_fehlers_wird_gemeldet(self):
        code = '''klasse A {
    funktion f(dies) { zurück 1 }
    kaputt kaputt
}'''
        with self.assertRaises(SyntaxError) as ctx:
            lauf(code)
        self.assertIn('Zeile 3', str(ctx.exception))

    def test_erlaubte_elemente_funktionieren_weiter(self):
        code = '''klasse A {
    sei zaehler = 0
    konstante MAX = 5
    funktion __init__(dies) { dies.x = 1 }
    statisch funktion hilf() { zurück "ok" }
}
sei a = neu A()
[a.x, A.zaehler, A.MAX, A.hilf()]'''
        self.assertEqual(lauf(code)[0], [1, 0, 5, 'ok'])


class TestNeuMitNamensraum(unittest.TestCase):
    """'neu modul.Klasse(...)' war bisher ein Syntaxfehler."""

    MODUL = 'klasse Punkt { funktion __init__(dies, x) { dies.x = x } }\nsei KONST = 42\n'

    def _interpreter(self, tmp):
        with open(os.path.join(tmp, 'mod.deu'), 'w', encoding='utf-8') as f:
            f.write(self.MODUL)
        return Interpreter(ladepfad=tmp)

    def test_klasse_aus_namensraum_instanziieren(self):
        with tempfile.TemporaryDirectory() as tmp:
            ergebnis, _ = lauf('lade "mod.deu" als m\nsei p = neu m.Punkt(7)\np.x',
                               self._interpreter(tmp))
            self.assertEqual(ergebnis, 7)

    def test_keyword_argument_und_verkettung(self):
        with tempfile.TemporaryDirectory() as tmp:
            ergebnis, _ = lauf('lade "mod.deu" als m\nneu m.Punkt(x=3).x',
                               self._interpreter(tmp))
            self.assertEqual(ergebnis, 3)

    def test_unbekanntes_attribut_im_namensraum(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AttributeError):
                lauf('lade "mod.deu" als m\nneu m.Fehlt()', self._interpreter(tmp))

    def test_namensraum_wert_der_keine_klasse_ist(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TypeError) as ctx:
                lauf('lade "mod.deu" als m\nneu m.KONST()', self._interpreter(tmp))
            self.assertIn("'m.KONST' ist keine Klasse", str(ctx.exception))

    def test_lokale_klasse_unveraendert(self):
        code = 'klasse A { funktion __init__(dies) { dies.n = 5 } }\nneu A().n'
        self.assertEqual(lauf(code)[0], 5)

    def test_unbekannte_klasse_meldet_namensfehler(self):
        with self.assertRaises(NameError):
            lauf('neu Gibtsnicht()')


class TestZuweisungOhneDeklaration(unittest.TestCase):
    """Zuweisung an einen unbekannten Namen legte still eine neue Variable an;
    die Fehlermeldung in Umgebung.weise_zu war dadurch unerreichbar."""

    def test_zuweisung_ohne_sei_wirft_namensfehler(self):
        with self.assertRaises(NameError) as ctx:
            lauf('tippfelher = 5')
        self.assertIn("benutze 'sei'", str(ctx.exception))

    def test_vorschlag_bei_aehnlichem_namen(self):
        with self.assertRaises(NameError) as ctx:
            lauf('sei zaehler = 0\nzaehlerr = 5')
        self.assertIn("meintest du 'zaehler'", str(ctx.exception))

    def test_nach_sei_ist_zuweisung_erlaubt(self):
        self.assertEqual(lauf('sei x = 1\nx = 2\nx')[0], 2)

    def test_aeussere_variable_aus_funktion_beschreibbar(self):
        code = '''sei zaehler = 0
funktion hoch() { zaehler = zaehler + 1 }
hoch()
hoch()
zaehler'''
        self.assertEqual(lauf(code)[0], 2)

    def test_zuweisung_endet_am_blockskope(self):
        with self.assertRaises(NameError):
            lauf('wenn wahr { sei nurimblock = 1 }\nnurimblock = 2')

    def test_schleifen_und_fange_variablen_bleiben_zuweisbar(self):
        self.assertEqual(lauf('für i in [1] { i = 9 }\n"ok"')[0], 'ok')
        self.assertEqual(lauf('versuche { werfe "x" } fange f { f = 1 }\n"ok"')[0], 'ok')

    def test_attribut_und_index_zuweisung_unveraendert(self):
        self.assertEqual(lauf('sei l = [1,2]\nl[0] = 9\nl')[0], [9, 2])
        code = '''klasse A { funktion __init__(dies) { dies.x = 1 } }
sei a = neu A()
a.y = 2
a.y'''
        self.assertEqual(lauf(code)[0], 2)

    def test_konstante_meldet_weiterhin_typfehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('konstante K = 1\nK = 2')
        self.assertIn('Konstante', str(ctx.exception))


class TestGleichUeberladungUeberall(unittest.TestCase):
    """__gleich__ wirkte nur beim '=='-Operator, nicht bei passe/fall, 'in' und
    den wertbasierten Listenmethoden."""

    KLASSE = '''klasse Geld {
    funktion __init__(dies, w) { dies.w = w }
    funktion __gleich__(dies, a) { zurück dies.w == a.w }
}
sei a = neu Geld(5)
sei b = neu Geld(5)
sei c = neu Geld(9)
'''

    def test_gleich_operator_unveraendert(self):
        self.assertIs(lauf(self.KLASSE + 'a == b')[0], True)
        self.assertIs(lauf(self.KLASSE + 'a == c')[0], False)

    def test_passe_nutzt_ueberladung(self):
        code = self.KLASSE + '''passe a {
    fall c: { "falsch" }
    fall b: { "treffer" }
    sonst: { "kein Treffer" }
}'''
        self.assertEqual(lauf(code)[0], 'treffer')

    def test_in_operator_nutzt_ueberladung(self):
        self.assertIs(lauf(self.KLASSE + 'a in [c, b]')[0], True)
        self.assertIs(lauf(self.KLASSE + 'a in [c]')[0], False)
        self.assertIs(lauf(self.KLASSE + 'a nicht in [c]')[0], True)

    def test_listenmethoden_nutzen_ueberladung(self):
        self.assertIs(lauf(self.KLASSE + '[c, b].enthält(a)')[0], True)
        self.assertEqual(lauf(self.KLASSE + '[c, b].index_von(a)')[0], 1)
        self.assertEqual(lauf(self.KLASSE + '[b, c, b].zaehle(a)')[0], 2)

    def test_index_von_ohne_treffer_wirft_wertfehler(self):
        with self.assertRaises(ValueError):
            lauf(self.KLASSE + '[c].index_von(a)')

    def test_mengen_und_woerterbuecher_bleiben_hashbasiert(self):
        # Ohne __hash__-Überladung kann __gleich__ die Mitgliedschaft nicht beeinflussen
        self.assertIs(lauf(self.KLASSE + 'a in menge([b])')[0], False)
        self.assertIs(lauf(self.KLASSE + 'a in menge([a])')[0], True)

    def test_ohne_ueberladung_bleibt_identitaet(self):
        code = '''klasse Ohne { funktion __init__(dies) { dies.n = 1 } }
sei o1 = neu Ohne()
sei o2 = neu Ohne()
[o1 == o2, o1 in [o2], o1 in [o1]]'''
        self.assertEqual(lauf(code)[0], [False, False, True])

    def test_normale_werte_unveraendert(self):
        code = '[2 in [1,2,3], 5 nicht in [1,2], "a" in "abc", 1 in {1,2}, "k" in {"k": 1}]'
        self.assertEqual(lauf(code)[0], [True, True, True, True, True])
        self.assertEqual(lauf('passe 2 { fall 1, 2: { "ja" } sonst: { "nein" } }')[0], 'ja')


class TestKlassenkonstantenSindGeschuetzt(unittest.TestCase):
    """Eine Klassenkonstante ließ sich pro Instanz überdecken (dies.MAX = 1)."""

    KLASSE = '''klasse K {
    konstante MAX = 100
    sei zaehler = 0
    funktion __init__(dies) { dies.x = 1 }
    funktion brich(dies) { dies.MAX = 1 }
}
sei k = neu K()
'''
    KIND = 'klasse Kind(K) { }\nsei kind = neu Kind()\n'

    def test_konstante_bleibt_lesbar(self):
        self.assertEqual(lauf(self.KLASSE + 'k.MAX')[0], 100)

    def test_zuweisung_ueber_klasse(self):
        with self.assertRaises(TypeError) as ctx:
            lauf(self.KLASSE + 'K.MAX = 5')
        self.assertIn('neu zugewiesen', str(ctx.exception))

    def test_zuweisung_ueber_instanz(self):
        with self.assertRaises(TypeError) as ctx:
            lauf(self.KLASSE + 'k.MAX = 7')
        self.assertIn('pro Instanz überdeckt', str(ctx.exception))

    def test_zuweisung_ueber_dies_in_methode(self):
        with self.assertRaises(TypeError):
            lauf(self.KLASSE + 'k.brich()')

    def test_geerbte_konstante_ueber_klasse_geschuetzt(self):
        with self.assertRaises(TypeError) as ctx:
            lauf(self.KLASSE + self.KIND + 'Kind.MAX = 5')
        # Die Meldung nennt die deklarierende Klasse, nicht die erbende
        self.assertIn("Klasse 'K'", str(ctx.exception))

    def test_geerbte_konstante_ueber_instanz_geschuetzt(self):
        with self.assertRaises(TypeError):
            lauf(self.KLASSE + self.KIND + 'kind.MAX = 5')

    def test_nicht_konstante_klassenattribute_bleiben_schreibbar(self):
        code = self.KLASSE + '''K.zaehler = 9
k.zaehler = 3
[k.zaehler, K.zaehler]'''
        self.assertEqual(lauf(code)[0], [3, 9])

    def test_neue_instanzattribute_weiterhin_moeglich(self):
        self.assertEqual(lauf(self.KLASSE + 'k.frisch = 1\nk.frisch')[0], 1)
        self.assertEqual(lauf(self.KLASSE + 'k.x')[0], 1)


class TestAbstraktionen(unittest.TestCase):
    """Verschachtelte Klauseln sowie Mengen- und Wörterbuch-Abstraktionen."""

    def test_einfache_listen_abstraktion_unveraendert(self):
        self.assertEqual(lauf('[x * x für x in bereich(1, 6)]')[0], [1, 4, 9, 16, 25])
        self.assertEqual(lauf('[x für x in bereich(1, 11) wenn x % 2 == 0]')[0],
                         [2, 4, 6, 8, 10])

    def test_destrukturierung_unveraendert(self):
        self.assertEqual(lauf('[a + b für [a, b] in [[1,2],[3,4]]]')[0], [3, 7])

    def test_verschachtelte_klauseln(self):
        self.assertEqual(lauf('[x * y für x in [1,2,3] für y in [10,20]]')[0],
                         [10, 20, 20, 40, 30, 60])

    def test_spaetere_klausel_sieht_frühere_variable(self):
        self.assertEqual(lauf('[y für x in [3] für y in bereich(x)]')[0], [0, 1, 2])

    def test_filter_an_jeder_klausel(self):
        code = '[[x, y] für x in bereich(1,4) wenn x != 2 für y in bereich(1,4) wenn y > x]'
        self.assertEqual(lauf(code)[0], [[1, 2], [1, 3]])

    def test_mengen_abstraktion(self):
        self.assertEqual(lauf('{x % 3 für x in bereich(10)}')[0], {0, 1, 2})
        self.assertEqual(lauf('{x für x in bereich(20) wenn x % 5 == 0}')[0], {0, 5, 10, 15})

    def test_mengen_abstraktion_verschachtelt(self):
        self.assertEqual(lauf('{x + y für x in [1,2] für y in [10,20]}')[0], {11, 21, 12, 22})

    def test_woerterbuch_abstraktion(self):
        self.assertEqual(lauf('{x: x * x für x in bereich(1, 5)}')[0],
                         {1: 1, 2: 4, 3: 9, 4: 16})

    def test_woerterbuch_abstraktion_mit_filter(self):
        code = '{w: laenge(w) für w in ["a","bb","ccc"] wenn laenge(w) > 1}'
        self.assertEqual(lauf(code)[0], {'bb': 2, 'ccc': 3})

    def test_literale_bleiben_literale(self):
        self.assertEqual(lauf('typ({})')[0], 'Woerterbuch')
        self.assertEqual(lauf('typ({1, 2})')[0], 'Menge')
        self.assertEqual(lauf('typ({"a": 1})')[0], 'Woerterbuch')
        self.assertEqual(lauf('{1, 2, 3}')[0], {1, 2, 3})
        self.assertEqual(lauf('{"a": 1, "b": 2}')[0], {'a': 1, 'b': 2})

    def test_ergebnistypen(self):
        self.assertEqual(lauf('typ([x für x in [1]])')[0], 'Liste')
        self.assertEqual(lauf('typ({x für x in [1]})')[0], 'Menge')
        self.assertEqual(lauf('typ({x: x für x in [1]})')[0], 'Woerterbuch')

    def test_nicht_iterierbare_klausel_meldet_deutsch(self):
        for code in ('[x für x in 5]', '{x für x in 5}', '{x: x für x in 5}'):
            with self.subTest(code=code):
                with self.assertRaises(TypeError) as ctx:
                    lauf(code)
                self.assertIn('Iterierbares', str(ctx.exception))

    def test_unhashbare_ergebnisse_melden_deutsch(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('{[x] für x in [1]}')
        self.assertIn('hashbar', str(ctx.exception))
        with self.assertRaises(TypeError) as ctx:
            lauf('{[x]: x für x in [1]}')
        self.assertIn('hashbar', str(ctx.exception))

    def test_abstraktionsvariable_bleibt_lokal(self):
        with self.assertRaises(NameError):
            lauf('[x für x in [1]]\nx')


class TestFauleBereiche(unittest.TestCase):
    """'bereich' liefert eine faule Folge statt einer Liste."""

    def test_typ_und_darstellung(self):
        self.assertEqual(lauf('typ(bereich(3))')[0], 'Bereich')
        self.assertEqual(lauf('zeichenkette(bereich(3))')[0], 'bereich(0, 3)')
        self.assertEqual(lauf('zeichenkette(bereich(0, 10, 2))')[0], 'bereich(0, 10, 2)')

    def test_belegt_keinen_speicher_fuer_die_elemente(self):
        ergebnis, _ = lauf('bereich(10000000)')
        self.assertEqual(len(ergebnis), 10_000_000)
        self.assertLess(sys.getsizeof(ergebnis), 500)

    def test_laenge_index_und_schnitt(self):
        self.assertEqual(lauf('laenge(bereich(0, 10, 2))')[0], 5)
        self.assertEqual(lauf('bereich(0, 10, 2).laenge()')[0], 5)
        self.assertEqual(lauf('bereich(0, 10, 2)[2]')[0], 4)
        self.assertEqual(lauf('bereich(5)[-1]')[0], 4)
        self.assertEqual(lauf('typ(bereich(10)[1:3])')[0], 'Bereich')   # Schnitt bleibt faul
        self.assertEqual(lauf('liste(bereich(10)[1:3])')[0], [1, 2])

    def test_index_ausserhalb_meldet_deutsch(self):
        with self.assertRaises(IndexError) as ctx:
            lauf('bereich(3)[9]')
        self.assertIn('außerhalb des Bereichs', str(ctx.exception))

    def test_mitgliedschaft(self):
        self.assertIs(lauf('4 in bereich(0, 10, 2)')[0], True)
        self.assertIs(lauf('5 in bereich(0, 10, 2)')[0], False)
        self.assertIs(lauf('bereich(3).enthält(2)')[0], True)

    def test_umwandlung(self):
        self.assertEqual(lauf('liste(bereich(3))')[0], [0, 1, 2])
        self.assertEqual(lauf('menge(bereich(3))')[0], {0, 1, 2})
        self.assertEqual(lauf('bereich(3).liste()')[0], [0, 1, 2])
        self.assertEqual(lauf('bereich(3).erste()')[0], 0)
        self.assertEqual(lauf('bereich(3).letzte()')[0], 2)

    def test_wird_von_den_eingebauten_akzeptiert(self):
        self.assertEqual(lauf('summe(bereich(5))')[0], 10)
        self.assertEqual(lauf('max(bereich(5))')[0], 4)
        self.assertEqual(lauf('min(bereich(2, 5))')[0], 2)
        self.assertIs(lauf('alle(bereich(1, 4))')[0], True)
        self.assertIs(lauf('einige(bereich(0, 1))')[0], False)
        self.assertEqual(lauf('sortiere(bereich(3, 0, -1))')[0], [1, 2, 3])
        self.assertEqual(lauf('aufzaehlen(bereich(2))')[0], [[0, 0], [1, 1]])
        self.assertEqual(lauf('mittelwert(bereich(1, 5))')[0], 2.5)
        self.assertEqual(lauf('zippe(bereich(2), ["a", "b"])')[0], [[0, 'a'], [1, 'b']])

    def test_schleifen_und_abstraktionen(self):
        self.assertEqual(lauf('sei s = 0; für i in bereich(4) { s += i }; s')[0], 6)
        self.assertEqual(lauf('[x * 2 für x in bereich(4)]')[0], [0, 2, 4, 6])
        self.assertEqual(lauf('{x % 2 für x in bereich(6)}')[0], {0, 1})
        self.assertEqual(lauf('{x: x für x in bereich(2)}')[0], {0: 0, 1: 1})

    def test_wahrheitswert(self):
        self.assertIs(lauf('wahrheitswert(bereich(0))')[0], False)
        self.assertIs(lauf('wahrheitswert(bereich(3))')[0], True)

    def test_typ_hinweis_bereich(self):
        code = 'funktion f(b: Bereich) { zurück laenge(b) }; f(bereich(7))'
        self.assertEqual(lauf(code)[0], 7)
        with self.assertRaises(TypeError):
            lauf('funktion f(b: Bereich) { zurück 1 }; f([1, 2])')

    def test_bereich_ist_keine_liste(self):
        with self.assertRaises(TypeError):
            lauf('sei x: Liste = bereich(3)')

    def test_ist_unveraenderlich(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('sei b = bereich(3); b[0] = 9')
        self.assertIn('unveränderlich', str(ctx.exception))

    def test_hat_keine_listenmethoden(self):
        with self.assertRaises(AttributeError) as ctx:
            lauf('bereich(3).anhaengen(1)')
        self.assertIn('Bereich', str(ctx.exception))

    def test_mische_verlangt_weiterhin_eine_liste(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('mische(bereich(3))')
        self.assertIn("'mische' erwartet eine Liste", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
