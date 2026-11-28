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


class TestZusammenspielMerkmale(unittest.TestCase):
    """Generatoren zusammen mit __iter__/__laenge__, Dekoratoren, Mustervergleich, ?., Fehlerklassen und 'lade'."""

    def test_generator_als_iter_einer_klasse_mit_laenge(self):
        code = ('klasse Kasten {\n funktion __init__(dies, n) { dies.n = n }\n'
                ' funktion __iter__(dies) { für i in bereich(dies.n) { ergib i * 10 } }\n'
                ' funktion __laenge__(dies) { zurück dies.n }\n}\n'
                'sei k = neu Kasten(3)\ndrucke(laenge(k), liste(k), summe(k))\n'
                'sei [a, b, c] = k\ndrucke(a, b, c)\nfür v in k { drucke(v) }')
        self.assertEqual(ausgabe(code), ['3 [0, 10, 20] 30', '0 10 20', '0', '10', '20'])

    def test_dekorator_umhuellt_generator_mit_generator(self):
        code = ('funktion zwei(f) { zurück funktion(n) { für x in f(n) { ergib x * 2 } } }\n'
                '@zwei\nfunktion zaehle(n) { für i in bereich(n) { ergib i } }\n'
                'drucke(typ(zaehle(3)), liste(zaehle(3)))')
        self.assertEqual(ausgabe(code), ['Generator [0, 2, 4]'])

    def test_dekorator_reicht_generator_unveraendert_durch(self):
        code = ('funktion wickel(f) -> funktion(n) -> f(n)\n'
                '@wickel\nfunktion g(n) { für i in bereich(n) { ergib i } }\n'
                'sei h = g(3)\ndrucke(typ(h), naechstes(h), liste(h))')
        self.assertEqual(ausgabe(code), ['Generator 0 [1, 2]'])

    def test_passe_ueber_generatorwerte_mit_sei_mustern(self):
        code = ('funktion g() { ergib 1\n ergib [1, 2]\n ergib {"a": 5}\n ergib "text"\n ergib nichts\n ergib 7 }\n'
                'für v in g() { passe v {\n fall 1: { drucke("eins") }\n fall sei [a, b]: { drucke("paar", a, b) }\n'
                ' fall sei {"a": x}: { drucke("dict", x) }\n fall nichts: { drucke("nichts") }\n'
                ' fall Ganzzahl n wenn n > 5: { drucke("gross", n) }\n sonst: { drucke("?") } } }')
        self.assertEqual(ausgabe(code), ['eins', 'paar 1 2', 'dict 5', '?', 'nichts', 'gross 7'])

    def test_optional_chaining_auf_iterator_instanz(self):
        code = ('klasse Z {\n funktion __init__(dies, n) { dies.i = 0\n dies.n = n }\n'
                ' funktion __iter__(dies) { zurück dies }\n'
                ' funktion __naechstes__(dies) { wenn dies.i >= dies.n { werfe IterationsEnde() }\n dies.i += 1\n zurück dies.i }\n'
                ' funktion name(dies) { zurück "z" }\n}\n'
                'sei z = neu Z(2)\nsei q = nichts\n'
                'drucke(z?.name(), z?.n, q?.name(), q?.n)\ndrucke(naechstes(z), z?.i)\ndrucke(liste(z), z?.i)')
        self.assertEqual(ausgabe(code), ['z 2 nichts nichts', '1 1', '[2] 2'])

    def test_eigene_fehlerklasse_aus_generator_aussen_und_innen_gefangen(self):
        code = ('klasse MeinFehler(Fehler) { funktion __init__(dies, msg, code) { dies.nachricht = msg\n dies.code = code } }\n'
                'funktion g() { ergib 1\n versuche { werfe neu MeinFehler("innen", 5) } fange (MeinFehler) e { ergib e.code }\n'
                ' werfe neu MeinFehler("aus gen", 7)\n ergib "nie" }\n'
                'versuche { für x in g() { drucke("x", x) } } fange (MeinFehler) e { drucke("aussen", e.nachricht, e.code, e.art) }\n'
                'sei h = g()\nnaechstes(h)\nnaechstes(h)\nversuche { naechstes(h) } fange (MeinFehler) e { drucke("gefangen", e.code) }\n'
                'versuche { naechstes(h) } fange (IterationsEnde) e { drucke("danach zu Ende") }')
        self.assertEqual(ausgabe(code), ['x 1', 'x 5', 'aussen aus gen 7 MeinFehler', 'gefangen 7', 'danach zu Ende'])

    def test_generator_aus_geladenem_modul(self):
        import tempfile
        with tempfile.TemporaryDirectory() as ordner:
            with open(os.path.join(ordner, 'm.deu'), 'w', encoding='utf-8') as f:
                f.write('funktion zaehle(n) { sei i = 0\n solange i < n { i += 1\n ergib i } }\n'
                        'funktion kaputt() { ergib 1\n sei z = 1 / 0\n ergib 2 }\n')
            code = ('lade "m.deu" als m\ndrucke(typ(m.zaehle(2)), liste(m.zaehle(3)))\n'
                    'sei g = m.zaehle(2)\ndrucke(naechstes(g))\n'
                    'versuche { für x in m.kaputt() { drucke(x) } } fange e { drucke(e.art, e.zeile) }')
            puffer = io.StringIO()
            with contextlib.redirect_stdout(puffer):
                Interpreter(ladepfad=ordner).ausfuehren(parse(code))
        self.assertEqual(puffer.getvalue().splitlines(), ['Generator [1, 2, 3]', '1', '1', 'DivisionDurchNullFehler 5'])


