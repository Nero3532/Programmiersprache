# -*- coding: utf-8 -*-
"""
Tests für funktionale Sprachmittel:

  * Lambda-Kurzform   funktion(x) -> ausdruck   (anonym und benannt)
  * Funktionen höherer Ordnung   abbilden, filtere, reduziere (Funktion und Listen-Methode)
  * sortiere / max / min mit  schluessel=  (bzw. schlüssel=)  und  umgekehrt=
  * Abschließendes Komma in Aufrufen, Parameterlisten, Listen und Wörterbüchern
  * Syntaxfehler bei Resten in einer {…}-Interpolation ("{1 2}")

Ausführen mit:
    py -m unittest discover -s tests -p test_funktional.py -v
"""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch import ast_knoten as ast
from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter


def parse(code: str):
    return Parser(Lexer(code).tokenisieren()).parse()


def auswerten(code: str):
    """Führt Code aus und gibt den Wert der letzten Anweisung zurück."""
    return Interpreter().ausfuehren(parse(code))


def ausgabe(code: str) -> str:
    """Führt Code aus und gibt das auf stdout Gedruckte zurück."""
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter().ausfuehren(parse(code))
    return puffer.getvalue()


class _Basis(unittest.TestCase):
    def fehler(self, code: str, art=Exception) -> str:
        """Führt Code aus, erwartet einen Fehler der Art `art` und gibt dessen Text zurück."""
        with self.assertRaises(art) as ctx:
            auswerten(code)
        return str(ctx.exception)

    def assertDeutsch(self, text: str):
        """Die Meldung darf keinen rohen Python-Fehlertext enthalten."""
        for roh in ('positional argument', '<lambda>', 'NoneType', 'object is not', 'takes ', 'missing '):
            self.assertNotIn(roh, text)


# ---------------------------------------------------------------------------
# 1. Lambda-Kurzform
# ---------------------------------------------------------------------------

