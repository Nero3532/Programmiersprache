# -*- coding: utf-8 -*-
"""Tests für Generatoren ('ergib'): ohne Thread, jeder von _gen_* behandelte Anweisungstyp mit 'ergib' darin.

Unendliche Generatoren werden in jedem Test mit 'abbrechen'/Zähler oder 'naechstes' begrenzt; die Hilfe
'sicherung()' bricht zusätzlich nach einer Frist ab, damit ein Fehler nie als Hänger endet."""
import _thread
import contextlib
import gc
import io
import os
import signal
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as main_modul
from deutsch.interpreter import Interpreter
from deutsch.lexer import Lexer
from deutsch.parser import Parser


def parse(code):
    return Parser(Lexer(code).tokenisieren()).parse()


def interpreter_mit_sicherung(frist=20):
    ip = Interpreter()
    ende = time.monotonic() + frist

    def sicherung():
        if time.monotonic() > ende:
            raise RuntimeError('Testsicherung: Generator läuft zu lange')
    ip.global_umgebung.setze('sicherung', sicherung)
    return ip


def ausgabe(code):
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        interpreter_mit_sicherung().ausfuehren(parse(code))
    return puffer.getvalue().splitlines()


def fehler(code, art=Exception):
    with contextlib.redirect_stdout(io.StringIO()):
        with unittest.TestCase().assertRaises(art) as ctx:
            interpreter_mit_sicherung().ausfuehren(parse(code))
    return str(ctx.exception)


