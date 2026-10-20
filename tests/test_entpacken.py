# -*- coding: utf-8 -*-
"""
Tests für Entpacken und Destrukturierung:

  * Spread  f(*liste), f(**woerterbuch), [*a, *b], {**a, **b}, {*a, *b}
    (auch bei  neu K(…)  und Methoden)
  * **kwargs-Parameter:  funktion f(a, *rest, **optionen)
  * Destrukturierende Zuweisung an bestehende Variablen:  [a, b] = [b, a]
  * Rest-Muster  [kopf, *rest]  bei  sei, Zuweisung und  für  (auch verschachtelt)
  * Kettenzuweisung  a = b = 0   (und der Syntaxfehler bei  sei a = b = 0)

Ausführen mit:
    py -m unittest discover -s tests -p test_entpacken.py -v
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

    def syntaxfehler(self, code: str) -> str:
        """Erwartet einen Syntaxfehler beim Parsen und gibt dessen Text zurück."""
        with self.assertRaises(SyntaxError) as ctx:
            parse(code)
        return str(ctx.exception)


# ---------------------------------------------------------------------------
# 1. Spread in Aufrufen
# ---------------------------------------------------------------------------

class TestSpreadAufruf(_Basis):
    DEF = 'funktion f(a, b, c = 3) { zurück [a, b, c] }\n'

    def test_liste_als_positionale_argumente(self):
        self.assertEqual(auswerten(self.DEF + 'f(*[1, 2])'), [1, 2, 3])
        self.assertEqual(auswerten(self.DEF + 'sei l = [4, 5, 6]\nf(*l)'), [4, 5, 6])

    def test_gemischt_mit_normalen_argumenten(self):
        self.assertEqual(auswerten(self.DEF + 'f(1, *[2])'), [1, 2, 3])
        self.assertEqual(auswerten(self.DEF + 'f(*[1], 2, *[9])'), [1, 2, 9])

    def test_gemischt_mit_keyword_argumenten(self):
        self.assertEqual(auswerten(self.DEF + 'f(*[1, 2], c = 7)'), [1, 2, 7])

    def test_woerterbuch_als_keyword_argumente(self):
        self.assertEqual(auswerten(self.DEF + 'f(**{"a": 1, "b": 2})'), [1, 2, 3])
        self.assertEqual(auswerten(self.DEF + 'f(**{"a": 1, "b": 2, "c": 5})'), [1, 2, 5])

    def test_stern_und_doppelstern_zusammen(self):
        self.assertEqual(auswerten(self.DEF + 'f(1, *[2], **{"c": 8})'), [1, 2, 8])
        self.assertEqual(auswerten(self.DEF + 'f(*[1], b = 2, **{"c": 4})'), [1, 2, 4])
        self.assertEqual(auswerten(self.DEF + 'f(**{"a": 1}, b = 2)'), [1, 2, 3])

    def test_mehrere_doppelsterne(self):
        self.assertEqual(auswerten(self.DEF + 'f(**{"a": 1}, **{"b": 2})'), [1, 2, 3])

    def test_jede_sammlung_wird_entpackt(self):
        self.assertEqual(auswerten('funktion f(*x) { zurück x }\nf(*"abc")'), ['a', 'b', 'c'])
        self.assertEqual(auswerten('funktion f(*x) { zurück x }\nf(*{7})'), [7])
        self.assertEqual(auswerten('funktion f(*x) { zurück x }\nf(*{"k": 1})'), ['k'])
        self.assertEqual(auswerten('funktion f(*x) { zurück x }\nf(*[])'), [])

    def test_leeres_woerterbuch_bei_eingebauter_funktion(self):
        self.assertEqual(auswerten('max(*[1, 5, 3], **{})'), 5)

    def test_eingebaute_funktion_und_listenmethode(self):
        self.assertEqual(auswerten('max(*[1, 5, 3])'), 5)
        self.assertEqual(auswerten('sei l = []\nl.anhaengen(*[4])\nl'), [4])

    def test_methode(self):
        code = '''
klasse K {
    funktion __init__(dies, x) { dies.x = x }
    funktion plus(dies, a, b = 0) { zurück dies.x + a + b }
}
sei k = neu K(10)
[k.plus(*[1]), k.plus(*[1, 2]), k.plus(1, **{"b": 5})]
'''
        self.assertEqual(auswerten(code), [11, 13, 16])

    def test_neu_instanz(self):
        code = '''
klasse P {
    funktion __init__(dies, x, y = 0) { dies.x = x; dies.y = y }
}
sei a = neu P(*[1, 2])
sei b = neu P(**{"x": 3, "y": 4})
sei c = neu P(5, **{"y": 6})
[a.x, a.y, b.x, b.y, c.x, c.y]
'''
        self.assertEqual(auswerten(code), [1, 2, 3, 4, 5, 6])

    def test_auswertungsreihenfolge_links_nach_rechts(self):
        code = '''
sei spur = []
funktion m(x) { spur.anhaengen(x); zurück [x] }
funktion g(*a, **k) { zurück spur }
g(*m(1), *m(2), **{"z": m(3)[0]})
'''
        self.assertEqual(auswerten(code), [1, 2, 3])

    def test_mehrzeiliger_aufruf(self):
        code = 'funktion f(a, b) { zurück a - b }\nf(\n    *[9],\n    **{"b": 4},\n)'
        self.assertEqual(auswerten(code), 5)

    # ---- Fehler

    def test_stern_mit_falschem_typ(self):
        text = self.fehler(self.DEF + 'f(*5)', TypeError)
        self.assertIn("Entpacken mit '*' erwartet eine Liste, Menge, Zeichenkette oder ein Wörterbuch", text)
        self.assertIn('bekam Ganzzahl', text)
        self.assertIn('bekam Nichts', self.fehler(self.DEF + 'f(*nichts)', TypeError))

    def test_doppelstern_mit_falschem_typ(self):
        text = self.fehler(self.DEF + 'f(**[1, 2])', TypeError)
        self.assertIn("Entpacken mit '**' erwartet ein Wörterbuch", text)
        self.assertIn('bekam Liste', text)

    def test_doppelstern_schluessel_keine_zeichenketten(self):
        text = self.fehler(self.DEF + 'f(**{1: 2})', TypeError)
        self.assertIn('Zeichenketten als Schlüssel', text)

    def test_keyword_doppelt_angegeben(self):
        self.assertIn("Keyword-Argument 'a' mehrfach angegeben",
                      self.fehler(self.DEF + 'f(a = 1, **{"a": 2})', TypeError))
        self.assertIn("Keyword-Argument 'b' mehrfach angegeben",
                      self.fehler(self.DEF + 'f(**{"b": 1}, **{"b": 2})', TypeError))

    def test_unbekanntes_keyword_aus_woerterbuch(self):
        self.assertIn("hat kein Parameter 'zz'", self.fehler(self.DEF + 'f(1, 2, **{"zz": 1})', TypeError))

    def test_zu_viele_entpackte_argumente(self):
        self.assertIn('höchstens 3 Argument', self.fehler(self.DEF + 'f(*[1, 2, 3, 4])', TypeError))

    def test_stern_nach_keyword_ist_syntaxfehler(self):
        text = self.syntaxfehler(self.DEF + 'f(a = 1, *[2])')
        self.assertIn("Entpackte Argumente ('*') müssen vor Keyword-Argumenten stehen", text)
        self.assertIn('Zeile 2', text)

    def test_stern_nach_doppelstern_ist_syntaxfehler(self):
        self.assertIn('müssen vor Keyword-Argumenten stehen', self.syntaxfehler('f(**{}, *[1])'))

    def test_positional_nach_doppelstern_ist_syntaxfehler(self):
        self.assertIn('Positionale Argumente müssen vor Keyword-Argumenten stehen',
                      self.syntaxfehler('f(**{}, 1)'))


# ---------------------------------------------------------------------------
# 1b. Spread in Listen-, Wörterbuch- und Mengen-Literalen
# ---------------------------------------------------------------------------

class TestSpreadLiterale(_Basis):
    def test_liste(self):
        self.assertEqual(auswerten('sei a = [1, 2]\nsei b = [3]\n[*a, *b, 4]'), [1, 2, 3, 4])
        self.assertEqual(auswerten('[0, *[1, 2], 3]'), [0, 1, 2, 3])
        self.assertEqual(auswerten('[*[]]'), [])

    def test_liste_ist_eine_kopie(self):
        code = 'sei a = [1]\nsei b = [*a]\nb.anhaengen(2)\n[a, b]'
        self.assertEqual(auswerten(code), [[1], [1, 2]])

    def test_liste_aus_jeder_sammlung(self):
        self.assertEqual(auswerten('[*"abc"]'), ['a', 'b', 'c'])
        self.assertEqual(auswerten('[*{1}, *{"k": 1}]'), [1, 'k'])
        self.assertEqual(auswerten('[*bereich(3)]'), [0, 1, 2])

    def test_liste_mehrzeilig_mit_abschliessendem_komma(self):
        self.assertEqual(auswerten('sei a = [1]\n[\n    *a,\n    2,\n]'), [1, 2])

    def test_woerterbuch(self):
        self.assertEqual(auswerten('{**{"a": 1}, **{"b": 2}}'), {'a': 1, 'b': 2})

    def test_woerterbuch_spaetere_schluessel_gewinnen(self):
        self.assertEqual(auswerten('{**{"a": 1, "b": 1}, **{"b": 2}, "a": 3}'), {'a': 3, 'b': 2})
        self.assertEqual(auswerten('{"x": 0, **{"x": 5}}'), {'x': 5})

    def test_woerterbuch_gemischt(self):
        code = 'sei a = {"p": 1}\nsei b = {"q": 2}\n{**a, **b, "x": 1}'
        self.assertEqual(auswerten(code), {'p': 1, 'q': 2, 'x': 1})

    def test_woerterbuch_ist_eine_kopie(self):
        code = 'sei a = {"p": 1}\nsei b = {**a}\nb["q"] = 2\n[a, b]'
        self.assertEqual(auswerten(code), [{'p': 1}, {'p': 1, 'q': 2}])

    def test_woerterbuch_beliebige_schluessel(self):
        self.assertEqual(auswerten('{**{1: "a"}, 2: "b"}'), {1: 'a', 2: 'b'})

    def test_menge(self):
        self.assertEqual(auswerten('{*[1, 2], *[2, 3]}'), {1, 2, 3})
        self.assertEqual(auswerten('{0, *[1, 2], *{3}}'), {0, 1, 2, 3})
        self.assertIsInstance(auswerten('{*[1]}'), set)

    def test_leere_geschweifte_klammern_bleiben_woerterbuch(self):
        self.assertEqual(auswerten('{}'), {})
        self.assertEqual(auswerten('{**{}}'), {})

    def test_in_interpolation(self):
        self.assertEqual(ausgabe('sei a = [1, 2]\ndrucke("{[*a, 3]}")'), '[1, 2, 3]\n')

    # ---- Fehler

    def test_liste_falscher_typ(self):
        text = self.fehler('[*5]', TypeError)
        self.assertIn("Entpacken mit '*'", text)
        self.assertIn('bekam Ganzzahl', text)

    def test_woerterbuch_falscher_typ(self):
        text = self.fehler('{**[1]}', TypeError)
        self.assertIn("Entpacken mit '**' erwartet ein Wörterbuch", text)
        self.assertIn('bekam Liste', text)

    def test_menge_falscher_typ(self):
        self.assertIn("Entpacken mit '*'", self.fehler('{*5}', TypeError))

    def test_menge_unhashbare_elemente(self):
        self.assertIn('hashbar', self.fehler('{*[[1]]}', TypeError))

    def test_woerterbuch_und_menge_nicht_mischen(self):
        self.assertIn('Wörterbuch', self.syntaxfehler('{**{"a": 1}, 3}'))
        self.assertIn('Wörterbuch', self.syntaxfehler('{"a": 1, *[1]}'))
        self.assertIn('Menge', self.syntaxfehler('{1, "a": 2}'))
        self.assertIn('Menge', self.syntaxfehler('{*[1], **{"a": 1}}'))

    def test_stern_in_comprehension_ist_syntaxfehler(self):
        self.assertIn('Comprehension', self.syntaxfehler('[*[1] für x in [1]]'))

    def test_stern_allein_ist_syntaxfehler(self):
        with self.assertRaises(SyntaxError):
            parse('*a')


# ---------------------------------------------------------------------------
# 2. **kwargs-Parameter
# ---------------------------------------------------------------------------

class TestKwargsParameter(_Basis):
    def test_sammelt_ueberzaehlige_keywords(self):
        code = 'funktion f(a, **optionen) { zurück [a, optionen] }\nf(1, x = 2, y = 3)'
        self.assertEqual(auswerten(code), [1, {'x': 2, 'y': 3}])

    def test_ohne_ueberzaehlige_keywords_leeres_woerterbuch(self):
        code = 'funktion f(a, **optionen) { zurück optionen }\nf(1)'
        self.assertEqual(auswerten(code), {})

    def test_benannte_parameter_bleiben_benannt(self):
        code = 'funktion f(a, b = 2, **rest) { zurück [a, b, rest] }\nf(b = 5, a = 1, z = 9)'
        self.assertEqual(auswerten(code), [1, 5, {'z': 9}])

    def test_nur_kwargs(self):
        self.assertEqual(auswerten('funktion f(**k) { zurück k }\nf(a = 1)'), {'a': 1})

    def test_mit_variadischem_parameter(self):
        code = 'funktion f(a, *rest, **optionen) { zurück [a, rest, optionen] }\nf(1, 2, 3, x = 4)'
        self.assertEqual(auswerten(code), [1, [2, 3], {'x': 4}])

    def test_variadischer_name_als_keyword_landet_im_woerterbuch(self):
        code = 'funktion f(*rest, **k) { zurück [rest, k] }\nf(rest = 1)'
        self.assertEqual(auswerten(code), [[], {'rest': 1}])

    def test_aus_entpacktem_woerterbuch(self):
        code = 'funktion f(a, **k) { zurück [a, k] }\nf(**{"a": 1, "b": 2, "c": 3})'
        self.assertEqual(auswerten(code), [1, {'b': 2, 'c': 3}])

    def test_weiterreichen(self):
        code = '''
funktion innen(a, b = 0, c = 0) { zurück [a, b, c] }
funktion aussen(*args, **kw) { zurück innen(*args, **kw) }
aussen(1, c = 3)
'''
        self.assertEqual(auswerten(code), [1, 0, 3])

    def test_abschliessendes_komma(self):
        self.assertEqual(auswerten('funktion f(a, **k,) { zurück k }\nf(1, x = 2)'), {'x': 2})
        self.assertEqual(auswerten('funktion f(*a, **k,) { zurück [a, k] }\nf(1, x = 2)'), [[1], {'x': 2}])

    def test_mehrzeilige_parameterliste(self):
        code = 'funktion f(\n    a,\n    **k\n) { zurück k }\nf(1, x = 2)'
        self.assertEqual(auswerten(code), {'x': 2})

    def test_lambda_kurzform(self):
        self.assertEqual(auswerten('(funktion(**k) -> k)(a = 1)'), {'a': 1})
        self.assertEqual(auswerten('(funktion(x, **k) -> [x, k])(1, a = 2)'), [1, {'a': 2}])

    def test_methode_und_konstruktor(self):
        code = '''
klasse K {
    funktion __init__(dies, **felder) { dies.felder = felder }
    funktion mit(dies, a, **mehr) { zurück [a, mehr] }
}
sei k = neu K(x = 1, y = 2)
[k.felder, k.mit(7, z = 8)]
'''
        self.assertEqual(auswerten(code), [{'x': 1, 'y': 2}, [7, {'z': 8}]])

    def test_woerterbuch_ist_pro_aufruf_neu(self):
        code = '''
funktion f(**k) { k["n"] = 1; zurück k }
f()
f()
'''
        self.assertEqual(auswerten(code), {'n': 1})

    def test_typ_hinweis(self):
        self.assertEqual(auswerten('funktion f(**k: Woerterbuch) { zurück k }\nf(a = 1)'), {'a': 1})
        self.assertIn("Parameter 'k'", self.fehler('funktion f(**k: Liste) { zurück k }\nf(a = 1)', TypeError))

    def test_parameter_struktur_im_ast(self):
        baum = parse('funktion f(a, *r, **k) { }')
        definition = baum.anweisungen[0]
        self.assertEqual([p[0] for p in definition.parameter], ['a', 'r'])
        self.assertEqual(definition.kwargs_parameter, ('k', None))

    # ---- Fehler

    def test_unbekanntes_keyword_ohne_doppelstern_bleibt_fehler(self):
        text = self.fehler('funktion f(a) { zurück a }\nf(1, b = 2)', TypeError)
        self.assertIn("'f' hat kein Parameter 'b'", text)

    def test_variadischer_name_ohne_doppelstern_bleibt_fehler(self):
        text = self.fehler('funktion f(*r) { zurück r }\nf(r = 1)', TypeError)
        self.assertIn('kann nicht per Keyword gesetzt werden', text)

    def test_positionale_argumente_ohne_platz(self):
        text = self.fehler('funktion f(**k) { zurück k }\nf(1)', TypeError)
        self.assertIn('höchstens 0 Argument', text)

    def test_keyword_doppelt_mit_benanntem_parameter(self):
        text = self.fehler('funktion f(a, **k) { zurück a }\nf(1, a = 2)', TypeError)
        self.assertIn("mehrere Werte für Parameter 'a'", text)

    def test_doppelstern_muss_letzter_parameter_sein(self):
        text = self.syntaxfehler('funktion f(**k, a) { }')
        self.assertIn('**-Parameter muss der letzte Parameter sein', text)
        self.assertIn('Zeile 1', text)

    def test_nur_ein_doppelstern_parameter(self):
        self.assertIn('**-Parameter muss der letzte Parameter sein',
                      self.syntaxfehler('funktion f(**a, **b) { }'))

    def test_doppelstern_parameter_nicht_vor_stern_parameter(self):
        self.assertIn('**-Parameter muss der letzte Parameter sein',
                      self.syntaxfehler('funktion f(**a, *b) { }'))

    def test_normaler_parameter_nach_stern_parameter_bleibt_fehler(self):
        with self.assertRaises(SyntaxError):
            parse('funktion f(*a, b) { }')

    def test_doppelstern_parameter_ohne_standardwert(self):
        self.assertIn('keinen Standardwert', self.syntaxfehler('funktion f(**k = 1) { }'))

    def test_doppelter_parametername(self):
        self.assertIn("'a' ist doppelt vergeben", self.syntaxfehler('funktion f(a, **a) { }'))


# ---------------------------------------------------------------------------
# 3. Destrukturierende Zuweisung an bestehende Variablen
# ---------------------------------------------------------------------------

class TestDestrukturierendeZuweisung(_Basis):
    def test_tausch(self):
        self.assertEqual(auswerten('sei a = 1\nsei b = 2\n[a, b] = [b, a]\n[a, b]'), [2, 1])

    def test_rechte_seite_wird_vor_dem_zuweisen_ausgewertet(self):
        code = 'sei a = 1\nsei b = 2\nsei c = 3\n[a, b, c] = [c, a, b]\n[a, b, c]'
        self.assertEqual(auswerten(code), [3, 1, 2])

    def test_aus_funktionsergebnis(self):
        code = 'funktion zwei() { zurück [7, 8] }\nsei x = 0\nsei y = 0\n[x, y] = zwei()\n[x, y]'
        self.assertEqual(auswerten(code), [7, 8])

    def test_ergebnis_der_anweisung_ist_der_wert(self):
        self.assertEqual(auswerten('sei a = 0\nsei b = 0\n[a, b] = [1, 2]'), [1, 2])

    def test_in_funktion_auf_aeussere_variablen(self):
        code = '''
sei a = 1
sei b = 2
funktion tausche() { [a, b] = [b, a] }
tausche()
[a, b]
'''
        self.assertEqual(auswerten(code), [2, 1])

    def test_ziele_attribut_und_index(self):
        code = '''
klasse K { funktion __init__(dies) { dies.x = 0 } }
sei k = neu K()
sei liste = [5, 6]
[k.x, liste[0]] = [liste[1], 99]
[k.x, liste]
'''
        self.assertEqual(auswerten(code), [6, [99, 6]])

    def test_tausch_von_listenelementen(self):
        code = 'sei l = [1, 2, 3]\n[l[0], l[2]] = [l[2], l[0]]\nl'
        self.assertEqual(auswerten(code), [3, 2, 1])

    def test_ziel_in_woerterbuch(self):
        code = 'sei d = {"a": 1}\nsei x = 0\n[d["a"], x] = [5, 6]\n[d, x]'
        self.assertEqual(auswerten(code), [{'a': 5}, 6])

    def test_abschliessendes_komma(self):
        self.assertEqual(auswerten('sei a = 0\nsei b = 0\n[a, b,] = [1, 2]\n[a, b]'), [1, 2])

    def test_typ_hinweis_wird_geprueft(self):
        text = self.fehler('sei a: Ganzzahl = 1\nsei b = 2\n[a, b] = ["x", 6]', TypeError)
        self.assertIn("Variable 'a'", text)
        self.assertIn("erwartet Typ 'Ganzzahl'", text)

    def test_typ_hinweis_passend(self):
        self.assertEqual(auswerten('sei a: Ganzzahl = 1\nsei b = 2\n[a, b] = [5, "x"]\n[a, b]'), [5, 'x'])

    def test_konstante_wird_geprueft(self):
        text = self.fehler('konstante A = 1\nsei b = 2\n[A, b] = [5, 6]', TypeError)
        self.assertIn("'A' ist eine Konstante", text)

    def test_konstante_im_aeusseren_scope(self):
        code = 'konstante A = 1\nfunktion f() { sei b = 0\n[A, b] = [1, 2] }\nf()'
        self.assertIn('Konstante', self.fehler(code, TypeError))

    # ---- Fehler

    def test_unbekannter_name_ist_namensfehler(self):
        text = self.fehler('sei a = 1\n[a, zzz] = [1, 2]', NameError)
        self.assertIn("Variable 'zzz' ist nicht deklariert", text)
        self.assertIn("Neue Variablen mit 'sei' anlegen", text)

    def test_unbekannter_name_ändert_nichts(self):
        code = 'sei a = 1\nversuche { [a, zzz] = [5, 6] } fange e { }\na'
        self.assertEqual(auswerten(code), 1)

    def test_namensfehler_schlaegt_vorschlag_vor(self):
        text = self.fehler('sei anzahl = 1\nsei b = 0\n[anzhal, b] = [1, 2]', NameError)
        self.assertIn("meintest du 'anzahl'", text)

    def test_falsche_anzahl(self):
        text = self.fehler('sei a = 1\nsei b = 2\n[a, b] = [1]', TypeError)
        self.assertIn('Destrukturierung erwartet 2 Werte, bekam 1', text)
        text = self.fehler('sei a = 1\nsei b = 2\n[a, b] = [1, 2, 3]', TypeError)
        self.assertIn('Destrukturierung erwartet 2 Werte, bekam 3', text)

    def test_falsche_anzahl_ändert_nichts(self):
        code = 'sei a = 1\nsei b = 2\nversuche { [a, b] = [7] } fange e { }\n[a, b]'
        self.assertEqual(auswerten(code), [1, 2])

    def test_kein_listenwert(self):
        text = self.fehler('sei a = 1\nsei b = 2\n[a, b] = 5', TypeError)
        self.assertIn('Destrukturierung erwartet eine Liste, bekam Ganzzahl', text)

    def test_ungueltiges_ziel_ist_syntaxfehler(self):
        text = self.syntaxfehler('[1, b] = [1, 2]')
        self.assertIn('Ungültige Zuweisung', text)
        self.assertIn('Zeile 1', text)

    def test_leeres_muster_ist_syntaxfehler(self):
        self.assertIn('Ungültige Zuweisung', self.syntaxfehler('[] = [1]'))

    def test_verbundzuweisung_an_muster_ist_syntaxfehler(self):
        self.assertIn('Ungültige Verbund-Zuweisung', self.syntaxfehler('[a, b] += 1'))

    def test_listen_ausdruck_ist_kein_ziel(self):
        self.assertIn('Ungültige Zuweisung', self.syntaxfehler('[x für x in [1]] = [1]'))


# ---------------------------------------------------------------------------
# 4. Rest-Muster und verschachtelte Muster
# ---------------------------------------------------------------------------

class TestRestMuster(_Basis):
    def test_sei_kopf_und_rest(self):
        self.assertEqual(auswerten('sei [kopf, *rest] = [1, 2, 3]\n[kopf, rest]'), [1, [2, 3]])

    def test_sei_erstes_mitte_letztes(self):
        code = 'sei [erstes, *mitte, letztes] = [1, 2, 3, 4, 5]\n[erstes, mitte, letztes]'
        self.assertEqual(auswerten(code), [1, [2, 3, 4], 5])

    def test_rest_darf_leer_sein(self):
        self.assertEqual(auswerten('sei [a, *r] = [1]\n[a, r]'), [1, []])
        self.assertEqual(auswerten('sei [a, *m, z] = [1, 2]\n[a, m, z]'), [1, [], 2])

    def test_nur_rest(self):
        self.assertEqual(auswerten('sei [*alle] = [1, 2]\nalle'), [1, 2])
        self.assertEqual(auswerten('sei [*alle] = []\nalle'), [])

    def test_rest_am_anfang(self):
        self.assertEqual(auswerten('sei [*vorn, z] = [1, 2, 3]\n[vorn, z]'), [[1, 2], 3])

    def test_rest_ist_eine_kopie(self):
        code = 'sei q = [1, 2, 3]\nsei [a, *r] = q\nr.anhaengen(9)\nq'
        self.assertEqual(auswerten(code), [1, 2, 3])

    def test_zuweisung_mit_rest(self):
        code = 'sei a = 0\nsei b = 0\n[a, *b] = [7, 8, 9]\n[a, b]'
        self.assertEqual(auswerten(code), [7, [8, 9]])

    def test_zuweisung_rest_in_der_mitte(self):
        code = 'sei a = 0\nsei m = 0\nsei z = 0\n[a, *m, z] = [1, 2, 3, 4]\n[a, m, z]'
        self.assertEqual(auswerten(code), [1, [2, 3], 4])

    def test_zuweisung_rest_an_attribut_und_index(self):
        code = '''
klasse K { funktion __init__(dies) { dies.r = nichts } }
sei k = neu K()
sei l = [0, 0]
[l[0], *k.r] = [1, 2, 3]
[l, k.r]
'''
        self.assertEqual(auswerten(code), [[1, 0], [2, 3]])

    def test_fuer_schleife(self):
        code = '''
sei ausgabe = []
für [k, *r] in [[1, 2, 3], [4], [5, 6]] { ausgabe.anhaengen([k, r]) }
ausgabe
'''
        self.assertEqual(auswerten(code), [[1, [2, 3]], [4, []], [5, [6]]])

    def test_fuer_schleife_mit_aufzaehlen(self):
        code = 'sei s = []\nfür [i, *w] in aufzaehlen(["a", "b"]) { s.anhaengen([i, w]) }\ns'
        self.assertEqual(auswerten(code), [[0, ['a']], [1, ['b']]])

    def test_listen_comprehension(self):
        self.assertEqual(auswerten('[k für [k, *r] in [[1, 2], [3]]]'), [1, 3])
        self.assertEqual(auswerten('[laenge(r) für [k, *r] in [[1, 2, 3], [3]]]'), [2, 0])

    def test_verschachtelt_sei(self):
        self.assertEqual(auswerten('sei [a, [b, c]] = [1, [2, 3]]\n[a, b, c]'), [1, 2, 3])

    def test_verschachtelt_mit_rest_innen_und_aussen(self):
        code = 'sei [a, [b, *c], *d] = [1, [2, 3, 4], 5, 6]\n[a, b, c, d]'
        self.assertEqual(auswerten(code), [1, 2, [3, 4], [5, 6]])

    def test_verschachtelt_fuer(self):
        code = 'sei s = []\nfür [n, [x, y]] in [[1, [2, 3]], [4, [5, 6]]] { s.anhaengen(n + x + y) }\ns'
        self.assertEqual(auswerten(code), [6, 15])

    def test_verschachtelt_zuweisung(self):
        code = 'sei a = 0\nsei b = 0\nsei c = 0\n[a, [b, c]] = [1, [2, 3]]\n[a, b, c]'
        self.assertEqual(auswerten(code), [1, 2, 3])

    def test_abschliessendes_komma(self):
        self.assertEqual(auswerten('sei [a, *r,] = [1, 2]\n[a, r]'), [1, [2]])

    def test_muster_im_ast(self):
        baum = parse('sei [a, *r, [b, c]] = x')
        muster = baum.anweisungen[0].muster
        self.assertIsInstance(muster, ast.Muster)
        self.assertEqual(muster.rest, 1)
        self.assertEqual(muster.ziele[:2], ['a', 'r'])
        self.assertIsInstance(muster.ziele[2], ast.Muster)

    # ---- Fehler

    def test_zu_wenige_werte_nennt_die_anzahl(self):
        text = self.fehler('sei [a, *b, c] = [1]', TypeError)
        self.assertIn('Destrukturierung erwartet mindestens 2 Werte, bekam 1', text)

    def test_zu_wenige_werte_einzahl(self):
        text = self.fehler('sei [a, *b] = []', TypeError)
        self.assertIn('Destrukturierung erwartet mindestens 1 Wert, bekam 0', text)

    def test_zu_wenige_werte_bei_zuweisung(self):
        text = self.fehler('sei a = 0\nsei b = 0\nsei c = 0\n[a, *b, c] = [1]', TypeError)
        self.assertIn('mindestens 2 Werte, bekam 1', text)

    def test_zu_wenige_werte_in_der_schleife(self):
        text = self.fehler('für [a, *b, c] in [[1]] { }', TypeError)
        self.assertIn('mindestens 2 Werte, bekam 1', text)

    def test_rest_muss_zu_einer_liste_passen(self):
        self.assertIn('Destrukturierung erwartet eine Liste, bekam Ganzzahl',
                      self.fehler('sei [a, *b] = 5', TypeError))

    def test_zwei_sterne_bei_sei(self):
        text = self.syntaxfehler('sei [a, *b, *c] = [1, 2, 3]')
        self.assertIn("höchstens ein '*'", text)

    def test_zwei_sterne_bei_zuweisung(self):
        text = self.syntaxfehler('[a, *b, *c] = [1, 2, 3]')
        self.assertIn("höchstens ein '*'", text)
        self.assertIn('Zeile 1', text)

    def test_zwei_sterne_bei_fuer(self):
        self.assertIn("höchstens ein '*'", self.syntaxfehler('für [a, *b, *c] in [[1]] { }'))

    def test_stern_hinter_stern_ist_kein_ziel(self):
        self.assertIn('Hinter', self.syntaxfehler('[a, *[b, c]] = [1, 2]'))

    def test_verschachtelt_falscher_typ(self):
        text = self.fehler('sei [a, [b, c]] = [1, 2]', TypeError)
        self.assertIn('Destrukturierung erwartet eine Liste, bekam Ganzzahl', text)

    def test_verschachtelt_falsche_anzahl(self):
        text = self.fehler('sei [a, [b, c]] = [1, [2]]', TypeError)
        self.assertIn('Destrukturierung erwartet 2 Werte, bekam 1', text)

    def test_leeres_muster_bei_sei_bleibt_syntaxfehler(self):
        with self.assertRaises(SyntaxError):
            parse('sei [] = [1]')


# ---------------------------------------------------------------------------
# 5. Kettenzuweisung
# ---------------------------------------------------------------------------

class TestKettenzuweisung(_Basis):
    def test_zwei_variablen(self):
        self.assertEqual(auswerten('sei a = 1\nsei b = 2\na = b = 0\n[a, b]'), [0, 0])

    def test_drei_variablen(self):
        self.assertEqual(auswerten('sei a = 1\nsei b = 2\nsei c = 3\na = b = c = 9\n[a, b, c]'), [9, 9, 9])

    def test_rechte_seite_wird_einmal_ausgewertet(self):
        code = '''
sei n = 0
funktion zaehle() { n += 1; zurück n }
sei a = 0
sei b = 0
a = b = zaehle()
[a, b, n]
'''
        self.assertEqual(auswerten(code), [1, 1, 1])

    def test_ergebnis_ist_der_wert(self):
        self.assertEqual(auswerten('sei a = 0\nsei b = 0\na = b = 5'), 5)

    def test_gemeinsames_objekt(self):
        code = 'sei a = 0\nsei b = 0\na = b = []\na.anhaengen(1)\n[a, b]'
        self.assertEqual(auswerten(code), [[1], [1]])

    def test_mit_attribut_und_index(self):
        code = '''
klasse K { funktion __init__(dies) { dies.x = 0 } }
sei k = neu K()
sei l = [0, 0]
sei v = 0
v = k.x = l[1] = 4
[v, k.x, l]
'''
        self.assertEqual(auswerten(code), [4, 4, [0, 4]])

    def test_mit_muster(self):
        code = 'sei a = 0\nsei b = 0\nsei z = 0\nz = [a, b] = [1, 2]\n[a, b, z]'
        self.assertEqual(auswerten(code), [1, 2, [1, 2]])

    def test_typ_hinweis_und_konstante(self):
        text = self.fehler('sei a: Ganzzahl = 1\nsei b = 0\nb = a = "x"', TypeError)
        self.assertIn("erwartet Typ 'Ganzzahl'", text)
        text = self.fehler('konstante A = 1\nsei b = 0\nb = A = 2', TypeError)
        self.assertIn('Konstante', text)

    def test_in_funktion_auf_aeussere_variablen(self):
        code = 'sei a = 1\nsei b = 2\nfunktion setze() { a = b = 7 }\nsetze()\n[a, b]'
        self.assertEqual(auswerten(code), [7, 7])

    # ---- Fehler

    def test_unbekannter_name_hinten(self):
        text = self.fehler('sei a = 1\na = b = 0', NameError)
        self.assertIn("Variable 'b' ist nicht deklariert", text)
        self.assertIn("mit 'sei' anlegen", text)

    def test_unbekannter_name_vorn(self):
        text = self.fehler('sei b = 1\na = b = 0', NameError)
        self.assertIn("Variable 'a' ist nicht deklariert", text)

    def test_unbekannter_name_ändert_nichts(self):
        code = 'sei a = 1\nversuche { a = zzz = 0 } fange e { }\na'
        self.assertEqual(auswerten(code), 1)

    def test_sei_kette_ist_syntaxfehler_mit_hinweis(self):
        text = self.syntaxfehler('sei a = b = 0')
        self.assertIn('Kettenzuweisung', text)
        self.assertIn("jede Variable einzeln mit 'sei' an", text)
        self.assertIn('Zeile 1', text)

    def test_sei_kette_mit_typ_hinweis(self):
        self.assertIn('Kettenzuweisung', self.syntaxfehler('sei a: Ganzzahl = b = 0'))

    def test_sei_kette_in_zeile_drei(self):
        self.assertIn('Zeile 3', self.syntaxfehler('sei x = 1\nsei y = 2\nsei a = b = 0'))

    def test_konstante_kette_ist_syntaxfehler(self):
        text = self.syntaxfehler('konstante a = b = 0')
        self.assertIn('Kettenzuweisung', text)
        self.assertIn("'konstante'", text)

    def test_sei_muster_kette_ist_syntaxfehler(self):
        self.assertIn('Kettenzuweisung', self.syntaxfehler('sei [a, b] = c = [1, 2]'))

    def test_ungueltiges_ziel_in_kette(self):
        with self.assertRaises(SyntaxError):
            parse('sei a = 0\na = 1 = 2')

    def test_vergleich_ist_keine_kette(self):
        self.assertEqual(auswerten('sei a = 1\nsei b = (a == 1)\nb'), True)


# ---------------------------------------------------------------------------
# Regression: bisheriges Verhalten bleibt
# ---------------------------------------------------------------------------

class TestBisherigesVerhalten(_Basis):
    def test_einfache_zuweisung_und_verbund(self):
        self.assertEqual(auswerten('sei a = 1\na = 2\na += 3\na'), 5)

    def test_zuweisung_an_unbekannten_namen_bleibt_namensfehler(self):
        self.assertIn("mit 'sei' anlegen", self.fehler('x = 1', NameError))

    def test_sei_destrukturierung_und_fuer(self):
        self.assertEqual(auswerten('sei [a, b] = [1, 2]\n[a, b]'), [1, 2])
        self.assertEqual(auswerten('sei s = 0\nfür [a, b] in [[1, 2], [3, 4]] { s += a * b }\ns'), 14)

    def test_alte_anzahlmeldung(self):
        self.assertIn('Destrukturierung erwartet 2 Werte, bekam 3',
                      self.fehler('sei [p, q] = [1, 2, 3]', TypeError))

    def test_listenliteral_wie_zuvor(self):
        self.assertEqual(auswerten('[1, 2 * 3, [4]]'), [1, 6, [4]])
        self.assertEqual(auswerten('2 * 3'), 6)
        self.assertEqual(auswerten('2 ** 3'), 8)

    def test_ausdruecke_mit_stern_bleiben_malnehmen(self):
        self.assertEqual(auswerten('funktion f(a, b) { zurück a * b }\nf(2, 3)'), 6)
        self.assertEqual(auswerten('[2 * 3]'), [6])

    def test_variadischer_parameter_wie_zuvor(self):
        self.assertEqual(auswerten('funktion f(a, *r) { zurück [a, r] }\nf(1, 2, 3)'), [1, [2, 3]])

    def test_woerterbuch_und_menge_wie_zuvor(self):
        self.assertEqual(auswerten('{"a": 1, "b": 2}'), {'a': 1, 'b': 2})
        self.assertEqual(auswerten('{1, 2, 2}'), {1, 2})


if __name__ == '__main__':
    unittest.main()