class TestLambdaKurzform(_Basis):
    def test_einfach(self):
        self.assertEqual(auswerten('sei f = funktion(x) -> x * 2\nf(4)'), 8)

    def test_sofort_aufgerufen(self):
        self.assertEqual(auswerten('(funktion(x) -> x + 1)(2)'), 3)

    def test_ohne_parameter(self):
        self.assertEqual(auswerten('sei f = funktion() -> 42\nf()'), 42)

    def test_mehrere_parameter(self):
        self.assertEqual(auswerten('sei f = funktion(a, b, c) -> a * b + c\nf(2, 3, 4)'), 10)

    def test_standardwerte(self):
        code = 'sei f = funktion(a, b = 10) -> a + b\n[f(1), f(1, 2)]'
        self.assertEqual(auswerten(code), [11, 3])

    def test_variadischer_parameter(self):
        code = 'sei f = funktion(erst, *rest) -> [erst, laenge(rest)]\n[f(1), f(1, 2, 3)]'
        self.assertEqual(auswerten(code), [[1, 0], [1, 2]])

    def test_typhinweise_bei_parametern(self):
        code = 'sei f = funktion(x: Ganzzahl, y: Zeichenkette = "a") -> y * x\nf(2)'
        self.assertEqual(auswerten(code), 'aa')
        text = self.fehler('sei f = funktion(x: Ganzzahl) -> x\nf("text")', TypeError)
        self.assertIn("erwartet Typ 'Ganzzahl'", text)

    def test_schluesselwoerter_als_kwargs(self):
        self.assertEqual(auswerten('sei f = funktion(a, b = 5) -> a - b\nf(b = 1, a = 10)'), 9)

    def test_closure_wie_blockform(self):
        code = '''
funktion mache(n) { zurück funktion(x) -> x + n }
sei plus3 = mache(3)
sei plus10 = mache(10)
[plus3(1), plus10(1)]
'''
        self.assertEqual(auswerten(code), [4, 11])

    def test_closure_sieht_spaetere_aenderung_der_variable(self):
        code = '''
sei n = 1
sei f = funktion() -> n
n = 2
f()
'''
        self.assertEqual(auswerten(code), 2)

    def test_closure_in_schleife_pro_durchlauf(self):
        code = 'sei fs = [funktion(x) -> x + i für i in bereich(3)]\nabbilden(fs, funktion(f) -> f(10))'
        self.assertEqual(auswerten(code), [10, 11, 12])

    def test_gleichbedeutend_mit_blockform(self):
        kurz = parse('sei f = funktion(a, b = 1) -> a + b').anweisungen[0].wert
        self.assertIsInstance(kurz, ast.FunktionDefinition)
        self.assertEqual([p[0] for p in kurz.parameter], ['a', 'b'])
        self.assertEqual(len(kurz.koerper.anweisungen), 1)
        self.assertIsInstance(kurz.koerper.anweisungen[0], ast.ZurueckAnweisung)
        for code in ('sei f = funktion(a, b = 1) -> a + b\nf(2)',
                     'sei f = funktion(a, b = 1) { zurück a + b }\nf(2)'):
            self.assertEqual(auswerten(code), 3)

    def test_rumpf_reicht_so_weit_wie_moeglich(self):
        # Ternär, Operatorkette und Aufrufe gehören noch zum Rumpf
        code = 'sei f = funktion(x) -> "pos" wenn x > 0 sonst "neg"\n[f(1), f(-1)]'
        self.assertEqual(auswerten(code), ['pos', 'neg'])
        self.assertEqual(auswerten('sei f = funktion(x) -> x + 1 und wahr\nf(0)'), True)
        self.assertEqual(auswerten('sei g = funktion(x) -> x * 2\nsei f = funktion(x) -> g(x) + g(x)\nf(3)'), 12)

    def test_rumpf_endet_an_komma_und_klammer(self):
        code = '''
sei fs = [funktion(x) -> x + 1, funktion(x) -> x * 2,]
sei tabelle = {"a": funktion(x) -> x - 1, "b": funktion(x) -> x}
[fs[0](5), fs[1](5), tabelle["a"](5), laenge(fs)]
'''
        self.assertEqual(auswerten(code), [6, 10, 4, 2])

    def test_lambda_gibt_woerterbuch_zurueck(self):
        self.assertEqual(auswerten('sei f = funktion() -> {"a": 1}\nf()'), {'a': 1})

    def test_verschachtelt(self):
        self.assertEqual(auswerten('sei add = funktion(a) -> funktion(b) -> a + b\nadd(1)(2)'), 3)

    def test_als_standardwert_eines_parameters(self):
        code = 'funktion g(n, f = funktion(x) -> x + 1) { zurück f(n) }\n[g(1), g(1, funktion(x) -> x * 10)]'
        self.assertEqual(auswerten(code), [2, 10])

    def test_in_interpolation(self):
        self.assertEqual(auswerten('"{abbilden([1, 2], funktion(x) -> x * 2)}"'), '[2, 4]')

    def test_mehrzeilig_im_aufruf(self):
        code = '''
sei erg = abbilden(
    [1, 2, 3],
    funktion(x) ->
        x * 10
)
erg
'''
        self.assertEqual(auswerten(code), [10, 20, 30])

    def test_mehrzeilig_rumpf_in_klammern(self):
        code = '''
sei f = (funktion(a, b) ->
    a
    + b)
f(1, 2)
'''
        self.assertEqual(auswerten(code), 3)

    def test_zeilenumbruch_nach_pfeil_ausserhalb_von_klammern(self):
        self.assertEqual(auswerten('sei f = funktion(x) ->\n    x + 1\nf(1)'), 2)

    # --- benannte Kurzfunktionen

    def test_benannte_kurzfunktion_als_anweisung(self):
        self.assertEqual(auswerten('funktion quadrat(x) -> x * x\nquadrat(5)'), 25)

    def test_benannte_kurzfunktion_rekursiv(self):
        self.assertEqual(auswerten('funktion fak(n) -> 1 wenn n <= 1 sonst n * fak(n - 1)\nfak(5)'), 120)

    def test_benannte_kurzfunktion_als_ausdruck(self):
        self.assertEqual(auswerten('sei g = funktion h(x) -> x + 1\n[g(1), h(2)]'), [2, 3])

    def test_kurzmethoden_in_klasse(self):
        code = '''
klasse Z {
    funktion __init__(dies, n) { dies.n = n }
    funktion plus(dies, x) -> dies.n + x
    statisch funktion doppelt(x) -> x * 2
}
sei z = neu Z(5)
[z.plus(1), Z.doppelt(4), abbilden([1, 2], z.plus)]
'''
        self.assertEqual(auswerten(code), [6, 8, [6, 7]])

    def test_benannte_kurzfunktion_mit_semikolon(self):
        self.assertEqual(auswerten('funktion f(x) -> x + 1; f(1)'), 2)

    # --- Abgrenzung zum Rückgabetyp

    def test_rueckgabetyp_mit_block_bleibt_gueltig(self):
        self.assertEqual(auswerten('funktion f(x) -> Ganzzahl { zurück x + 1 }\nf(1)'), 2)
        self.assertEqual(auswerten('sei f = funktion(x) -> Ganzzahl { zurück x }\nf(3)'), 3)
        text = self.fehler('funktion f(x) -> Ganzzahl { zurück "a" }\nf(1)', TypeError)
        self.assertIn("erwartet Typ 'Ganzzahl'", text)

    def test_name_nach_pfeil_ohne_klammer_ist_ausdruck(self):
        self.assertEqual(auswerten('sei zahl = 7\nsei f = funktion() -> zahl\nf()'), 7)

    # --- Fehler

    def test_fehlender_rumpf(self):
        for code in ('sei f = funktion(x) ->', 'drucke(funktion(x) -> )', 'sei l = [funktion(x) -> ]',
                     'sei f = funktion(x) -> ;'):
            with self.assertRaises(SyntaxError, msg=code) as ctx:
                parse(code)
            self.assertIn("Nach '->' fehlt der Funktionsrumpf", str(ctx.exception))

    def test_zu_viele_argumente_nennt_anonym_statt_none(self):
        text = self.fehler('(funktion(x) -> x)(1, 2)', TypeError)
        self.assertIn("'<anonym>' erwartet höchstens 1 Argument(e), bekam 2", text)
        self.assertNotIn('None', text)

    def test_fehlende_argumente_nennt_anonym_statt_none(self):
        text = self.fehler('(funktion(a, b) -> a)(1)', TypeError)
        self.assertIn("'<anonym>': Pflichtargument(e) fehlen: b", text)

    def test_laufzeitfehler_im_rumpf_nennt_zeile(self):
        text = self.fehler('sei f = funktion(x) -> 1 / x\n\nf(0)', ZeroDivisionError)
        self.assertIn('Division durch Null', text)
        self.assertIn('Zeile', text)