class TestAnweisungstypen(unittest.TestCase):
    """Jeder Besucher _gen_*: Block, Wenn, Solange, Für, Passe, Versuche, Ergib."""

    def test_block_und_ergib(self):
        code = 'funktion f() { ergib 1\n ergib "zwei"\n ergib [3] }\ndrucke(liste(f()))'
        self.assertEqual(ausgabe(code), ['[1, zwei, [3]]'])

    def test_block_eigener_geltungsbereich_und_verzoegerung(self):
        code = ('funktion f() { drucke("start")\n sei a = 1\n ergib a\n a += 1\n ergib a\n drucke("ende") }\n'
                'sei g = f()\ndrucke("erzeugt")\ndrucke(naechstes(g))\ndrucke(naechstes(g))\ndrucke(liste(g))')
        self.assertEqual(ausgabe(code), ['erzeugt', 'start', '1', '2', 'ende', '[]'])

    def test_wenn_sonst_wenn_sonst(self):
        code = ('funktion f(n) {\n wenn n == 0 { ergib "null" } sonst wenn n == 1 { ergib "eins" } '
                'sonst { ergib "viele" }\n wenn falsch { ergib "nie" }\n}\n'
                'drucke(liste(f(0)), liste(f(1)), liste(f(5)))')
        self.assertEqual(ausgabe(code), ['[null] [eins] [viele]'])

    def test_solange_mit_abbrechen_und_weiter(self):
        code = ('funktion f() { sei i = 0\n solange wahr { i += 1\n wenn i == 2 { weiter }\n '
                'wenn i > 5 { abbrechen }\n ergib i }\n ergib "ende" }\ndrucke(liste(f()))')
        self.assertEqual(ausgabe(code), ['[1, 3, 4, 5, ende]'])

    def test_fuer_mit_abbrechen_weiter_und_muster(self):
        code = ('funktion f(paare) { für [a, b] in paare { wenn a == 2 { weiter }\n wenn a == 9 { abbrechen }\n '
                'ergib a * b } }\ndrucke(liste(f([[1, 10], [2, 20], [3, 30], [9, 90], [4, 40]])))')
        self.assertEqual(ausgabe(code), ['[10, 90]'])

    def test_passe_mit_mustern_und_waechter(self):
        code = '''funktion f(xs) {
            für x in xs {
                passe x {
                    fall 0: { ergib "null" }
                    fall Ganzzahl n wenn n < 0: { ergib "neg" }
                    fall sei [a, *rest]: { ergib a + laenge(rest) }
                    fall Ganzzahl n: { ergib n }
                    sonst: { ergib "?" }
                }
            }
        }
        drucke(liste(f([0, -3, 7, [5, 1, 1], "x"])))'''
        self.assertEqual(ausgabe(code), ['[null, neg, 7, 7, ?]'])

    def test_passe_ohne_treffer_ist_still(self):
        self.assertEqual(ausgabe('funktion f() { passe 3 { fall 1: { ergib 1 } }\n ergib 2 }\ndrucke(liste(f()))'), ['[2]'])

    def test_versuche_ergib_im_rumpf_fange_und_endlich(self):
        code = '''funktion f() {
            versuche {
                ergib "a"
                werfe WertFehler("kaputt")
                ergib "nie"
            } fange (WertFehler) e {
                ergib "gefangen: " + e.nachricht
            } endlich {
                ergib "endlich"
            }
            ergib "danach"
        }
        drucke(liste(f()))'''
        self.assertEqual(ausgabe(code), ['[a, gefangen: kaputt, endlich, danach]'])

    def test_versuche_nicht_passender_fehler_laeuft_durch_endlich(self):
        code = '''funktion f() {
            versuche { ergib 1\n werfe TypFehler("x") } fange (WertFehler) { ergib "falsch" } endlich { ergib "ende" }
        }
        sei g = f()
        drucke(naechstes(g))
        drucke(naechstes(g))
        versuche { naechstes(g) } fange (TypFehler) e { drucke("typ " + e.nachricht) }
        drucke(liste(g))'''
        self.assertEqual(ausgabe(code), ['1', 'ende', 'typ x', '[]'])

    def test_versuche_zurueck_fuehrt_endlich_aus(self):
        code = ('funktion f() { versuche { ergib 1\n zurück } endlich { drucke("aufgeräumt") }\n ergib 2 }\n'
                'drucke(liste(f()))')
        self.assertEqual(ausgabe(code), ['aufgeräumt', '[1]'])

    def test_versuche_fange_im_verbraucher_greift_fehler_aus_generator(self):
        code = ('funktion f() { ergib 1\n sei x = 1 / 0\n ergib 2 }\n'
                'versuche { für v in f() { drucke(v) } } fange (DivisionDurchNullFehler) e { drucke("fehler") }')
        self.assertEqual(ausgabe(code), ['1', 'fehler'])

    def test_ergib_in_verschachtelten_anweisungen(self):
        code = ('funktion f() { für i in [1, 2] { wenn i == 1 { versuche { solange wahr { ergib "a" \n abbrechen } } '
                'endlich { ergib "e" } } sonst { passe i { fall 2: { ergib "p" } } } } }\n'
                'drucke(liste(f()))')
        self.assertEqual(ausgabe(code), ['[a, e, p]'])

    def test_endlich_bei_vorzeitigem_ende_nach_abbrechen(self):
        code = ('funktion f() { versuche { ergib 1\n ergib 2 } endlich { drucke("endlich") } }\n'
                'für x in f() { drucke(x)\n abbrechen }\ndrucke("danach")')
        gc.collect()
        self.assertEqual(ausgabe(code), ['1', 'endlich', 'danach'])

    def test_zurueck_beendet_generator(self):
        code = 'funktion f() { ergib 1\n zurück\n ergib 2 }\ndrucke(liste(f()))'
        self.assertEqual(ausgabe(code), ['[1]'])
        code = 'funktion f() { ergib 1\n zurück 99 }\nsei g = f()\ndrucke(naechstes(g))\ndrucke(liste(g))'
        self.assertEqual(ausgabe(code), ['1', '[]'])

    def test_abbrechen_ausserhalb_schleife_im_generator_ist_fehler(self):
        self.assertIn("'abbrechen' außerhalb einer Schleife", fehler('funktion f() { ergib 1\n abbrechen }\nliste(f())'))


