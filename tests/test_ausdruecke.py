# -*- coding: utf-8 -*-
"""
Tests für neue Ausdrucks-Syntax:

  * Bit-Operatoren  & | ^ ~ << >>  (+ Verbund-Zuweisungen, Mengen-Operatoren)
  * Zahlliterale    0xFF, 0b101, 0o17, 1_000
  * Null-Koaleszenz a ?? b
  * Zeilenumbrüche innerhalb von ( ... )
  * Zeilennummern in Fehlern innerhalb von {...}-Interpolationen

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch import ast_knoten as ast
from deutsch.lexer import Lexer
from deutsch.parser import Parser, _TOKEN_ANZEIGE
from deutsch.interpreter import Interpreter
from deutsch.token_typen import TokenTyp


def parse(code: str):
    return Parser(Lexer(code).tokenisieren()).parse()


def ausgabe(code: str) -> str:
    """Führt Code aus und gibt das auf stdout Gedruckte zurück."""
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter().ausfuehren(parse(code))
    return puffer.getvalue()


def zeile_von(code: str) -> str:
    """Wertet drucke(<code>) aus und gibt die Ausgabe ohne Zeilenende zurück."""
    return ausgabe(f'drucke({code})').rstrip('\n')


class _Basis(unittest.TestCase):
    def syntaxfehler(self, code: str) -> str:
        with self.assertRaises(SyntaxError) as ctx:
            ausgabe(code)
        return str(ctx.exception)


# ---------------------------------------------------------------------------
# 1. Bit-Operatoren
# ---------------------------------------------------------------------------

class TestBitOperatoren(_Basis):
    def test_ganzzahlen(self):
        self.assertEqual(zeile_von('6 & 3'), '2')
        self.assertEqual(zeile_von('6 | 3'), '7')
        self.assertEqual(zeile_von('6 ^ 3'), '5')
        self.assertEqual(zeile_von('1 << 4'), '16')
        self.assertEqual(zeile_von('256 >> 2'), '64')
        self.assertEqual(zeile_von('-8 >> 1'), '-4')

    def test_unaeres_tilde(self):
        self.assertEqual(zeile_von('~5'), '-6')
        self.assertEqual(zeile_von('~-1'), '0')
        self.assertEqual(zeile_von('-~5'), '6')
        self.assertEqual(zeile_von('~~7'), '7')

    def test_tilde_bindet_wie_unaeres_minus(self):
        # stärker als '+', schwächer als '**' (wie '-2 ** 2' = -4)
        self.assertEqual(zeile_von('~1 + 1'), '-1')       # (~1) + 1
        self.assertEqual(zeile_von('~2 ** 2'), '-5')      # ~(2 ** 2)

    def test_wahrheitswerte_zaehlen_als_ganzzahlen(self):
        self.assertEqual(zeile_von('wahr & falsch'), 'falsch')
        self.assertEqual(zeile_von('wahr | falsch'), 'wahr')

    # --- Vorrang: | < ^ < & < Schiebung < + -

    def test_vorrang_und_vor_oder(self):
        self.assertEqual(zeile_von('1 | 2 & 3'), '3')
        self.assertEqual(zeile_von('4 | 2 & 3'), '6')      # 4 | (2 & 3); links gelesen wäre es 2
        self.assertEqual(zeile_von('2 & 3 | 4'), '6')

    def test_vorrang_xor_zwischen_oder_und_und(self):
        self.assertEqual(zeile_von('1 | 2 ^ 3'), '1')      # 1 | (2 ^ 3); links gelesen: 0
        self.assertEqual(zeile_von('6 ^ 3 & 1'), '7')      # 6 ^ (3 & 1); links gelesen: 1

    def test_vorrang_schiebung_staerker_als_und(self):
        self.assertEqual(zeile_von('1 & 3 << 1'), '0')     # 1 & (3 << 1); links gelesen: 2

    def test_vorrang_addition_staerker_als_schiebung(self):
        self.assertEqual(zeile_von('1 + 2 << 1'), '6')     # (1 + 2) << 1
        self.assertEqual(zeile_von('2 << 1 + 1'), '8')     # 2 << (1 + 1)
        self.assertEqual(zeile_von('16 >> 1 + 1'), '4')

    def test_vorrang_schiebung_linksassoziativ(self):
        self.assertEqual(zeile_von('64 >> 2 >> 1'), '8')
        self.assertEqual(zeile_von('1 << 2 << 3'), '32')

    def test_vergleiche_binden_schwaecher_als_bit_operatoren(self):
        self.assertEqual(zeile_von('4 | 1 == 5'), 'wahr')  # (4 | 1) == 5
        self.assertEqual(zeile_von('3 & 1 == 1'), 'wahr')
        self.assertEqual(zeile_von('1 << 1 < 3'), 'wahr')  # (1 << 1) < 3

    def test_vergleiche_mit_kleiner_groesser_funktionieren_weiter(self):
        self.assertEqual(zeile_von('1 < 2'), 'wahr')
        self.assertEqual(zeile_von('2 <= 2'), 'wahr')
        self.assertEqual(zeile_von('3 > 2'), 'wahr')
        self.assertEqual(zeile_von('3 >= 4'), 'falsch')
        self.assertEqual(zeile_von('1 < 2 < 3'), 'wahr')
        self.assertEqual(ausgabe('sei a = 1\nsei b = 2\ndrucke(a<b, a<=b, a>b, a>=b)'),
                         'wahr wahr falsch falsch\n')

    def test_lexer_trennt_schiebung_von_vergleich(self):
        typen = [t.typ for t in Lexer('a << b <= c >> d >= e < f > g').tokenisieren()]
        self.assertEqual(
            [t for t in typen if t not in (TokenTyp.BEZEICHNER, TokenTyp.DATEIENDE)],
            [TokenTyp.KLEINER_KLEINER, TokenTyp.KLEINERGLEICH, TokenTyp.GROESSER_GROESSER,
             TokenTyp.GROESSERGLEICH, TokenTyp.KLEINER, TokenTyp.GROESSER])

    def test_bit_operatoren_im_vergleich_mit_nicht_und_und(self):
        self.assertEqual(zeile_von('nicht 1 & 2'), 'wahr')          # nicht (1 & 2) = nicht 0
        self.assertEqual(zeile_von('1 & 3 == 1 und 2 | 1 == 3'), 'wahr')

    # --- Verbund-Zuweisungen

    def test_verbund_zuweisungen(self):
        code = (
            'sei x = 5\n'
            'x &= 4\ndrucke(x)\n'      # 4
            'x |= 3\ndrucke(x)\n'      # 7
            'x ^= 1\ndrucke(x)\n'      # 6
            'x <<= 2\ndrucke(x)\n'     # 24
            'x >>= 1\ndrucke(x)\n'     # 12
        )
        self.assertEqual(ausgabe(code), '4\n7\n6\n24\n12\n')

    def test_verbund_zuweisung_auf_liste_und_attribut(self):
        code = (
            'sei l = [12, 1]\n'
            'l[0] &= 4\nl[1] <<= 3\n'
            'drucke(l)\n'
            'klasse K { funktion __init__(selbst) { selbst.w = 1 } }\n'
            'sei k = neu K()\n'
            'k.w |= 6\ndrucke(k.w)\n'
        )
        self.assertEqual(ausgabe(code), '[4, 8]\n7\n')

    def test_verbund_zuweisung_auf_unbekannte_variable(self):
        with self.assertRaises(NameError):
            ausgabe('y |= 1')

    def test_verbund_zuweisung_auf_ungueltiges_ziel(self):
        self.assertIn('Ungültige Verbund-Zuweisung', self.syntaxfehler('1 |= 2'))

    # --- Mengen

    def test_mengen_operatoren(self):
        self.assertEqual(zeile_von('{1, 2, 3} | {3, 4}'), '{1, 2, 3, 4}')
        self.assertEqual(zeile_von('{1, 2, 3} & {2, 3, 9}'), '{2, 3}')
        self.assertEqual(zeile_von('{1, 2, 3} ^ {3, 4}'), '{1, 2, 4}')

    def test_mengen_ergebnis_ist_neue_menge(self):
        code = 'sei a = {1, 2}\nsei b = {2, 3}\nsei c = a | b\nc.hinzufügen(9)\ndrucke(a, b, c)'
        self.assertEqual(ausgabe(code), '{1, 2} {2, 3} {1, 2, 3, 9}\n')

    def test_mengen_verbund_zuweisung(self):
        code = ('sei m = {1, 2, 3}\n'
                'm |= {5}\ndrucke(m)\n'
                'm &= {2, 3, 5, 8}\ndrucke(m)\n'
                'm ^= {3, 4}\ndrucke(m)\n')
        self.assertEqual(ausgabe(code), '{1, 2, 3, 5}\n{2, 3, 5}\n{2, 4, 5}\n')

    def test_mengen_vorrang_wie_ganzzahlen(self):
        self.assertEqual(zeile_von('{1} | {2, 3} & {3, 4}'), '{1, 3}')

    # --- Fehlerfälle: andere Typen -> deutscher TypeError

    def test_fehler_listen(self):
        with self.assertRaisesRegex(TypeError, "Operator '&' nicht unterstützt für Liste und Liste"):
            ausgabe('drucke([1] & [2])')

    def test_fehler_kommazahl(self):
        with self.assertRaisesRegex(TypeError, "Operator '\\|' nicht unterstützt für Kommazahl und Ganzzahl"):
            ausgabe('drucke(1.5 | 1)')

    def test_fehler_woerterbuch_wird_nicht_zusammengefuehrt(self):
        with self.assertRaisesRegex(TypeError, "Operator '\\|' nicht unterstützt für Woerterbuch und Woerterbuch"):
            ausgabe('drucke({"a": 1} | {"b": 2})')

    def test_fehler_zeichenkette_und_nichts(self):
        with self.assertRaisesRegex(TypeError, "Operator '<<' nicht unterstützt für Zeichenkette und Ganzzahl"):
            ausgabe('drucke("a" << 1)')
        with self.assertRaisesRegex(TypeError, "Operator '\\^' nicht unterstützt für Nichts und Ganzzahl"):
            ausgabe('drucke(nichts ^ 1)')

    def test_fehler_menge_mit_liste(self):
        with self.assertRaisesRegex(TypeError, "Operator '&' nicht unterstützt für Menge und Liste"):
            ausgabe('drucke({1} & [1])')

    def test_fehler_mengen_schiebung(self):
        with self.assertRaisesRegex(TypeError, "Operator '<<' nicht unterstützt für Menge und Menge"):
            ausgabe('drucke({1} << {2})')

    def test_fehler_unaeres_tilde(self):
        with self.assertRaisesRegex(TypeError, "Operator '~' nicht unterstützt für Zeichenkette"):
            ausgabe('drucke(~"a")')
        with self.assertRaisesRegex(TypeError, "Operator '~' nicht unterstützt für Kommazahl"):
            ausgabe('drucke(~1.5)')

    def test_fehler_instanz(self):
        code = 'klasse K { }\ndrucke(neu K() | 1)'
        with self.assertRaisesRegex(TypeError, "Operator '\\|' nicht unterstützt für K und Ganzzahl"):
            ausgabe(code)

    def test_fehler_negative_schiebezahl(self):
        with self.assertRaisesRegex(ValueError, 'Negative Schiebezahl'):
            ausgabe('drucke(1 << -1)')
        with self.assertRaisesRegex(ValueError, 'Negative Schiebezahl'):
            ausgabe('drucke(8 >> -2)')

    def test_fehler_zu_grosse_linksschiebung(self):
        with self.assertRaisesRegex(OverflowError, 'Linksschiebung ist zu groß'):
            ausgabe('drucke(1 << (1 << 70))')

    def test_fehler_fehlender_operand(self):
        self.assertIn('Zeile 1', self.syntaxfehler('drucke(1 &)'))
        self.assertIn('Zeile 1', self.syntaxfehler('sei a = 1 |'))
        self.assertIn('Zeile 1', self.syntaxfehler('sei a = <<'))


# ---------------------------------------------------------------------------
# 2. Zahlliterale
# ---------------------------------------------------------------------------

class TestZahlliterale(_Basis):
    def test_hex_bin_oktal(self):
        self.assertEqual(zeile_von('0xFF'), '255')
        self.assertEqual(zeile_von('0b101'), '5')
        self.assertEqual(zeile_von('0o17'), '15')

    def test_praefix_gross_und_kleinschreibung(self):
        self.assertEqual(zeile_von('0XfF'), '255')
        self.assertEqual(zeile_von('0B11'), '3')
        self.assertEqual(zeile_von('0O10'), '8')
        self.assertEqual(zeile_von('0xdeadBEEF'), str(0xDEADBEEF))

    def test_token_ist_ganzzahl(self):
        tokens = Lexer('0xFF 0b101 0o17').tokenisieren()
        self.assertEqual([(t.typ, t.wert) for t in tokens[:3]],
                         [(TokenTyp.GANZZAHL, 255), (TokenTyp.GANZZAHL, 5), (TokenTyp.GANZZAHL, 15)])

    def test_unterstriche_in_ganzzahlen(self):
        self.assertEqual(zeile_von('1_000'), '1000')
        self.assertEqual(zeile_von('1_000_000'), '1000000')
        self.assertEqual(zeile_von('0xFF_FF'), '65535')
        self.assertEqual(zeile_von('0b1010_0101'), '165')
        self.assertEqual(zeile_von('0o7_7'), '63')

    def test_unterstriche_in_kommazahlen(self):
        self.assertEqual(zeile_von('3.141_59'), '3.14159')
        self.assertEqual(zeile_von('1_000.5'), '1000.5')
        self.assertEqual(zeile_von('1_0e1_0'), '100000000000')
        tokens = Lexer('3.141_59 1e-2 2.5E+1').tokenisieren()
        self.assertEqual([t.wert for t in tokens[:3]], [3.14159, 0.01, 25.0])
        self.assertTrue(all(t.typ == TokenTyp.KOMMAZAHL for t in tokens[:3]))

    def test_literale_in_ausdruecken(self):
        self.assertEqual(zeile_von('0xF0 | 0x0F'), '255')
        self.assertEqual(zeile_von('-0xFF'), '-255')
        self.assertEqual(zeile_von('0b1 << 0b11'), '8')
        self.assertEqual(zeile_von('[0x10, 1_0]'), '[16, 10]')

    def test_bezeichner_mit_unterstrich_unveraendert(self):
        self.assertEqual(ausgabe('sei _a = 1\nsei a_1 = 2\ndrucke(_a + a_1)'), '3\n')

    def test_fehler_praefix_ohne_ziffern(self):
        for code in ('0x', '0b', '0o', '0x_F'):
            with self.subTest(code=code):
                msg = self.syntaxfehler(f'sei a = {code}')
                self.assertIn('Zeile 1', msg)
                self.assertIn('braucht mindestens eine Ziffer', msg)

    def test_fehler_ungueltige_ziffer(self):
        self.assertIn("Ungültiges Zeichen '2' in Binärzahl", self.syntaxfehler('sei a = 0b102'))
        self.assertIn("Ungültiges Zeichen 'g' in Hexadezimalzahl", self.syntaxfehler('sei a = 0xFFg'))
        self.assertIn("Oktalzahl", self.syntaxfehler('sei a = 0o178'))

    def test_fehler_unterstrich(self):
        for code in ('1__0', '1_', '1_000_', '1_.5', '1.5_', '3.14__15', '1e5_', '0xFF_', '0b1__0'):
            with self.subTest(code=code):
                msg = self.syntaxfehler(f'sei a = {code}')
                self.assertIn('Zeile 1', msg)
                self.assertIn('Unterstrich', msg)

    def test_fehler_zeilennummer(self):
        self.assertIn('Zeile 3', self.syntaxfehler('sei a = 1\nsei b = 2\nsei c = 0x'))


# ---------------------------------------------------------------------------
# 3. Null-Koaleszenz
# ---------------------------------------------------------------------------

class TestNullKoaleszenz(_Basis):
    def test_nichts_wird_ersetzt(self):
        self.assertEqual(zeile_von('nichts ?? 5'), '5')
        self.assertEqual(ausgabe('sei a = nichts\ndrucke(a ?? "x")'), 'x\n')

    def test_andere_werte_bleiben(self):
        self.assertEqual(zeile_von('3 ?? 5'), '3')
        self.assertEqual(zeile_von('"a" ?? "b"'), 'a')

    def test_falsy_werte_sind_nicht_nichts(self):
        self.assertEqual(zeile_von('0 ?? 5'), '0')
        self.assertEqual(zeile_von('falsch ?? wahr'), 'falsch')
        self.assertEqual(zeile_von('"" ?? "b"'), '')
        self.assertEqual(zeile_von('[] ?? [1]'), '[]')

    def test_kette(self):
        self.assertEqual(zeile_von('nichts ?? nichts ?? 7'), '7')
        self.assertEqual(zeile_von('nichts ?? 4 ?? 7'), '4')
        self.assertEqual(zeile_von('nichts ?? nichts ?? nichts'), 'nichts')

    def test_rechte_seite_nur_bei_bedarf(self):
        code = (
            'sei zaehler = 0\n'
            'funktion teuer() { zaehler += 1\n zurück 99 }\n'
            'sei a = 1 ?? teuer()\n'
            'sei b = nichts ?? teuer()\n'
            'drucke(a, b, zaehler)\n'
        )
        self.assertEqual(ausgabe(code), '1 99 1\n')

    def test_linke_seite_nur_einmal(self):
        code = (
            'sei zaehler = 0\n'
            'funktion quelle() { zaehler += 1\n zurück nichts }\n'
            'sei r = quelle() ?? 5\n'
            'drucke(r, zaehler)\n'
        )
        self.assertEqual(ausgabe(code), '5 1\n')

    def test_rechts_ungueltig_wird_nicht_ausgewertet(self):
        self.assertEqual(zeile_von('1 ?? (1 / 0)'), '1')
        with self.assertRaises(ZeroDivisionError):
            ausgabe('drucke(nichts ?? (1 / 0))')

    def test_vorrang_unterhalb_von_oder(self):
        # a ?? (b oder c): 0 ist nicht 'nichts', bleibt also stehen (wäre es (a ?? b) oder c: 2)
        self.assertEqual(zeile_von('0 ?? 1 oder 2'), '0')
        self.assertEqual(zeile_von('nichts ?? falsch oder 7'), '7')
        e = parse('a ?? b oder c').anweisungen[0]
        self.assertIsInstance(e, ast.BinaereOperation)
        self.assertEqual(e.operator, '??')
        self.assertIsInstance(e.rechts, ast.BinaereOperation)
        self.assertEqual(e.rechts.operator, 'oder')

    def test_oder_links_von_koaleszenz(self):
        e = parse('a oder b ?? c').anweisungen[0]
        self.assertEqual(e.operator, '??')
        self.assertEqual(e.links.operator, 'oder')

    def test_vorrang_oberhalb_des_ternaers(self):
        e = parse('a ?? b wenn c sonst d').anweisungen[0]
        self.assertIsInstance(e, ast.TernaerAusdruck)
        self.assertEqual(e.dann_wert.operator, '??')
        e = parse('a wenn b ?? c sonst d').anweisungen[0]
        self.assertIsInstance(e, ast.TernaerAusdruck)
        self.assertEqual(e.bedingung.operator, '??')
        self.assertEqual(zeile_von('"ja" wenn nichts ?? wahr sonst "nein"'), 'ja')
        self.assertEqual(zeile_von('nichts ?? 1 wenn falsch sonst 2'), '2')

    def test_vorrang_gegenueber_vergleich_und_arithmetik(self):
        self.assertEqual(zeile_von('nichts ?? 1 + 2'), '3')
        self.assertEqual(zeile_von('(nichts ?? 3) == 3'), 'wahr')
        self.assertEqual(zeile_von('nichts ?? 3 == 3'), 'wahr')      # nichts ?? (3 == 3)

    def test_zusammen_mit_attribut_und_index(self):
        code = ('sei d = {"a": 1}\n'
                'drucke(d.hole("b") ?? "leer", d.hole("a") ?? "leer")\n')
        self.assertEqual(ausgabe(code), 'leer 1\n')

    def test_in_interpolation(self):
        self.assertEqual(ausgabe('sei n = nichts\ndrucke("Name: {n ?? \'?\'}")'), 'Name: ?\n')

    def test_fehler_einzelnes_fragezeichen(self):
        msg = self.syntaxfehler('sei a = 1 ? 2')
        self.assertIn('Zeile 1', msg)
        self.assertIn("'??'", msg)

    def test_fehler_fehlender_operand(self):
        self.assertIn('Zeile 1', self.syntaxfehler('sei a = 1 ??'))
        self.assertIn('Zeile 1', self.syntaxfehler('sei a = ?? 1'))


# ---------------------------------------------------------------------------
# 4. Zeilenumbrüche innerhalb von Klammern
# ---------------------------------------------------------------------------

class TestMehrzeiligeKlammern(_Basis):
    def test_aufruf_argumente(self):
        code = 'drucke(\n    1,\n    2,\n    3\n)'
        self.assertEqual(ausgabe(code), '1 2 3\n')

    def test_umbruch_nach_komma_und_vor_klammer_zu(self):
        self.assertEqual(ausgabe('drucke(1,\n 2\n)'), '1 2\n')
        self.assertEqual(ausgabe('drucke(\n1, 2)'), '1 2\n')
        self.assertEqual(ausgabe('drucke(1, 2\n)'), '1 2\n')

    def test_umbruch_mitten_im_ausdruck(self):
        self.assertEqual(ausgabe('drucke(1 +\n 2 *\n 3)'), '7\n')
        self.assertEqual(ausgabe('drucke(1\n + 2)'), '3\n')

    def test_keyword_argumente(self):
        code = (
            'funktion f(a, b = 10) { zurück a + b }\n'
            'drucke(f(\n    1,\n    b =\n 5\n))\n'
        )
        self.assertEqual(ausgabe(code), '6\n')
        code = 'funktion f(a, b = 10) { zurück a + b }\ndrucke(f(1, b\n= 7))'
        self.assertEqual(ausgabe(code), '8\n')

    def test_umbruch_in_nicht_in(self):
        self.assertEqual(ausgabe('drucke(5 nicht\n in [1, 2])'), 'wahr\n')
        self.assertEqual(ausgabe('drucke(1\n in\n [1, 2])'), 'wahr\n')

    def test_geklammerter_ausdruck(self):
        self.assertEqual(ausgabe('sei x = (\n    1 +\n    2\n)\ndrucke(x)'), '3\n')
        self.assertEqual(ausgabe('drucke((1 +\n2) * 2)'), '6\n')

    def test_parameterliste_funktion(self):
        code = (
            'funktion addiere(\n    a,\n    b = 2,\n    *rest\n) {\n    zurück a + b\n}\n'
            'drucke(addiere(1))'
        )
        self.assertEqual(ausgabe(code), '3\n')

    def test_parameterliste_anonyme_funktion_und_rueckgabetyp(self):
        code = (
            'sei f = funktion(\n    a: Ganzzahl,\n    b: Ganzzahl\n) -> Ganzzahl {\n    zurück a * b\n}\n'
            'drucke(f(3, 4))'
        )
        self.assertEqual(ausgabe(code), '12\n')

    def test_parameterliste_methode(self):
        code = (
            'klasse K {\n'
            '    funktion __init__(\n        selbst,\n        a,\n        b\n    ) {\n'
            '        selbst.s = a + b\n'
            '    }\n'
            '    statisch funktion mal(\n        x,\n        y\n    ) {\n'
            '        zurück x * y\n'
            '    }\n'
            '}\n'
            'drucke(neu K(1, 2).s, K.mal(\n 3,\n 4\n))'
        )
        self.assertEqual(ausgabe(code), '3 12\n')

    def test_neu_instanz(self):
        code = (
            'klasse P {\n    funktion __init__(selbst, x, y) {\n        selbst.x = x\n        selbst.y = y\n    }\n}\n'
            'sei p = neu P(\n    1,\n    y = 2\n)\n'
            'drucke(p.x, p.y)'
        )
        self.assertEqual(ausgabe(code), '1 2\n')

    def test_verschachtelte_aufrufe(self):
        code = 'drucke(\n  max(\n    1,\n    max(\n      5,\n      3\n    )\n  ),\n  2\n)'
        self.assertEqual(ausgabe(code), '5 2\n')

    def test_kommentare_und_leerzeilen_in_klammern(self):
        code = 'drucke(\n    1,   # eins\n\n    # zwei folgt\n    2\n)'
        self.assertEqual(ausgabe(code), '1 2\n')

    def test_listen_und_woerterbuecher_in_aufruf(self):
        code = 'drucke(\n    [1,\n 2],\n    {\n "a": 1\n }\n)'
        self.assertEqual(ausgabe(code), '[1, 2] {a: 1}\n')

    def test_anweisungen_nach_der_klammer_bleiben_getrennt(self):
        code = 'drucke(\n 1\n)\ndrucke(\n 2\n)\nsei x = (1)\ndrucke(x)'
        self.assertEqual(ausgabe(code), '1\n2\n1\n')

    def test_zeilenumbruch_nach_klammer_trennt_weiter(self):
        # Ein Aufruf in der Folgezeile ist keine Fortsetzung: 'f' und '(1)' sind zwei Anweisungen.
        code = 'sei f = 5\nf\n(1)\ndrucke(f)'
        self.assertEqual(ausgabe(code), '5\n')

    def test_block_in_klammer_behaelt_zeilenumbrueche_als_trenner(self):
        # 'zurück' + Zeilenumbruch + '5': der Umbruch beendet das 'zurück' (Ergebnis nichts), die 5 ist eigene Anweisung
        code = (
            'funktion rufe(f) { zurück f() }\n'
            'drucke(rufe(funktion() {\n    zurück\n    5\n}))'
        )
        self.assertEqual(ausgabe(code), 'nichts\n')

    def test_block_in_klammer_mit_mehreren_anweisungen(self):
        code = (
            'funktion rufe(f, v) { zurück f(v) }\n'
            'sei r = rufe(\n'
            '    funktion(e) {\n'
            '        sei y = e * 2\n'
            '        sei z = y + 1\n'
            '        zurück z\n'
            '    },\n'
            '    5\n'
            ')\n'
            'drucke(r)'
        )
        self.assertEqual(ausgabe(code), '11\n')

    def test_block_trennung_durch_zeilenende_gegen_aufruf(self):
        # Im Block gilt wieder: 'x' und '(2)' in getrennten Zeilen sind zwei Anweisungen, kein Aufruf x(2).
        code = (
            'funktion rufe(f) { zurück f() }\n'
            'drucke(rufe(funktion() {\n    sei x = 7\n    x\n    (2)\n    zurück x\n}))'
        )
        self.assertEqual(ausgabe(code), '7\n')

    def test_klammer_im_block_im_aufruf(self):
        code = (
            'funktion rufe(f) { zurück f() }\n'
            'drucke(\n'
            '    rufe(funktion() {\n'
            '        sei t = (\n            1 +\n            2\n        )\n'
            '        wenn t == 3 {\n            zurück "drei"\n        }\n'
            '        zurück "andere"\n'
            '    })\n'
            ')'
        )
        self.assertEqual(ausgabe(code), 'drei\n')

    def test_verschachtelte_bloecke_stellen_zustand_wieder_her(self):
        # Nach dem Block gilt in der äußeren Klammer wieder: Umbrüche werden ignoriert.
        code = (
            'funktion rufe(f) { zurück f() }\n'
            'drucke(rufe(funktion() {\n    zurück 1\n})\n,\n 2)'
        )
        self.assertEqual(ausgabe(code), '1 2\n')

    def test_ternaer_und_koaleszenz_ueber_zeilen(self):
        self.assertEqual(ausgabe('drucke(\n "ja"\n wenn wahr\n sonst "nein"\n)'), 'ja\n')
        self.assertEqual(ausgabe('drucke(\n nichts\n ??\n 4\n)'), '4\n')

    def test_fehler_nicht_geschlossene_klammer(self):
        msg = self.syntaxfehler('drucke(1,\n2')
        self.assertIn('Zeile 2', msg)
        self.assertIn("')' erwartet", msg)
        self.assertIn('Dateiende', msg)

    def test_fehler_fehlendes_komma_ueber_zeilen(self):
        msg = self.syntaxfehler('drucke(1\n2)')
        self.assertIn('Zeile 2', msg)

    def test_fehler_ausserhalb_von_klammern_bleibt_streng(self):
        # Umbruch vor einer Klammer-auf-Anweisung bleibt ein Trenner: das 'sei x =' hat keinen Wert
        msg = self.syntaxfehler('sei x =\n5')
        self.assertIn('Zeile 1', msg)
        self.assertIn('Zeilenende', msg)

    def test_fehler_in_parameterliste(self):
        msg = self.syntaxfehler('funktion f(a,\n  b,\n  1) { }')
        self.assertIn('Zeile 3', msg)


# ---------------------------------------------------------------------------
# 5. Zeilennummern in Interpolationen
# ---------------------------------------------------------------------------

class TestInterpolationZeilen(_Basis):
    def test_parserfehler_nennt_absolute_zeile(self):
        code = 'sei a = 1\nsei b = 2\ndrucke("wert {a +}")'
        msg = self.syntaxfehler(code)
        self.assertTrue(msg.startswith('Zeile 3:'), msg)

    def test_lexerfehler_nennt_absolute_zeile(self):
        code = 'sei a = 1\ndrucke("x {a @ b}")'
        msg = self.syntaxfehler(code)
        self.assertTrue(msg.startswith('Zeile 2:'), msg)
        self.assertIn('Unbekanntes Zeichen', msg)

    def test_erste_zeile_bleibt_zeile_1(self):
        self.assertTrue(self.syntaxfehler('drucke("{@}")').startswith('Zeile 1:'))

    def test_leere_interpolation(self):
        msg = self.syntaxfehler('sei a = 1\nsei s = "ab {} cd"')
        self.assertTrue(msg.startswith('Zeile 2:'), msg)

    def test_mehrzeilige_zeichenkette_zaehlt_zeilen_mit(self):
        code = 'sei a = 1\nsei t = """Anfang\nMitte\nEnde {a +} fertig"""'
        msg = self.syntaxfehler(code)
        self.assertTrue(msg.startswith('Zeile 4:'), msg)

    def test_zweite_interpolation_in_derselben_zeichenkette(self):
        code = 'sei a = 1\nsei s = "{a} und {a @}"\n'
        msg = self.syntaxfehler(code)
        self.assertTrue(msg.startswith('Zeile 2:'), msg)

    def test_interpolation_in_mehrzeiligem_aufruf(self):
        code = 'drucke(\n  "ok",\n  "bad {1 +}"\n)'
        msg = self.syntaxfehler(code)
        self.assertTrue(msg.startswith('Zeile 3:'), msg)

    def test_nicht_abgeschlossene_interpolation_nennt_zeile_der_klammer(self):
        code = 'sei x = 1\nsei t = "abc {x\ndrucke(1)\ndrucke(2)\n'
        msg = self.syntaxfehler(code)
        self.assertTrue(msg.startswith('Zeile 2:'), msg)
        self.assertIn('Nicht abgeschlossene Interpolation', msg)

    def test_nicht_abgeschlossene_interpolation_in_dreifach_string(self):
        code = 'sei x = 1\nsei t = """eins\nzwei {x\ndrei"""'
        msg = self.syntaxfehler(code)
        self.assertTrue(msg.startswith('Zeile 3:'), msg)
        self.assertIn('Nicht abgeschlossene Interpolation', msg)

    def test_lexer_startzeile(self):
        with self.assertRaisesRegex(SyntaxError, 'Zeile 7:'):
            Lexer('@', start_zeile=7).tokenisieren()
        tokens = Lexer('a\nb', start_zeile=5).tokenisieren()
        self.assertEqual([t.zeile for t in tokens if t.typ == TokenTyp.BEZEICHNER], [5, 6])

    def test_gueltige_interpolationen_mit_neuer_syntax(self):
        code = ('sei a = 6\n'
                'drucke("{a & 3} {a | 1} {a ^ 2} {a << 1} {a >> 1} {~a} {0xFF} {1_000}")')
        self.assertEqual(ausgabe(code), '2 7 4 12 3 -7 255 1000\n')

    def test_formatangabe_mit_groesser_kleiner_unveraendert(self):
        self.assertEqual(ausgabe('sei a = 5\ndrucke("[{a:>4}] [{a:<4}] [{a:^5}]")'), '[   5] [5   ] [  5  ]\n')


# ---------------------------------------------------------------------------
# 6. Mehrzeilige Muster bei 'sei' und 'für'
# ---------------------------------------------------------------------------

class TestMehrzeiligeMuster(_Basis):
    def test_sei_mehrzeilig(self):
        self.assertEqual(ausgabe('sei [\n  a,\n  b\n] = [1, 2]\ndrucke(a, b)'), '1 2\n')

    def test_sei_umbruch_nur_vor_der_schliessenden_klammer(self):
        self.assertEqual(ausgabe('sei [a, b\n] = [1, 2]\ndrucke(a, b)'), '1 2\n')

    def test_sei_umbruch_nur_nach_der_oeffnenden_klammer(self):
        self.assertEqual(ausgabe('sei [\na, b] = [1, 2]\ndrucke(a, b)'), '1 2\n')

    def test_sei_mit_rest(self):
        self.assertEqual(ausgabe('sei [\n  kopf,\n  *rest\n] = [1, 2, 3]\ndrucke(kopf, rest)'), '1 [2, 3]\n')

    def test_sei_verschachtelt_mit_abschliessendem_komma(self):
        code = 'sei [\n  a,\n  [\n    b,\n    *c\n  ],\n] = [1, [2, 3, 4]]\ndrucke(a, b, c)'
        self.assertEqual(ausgabe(code), '1 2 [3, 4]\n')

    def test_fuer_mehrzeilig(self):
        code = 'für [\n  i,\n  w\n] in aufzaehlen(["x", "y"]) {\n  drucke(i, w)\n}'
        self.assertEqual(ausgabe(code), '0 x\n1 y\n')

    def test_fuer_verschachtelt_mit_rest(self):
        code = ('für [\n  i,\n  [\n    kopf,\n    *rest\n  ]\n] in aufzaehlen([[1, 2, 3]]) {\n'
                '  drucke(i, kopf, rest)\n}')
        self.assertEqual(ausgabe(code), '0 1 [2, 3]\n')

    def test_listen_comprehension_mehrzeilig(self):
        self.assertEqual(ausgabe('drucke([a + b für [\n  a,\n  b\n] in [[1, 2], [3, 4]]])'), '[3, 7]\n')

    def test_zuweisung_mehrzeilig_wie_bisher(self):
        self.assertEqual(ausgabe('sei a = 0\nsei b = 0\n[\n  a,\n  b\n] = [3, 4]\ndrucke(a, b)'), '3 4\n')

    def test_anweisungen_danach_bleiben_zeilenweise_getrennt(self):
        code = 'sei [\n  a,\n  b\n] = [1, 2]\nsei c = 3\ndrucke(a, b, c)'
        self.assertEqual(ausgabe(code), '1 2 3\n')

    def test_muster_in_funktionsrumpf(self):
        code = 'funktion f(l) {\n  sei [\n    x,\n    y\n  ] = l\n  zurück x * y\n}\ndrucke(f([3, 4]))'
        self.assertEqual(ausgabe(code), '12\n')

    def test_umbruchzustand_wird_nach_dem_muster_zurueckgesetzt(self):
        # Hinter dem Muster gilt wieder: ein Umbruch beendet die Anweisung ('sei x =' hat keinen Wert)
        msg = self.syntaxfehler('sei [\n  a\n] = [1]\nsei x =\n5')
        self.assertIn('Zeile 4', msg)
        self.assertIn('Zeilenende', msg)

    def test_fehler_umbruch_vor_gleichzeichen(self):
        msg = self.syntaxfehler('sei [\n  a,\n  b\n]\n= [1, 2]')
        self.assertIn('Zeile 4', msg)
        self.assertIn("'=' erwartet", msg)
        self.assertIn('Zeilenende', msg)

    def test_fehler_nicht_geschlossenes_muster(self):
        msg = self.syntaxfehler('sei [\n  a,\n  b\n= [1, 2]')
        self.assertIn('Zeile 4', msg)
        self.assertIn("']' erwartet", msg)
        self.assertIn("(gefunden: '=')", msg)

    def test_fehler_leeres_muster(self):
        msg = self.syntaxfehler('sei [\n] = [1]')
        self.assertIn('Zeile 2', msg)
        self.assertIn("Name erwartet (gefunden: ']')", msg)

    def test_fehler_zwei_rest_eintraege(self):
        msg = self.syntaxfehler('sei [\n  *a,\n  *b\n] = [1, 2]')
        self.assertIn("höchstens ein '*'", msg)
        self.assertIn('Zeile 3', msg)

    def test_fehler_kein_name_im_muster(self):
        msg = self.syntaxfehler('für [\n  i,\n  5\n] in [[1, 2]] { }')
        self.assertIn('Zeile 3', msg)
        self.assertIn("Name erwartet (gefunden: '5')", msg)


# ---------------------------------------------------------------------------
# 7. Doppelte Parameternamen
# ---------------------------------------------------------------------------

class TestDoppelteParameter(_Basis):
    def test_verschiedene_namen_sind_erlaubt(self):
        self.assertEqual(ausgabe('funktion f(a, b, *r, **k) { zurück a }\ndrucke(f(1, 2))'), '1\n')

    def test_gleicher_name_in_verschiedenen_funktionen_ist_erlaubt(self):
        code = 'funktion f(a) { zurück a }\nfunktion g(a) { zurück f(a) + 1 }\ndrucke(g(1))'
        self.assertEqual(ausgabe(code), '2\n')

    def test_innere_funktion_darf_namen_der_aeusseren_wiederverwenden(self):
        code = 'funktion f(a) { zurück funktion(a) -> a * 2 }\ndrucke(f(1)(5))'
        self.assertEqual(ausgabe(code), '10\n')

    def _doppelt(self, code, name='a'):
        msg = self.syntaxfehler(code)
        self.assertIn(f"Der Parametername '{name}' ist doppelt vergeben", msg)
        self.assertNotIn('gefunden', msg)
        return msg

    def test_zwei_normale_parameter(self):
        self.assertTrue(self._doppelt('funktion f(a, a) { }').startswith('Zeile 1:'))

    def test_mit_stern_parameter(self):
        self._doppelt('funktion f(a, *a) { }')

    def test_stern_parameter_und_doppelstern_parameter(self):
        self._doppelt('funktion f(*a, **a) { }')

    def test_normaler_und_doppelstern_parameter(self):
        self._doppelt('funktion f(a, **a) { }')

    def test_mit_standardwerten_und_typ_hinweisen(self):
        self._doppelt('funktion f(a: Ganzzahl = 1, a: Ganzzahl = 2) { }')

    def test_kurzform(self):
        self._doppelt('funktion f(a, a) -> a')
        self._doppelt('sei g = funktion(x, y, x) -> x', name='x')

    def test_anonyme_funktion(self):
        self._doppelt('sei g = funktion(a, a) { zurück a }')

    def test_methode_in_klasse(self):
        self._doppelt('klasse K {\n  funktion m(selbst, selbst) { }\n}', name='selbst')

    def test_nennt_die_zeile_des_zweiten_namens(self):
        msg = self._doppelt('funktion f(\n  a,\n  b,\n  a\n) { }')
        self.assertTrue(msg.startswith('Zeile 4:'), msg)


# ---------------------------------------------------------------------------
# 8. Parameter nach '*rest'
# ---------------------------------------------------------------------------

class TestParameterNachRest(_Basis):
    def test_stern_parameter_mit_doppelstern_parameter(self):
        code = 'funktion f(a, *rest, **opt) { drucke(a, rest, opt) }\nf(1, 2, 3, x = 4)'
        self.assertEqual(ausgabe(code), '1 [2, 3] {x: 4}\n')

    def test_stern_parameter_mit_abschliessendem_komma(self):
        self.assertEqual(ausgabe('funktion f(*rest,) { drucke(rest) }\nf(1, 2)'), '[1, 2]\n')

    def test_stern_parameter_zuletzt_in_kurzform(self):
        self.assertEqual(ausgabe('drucke((funktion(a, *r) -> r)(1, 2, 3))'), '[2, 3]\n')

    def _fehler_nach_rest(self, code):
        msg = self.syntaxfehler(code)
        self.assertIn("Nach dem Rest-Parameter '*rest' darf nur noch ein '**name'-Parameter folgen", msg)
        self.assertNotIn('RPAREN', msg)
        self.assertNotIn('KOMMA', msg)
        return msg

    def test_normaler_parameter_nach_rest(self):
        msg = self._fehler_nach_rest('funktion f(*rest, b) { }')
        self.assertTrue(msg.startswith('Zeile 1:'), msg)
        self.assertIn("(gefunden: 'b')", msg)

    def test_parameter_mit_standardwert_nach_rest(self):
        self._fehler_nach_rest('funktion f(a, *rest, b = 1) { }')

    def test_zweiter_rest_parameter(self):
        msg = self._fehler_nach_rest('funktion f(*rest, *mehr) { }')
        self.assertIn("(gefunden: '*')", msg)

    def test_kurzform_und_anonyme_funktion(self):
        self._fehler_nach_rest('funktion f(*rest, b) -> b')
        self._fehler_nach_rest('sei g = funktion(*rest, b) { }')

    def test_mehrzeilig_nennt_die_zeile_des_parameters(self):
        msg = self._fehler_nach_rest('funktion f(\n  a,\n  *rest,\n  b\n) { }')
        self.assertTrue(msg.startswith('Zeile 4:'), msg)

    def test_doppelstern_parameter_bleibt_letzter_parameter(self):
        msg = self.syntaxfehler('funktion f(**opt, b) { }')
        self.assertIn('muss der letzte Parameter sein', msg)


# ---------------------------------------------------------------------------
# 9. Lesbare Syntaxfehler (keine internen Token-Namen)
# ---------------------------------------------------------------------------

class TestLesbareSyntaxfehler(_Basis):
    def test_jede_token_art_hat_eine_anzeige(self):
        for typ in TokenTyp:
            with self.subTest(typ=typ.name):
                self.assertIn(typ, _TOKEN_ANZEIGE)
                self.assertNotEqual(_TOKEN_ANZEIGE[typ].strip("'"), typ.name)

    def test_ausdruck_erwartet_ohne_doppelte_angabe(self):
        self.assertEqual(self.syntaxfehler('drucke(5 ??)'), "Zeile 1: Ausdruck erwartet (gefunden: ')')")

    def test_erwartetes_symbol(self):
        self.assertEqual(self.syntaxfehler('drucke(1 2)'), "Zeile 1: ')' erwartet (gefunden: '2')")
        self.assertEqual(self.syntaxfehler('sei x == 1'), "Zeile 1: '=' erwartet (gefunden: '==')")
        self.assertEqual(self.syntaxfehler('wenn wahr drucke(1)'), "Zeile 1: '{' erwartet (gefunden: 'drucke')")

    def test_erwarteter_name(self):
        self.assertEqual(self.syntaxfehler('sei = 5'), "Zeile 1: Name erwartet (gefunden: '=')")
        self.assertEqual(self.syntaxfehler('sei 5 = 5'), "Zeile 1: Name erwartet (gefunden: '5')")

    def test_gefundener_name_zeigt_den_text(self):
        self.assertEqual(self.syntaxfehler('drucke(a b)'), "Zeile 1: ')' erwartet (gefunden: 'b')")

    def test_zeilenende(self):
        self.assertEqual(self.syntaxfehler('sei x =\n5'), 'Zeile 1: Ausdruck erwartet (gefunden: Zeilenende)')

    def test_dateiende(self):
        self.assertEqual(self.syntaxfehler('drucke(1,\n2'), "Zeile 2: ')' erwartet (gefunden: Dateiende)")
        self.assertEqual(self.syntaxfehler('sei x = 1 +'), 'Zeile 1: Ausdruck erwartet (gefunden: Dateiende)')

    def test_schluesselwort(self):
        self.assertEqual(self.syntaxfehler('sei x = sonst'), "Zeile 1: Ausdruck erwartet (gefunden: 'sonst')")
        self.assertEqual(self.syntaxfehler('für x { }'), "Zeile 1: 'in' erwartet (gefunden: '{')")

    def test_erwartetes_schluesselwort(self):
        self.assertEqual(self.syntaxfehler('drucke(1 wenn 2)'), "Zeile 1: 'sonst' erwartet (gefunden: ')')")

    def test_schluesselwort_so_geschrieben_wie_im_code(self):
        self.assertIn("(gefunden: 'fuer')", self.syntaxfehler('drucke(fuer)'))
        self.assertIn("(gefunden: 'für')", self.syntaxfehler('drucke(für)'))

    def test_wahrheitswert_und_nichts(self):
        self.assertEqual(self.syntaxfehler('drucke(1 wahr)'), "Zeile 1: ')' erwartet (gefunden: 'wahr')")
        self.assertEqual(self.syntaxfehler('drucke(1 nichts)'), "Zeile 1: ')' erwartet (gefunden: 'nichts')")

    def test_zeichenkette(self):
        self.assertEqual(self.syntaxfehler('drucke(1 "abc")'), "Zeile 1: ')' erwartet (gefunden: Zeichenkette)")
        self.assertEqual(self.syntaxfehler('drucke(1 "a{1}")'), "Zeile 1: ')' erwartet (gefunden: Zeichenkette)")

    def test_mehrzeichen_operatoren_und_verbundzuweisung(self):
        self.assertEqual(self.syntaxfehler('drucke(1 <<)'), "Zeile 1: Ausdruck erwartet (gefunden: ')')")
        self.assertEqual(self.syntaxfehler('sei x = 1 += 2'), "Zeile 1: Ausdruck erwartet (gefunden: '+=')")

    def test_klassenkoerper_zeigt_zahl_und_zeichenkette_lesbar(self):
        self.assertIn("nicht erlaubt: '42'", self.syntaxfehler('klasse K { 42 }'))
        self.assertIn('nicht erlaubt: Zeichenkette', self.syntaxfehler('klasse K { "abc" }'))
        self.assertIn('nicht erlaubt: Zeichenkette', self.syntaxfehler('klasse K { "a{1}" }'))
        self.assertIn("nicht erlaubt: 'wahr'", self.syntaxfehler('klasse K { wahr }'))

    def test_keine_internen_token_namen_in_den_meldungen(self):
        faelle = [
            'drucke(5 ??)', 'drucke(1 2)', 'sei = 5', 'sei x =\n5', 'drucke(1,\n2', 'für x { }',
            'drucke(1 wenn 2)', 'wenn wahr', 'sei x = )', 'klasse K { 42 }', 'klasse K { "a{1}" }',
            'funktion f(a: 5) { }', 'passe 1 { x }', 'lade 5 als', 'x += ', 'drucke(1) }', ';',
            'sei [a, b = [1, 2]', 'funktion f(*r, b) { }', 'funktion f(a, a) { }',
        ]
        for code in faelle:
            with self.subTest(code=code):
                self.assertNotRegex(self.syntaxfehler(code), r'\b[A-Z][A-Z_]{2,}\b')


if __name__ == '__main__':
    unittest.main()