# ---------------------------------------------------------------------------
# 2. abbilden / filtere / reduziere
# ---------------------------------------------------------------------------

class TestAbbilden(_Basis):
    def test_lambda(self):
        self.assertEqual(auswerten('abbilden([1, 2, 3], funktion(x) -> x * 2)'), [2, 4, 6])

    def test_nutzerfunktion(self):
        self.assertEqual(auswerten('funktion q(x) { zurück x * x }\nabbilden([1, 2, 3], q)'), [1, 4, 9])

    def test_eingebaute_funktion(self):
        self.assertEqual(auswerten('abbilden(["a", "bcd"], laenge)'), [1, 3])
        self.assertEqual(auswerten('abbilden([1, 2], zeichenkette)'), ['1', '2'])

    def test_eingebaute_methode(self):
        self.assertEqual(auswerten('abbilden(["a", "b"], funktion(s) -> s.gross())'), ['A', 'B'])

    def test_leere_liste(self):
        self.assertEqual(auswerten('abbilden([], funktion(x) -> x)'), [])

    def test_menge_und_zeichenkette(self):
        self.assertEqual(auswerten('abbilden({3, 1, 2}, funktion(x) -> x * 10)'), [10, 20, 30])
        self.assertEqual(auswerten('abbilden("abc", funktion(c) -> c.gross())'), ['A', 'B', 'C'])

    def test_original_bleibt_unveraendert(self):
        self.assertEqual(auswerten('sei l = [1, 2]\nsei m = abbilden(l, funktion(x) -> x + 1)\n[l, m]'),
                         [[1, 2], [2, 3]])

    def test_methode(self):
        self.assertEqual(auswerten('[1, 2, 3].abbilden(funktion(x) -> x + 1)'), [2, 3, 4])

    def test_funktion_ruft_gebundene_methode(self):
        code = '''
klasse K {
    funktion __init__(dies, n) { dies.n = n }
    funktion mal(dies, x) { zurück dies.n * x }
}
abbilden([1, 2, 3], (neu K(3)).mal)
'''
        self.assertEqual(auswerten(code), [3, 6, 9])

    def test_fehler_keine_funktion(self):
        text = self.fehler('abbilden([1], 5)', TypeError)
        self.assertIn("'abbilden' erwartet als 2. Argument eine Funktion, bekam Ganzzahl", text)
        text = self.fehler('[1].abbilden("x")', TypeError)
        self.assertIn("'abbilden' erwartet als Argument eine Funktion, bekam Zeichenkette", text)

    def test_fehler_falsche_parameterzahl_der_funktion(self):
        text = self.fehler('abbilden([1], funktion(a, b) -> a)', TypeError)
        self.assertIn('erwartet genau 2 Argumente, wird hier aber mit 1 Argument aufgerufen', text)
        self.assertDeutsch(text)
        text = self.fehler('abbilden([1], funktion() -> 1)', TypeError)
        self.assertIn('erwartet genau 0 Argumente, wird hier aber mit 1 Argument aufgerufen', text)

    def test_fehler_falsche_parameterzahl_eingebaute_funktion(self):
        text = self.fehler('abbilden([1], [].einfuegen)', TypeError)
        self.assertIn('erwartet genau 2 Argumente, wird hier aber mit 1 Argument aufgerufen', text)
        self.assertDeutsch(text)

    def test_optionale_parameter_sind_erlaubt(self):
        self.assertEqual(auswerten('abbilden([1, 2], funktion(x, y = 10) -> x + y)'), [11, 12])
        self.assertEqual(auswerten('abbilden([1, 2], funktion(*alle) -> laenge(alle))'), [1, 1])

    def test_fehler_falsche_sammlung(self):
        text = self.fehler('abbilden(5, funktion(x) -> x)', TypeError)
        self.assertIn("'abbilden' erwartet als erstes eine Liste, Menge oder Zeichenkette, bekam Ganzzahl", text)

    def test_fehler_falsche_argumentzahl(self):
        self.assertIn("'abbilden' erwartet 2 Argument(e), bekam 1", self.fehler('abbilden([1])', TypeError))
        self.assertIn("'abbilden' erwartet 1 Argument(e), bekam 0", self.fehler('[1].abbilden()', TypeError))

    def test_fehler_in_der_funktion_wird_durchgereicht(self):
        text = self.fehler('abbilden([1, 0], funktion(x) -> 1 / x)', ZeroDivisionError)
        self.assertIn('Division durch Null', text)