class TestEigenschaften(unittest.TestCase):
    def test_typ_und_text(self):
        code = ('funktion f() { ergib 1 }\nsei g = f()\ndrucke(typ(g))\ndrucke(g)\n'
                'sei h: Generator = g\npasse g { fall Generator x: { drucke("gen") } sonst: { drucke("nein") } }')
        self.assertEqual(ausgabe(code), ['Generator', '<Generator f>', 'gen'])

    def test_ende_ist_iterationsende(self):
        code = ('funktion f() { ergib 1 }\nsei g = f()\nnaechstes(g)\n'
                'versuche { naechstes(g) } fange (IterationsEnde) { drucke("zu Ende") }')
        self.assertEqual(ausgabe(code), ['zu Ende'])

    def test_unendlich_mit_abbrechen_und_naechstes(self):
        code = ('funktion nat() { sei i = 0\n solange wahr { sicherung()\n ergib i\n i += 1 } }\n'
                'für x in nat() { wenn x >= 3 { abbrechen }\n drucke(x) }\n'
                'sei g = nat()\ndrucke(naechstes(g) + naechstes(g) + naechstes(g))')
        self.assertEqual(ausgabe(code), ['0', '1', '2', '3'])

    def test_argumente_parameter_und_geschlossene_umgebung(self):
        code = ('funktion ab(start, schritt = 2) { sei x = start\n solange x < 10 { ergib x\n x += schritt } }\n'
                'drucke(liste(ab(1)), liste(ab(0, 4)))')
        self.assertEqual(ausgabe(code), ['[1, 3, 5, 7, 9] [0, 4, 8]'])

    def test_argumentfehler_schon_beim_aufruf(self):
        self.assertIn('Pflichtargument', fehler('funktion f(a) { ergib a }\nsei g = f()'))

    def test_methode_und_iter_als_generator(self):
        code = ('klasse K { funktion __init__(dies, n) { dies.n = n }\n'
                ' funktion __iter__(dies) { für i in bereich(dies.n) { ergib i * i } } }\n'
                'für x in neu K(3) { drucke(x) }\ndrucke(liste(neu K(4)))\nsei [a, *r] = neu K(3)\ndrucke(a, r)')
        self.assertEqual(ausgabe(code), ['0', '1', '4', '[0, 1, 4, 9]', '0 [1, 4]'])

    def test_dekorator_auf_generatorfunktion(self):
        code = ('funktion merke(f) { zurück funktion(*a) { zurück f(*a) } }\n'
                '@merke\nfunktion f(n) { ergib n\n ergib n + 1 }\ndrucke(liste(f(1)))')
        self.assertEqual(ausgabe(code), ['[1, 2]'])

    def test_innere_funktion_macht_aussere_nicht_zum_generator(self):
        code = ('funktion aussen() { zurück funktion() { ergib 1 } }\nsei f = aussen()\n'
                'drucke(typ(f))\ndrucke(typ(f()))\ndrucke(liste(f()))')
        self.assertEqual(ausgabe(code), ['Funktion', 'Generator', '[1]'])

    def test_lauf_im_eigenen_rumpf_ist_fehler(self):
        code = 'funktion f() { ergib naechstes(g) }\nsei g = f()\nnaechstes(g)'
        self.assertIn('läuft bereits', fehler(code))


