# -*- coding: utf-8 -*-
"""
Tests für Parser-/Lexer-Verhalten rund um Operator-Vorrang und Fehlerstellen:

  * Vorrang von 'nicht' (wie in Python: unterhalb der Vergleiche, oberhalb von 'und')
  * Zeilenzählung in mehrzeiligen Zeichenketten (dreifache Anführungszeichen)
  * Fehlermeldungen im Klassenkörper (inkl. „meintest du …?")

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
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter


def parse(code: str):
    return Parser(Lexer(code).tokenisieren()).parse()


def ausgabe(code: str) -> str:
    """Führt Code aus und gibt das auf stdout Gedruckte zurück."""
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter().ausfuehren(parse(code))
    return puffer.getvalue()


def fehlertext(code: str) -> str:
    """Parst Code, erwartet einen SyntaxError und gibt dessen Text zurück."""
    try:
        parse(code)
    except SyntaxError as e:
        return str(e)
    raise AssertionError(f'Kein SyntaxError für: {code!r}')


class TestNichtVorrang(unittest.TestCase):
    def test_nicht_bindet_schwaecher_als_vergleich(self):
        self.assertEqual(ausgabe('drucke(nicht 1 == 2)'), 'wahr\n')
        self.assertEqual(ausgabe('drucke(nicht 1 == 1)'), 'falsch\n')
        self.assertEqual(ausgabe('drucke(nicht 1 < 2)'), 'falsch\n')

    def test_nicht_vor_in(self):
        self.assertEqual(ausgabe('drucke(nicht 3 in [1, 2])'), 'wahr\n')
        self.assertEqual(ausgabe('drucke(nicht 1 in [1, 2])'), 'falsch\n')

    def test_nicht_in_infix_funktioniert_weiter(self):
        self.assertEqual(ausgabe('drucke(5 nicht in [1, 2, 3])'), 'wahr\n')
        self.assertEqual(ausgabe('drucke(2 nicht in [1, 2, 3])'), 'falsch\n')
        # Präfix-'nicht' vor infix-'nicht in': nicht (3 nicht in [1])
        self.assertEqual(ausgabe('drucke(nicht 3 nicht in [1])'), 'falsch\n')

    def test_nicht_und_ist_nicht_a_und_b(self):
        # a=falsch, b=falsch: (nicht a) und b = falsch  (nicht (a und b) wäre wahr)
        self.assertEqual(ausgabe('sei a = falsch\nsei b = falsch\ndrucke(nicht a und b)'),
                         'falsch\n')
        knoten = parse('nicht a und b').anweisungen[0]
        self.assertIsInstance(knoten, ast.BinaereOperation)
        self.assertEqual(knoten.operator, 'und')
        self.assertIsInstance(knoten.links, ast.UnaereOperation)
        self.assertEqual(knoten.links.operator, 'nicht')
        self.assertIsInstance(knoten.links.operand, ast.Bezeichner)

    def test_nicht_oder_ist_nicht_x_oder_y(self):
        # x=wahr, y=wahr: (nicht x) oder y = wahr  (nicht (x oder y) wäre falsch)
        self.assertEqual(ausgabe('sei x = wahr\nsei y = wahr\ndrucke(nicht x oder y)'),
                         'wahr\n')
        knoten = parse('nicht x oder y').anweisungen[0]
        self.assertEqual(knoten.operator, 'oder')
        self.assertIsInstance(knoten.links, ast.UnaereOperation)

    def test_und_nach_nicht_mit_vergleich(self):
        # (nicht 1 == 2) und (2 == 2)
        self.assertEqual(ausgabe('drucke(nicht 1 == 2 und 2 == 2)'), 'wahr\n')
        self.assertEqual(ausgabe('drucke(wahr und nicht 1 == 1)'), 'falsch\n')

    def test_doppeltes_nicht(self):
        self.assertEqual(ausgabe('drucke(nicht nicht wahr)'), 'wahr\n')
        self.assertEqual(ausgabe('drucke(nicht nicht 1 == 2)'), 'falsch\n')

    def test_vergleichsketten_unveraendert(self):
        self.assertEqual(ausgabe('drucke(1 < 2 < 3)'), 'wahr\n')
        self.assertEqual(ausgabe('drucke(3 < 2 < 1)'), 'falsch\n')
        # nicht gilt für die ganze Kette
        self.assertEqual(ausgabe('drucke(nicht 1 < 2 < 3)'), 'falsch\n')
        self.assertEqual(ausgabe('drucke(nicht 3 < 2 < 1)'), 'wahr\n')
        kette = parse('nicht 1 < 2 < 3').anweisungen[0]
        self.assertIsInstance(kette, ast.UnaereOperation)
        self.assertIsInstance(kette.operand, ast.VergleichsKette)

    def test_unaeres_minus_unveraendert(self):
        self.assertEqual(ausgabe('drucke(-2 ** 2)'), '-4\n')
        self.assertEqual(ausgabe('drucke(2 - -3)'), '5\n')
        self.assertEqual(ausgabe('drucke(2 ** -1)'), '0.5\n')
        # Minus bindet stärker als der Vergleich, 'nicht' schwächer
        self.assertEqual(ausgabe('drucke(nicht -1 == 1)'), 'wahr\n')

    def test_nicht_in_bedingungen_und_klammern(self):
        self.assertEqual(ausgabe('wenn nicht 1 == 2 { drucke("ja") }'), 'ja\n')
        self.assertEqual(ausgabe('wenn nicht (1 == 1) { drucke("ja") } sonst { drucke("nein") }'),
                         'nein\n')
        self.assertEqual(ausgabe('drucke(wahr == (nicht falsch))'), 'wahr\n')
        self.assertEqual(ausgabe('drucke([x für x in [1, 2, 3] wenn nicht x == 2])'),
                         '[1, 3]\n')

    def test_fehler_nicht_als_operand(self):
        # Wie in Python ist 'a == nicht b' nicht erlaubt – Fehler mit Hinweis auf Klammern
        for code in ('1 == nicht 2', '1 + nicht 2', '-nicht wahr'):
            with self.subTest(code=code):
                text = fehlertext(code)
                self.assertIn('Zeile 1', text)
                self.assertIn("'nicht'", text)
                self.assertIn('Klammern', text)

    def test_fehler_nicht_ohne_operand(self):
        text = fehlertext('sei x = 1\ndrucke(nicht)')
        self.assertIn('Zeile 2', text)


class TestZeilenzaehlung(unittest.TestCase):
    def test_token_nach_dreizeiligem_string_hat_richtige_zeile(self):
        code = 'sei t = """eins\nzwei\ndrei"""\nsei u = 1\n'
        tokens = Lexer(code).tokenisieren()
        zeichenkette = next(t for t in tokens if t.wert == 'eins\nzwei\ndrei')
        self.assertEqual(zeichenkette.zeile, 1)
        sei_zeilen = [t.zeile for t in tokens if t.typ.name == 'SEI']
        self.assertEqual(sei_zeilen, [1, 4])

    def test_parser_fehler_nach_dreizeiligem_string(self):
        code = 'sei t = """eins\nzwei\ndrei"""\nsei = 5\n'
        self.assertIn('Zeile 4', fehlertext(code))

    def test_lexer_fehler_nach_dreizeiligem_string(self):
        code = 'sei t = """eins\nzwei\ndrei"""\nsei u = $\n'
        self.assertIn('Zeile 4', fehlertext(code))

    def test_einfache_anfuehrungszeichen_dreifach(self):
        code = "sei t = '''eins\nzwei\ndrei'''\nsei = 5\n"
        self.assertIn('Zeile 4', fehlertext(code))

    def test_interpolierter_mehrzeiliger_string(self):
        code = 'sei n = 1\nsei t = """a {n}\nb\nc"""\nsei = 5\n'
        self.assertIn('Zeile 5', fehlertext(code))

    def test_mehrere_mehrzeilige_strings_hintereinander(self):
        code = 'sei a = """1\n2"""\nsei b = """3\n4\n5"""\nsei = 5\n'
        self.assertIn('Zeile 6', fehlertext(code))

    def test_nicht_abgeschlossener_dreifach_string_meldet_letzte_zeile(self):
        self.assertIn('Zeile 2', fehlertext('sei t = """eins\nzwei'))

    def test_mehrzeiliger_string_inhalt_bleibt_erhalten(self):
        self.assertEqual(ausgabe('drucke("""a\nb""")'), 'a\nb\n')
        self.assertEqual(ausgabe('sei n = 2\ndrucke("""a {n}\nb""")'), 'a 2\nb\n')


