# -*- coding: utf-8 -*-
"""
Tests für Bytecode-Compiler und Maschine.

Der wichtigste Test ist der Vergleich: dasselbe Programm einmal über die Maschine
und einmal über den Baum-Interpreter muss dasselbe Ergebnis liefern.

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import contextlib
import glob
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter
from deutsch.bytecode import kompiliere, kompilierbar

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEISPIELE = os.path.join(PROJEKT_WURZEL, 'beispiele')


def _lauf(code: str, maschine: bool, ladepfad: str = None):
    """Führt Code aus und gibt (Rückgabewert, Ausgabe) zurück."""
    # Der Baum wird je Lauf neu geparst, damit der Code-Cache am Knoten nicht geteilt wird
    baum = Parser(Lexer(code).tokenisieren()).parse()
    interpreter = Interpreter(ladepfad=ladepfad)
    interpreter._vm_aktiv = maschine
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        ergebnis = interpreter.ausfuehren(baum)
    return ergebnis, puffer.getvalue()


def _vergleichbar(wert):
    """Datenwerte direkt vergleichen, Funktionen und Instanzen über ihre Darstellung.

    Zwei Läufe erzeugen zwangsläufig verschiedene Funktionsobjekte; verglichen wird
    deshalb, was davon sichtbar ist.
    """
    if isinstance(wert, (int, float, str, bool, type(None), range)):
        return wert
    if isinstance(wert, list):
        return [_vergleichbar(e) for e in wert]
    if isinstance(wert, dict):
        return {k: _vergleichbar(v) for k, v in wert.items()}
    if isinstance(wert, set):
        return wert
    return repr(wert)


def beide_wege(pruefling, code: str, ladepfad: str = None):
    """Vergleicht Maschine und Baum-Interpreter und gibt das gemeinsame Ergebnis zurück."""
    mit_wert, mit_ausgabe = _lauf(code, True, ladepfad)
    ohne_wert, ohne_ausgabe = _lauf(code, False, ladepfad)
    pruefling.assertEqual(mit_ausgabe, ohne_ausgabe,
                          'Ausgabe von Maschine und Baum-Interpreter weicht ab')
    pruefling.assertEqual(_vergleichbar(mit_wert), _vergleichbar(ohne_wert),
                          'Rückgabewert von Maschine und Baum-Interpreter weicht ab')
    return mit_wert


PROGRAMME = {
    'Arithmetik': 'funktion f(a, b) { zurück a * b + a - b / 2 }\nf(7, 3)',
    'Vergleichskette': 'funktion f(x) { zurück 1 < x < 10 }\n[f(5), f(50)]',
    'Logik mit Kurzschluss': 'funktion f(a, b) { zurück a und b oder nicht a }\n[f(wahr, falsch), f(falsch, falsch)]',
    'Verzweigung': 'funktion f(n) { wenn n > 5 { zurück "gross" } sonst wenn n > 2 { zurück "mittel" } sonst { zurück "klein" } }\n[f(9), f(3), f(1)]',
    'solange mit abbrechen': 'funktion f() { sei i = 0; solange wahr { i += 1; wenn i > 4 { abbrechen } }; zurück i }\nf()',
    'solange mit weiter': 'funktion f() { sei i = 0; sei s = 0; solange i < 6 { i += 1; wenn i % 2 == 0 { weiter }; s += i }; zurück s }\nf()',
    'für über Liste': 'funktion f(l) { sei s = 0; für x in l { s += x }; zurück s }\nf([1,2,3,4])',
    'für über Bereich mit abbrechen': 'funktion f() { sei s = 0; für i in bereich(100) { wenn i > 5 { abbrechen }; s += i }; zurück s }\nf()',
    'für mit Destrukturierung': 'funktion f(paare) { sei s = 0; für [a, b] in paare { s += a * b }; zurück s }\nf([[1,2],[3,4]])',
    'Rekursion': 'funktion fak(n) { wenn n <= 1 { zurück 1 }; zurück n * fak(n - 1) }\nfak(6)',
    'Ternär': 'funktion f(n) { zurück "ja" wenn n > 0 sonst "nein" }\n[f(1), f(-1)]',
    'Listen und Index': 'funktion f() { sei l = [1,2,3]; l[0] = 9; zurück l[0] + l[2] }\nf()',
    'Schnitt': 'funktion f(l) { zurück l[1:3] }\nf([1,2,3,4,5])',
    'Schnitt-Zuweisung': 'funktion f() { sei l = [1,2,3,4]; l[1:3] = [9]; zurück l }\nf()',
    'Wörterbuch': 'funktion f() { sei d = {"a": 1}; d["b"] = 2; zurück d.laenge() }\nf()',
    'Menge': 'funktion f() { sei m = {1, 2, 2, 3}; zurück m.laenge() }\nf()',
    'Interpolation': 'funktion f(n) { zurück "Wert {n} und {n * 2}" }\nf(21)',
    'Formatangabe': 'funktion f(x) { zurück "{x:.2f}" }\nf(3.14159)',
    'Methodenaufruf': 'funktion f(t) { zurück t.gross().laenge() }\nf("hallo")',
    'Modulaufruf': 'funktion f(x) { zurück mathe.wurzel(x) }\nf(16)',
    'Keyword-Argumente': 'funktion f(a, b = 2, c = 3) { zurück a * 100 + b * 10 + c }\n[f(1), f(1, c=9), f(1, b=5, c=6)]',
    'Variadisch': 'funktion f(*x) { sei s = 0; für w in x { s += w }; zurück s }\nf(1,2,3,4)',
    'Entpackung': 'funktion f(a, b, c) { zurück [a, b, c] }\nf(*[1,2], 3)',
    'Destrukturierende Deklaration': 'funktion f(l) { sei [a, b] = l; zurück a - b }\nf([9, 4])',
    'Attribut setzen': 'klasse P { funktion __init__(dies, x) { dies.x = x } }\nfunktion f() { sei p = neu P(1); p.x += 4; zurück p.x }\nf()',
    'neu mit Keyword': 'klasse P { funktion __init__(dies, x, y) { dies.x = x; dies.y = y } }\nfunktion f() { sei p = neu P(y=2, x=1); zurück p.x * 10 + p.y }\nf()',
    'Blockskopierung': 'funktion f() { sei x = 1; wenn wahr { sei x = 2 }; zurück x }\nf()',
    'Globaler Zugriff': 'sei g = 5\nfunktion f() { zurück g * 2 }\nf()',
    'Globale Zuweisung': 'sei g = 5\nfunktion f() { g = 9; zurück g }\n[f(), g]',
    'Typ-Hinweise': 'funktion f(a: Ganzzahl) -> Ganzzahl { zurück a * 2 }\nf(21)',
    'pruefe': 'funktion f(n) { pruefe n > 0, "muss positiv sein"; zurück n }\nf(3)',
    'verschachtelte Schleifen': 'funktion f(n) { sei s = 0; für i in bereich(n) { für j in bereich(n) { s += i * j } }; zurück s }\nf(8)',
}


class TestGleichesErgebnis(unittest.TestCase):
    """Maschine und Baum-Interpreter müssen sich identisch verhalten."""

    def test_programme(self):
        for name, code in PROGRAMME.items():
            with self.subTest(programm=name):
                beide_wege(self, code)

    def test_beispielskripte(self):
        dateien = sorted(glob.glob(os.path.join(BEISPIELE, '*.deu')))
        self.assertGreater(len(dateien), 0)
        for pfad in dateien:
            if os.path.basename(pfad) == 'fibonacci.deu':
                continue           # misst Laufzeiten, Ausgabe ist naturgemäß verschieden
            with self.subTest(datei=os.path.basename(pfad)):
                with io.open(pfad, encoding='utf-8') as datei:
                    beide_wege(self, datei.read(), BEISPIELE)


class TestGleicheFehler(unittest.TestCase):
    """Auch Fehlermeldungen dürfen sich nicht unterscheiden."""

    FEHLERHAFT = {
        'Division durch Null': 'funktion f(a) { zurück a / 0 }\nf(1)',
        'unbekannter Name': 'funktion f() { zurück gibtsnicht }\nf()',
        'Typfehler': 'funktion f() { zurück 1 + [1] }\nf()',
        'Index': 'funktion f() { sei l = [1]; zurück l[5] }\nf()',
        'Schluessel': 'funktion f() { sei d = {}; zurück d["x"] }\nf()',
        'Attribut': 'funktion f() { zurück "a".gibtsnicht() }\nf()',
        'Zuweisung ohne sei': 'funktion f() { unbekannt = 1 }\nf()',
        'Typ-Hinweis verletzt': 'funktion f(a: Ganzzahl) { zurück a }\nf("text")',
        'pruefe schlaegt fehl': 'funktion f() { pruefe falsch, "geht nicht" }\nf()',
        'werfe': 'funktion f() { werfe "peng" }\nf()',
        'Zeichenkette unveraenderlich': 'funktion f() { sei s = "ab"; s[0] = "x" }\nf()',
    }

    def test_fehlermeldungen_stimmen_ueberein(self):
        for name, code in self.FEHLERHAFT.items():
            with self.subTest(fall=name):
                meldungen = []
                for maschine in (True, False):
                    try:
                        _lauf(code, maschine)
                        meldungen.append('(kein Fehler)')
                    except Exception as fehler:
                        meldungen.append(f'{type(fehler).__name__}: {fehler}')
                self.assertEqual(meldungen[0], meldungen[1])
                self.assertNotEqual(meldungen[0], '(kein Fehler)')

    def test_aufrufkette_wird_auch_von_der_maschine_gefuellt(self):
        code = 'funktion a() { zurück b() }\nfunktion b() { zurück 1 / 0 }\na()'
        baum = Parser(Lexer(code).tokenisieren()).parse()
        interpreter = Interpreter()
        with self.assertRaises(ZeroDivisionError):
            interpreter.ausfuehren(baum)
        self.assertEqual(len(interpreter._letzter_aufruf_stack), 2)


class TestUebersetzbarkeit(unittest.TestCase):
    """Was die Maschine nicht kann, darf sie nicht anfassen."""

    def _definition(self, code: str):
        baum = Parser(Lexer(code).tokenisieren()).parse()
        return baum.anweisungen[0]

    def test_einfacher_koerper_wird_uebersetzt(self):
        definition = self._definition('funktion f(a) { zurück a + 1 }')
        self.assertTrue(kompilierbar(definition))
        self.assertIsNotNone(kompiliere(definition))

    def test_nicht_uebersetzbare_koerper(self):
        for name, code in (
            ('verschachtelte Funktion', 'funktion f() { funktion g() { zurück 1 }; zurück g() }'),
            ('Klasse', 'funktion f() { klasse K { }; zurück 1 }'),
            ('versuche', 'funktion f() { versuche { zurück 1 } fange e { zurück 2 } }'),
            ('passe', 'funktion f(n) { passe n { fall 1: { zurück 1 } } }'),
            ('Generator', 'funktion f() { ergibt 1 }'),
            ('Abstraktion', 'funktion f(l) { zurück [x für x in l] }'),
            ('konstante', 'funktion f() { konstante K = 1; zurück K }'),
        ):
            with self.subTest(fall=name):
                definition = self._definition(code)
                self.assertFalse(kompilierbar(definition))
                self.assertIsNone(kompiliere(definition))

    def test_nicht_uebersetzbares_laeuft_trotzdem(self):
        code = ('funktion f(l) { versuche { zurück [x * 2 für x in l] } fange e { zurück [] } }\n'
                'f([1,2,3])')
        self.assertEqual(beide_wege(self, code), [2, 4, 6])

    def test_uebersetzung_wird_gemerkt(self):
        definition = self._definition('funktion f(a) { zurück a + 1 }')
        interpreter = Interpreter()
        erst = interpreter._code_fuer(definition)
        self.assertIs(erst, interpreter._code_fuer(definition))

    def test_abschaltbar(self):
        definition = self._definition('funktion f(a) { zurück a + 1 }')
        interpreter = Interpreter()
        interpreter._vm_aktiv = False
        self.assertIsNone(interpreter._code_fuer(definition))


if __name__ == '__main__':
    unittest.main()