class TestFiltere(_Basis):
    def test_lambda(self):
        self.assertEqual(auswerten('filtere([1, 2, 3, 4], funktion(x) -> x % 2 == 0)'), [2, 4])

    def test_wahrheitswert_nach_sprachregeln(self):
        self.assertEqual(auswerten('filtere([0, 1, "", "a", nichts, []], funktion(x) -> x)'), [1, 'a'])

    def test_eingebaute_funktion(self):
        self.assertEqual(auswerten('filtere(["", "a", ""], laenge)'), ['a'])

    def test_nichts_passt(self):
        self.assertEqual(auswerten('filtere([1, 2], funktion(x) -> falsch)'), [])

    def test_zeichenkette(self):
        self.assertEqual(auswerten('filtere("a1b2", funktion(c) -> c.ist_ziffer())'), ['1', '2'])

    def test_methode(self):
        self.assertEqual(auswerten('[1, 2, 3].filtere(funktion(x) -> x > 1)'), [2, 3])

    def test_fehler(self):
        self.assertIn("'filtere' erwartet als 2. Argument eine Funktion, bekam Liste",
                      self.fehler('filtere([1], [])', TypeError))
        text = self.fehler('filtere([1], funktion(a, b) -> wahr)', TypeError)
        self.assertIn("'filtere': Die übergebene Funktion erwartet genau 2 Argumente", text)
        self.assertIn("'filtere' erwartet 2 Argument(e), bekam 3",
                      self.fehler('filtere([1], laenge, 1)', TypeError))
        self.assertIn("'filtere' erwartet als erstes eine Liste",
                      self.fehler('filtere(nichts, laenge)', TypeError))


class TestReduziere(_Basis):
    def test_ohne_start(self):
        self.assertEqual(auswerten('reduziere([1, 2, 3, 4], funktion(a, b) -> a + b)'), 10)

    def test_mit_start(self):
        self.assertEqual(auswerten('reduziere([1, 2, 3], funktion(a, b) -> a + b, 100)'), 106)

    def test_reihenfolge_links_nach_rechts(self):
        self.assertEqual(auswerten('reduziere(["a", "b", "c"], funktion(a, b) -> a + b)'), 'abc')
        self.assertEqual(auswerten('reduziere([10, 2, 3], funktion(a, b) -> a - b)'), 5)

    def test_einzelnes_element_ohne_start(self):
        self.assertEqual(auswerten('reduziere([7], funktion(a, b) -> a + b)'), 7)

    def test_leere_sammlung_mit_start(self):
        self.assertEqual(auswerten('reduziere([], funktion(a, b) -> a + b, 5)'), 5)

    def test_start_nichts_ist_gueltig(self):
        self.assertEqual(auswerten('reduziere([1, 2], funktion(a, b) -> b, nichts)'), 2)
        self.assertIsNone(auswerten('reduziere([], funktion(a, b) -> b, nichts)'))

    def test_startwert_bestimmt_den_ergebnistyp(self):
        self.assertEqual(auswerten('reduziere(["a", "bb", "ccc"], funktion(acc, w) -> acc + laenge(w), 0)'), 6)
        self.assertEqual(auswerten('reduziere([1, 2], funktion(acc, x) -> acc + [x * x], [])'), [1, 4])

    def test_eingebaute_funktion(self):
        self.assertEqual(auswerten('reduziere([3, 9, 4], max)'), 9)

    def test_methode(self):
        self.assertEqual(auswerten('[1, 2, 3].reduziere(funktion(a, b) -> a * b)'), 6)
        self.assertEqual(auswerten('[1, 2, 3].reduziere(funktion(a, b) -> a + b, 10)'), 16)

    def test_fehler_leere_sammlung_ohne_start(self):
        text = self.fehler('reduziere([], funktion(a, b) -> a)', ValueError)
        self.assertIn("'reduziere' kann eine leere Sammlung nicht ohne Startwert reduzieren", text)
        text = self.fehler('[].reduziere(funktion(a, b) -> a)', ValueError)
        self.assertIn('leere Sammlung', text)

    def test_fehler_keine_funktion(self):
        text = self.fehler('reduziere([1, 2], 3)', TypeError)
        self.assertIn("'reduziere' erwartet als 2. Argument eine Funktion, bekam Ganzzahl", text)

    def test_fehler_falsche_parameterzahl_der_funktion(self):
        text = self.fehler('reduziere([1, 2], funktion(a) -> a)', TypeError)
        self.assertIn("'reduziere': Die übergebene Funktion erwartet genau 1 Argument, "
                      "wird hier aber mit 2 Argumenten aufgerufen", text)
        text = self.fehler('[1, 2].reduziere(funktion(a, b, c) -> a)', TypeError)
        self.assertIn('erwartet genau 3 Argumente, wird hier aber mit 2 Argumenten aufgerufen', text)

    def test_fehler_falsche_argumentzahl(self):
        self.assertIn("'reduziere' erwartet 2–3 Argumente, bekam 1", self.fehler('reduziere([1])', TypeError))
        self.assertIn("'reduziere' erwartet 2–3 Argumente, bekam 4",
                      self.fehler('reduziere([1], max, 1, 2)', TypeError))
        self.assertIn("'reduziere' erwartet 1–2 Argumente, bekam 0", self.fehler('[1].reduziere()', TypeError))

    def test_fehler_falsche_sammlung(self):
        self.assertIn("'reduziere' erwartet als erstes eine Liste",
                      self.fehler('reduziere(3, funktion(a, b) -> a)', TypeError))