class TestKlassenkoerper(unittest.TestCase):
    def test_gueltiger_klassenkoerper(self):
        code = (
            'klasse K {\n'
            '\n'
            '    # Kommentar\n'
            '    konstante MAX = 5\n'
            '    sei zaehler = 0\n'
            '\n'
            '    funktion wert(dies) { zurück 1 }\n'
            '    statisch funktion fabrik() { zurück 2 }\n'
            '}\n'
            'drucke(K.MAX)\n'
            'drucke(K.fabrik())\n'
            'drucke((neu K()).wert())\n'
        )
        self.assertEqual(ausgabe(code), '5\n2\n1\n')

    def test_leere_klasse_und_semikolons(self):
        self.assertEqual(ausgabe('klasse K { }\nklasse L {\n}\nklasse M { ; sei x = 1; }\ndrucke(M.x)'),
                         '1\n')

    def test_tippfehler_funktion_meldet_zeile_und_vorschlag(self):
        code = (
            'klasse K {\n'
            '    funktion a(dies) { zurück 1 }\n'
            '    funtion b(dies) { zurück 2 }\n'
            '}\n'
        )
        text = fehlertext(code)
        self.assertIn('Zeile 3', text)
        self.assertIn("'funtion'", text)
        self.assertIn('Klassenkörper', text)
        self.assertIn("'funktion', 'statisch funktion', 'sei' und 'konstante'", text)
        self.assertIn("meintest du 'funktion'?", text)

    def test_tippfehler_statisch(self):
        text = fehlertext('klasse K {\n    statich funktion f() { }\n}')
        self.assertIn('Zeile 2', text)
        self.assertIn("meintest du 'statisch'?", text)

    def test_tippfehler_konstante(self):
        text = fehlertext('klasse K {\n    konstnte X = 1\n}')
        self.assertIn('Zeile 2', text)
        self.assertIn("meintest du 'konstante'?", text)

    def test_unbekanntes_token_ohne_vorschlag(self):
        text = fehlertext('klasse K {\n    42\n}')
        self.assertIn('Zeile 2', text)
        self.assertIn('Klassenkörper', text)
        self.assertNotIn('meintest du', text)

    def test_anweisung_im_klassenkoerper_ohne_vorschlag(self):
        text = fehlertext('klasse K {\n    drucke("x")\n}')
        self.assertIn('Zeile 2', text)
        self.assertIn("'drucke'", text)
        self.assertNotIn('meintest du', text)

    def test_schluesselwort_im_klassenkoerper(self):
        text = fehlertext('klasse K {\n    wenn wahr { }\n}')
        self.assertIn('Zeile 2', text)
        self.assertIn("'wenn'", text)
        self.assertNotIn('meintest du', text)

    def test_fehlerzeile_nach_mehrzeiligem_string_im_klassenkoerper(self):
        code = (
            'klasse K {\n'
            '    sei text = """a\n'
            'b\n'
            'c"""\n'
            '    funtion f(dies) { }\n'
            '}\n'
        )
        text = fehlertext(code)
        self.assertIn('Zeile 5', text)
        self.assertIn("meintest du 'funktion'?", text)

    def test_folgefehler_nicht_mehr_an_falscher_stelle(self):
        # Früher wurde 'funtion' still übersprungen; der Fehler kam erst später
        # (hier: ab Zeile 4 in 'b(dies)') statt in Zeile 3 beim Tippfehler.
        code = (
            'klasse K {\n'
            '    funktion a(dies) { zurück 1 }\n'
            '    funtion b(dies) { zurück 2 }\n'
            '    funktion c(dies) { zurück 3 }\n'
            '}\n'
        )
        self.assertIn('Zeile 3', fehlertext(code))


if __name__ == '__main__':
    unittest.main()