class TestVorzeitigesSchliessen(unittest.TestCase):
    """Schleifen schließen einen Generator beim vorzeitigen Ende sofort; Fehler aus 'endlich' werden gemeldet."""
    G = ('funktion g() { versuche { ergib 1\n ergib 2 } endlich { drucke("endlich") } }\n'
         'funktion k() { versuche { ergib 1\n ergib 2 } endlich { werfe WertFehler("aus endlich") } }\n')

    def test_abbrechen_schliesst_sofort(self):
        self.assertEqual(ausgabe(self.G + 'für x in g() { drucke(x)\n abbrechen }\ndrucke("danach")'),
                         ['1', 'endlich', 'danach'])

    def test_fehler_aus_endlich_bei_abbrechen_mit_ort(self):
        msg = fehler(self.G + 'für x in k() { abbrechen }', ValueError)
        self.assertIn('Zeile 4', msg)
        self.assertIn('aus endlich', msg)

    def test_fehler_aus_endlich_ist_fangbar(self):
        code = self.G + 'versuche { für x in k() { abbrechen } } fange (WertFehler) e { drucke("gefangen", e.nachricht, e.zeile) }'
        self.assertEqual(ausgabe(code), ['gefangen aus endlich 4'])

    def test_fehler_aus_endlich_bei_zurueck_in_funktion(self):
        code = self.G + ('funktion f() { für x in k() { zurück x } }\n'
                         'versuche { f() } fange (WertFehler) e { drucke("gefangen", e.nachricht) }')
        self.assertEqual(ausgabe(code), ['gefangen aus endlich'])

    def test_laufender_fehler_bleibt_der_gemeldete(self):
        code = self.G + ('versuche { für x in k() { werfe TypFehler("original") } } '
                         'fange e { drucke(e.art, e.nachricht) }')
        self.assertEqual(ausgabe(code), ['TypFehler original'])

    def test_in_generator_schleife(self):
        code = self.G + ('funktion h() { für x in k() { ergib x\n abbrechen }\n ergib "fertig" }\n'
                         'sei q = h()\ndrucke(naechstes(q))\n'
                         'versuche { naechstes(q) } fange (WertFehler) e { drucke("gefangen", e.nachricht) }')
        self.assertEqual(ausgabe(code), ['1', 'gefangen aus endlich'])

    def test_in_generator_schleife_ohne_fehler(self):
        code = self.G + ('funktion h() { für x in g() { ergib x\n abbrechen }\n ergib "fertig" }\ndrucke(liste(h()))')
        self.assertEqual(ausgabe(code), ['endlich', '[1, fertig]'])

    def test_voll_durchlaufen_laeuft_endlich_einmal(self):
        self.assertEqual(ausgabe(self.G + 'für x in g() { drucke(x) }'), ['1', '2', 'endlich'])

    def test_verwerfen_ohne_schleife_keine_rohe_ausgabe(self):
        gemeldet = []
        code = self.G + 'sei q = k()\nnaechstes(q)\nq = nichts'
        with mock.patch.object(sys, 'unraisablehook', gemeldet.append):
            ausgabe(code)
            gc.collect()
        self.assertEqual(gemeldet, [])

    def test_verwerfen_ohne_fehler_fuehrt_endlich_aus(self):
        self.assertEqual(ausgabe(self.G + 'sei q = g()\nnaechstes(q)\nq = nichts\ndrucke("danach")'),
                         ['endlich', 'danach'])

    def test_cli_meldet_fehler_mit_exitcode(self):
        import subprocess
        wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        code = self.G + 'für x in k() { abbrechen }'
        ergebnis = subprocess.run([sys.executable, '-m', 'deutsch', '-c', code], cwd=wurzel,
                                  capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertNotEqual(ergebnis.returncode, 0)
        self.assertIn('aus endlich', ergebnis.stderr)
        self.assertNotIn('Exception ignored', ergebnis.stderr)

    def test_comprehension_fehler_schliesst_generator_sofort(self):
        code = self.G + ('versuche { sei l = [1 / (x - 1) für x in g()] } fange e { drucke("gefangen", e.art) }\n'
                         'drucke("danach")')
        self.assertEqual(ausgabe(code), ['endlich', 'gefangen DivisionDurchNullFehler', 'danach'])

    def test_comprehension_laufender_fehler_bleibt_der_gemeldete(self):
        code = self.G + 'versuche { sei l = [1 / 0 für x in k()] } fange e { drucke(e.art) }'
        self.assertEqual(ausgabe(code), ['DivisionDurchNullFehler'])

    def test_comprehension_voll_durchlaufen_endlich_einmal(self):
        self.assertEqual(ausgabe(self.G + 'drucke([x für x in g()])'), ['endlich', '[1, 2]'])


def _cli(code, eingabe=None, argumente=()):
    import subprocess
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = list(argumente) if eingabe is not None else ['-c', code]
    return subprocess.run([sys.executable, '-m', 'deutsch', *args], cwd=wurzel, input=eingabe,
                          capture_output=True, text=True, encoding='utf-8', timeout=60)


class TestProgrammendeSchliesst(unittest.TestCase):
    """Bei Programmende noch angehaltene Generatoren: 'endlich' läuft deterministisch, umgekehrte Erzeugungsreihenfolge."""
    @staticmethod
    def G(n):
        return f'funktion g{n}() {{ versuche {{ ergib 1\n ergib 2 }} endlich {{ drucke("endlich {n}") }} }}\n'

    def test_angehaltene_generatoren_in_umgekehrter_reihenfolge(self):
        r = _cli(self.G(1) + self.G(2) + 'sei a = g1()\nsei b = g2()\nnaechstes(a)\nnaechstes(b)\ndrucke("ende")')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.splitlines(), ['ende', 'endlich 2', 'endlich 1'])
        self.assertEqual(r.stderr, '')

    def test_fehler_aus_endlich_ist_normale_meldung_mit_exitcode_1(self):
        r = _cli('funktion k() { versuche { ergib 1\n ergib 2 } endlich { werfe WertFehler("aus endlich") } }\n'
                 'sei q = k()\nnaechstes(q)')
        self.assertEqual(r.returncode, 1)
        self.assertIn('[WertFehler]', r.stderr)
        self.assertIn('aus endlich', r.stderr)
        self.assertNotIn('Traceback', r.stderr)
        self.assertNotIn('Exception ignored', r.stderr)

    def test_programmfehler_bleibt_der_gemeldete_endlich_laeuft_trotzdem(self):
        r = _cli('funktion k() { versuche { ergib 1\n ergib 2 } endlich { drucke("aufgeräumt")\n werfe WertFehler("aus endlich") } }\n'
                 'sei q = k()\nnaechstes(q)\nwerfe TypFehler("original")')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.splitlines(), ['aufgeräumt'])
        self.assertIn('[TypFehler]', r.stderr)
        self.assertNotIn('aus endlich', r.stderr)

    def test_beendeter_generator_wird_nicht_nochmal_geschlossen(self):
        r = _cli(self.G(1) + 'für x in g1() { drucke(x) }')
        self.assertEqual(r.stdout.splitlines(), ['1', '2', 'endlich 1'])

    def test_repl_schliesst_erst_beim_beenden(self):
        r = _cli('', eingabe=self.G(1) + 'sei q = g1()\nnaechstes(q)\ndrucke("noch da")\nbeenden\n')
        zeilen = [z.replace('>>> ', '').strip() for z in r.stdout.splitlines()]
        self.assertLess(zeilen.index('noch da'), zeilen.index('endlich 1'))
        self.assertEqual(zeilen.count('endlich 1'), 1)