class TestVerkettung(_Basis):
    def test_methoden_verkettet(self):
        code = '[1, 2, 3, 4, 5].abbilden(funktion(x) -> x * x).filtere(funktion(x) -> x > 4).reduziere(funktion(a, b) -> a + b)'
        self.assertEqual(auswerten(code), 9 + 16 + 25)

    def test_verkettung_ueber_mehrere_zeilen(self):
        code = '''
sei erg = [1, 2, 3, 4].abbilden(
    funktion(x) -> x * x
).filtere(
    funktion(x) ->
        x > 4,
)
erg
'''
        self.assertEqual(auswerten(code), [9, 16])

    def test_funktionen_ineinander(self):
        code = 'reduziere(filtere(abbilden([1, 2, 3, 4], funktion(x) -> x * 3), funktion(x) -> x % 2 == 0), funktion(a, b) -> a + b)'
        self.assertEqual(auswerten(code), 6 + 12)

    def test_ergebnis_ist_normale_liste(self):
        # Das Ergebnis von abbilden ist eine neue Liste und lässt sich in place weiter bearbeiten
        code = 'sei l = [3, 1, 2].abbilden(funktion(x) -> x * 2)\nl.sortiere()\nl.anhaengen(0)\nl'
        self.assertEqual(auswerten(code), [2, 4, 6, 0])

    def test_mehrzeilige_lambdas_als_argument(self):
        code = '''
sei summe_gerader = reduziere(
    filtere(
        [1, 2, 3, 4, 5, 6],
        funktion(x) -> x % 2 == 0,
    ),
    funktion(acc, x) ->
        acc + x,
    0,
)
summe_gerader
'''
        self.assertEqual(auswerten(code), 12)

    def test_blockform_und_kurzform_gemischt(self):
        code = '''
abbilden(
    [1, 2, 3],
    funktion(x) {
        sei y = x * 2
        zurück y + 1
    }
).filtere(funktion(x) -> x > 3)
'''
        self.assertEqual(auswerten(code), [5, 7])

    def test_funktionsname_nicht_reserviert(self):
        # Eigene Variablen gleichen Namens überlagern die Eingebauten wie bei allen anderen
        code = 'funktion f() { sei abbilden = 5\nzurück abbilden }\nf()'
        self.assertEqual(auswerten(code), 5)


# ---------------------------------------------------------------------------
# 3. sortiere / max / min mit Schlüsselfunktion
# ---------------------------------------------------------------------------

