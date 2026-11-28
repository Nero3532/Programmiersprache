# -*- coding: utf-8 -*-
"""Tests für den Namensraum 'schildkroete' (Turtle-Grafik) mit Attrappe statt echtem 'turtle'."""
import os
import sys
import builtins
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import Interpreter


class Attrappe:
    def __init__(self):
        self.aufrufe = []

    def __getattr__(self, name):
        return lambda *a: self.aufrufe.append((name,) + a)


def lauf(code, attrappe=None):
    i = Interpreter()
    if attrappe is not None:
        i._turtle_modul = attrappe
    return i.ausfuehren(Parser(Lexer(code).tokenisieren()).parse())


class TestSchildkroete(unittest.TestCase):
    def pruefe(self, code, erwartet):
        a = Attrappe()
        lauf(code, a)
        self.assertEqual(a.aufrufe, erwartet)

    def test_bewegung(self):
        self.pruefe('schildkroete.vorwaerts(100)\nschildkroete.drehen(90)\nschildkroete.kreis(50)',
                    [('forward', 100), ('left', 90), ('circle', 50)])

    def test_umlaut_schreibweisen(self):
        self.pruefe('schildkröte.vorwärts(5)\nschildkröte.warte_auf_schließen()\n'
                    'schildkroete.warte_auf_schliessen()',
                    [('forward', 5), ('done',), ('done',)])

    def test_stift(self):
        self.pruefe('schildkroete.stift_hoch()\nschildkroete.stift_runter()',
                    [('penup',), ('pendown',)])

    def test_farbe_deutsch_und_durchgereicht(self):
        self.pruefe('schildkroete.farbe("Rot")\nschildkroete.farbe("weiß")\nschildkroete.farbe("grün")\n'
                    'schildkroete.farbe("#ff0000")',
                    [('color', 'red'), ('color', 'white'), ('color', 'green'), ('color', '#ff0000')])

    def test_text_statt_zahl(self):
        with self.assertRaisesRegex(TypeError, "'vorwaerts' erwartet eine Zahl"):
            lauf('schildkroete.vorwaerts("a")', Attrappe())

    def test_falsche_argumentanzahl(self):
        with self.assertRaisesRegex(TypeError, "'drehen' erwartet 1 Argument"):
            lauf('schildkroete.drehen()', Attrappe())
        with self.assertRaisesRegex(TypeError, "'stift_hoch' erwartet 0 Argument"):
            lauf('schildkroete.stift_hoch(1)', Attrappe())

    def test_farbe_kein_text(self):
        with self.assertRaisesRegex(TypeError, "'farbe' erwartet einen Text"):
            lauf('schildkroete.farbe(5)', Attrappe())

    def test_turtle_nicht_importierbar(self):
        echt = builtins.__import__

        def blockiert(name, *a, **k):
            if name == 'turtle':
                raise ImportError('kein tkinter')
            return echt(name, *a, **k)

        with mock.patch('builtins.__import__', blockiert):
            with self.assertRaisesRegex(RuntimeError, 'Turtle-Grafik nicht verfügbar: kein tkinter'):
                lauf('schildkroete.vorwaerts(1)')

    def test_fehlendes_display(self):
        class TclError(Exception):
            pass

        a = Attrappe()
        a.forward = mock.Mock(side_effect=TclError('no display'))
        with self.assertRaisesRegex(RuntimeError, 'Turtle-Grafik nicht verfügbar: no display'):
            lauf('schildkroete.vorwaerts(1)', a)

    def test_deutscher_fehler_in_fange(self):
        code = ('sei r = "ok"\nversuche {\n    schildkroete.vorwaerts("x")\n'
                '} fange TypFehler {\n    r = "gefangen"\n}\nr')
        self.assertEqual(lauf(code, Attrappe()), 'gefangen')


if __name__ == '__main__':
    unittest.main()