class _UnterbrechenderStapel(list):
    """Wirft ein Strg+C genau nach dem nächsten append: simuliert eine Ausnahme von außen in der Lücke
    zwischen dem Ändern des Zustands und dem 'try', das ihn zurücksetzt."""
    scharf = False

    def append(self, x):
        super().append(x)
        if self.scharf:
            self.scharf = False
            raise KeyboardInterrupt


class TestUnterbrechungInDerLuecke(unittest.TestCase):
    """Zustand (Aufrufkette, Datei, Ladekette) muss nach einer Ausnahme von außen an jeder Stelle sauber sein."""

    def _interpreter(self, code):
        ip = Interpreter()
        s = _UnterbrechenderStapel(ip._aufruf_stack)
        ip._aufruf_stack = s
        with contextlib.redirect_stdout(io.StringIO()):
            ip.ausfuehren(parse(code))
        return ip, s

    def _sauber(self, ip):
        self.assertEqual(list(ip._aufruf_stack), [])
        self.assertEqual(list(ip._lade_stack), [])
        self.assertIsNone(ip._aktuelle_datei)

    def test_next_nach_aufrufkette(self):
        ip, s = self._interpreter('funktion f() { ergib 1\n ergib 2 }\nsei g = f()')
        g = ip.global_umgebung.hole('g')
        s.scharf = True
        with self.assertRaises(KeyboardInterrupt):
            next(g)
        self._sauber(ip)
        self.assertFalse(g._laeuft)
        self.assertEqual((next(g), next(g)), (1, 2))  # weiter nutzbar
        self._sauber(ip)

    def test_close_nach_aufrufkette(self):
        ip, s = self._interpreter('funktion f() { versuche { ergib 1 } endlich { drucke("e") } }\nsei g = f()')
        g = ip.global_umgebung.hole('g')
        s.scharf = True
        with self.assertRaises(KeyboardInterrupt):
            g.close()
        self._sauber(ip)
        g.close()
        self._sauber(ip)

    def test_funktionsaufruf_nach_aufrufkette(self):
        ip, s = self._interpreter('funktion f() { zurück 5 }')
        s.scharf = True
        with self.assertRaises(KeyboardInterrupt):
            ip.ausfuehren(parse('f()'))
        self._sauber(ip)
        self.assertEqual(ip.ausfuehren(parse('f()')), 5)

    def test_lade_nach_ladekette(self):
        import tempfile
        with tempfile.TemporaryDirectory() as ordner:
            with open(os.path.join(ordner, 'm.deu'), 'w', encoding='utf-8') as f:
                f.write('sei a = 1\n')
            ip = Interpreter(ladepfad=ordner)
            ip._lade_stack = s = _UnterbrechenderStapel()
            s.scharf = True
            with self.assertRaises(KeyboardInterrupt):
                ip.ausfuehren(parse('lade "m.deu" als m'))
            self._sauber(ip)
            ip.ausfuehren(parse('lade "m.deu" als m'))  # kein 'zyklischer Import' durch einen Rest in der Ladekette
            self._sauber(ip)

    def test_unterbrechung_im_finally_von_next(self):
        # Strg+C mitten im 'finally' von __next__ (vor dem Aufräumen): die äußere Ebene räumt trotzdem auf
        from deutsch.interpreter import DeutschGenerator
        ip = Interpreter()
        echt = DeutschGenerator._verlassen
        zaehler = [0]

        def verlassen(gen, sicherung):
            zaehler[0] += 1
            if zaehler[0] == 3:
                raise KeyboardInterrupt
            echt(gen, sicherung)

        with mock.patch.object(DeutschGenerator, '_verlassen', verlassen):
            with self.assertRaises(KeyboardInterrupt):
                ip.ausfuehren(parse('funktion g() { solange wahr { ergib 1 } }\nfür x in g() { }'))
        self._sauber(ip)


if __name__ == '__main__':
    unittest.main()