class TestSortiereSchluessel(_Basis):
    def test_ohne_keyword_unveraendert(self):
        self.assertEqual(auswerten('sortiere([3, 1, 2])'), [1, 2, 3])
        self.assertEqual(auswerten('sortiere(["b", "a"])'), ['a', 'b'])
        self.assertEqual(auswerten('sortiere({3, 1, 2})'), [1, 2, 3])
        self.assertEqual(auswerten('sortiere([2, "a", 1])'), [1, 2, 'a'])  # gemischte Typen: nach Text
        self.assertEqual(auswerten('sortiere([])'), [])

    def test_mit_schluessel_eingebaute_funktion(self):
        self.assertEqual(auswerten('sortiere(["bb", "a", "ccc"], schluessel=laenge)'), ['a', 'bb', 'ccc'])

    def test_mit_schluessel_lambda(self):
        self.assertEqual(auswerten('sortiere([3, -5, 1], schluessel=funktion(x) -> abs(x))'), [1, 3, -5])

    def test_umlaut_schreibweise(self):
        self.assertEqual(auswerten('sortiere(["bb", "a"], schlüssel=laenge)'), ['a', 'bb'])
        self.assertEqual(auswerten('max(["bb", "a"], schlüssel=laenge)'), 'bb')

    def test_umgekehrt(self):
        self.assertEqual(auswerten('sortiere([2, 3, 1], umgekehrt=wahr)'), [3, 2, 1])
        self.assertEqual(auswerten('sortiere([2, 3, 1], umgekehrt=falsch)'), [1, 2, 3])

    def test_schluessel_und_umgekehrt(self):
        code = 'sortiere(["bb", "a", "ccc"], schluessel=laenge, umgekehrt=wahr)'
        self.assertEqual(auswerten(code), ['ccc', 'bb', 'a'])

    def test_gleiche_schluessel_behalten_reihenfolge(self):
        code = '''
sei p = [{"n": "Bo", "a": 30}, {"n": "Al", "a": 25}, {"n": "Cy", "a": 30}]
[abbilden(sortiere(p, schluessel=funktion(x) -> x["a"]), funktion(x) -> x["n"]),
 abbilden(sortiere(p, schluessel=funktion(x) -> x["a"], umgekehrt=wahr), funktion(x) -> x["n"])]
'''
        self.assertEqual(auswerten(code), [['Al', 'Bo', 'Cy'], ['Bo', 'Cy', 'Al']])

    def test_schluessel_nichts_heisst_kein_schluessel(self):
        self.assertEqual(auswerten('sortiere([2, 1], schluessel=nichts)'), [1, 2])

    def test_original_bleibt_unveraendert(self):
        self.assertEqual(auswerten('sei l = [3, 1, 2]\nsei s = sortiere(l, umgekehrt=wahr)\n[l, s]'),
                         [[3, 1, 2], [3, 2, 1]])

    def test_menge_mit_schluessel(self):
        self.assertEqual(auswerten('sortiere({1, 2, 3}, schluessel=funktion(x) -> -x)'), [3, 2, 1])

    def test_nicht_vergleichbare_schluessel_fallen_auf_text_zurueck(self):
        self.assertEqual(auswerten('sortiere([2, "a", 1], schluessel=funktion(x) -> x)'), [1, 2, 'a'])

    def test_methode_sortiert_in_place(self):
        code = 'sei l = ["bb", "a", "ccc"]\nsei r = l.sortiere(schluessel=laenge)\n[l, r]'
        self.assertEqual(auswerten(code), [['a', 'bb', 'ccc'], None])

    def test_methode_umgekehrt_und_schluessel(self):
        code = 'sei l = ["bb", "a", "ccc"]\nl.sortiere(schluessel=laenge, umgekehrt=wahr)\nl'
        self.assertEqual(auswerten(code), ['ccc', 'bb', 'a'])
        self.assertEqual(auswerten('sei l = [1, 3, 2]\nl.sortiere(umgekehrt=wahr)\nl'), [3, 2, 1])

    def test_methode_ohne_keyword_unveraendert(self):
        self.assertEqual(auswerten('sei l = [3, 1, 2]\nl.sortiere()\nl'), [1, 2, 3])
        self.assertIsNone(auswerten('[3, 1].sortiere()'))

    def test_methode_fehler_im_schluessel_laesst_liste_unveraendert(self):
        code = '''
sei l = [3, 0, 2]
versuche { l.sortiere(schluessel=funktion(x) -> 6 / x) } fange e { }
l
'''
        self.assertEqual(auswerten(code), [3, 0, 2])

    # --- Fehler

    def test_fehler_schluessel_keine_funktion(self):
        text = self.fehler('sortiere([1], schluessel=5)', TypeError)
        self.assertIn("'sortiere' erwartet für 'schluessel' eine Funktion, bekam Ganzzahl", text)
        text = self.fehler('[1].sortiere(schlüssel="x")', TypeError)
        self.assertIn("'sortiere' erwartet für 'schlüssel' eine Funktion, bekam Zeichenkette", text)

    def test_fehler_schluessel_falsche_parameterzahl(self):
        text = self.fehler('sortiere([1], schluessel=funktion(a, b) -> a)', TypeError)
        self.assertIn('erwartet genau 2 Argumente, wird hier aber mit 1 Argument aufgerufen', text)
        text = self.fehler('[1].sortiere(schluessel=funktion() -> 1)', TypeError)
        self.assertIn('erwartet genau 0 Argumente, wird hier aber mit 1 Argument aufgerufen', text)

    def test_fehler_unbekanntes_keyword(self):
        self.assertIn("'sortiere' hat kein Parameter 'foo'", self.fehler('sortiere([1], foo=1)', TypeError))
        self.assertIn("'sortiere' hat kein Parameter 'foo'", self.fehler('[1].sortiere(foo=1)', TypeError))

    def test_fehler_beide_schreibweisen_gleichzeitig(self):
        text = self.fehler('sortiere([1], schluessel=laenge, schlüssel=laenge)', TypeError)
        self.assertIn("'schluessel' und 'schlüssel' sind dasselbe Argument", text)

    def test_fehler_positionales_argument_bei_methode(self):
        text = self.fehler('[2, 1].sortiere(laenge)', TypeError)
        self.assertIn("'sortiere' nimmt nur die Keyword-Argumente 'schluessel' und 'umgekehrt' an", text)

    def test_fehler_falsche_argumentzahl_builtin(self):
        self.assertIn("'sortiere' erwartet 1 Argument(e), bekam 2", self.fehler('sortiere([1], [2])', TypeError))
        self.assertIn("'sortiere' erwartet 1 Argument(e), bekam 0", self.fehler('sortiere(schluessel=laenge)', TypeError))
        self.assertIn("'sortiere' erwartet eine Liste oder Menge", self.fehler('sortiere(5, schluessel=laenge)', TypeError))

    def test_fehler_im_schluessel_wird_durchgereicht(self):
        text = self.fehler('sortiere([1, 0], schluessel=funktion(x) -> 1 / x)', ZeroDivisionError)
        self.assertIn('Division durch Null', text)

    def test_andere_eingebaute_lehnen_keywords_weiter_ab(self):
        text = self.fehler('laenge([1], schluessel=laenge)', TypeError)
        self.assertIn('Eingebaute Funktionen unterstützen keine Keyword-Argumente', text)
        text = self.fehler('abbilden([1], funktion(x) -> x, schluessel=laenge)', TypeError)
        self.assertIn('Eingebaute Funktionen unterstützen keine Keyword-Argumente', text)

    def test_listenmethoden_ohne_keywords_lehnen_weiter_ab(self):
        text = self.fehler('[1].anhaengen(1, schluessel=laenge)', TypeError)
        self.assertIn('Eingebaute Funktionen unterstützen keine Keyword-Argumente', text)

    def test_python_parametername_als_keyword_ist_kein_python_fehler(self):
        text = self.fehler('sortiere([1], obj=1)', TypeError)
        self.assertIn("'sortiere' hat kein Parameter 'obj'", text)
        text = self.fehler('[1].sortiere(obj=1)', TypeError)
        self.assertIn("'sortiere' hat kein Parameter 'obj'", text)