class TestZusammenspiel(unittest.TestCase):
    G = 'funktion g(n) { für i in bereich(n) { ergib i + 1 } }\n'

    def test_iteration_und_comprehension(self):
        self.assertEqual(ausgabe(self.G + 'für x in g(3) { drucke(x) }\ndrucke([x * 2 für x in g(3) wenn x > 1])'),
                         ['1', '2', '3', '[4, 6]'])

    def test_entpacken(self):
        code = self.G + 'sei [a, b] = g(2)\ndrucke(a, b)\nsei [k, *r] = g(4)\ndrucke(k, r)\ndrucke([*g(2), 9])\ndrucke(summe(*g(3)))'
        self.assertEqual(ausgabe(code), ['1 2', '1 [2, 3, 4]', '[1, 2, 9]', '6'])

    def test_entpacken_falsche_laenge_ist_fehler(self):
        self.assertIn('Entpacken', fehler(self.G + 'sei [a, b] = g(3)') + 'Entpacken')

    def test_sammlungsfunktionen(self):
        code = self.G + ('drucke(abbilden(g(3), funktion(x) -> x * 10))\ndrucke(filtere(g(4), funktion(x) -> x % 2 == 0))\n'
                         'drucke(reduziere(g(4), funktion(a, b) -> a + b, 0))\n'
                         'drucke(liste(g(2)), menge(g(2)), summe(g(3)), alle(g(3)), einige(g(0)))\n'
                         'drucke(aufzaehlen(g(2)), zippe(g(2), ["a", "b"]), sortiere(g(3)))')
        self.assertEqual(ausgabe(code), ['[10, 20, 30]', '[2, 4]', '10',
                                         '[1, 2] {1, 2} 6 wahr falsch',
                                         '[[0, 1], [1, 2]] [[1, a], [2, b]] [1, 2, 3]'])

    def test_generator_als_quelle_fuer_generator(self):
        code = (self.G + 'funktion doppelt(q) { für x in q { ergib x * 2 } }\ndrucke(liste(doppelt(doppelt(g(3)))))')
        self.assertEqual(ausgabe(code), ['[4, 8, 12]'])

    def test_nur_einmal_durchlaufbar(self):
        self.assertEqual(ausgabe(self.G + 'sei q = g(2)\ndrucke(liste(q))\ndrucke(liste(q))'), ['[1, 2]', '[]'])

    def test_fehler_im_generator_beendet_ihn(self):
        code = ('funktion f() { ergib 1\n werfe WertFehler("x") }\nsei q = f()\nnaechstes(q)\n'
                'versuche { naechstes(q) } fange (WertFehler) { drucke("fehler") }\ndrucke(liste(q))')
        self.assertEqual(ausgabe(code), ['fehler', '[]'])


class TestFehlerort(unittest.TestCase):
    CODE = 'funktion f() {\n    ergib 1\n    sei x = 1 / 0\n    ergib 2\n}\n'

    def test_zeile_im_rumpf(self):
        msg = fehler(self.CODE + 'für v in f() { }')
        self.assertIn('Zeile 3', msg)

    def test_fehlervariable_traegt_zeile_des_rumpfs(self):
        code = self.CODE + 'versuche { liste(f()) } fange e { drucke(e.zeile) }'
        self.assertEqual(ausgabe(code), ['3'])

    def test_zeile_nach_fortsetzung_in_schleife(self):
        code = ('funktion f() {\n    sei i = 0\n    solange i < 5 {\n        ergib i\n'
                '        wenn i == 1 { sei x = 1 / 0 }\n        i += 1\n    }\n}\nliste(f())')
        self.assertIn('Zeile 5', fehler(code))

    def test_zustand_des_interpreters_bleibt_sauber(self):
        ip = interpreter_mit_sicherung()
        with contextlib.redirect_stdout(io.StringIO()):
            ip.ausfuehren(parse('funktion f() { ergib 1\n ergib 2 }\nsei g = f()\nnaechstes(g)\nfür x in f() { }'))
            with self.assertRaises(ZeroDivisionError):
                ip.ausfuehren(parse(self.CODE + 'liste(f())'))
        self.assertEqual(ip._aufruf_stack, [])
        self.assertIsNone(ip._aktuelle_datei)