class TestMaxMinSchluessel(_Basis):
    def test_ohne_keyword_unveraendert(self):
        self.assertEqual(auswerten('max([3, 9, 4])'), 9)
        self.assertEqual(auswerten('min(3, 9, 4)'), 3)
        self.assertEqual(auswerten('max("a", "b")'), 'b')
        self.assertIn("'max' kann Werte dieser Typen nicht vergleichen", self.fehler('max([1, "a"])', TypeError))

    def test_max_mit_schluessel(self):
        self.assertEqual(auswerten('max(["bb", "a", "ccc", "dd"], schluessel=laenge)'), 'ccc')
        self.assertEqual(auswerten('max([-9, 3, 5], schluessel=abs)'), -9)

    def test_min_mit_schluessel(self):
        self.assertEqual(auswerten('min(["bb", "a", "ccc"], schluessel=laenge)'), 'a')
        self.assertEqual(auswerten('min([-9, 3, -2], schluessel=funktion(x) -> abs(x))'), -2)

    def test_mehrere_einzelne_argumente(self):
        self.assertEqual(auswerten('max("ab", "c", "def", schluessel=laenge)'), 'def')
        self.assertEqual(auswerten('min(5, -7, 3, schlüssel=abs)'), 3)

    def test_gleichstand_gewinnt_das_erste(self):
        self.assertEqual(auswerten('max(["ab", "cd", "e"], schluessel=laenge)'), 'ab')
        self.assertEqual(auswerten('min(["ab", "c", "d"], schluessel=laenge)'), 'c')

    def test_woerterbuecher_nach_feld(self):
        code = '''
sei p = [{"n": "Bo", "a": 30}, {"n": "Al", "a": 25}]
[max(p, schluessel=funktion(x) -> x["a"])["n"], min(p, schlüssel=funktion(x) -> x["a"])["n"]]
'''
        self.assertEqual(auswerten(code), ['Bo', 'Al'])

    def test_schluessel_nichts(self):
        self.assertEqual(auswerten('max([1, 3, 2], schluessel=nichts)'), 3)

    def test_fehler_schluessel_keine_funktion(self):
        self.assertIn("'max' erwartet für 'schluessel' eine Funktion, bekam Ganzzahl",
                      self.fehler('max([1, 2], schluessel=1)', TypeError))
        self.assertIn("'min' erwartet für 'schlüssel' eine Funktion, bekam Liste",
                      self.fehler('min([1, 2], schlüssel=[])', TypeError))

    def test_fehler_schluessel_falsche_parameterzahl(self):
        text = self.fehler('max([1, 2], schluessel=funktion(a, b) -> a)', TypeError)
        self.assertIn("'max': Die übergebene Funktion erwartet genau 2 Argumente", text)

    def test_fehler_unbekanntes_keyword_und_umgekehrt(self):
        self.assertIn("'max' hat kein Parameter 'foo'", self.fehler('max([1], foo=1)', TypeError))
        # 'umgekehrt' gibt es nur bei sortiere
        self.assertIn("'min' hat kein Parameter 'umgekehrt'", self.fehler('min([1], umgekehrt=wahr)', TypeError))

    def test_fehler_leere_liste_und_keine_argumente(self):
        self.assertIn("'max' erwartet eine nicht-leere Liste", self.fehler('max([], schluessel=laenge)', ValueError))
        self.assertIn("'min' erwartet mindestens 1 Argument", self.fehler('min(schluessel=laenge)', TypeError))

    def test_fehler_nicht_vergleichbare_schluessel(self):
        text = self.fehler('max([1, 2], schluessel=funktion(x) -> 1 wenn x == 1 sonst "a")', TypeError)
        self.assertIn("'max' kann Schlüsselwerte dieser Typen nicht vergleichen: Ganzzahl, Zeichenkette", text)

    def test_fehler_im_schluessel_wird_durchgereicht(self):
        self.assertIn('Division durch Null',
                      self.fehler('min([1, 0], schluessel=funktion(x) -> 1 / x)', ZeroDivisionError))


# ---------------------------------------------------------------------------
# 4. Abschließendes Komma
# ---------------------------------------------------------------------------

class TestAbschliessendesKomma(_Basis):
    def test_aufruf(self):
        self.assertEqual(auswerten('funktion f(a, b) { zurück a + b }\nf(1, 2,)'), 3)
        self.assertEqual(auswerten('funktion f(a) { zurück a }\nf(5,)'), 5)

    def test_aufruf_mit_keywords(self):
        self.assertEqual(auswerten('funktion f(a, b = 0) { zurück a - b }\nf(10, b = 4,)'), 6)

    def test_aufruf_mehrzeilig(self):
        code = '''
funktion f(a, b) { zurück a * b }
f(
    3,
    4,
)
'''
        self.assertEqual(auswerten(code), 12)

    def test_eingebaute_funktion_und_neu(self):
        self.assertEqual(auswerten('max(1, 5, 3,)'), 5)
        code = 'klasse P { funktion __init__(dies, a, b) { dies.s = a + b } }\n(neu P(1, 2,)).s'
        self.assertEqual(auswerten(code), 3)

    def test_parameterliste(self):
        self.assertEqual(auswerten('funktion f(a, b,) { zurück a + b }\nf(1, 2)'), 3)
        self.assertEqual(auswerten('funktion f(a,) { zurück a }\nf(7)'), 7)
        self.assertEqual(auswerten('funktion f(a, b = 5,) { zurück a + b }\nf(1)'), 6)

    def test_parameterliste_mit_variadischem_parameter(self):
        self.assertEqual(auswerten('funktion f(a, *rest,) { zurück laenge(rest) }\nf(1, 2, 3)'), 2)

    def test_parameterliste_mehrzeilig(self):
        code = '''
funktion f(
    a,
    b,
) { zurück a - b }
f(5, 2)
'''
        self.assertEqual(auswerten(code), 3)

    def test_lambda_parameterliste(self):
        self.assertEqual(auswerten('(funktion(a, b,) -> a + b)(1, 2)'), 3)
        self.assertEqual(auswerten('(funktion(a, b,) { zurück a + b })(1, 2)'), 3)

    def test_liste(self):
        self.assertEqual(auswerten('[1, 2, 3,]'), [1, 2, 3])
        self.assertEqual(auswerten('[1,]'), [1])
        self.assertEqual(auswerten('[\n    1,\n    2,\n]'), [1, 2])

    def test_woerterbuch(self):
        self.assertEqual(auswerten('{"a": 1, "b": 2,}'), {'a': 1, 'b': 2})
        self.assertEqual(auswerten('{"a": 1,}'), {'a': 1})
        self.assertEqual(auswerten('{\n    "a": 1,\n    "b": 2,\n}'), {'a': 1, 'b': 2})

    def test_menge(self):
        self.assertEqual(auswerten('{1, 2, 3,}'), {1, 2, 3})

    def test_fehler_nur_komma(self):
        for code in ('drucke(,)', 'funktion f(,) { }', '[,]', '{,}'):
            with self.assertRaises(SyntaxError, msg=code):
                parse(code)

    def test_fehler_doppeltes_komma(self):
        for code in ('drucke(1,,)', 'drucke(1,, 2)', 'funktion f(a,,b) { }', 'funktion f(a,,) { }', '[1,,2]',
                     '{"a": 1,,}'):
            with self.assertRaises(SyntaxError, msg=code):
                parse(code)

    def test_fehler_komma_nach_variadischem_parameter_mit_weiterem_parameter(self):
        with self.assertRaises(SyntaxError):
            parse('funktion f(*a, b) { }')

    def test_fehler_positional_nach_keyword_bleibt(self):
        with self.assertRaises(SyntaxError) as ctx:
            parse('f(a = 1, 2,)')
        self.assertIn('Positionale Argumente müssen vor Keyword-Argumenten stehen', str(ctx.exception))


# ---------------------------------------------------------------------------
# 5. Reste in der {…}-Interpolation
# ---------------------------------------------------------------------------

class TestInterpolationRest(_Basis):
    def test_rest_ist_syntaxfehler(self):
        with self.assertRaises(SyntaxError) as ctx:
            parse('sei t = "{1 2}"')
        text = str(ctx.exception)
        self.assertIn('Zeile 1', text)
        self.assertIn("Ungültiger Ausdruck in der Interpolation '{1 2}'", text)
        self.assertIn("folgt unerwartet '2'", text)

    def test_weitere_reste(self):
        for code, rest in (('"{a b}"', "'b'"), ('"{1 + 2 3}"', "'3'"), ('''"{x 't'}"''', "'Zeichenkette'"),
                           ('"{1 wahr}"', "'wahr'"), ('"{1 )}"', "')'"), ('"{1 nichts}"', "'nichts'")):
            with self.assertRaises(SyntaxError, msg=code) as ctx:
                parse(code)
            self.assertIn('Interpolation', str(ctx.exception))
            self.assertIn(rest, str(ctx.exception))

    def test_rest_nennt_die_richtige_zeile(self):
        with self.assertRaises(SyntaxError) as ctx:
            parse('sei a = 1\nsei b = 2\nsei t = "x {a b} y"')
        self.assertIn('Zeile 3', str(ctx.exception))

    def test_fehler_wird_beim_parsen_gemeldet_nicht_erst_zur_laufzeit(self):
        with self.assertRaises(SyntaxError):
            ausgabe('drucke("vorher")\ndrucke("{1 2}")')

    def test_gueltige_interpolationen_unveraendert(self):
        self.assertEqual(auswerten('sei a = 2\n"a={a}"'), 'a=2')
        self.assertEqual(auswerten('"{1 + 2}"'), '3')
        self.assertEqual(auswerten('"{3.14159:.2f}"'), '3.14')
        self.assertEqual(auswerten('"{[1, 2][0]}"'), '1')
        self.assertEqual(auswerten('''sei d = {"k": 5}\n"{d['k']}"'''), '5')
        self.assertEqual(auswerten('"{ 1 + 1 }"'), '2')
        self.assertEqual(auswerten('"{wahr und falsch}"'), 'falsch')

    def test_mehrere_interpolationen_in_einer_zeichenkette(self):
        self.assertEqual(auswerten('sei a = 1\nsei b = 2\n"{a}-{b}"'), '1-2')
        with self.assertRaises(SyntaxError):
            parse('sei a = 1\nsei b = 2\n"{a}-{a b}"')


if __name__ == '__main__':
    unittest.main()