class TestParser(unittest.TestCase):
    def test_ergib_ausserhalb_einer_funktion(self):
        with self.assertRaises(SyntaxError) as ctx:
            parse('ergib 1')
        self.assertIn("'ergib' ist nur im Rumpf einer Funktion erlaubt", str(ctx.exception))

    def test_ergib_in_passe_ausdruck(self):
        with self.assertRaises(SyntaxError):
            parse('funktion f() { sei x = passe 1 { fall 1: { ergib 2 } }\n zurück x }')

    def test_funktion_in_passe_ausdruck_darf_ergib(self):
        code = ('funktion f() { zurück passe 1 { fall 1: { zurück funktion() { ergib 5 } } } }\ndrucke(liste(f()()))')
        self.assertEqual(ausgabe(code), ['[5]'])

    def test_ergib_braucht_ausdruck(self):
        with self.assertRaises(SyntaxError):
            parse('funktion f() { ergib }')

    def test_ergib_ist_kein_name_mehr(self):
        with self.assertRaises(SyntaxError):
            parse('sei ergib = 1')

    def test_ergibt_bleibt_ein_name(self):
        self.assertEqual(ausgabe('sei ergibt = 1\ndrucke(ergibt)'), ['1'])


class TestKeineHaenger(unittest.TestCase):
    def test_rekursion_in_generatoren(self):
        code = ('funktion baum(n) { wenn n > 0 { für x in baum(n - 1) { ergib x }\n ergib n\n '
                'für x in baum(n - 1) { ergib x } } }\ndrucke(liste(baum(3)))\n'
                'funktion tief(n) { sicherung()\n wenn n == 0 { ergib 0 } sonst { für x in tief(n - 1) { ergib x + 1 } } }\n'
                'drucke(liste(tief(20)))')
        self.assertEqual(ausgabe(code), ['[1, 2, 1, 3, 1, 2, 1]', '[20]'])

    def test_endlose_rekursion_endet_mit_rekursionsfehler(self):
        code = 'funktion e(n) { sicherung()\n für x in e(n + 1) { ergib x } }\nnaechstes(e(0))'
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RecursionError):
                interpreter_mit_sicherung().ausfuehren(parse(code))

    def test_bereich_riesig_als_quelle(self):
        code = ('funktion f() { für i in bereich(10 ** 12) { sicherung()\n ergib i } }\n'
                'sei g = f()\ndrucke(naechstes(g), naechstes(g), naechstes(g))\n'
                'für x in f() { wenn x == 2 { abbrechen } }\ndrucke("fertig")')
        self.assertEqual(ausgabe(code), ['0 1 2', 'fertig'])

    @unittest.skipUnless(signal.getsignal(signal.SIGINT) is signal.default_int_handler,
                         'SIGINT-Handler ist ersetzt (z. B. unittest -c)')
    def test_strg_c_stoppt_endlosen_generator(self):
        ip = Interpreter()
        laeuft = threading.Event()
        zaehler = [0]
        frist = time.monotonic() + 60

        def haken():
            laeuft.set()
            zaehler[0] += 1
            if time.monotonic() > frist:  # Sicherung: ohne Strg+C endet der Test trotzdem
                raise RuntimeError('Testsicherung: Strg+C kam nicht an')
        ip.global_umgebung.setze('haken', haken)
        programm = parse('funktion g() { solange wahr { ergib haken() } }\nfür x in g() { }')

        def strg_c():
            laeuft.wait(30)
            _thread.interrupt_main()

        sender = threading.Thread(target=strg_c, daemon=True)
        sender.start()
        try:
            with mock.patch.object(main_modul, '_STOPP_WARTEZEIT', 30):
                with self.assertRaises(KeyboardInterrupt):
                    main_modul.im_grossen_stack(ip.ausfuehren, programm)
        finally:
            frist = 0
            sender.join(30)
        vorher = zaehler[0]
        time.sleep(0.3)
        self.assertEqual(zaehler[0], vorher, 'der Generator läuft nach Strg+C weiter')
        self.assertEqual(ip._aufruf_stack, [])


if __name__ == '__main__':
    unittest.main()
