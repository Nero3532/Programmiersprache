# -*- coding: utf-8 -*-
"""
Tests für Module und Typ-Hinweise: Basisklassen und Typ-Hinweise mit Punktpfad ('modul.Klasse'),
Parameter-Hinweise bei Neuzuweisung, Aufrufkette mit Dateinamen, erneutes Werfen gefangener Fehler
(Datei und Zeile bleiben erhalten) und Konstanten in der Destrukturierung.

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import tempfile
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT_WURZEL)

from deutsch.lexer import Lexer
from deutsch.parser import Parser
from deutsch.interpreter import AufrufEintrag, AusnahmeFehler, Interpreter
from main import _ausfuehren


def lauf(code: str, interpreter: Interpreter = None, ladepfad: str = None):
    """Tokenisiert, parst und führt Code aus. Gibt (ergebnis, interpreter) zurück."""
    if interpreter is None:
        interpreter = Interpreter(ladepfad=ladepfad)
    baum = Parser(Lexer(code).tokenisieren()).parse()
    return interpreter.ausfuehren(baum), interpreter


def datei_schreiben(ordner: str, name: str, inhalt: str) -> str:
    """Legt ordner/name (name darf '/' enthalten) samt Unterordnern an und gibt den Pfad zurück."""
    pfad = os.path.join(ordner, *name.split('/'))
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, 'w', encoding='utf-8') as f:
        f.write(inhalt)
    return pfad


HILFE = '''\
klasse Basis {
    funktion hallo(dies) { zurück "hallo aus Basis" }
    funktion wer(dies) { zurück "basis" }
}
konstante zahl = 7
'''


class ModulTestCase(unittest.TestCase):
    """Legt je Test einen temporären Ordner an; 'hilfe.deu' (Klasse Basis) liegt schon darin."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ordner = tmp.name
        self.hilfe = datei_schreiben(self.ordner, 'hilfe.deu', HILFE)

    def datei(self, name: str, inhalt: str) -> str:
        return datei_schreiben(self.ordner, name, inhalt)

    def laufe(self, code: str):
        """Führt code im Ordner aus. Gibt (ergebnis, interpreter) zurück."""
        return lauf(code, ladepfad=self.ordner)

    def fehler(self, code: str, fehlertyp):
        """Führt code aus, erwartet fehlertyp und gibt die Ausnahme zurück."""
        with self.assertRaises(fehlertyp) as ctx:
            self.laufe(code)
        return ctx.exception

    def cli(self, hauptcode: str, dateiname: str = 'haupt.deu'):
        """Führt hauptcode wie die CLI aus (Ordner als Ladepfad). Gibt den Fehlertext zurück."""
        interpreter = Interpreter(ladepfad=self.ordner)
        ergebnis, text = _ausfuehren(hauptcode, interpreter, dateiname)
        self.assertIsNotNone(text, 'Es wurde ein Fehler erwartet')
        return text


# ------------------------------------------------------ 1. Basisklassen mit Punktpfad

class TestBasisklassenMitPunktpfad(ModulTestCase):
    def test_basis_aus_modul_wird_geerbt(self):
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            klasse Kind(h.Basis) { }
            sei k = neu Kind()
            k.hallo()
        ''')
        self.assertEqual(ergebnis, 'hallo aus Basis')

    def test_unterklasse_ueberschreibt_methode_der_modul_basis(self):
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            klasse Kind(h.Basis) { funktion wer(dies) { zurück "kind" } }
            [neu Kind().wer(), neu Kind().hallo()]
        ''')
        self.assertEqual(ergebnis, ['kind', 'hallo aus Basis'])

    def test_gemischte_basen_lokal_und_modul(self):
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            klasse Lokal { funktion wer(dies) { zurück "lokal" } funktion nur_lokal(dies) { zurück 1 } }
            klasse Kind(Lokal, h.Basis) { }
            sei k = neu Kind()
            [k.wer(), k.nur_lokal(), k.hallo()]
        ''')
        # Reihenfolge der Basen zählt: links zuerst (Lokal vor h.Basis)
        self.assertEqual(ergebnis, ['lokal', 1, 'hallo aus Basis'])

    def test_gemischte_basen_modul_zuerst(self):
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            klasse Lokal { funktion wer(dies) { zurück "lokal" } }
            klasse Kind(h.Basis, Lokal) { }
            neu Kind().wer()
        ''')
        self.assertEqual(ergebnis, 'basis')

    def test_zwei_basen_aus_zwei_modulen(self):
        self.datei('zweit.deu', 'klasse Zweite { funktion zwei(dies) { zurück 2 } }\n')
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            lade "zweit.deu" als z
            klasse Kind(h.Basis, z.Zweite) { }
            sei k = neu Kind()
            [k.hallo(), k.zwei()]
        ''')
        self.assertEqual(ergebnis, ['hallo aus Basis', 2])

    def test_mehrstufiger_pfad(self):
        self.datei('aussen.deu', 'lade "hilfe.deu" als h\n')
        ergebnis, _ = self.laufe('''
            lade "aussen.deu" als a
            klasse Kind(a.h.Basis) { }
            neu Kind().hallo()
        ''')
        self.assertEqual(ergebnis, 'hallo aus Basis')

    def test_instanz_ist_auch_instanz_der_modul_basis(self):
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            klasse Kind(h.Basis) { }
            sei b: h.Basis = neu Kind()
            b.wer()
        ''')
        self.assertEqual(ergebnis, 'basis')

    def test_in_geladener_datei_mit_modulbasis(self):
        self.datei('unter/kind.deu', '''lade "../hilfe.deu" als h
klasse Kind(h.Basis) { }
''')
        ergebnis, _ = self.laufe('''
            lade "unter/kind.deu" als k
            neu k.Kind().hallo()
        ''')
        self.assertEqual(ergebnis, 'hallo aus Basis')

    def test_unbekannte_klasse_im_modul(self):
        e = self.fehler('lade "hilfe.deu" als h\nklasse K(h.Gibtsnicht) { }', AttributeError)
        self.assertIn("Namensraum 'h' hat kein Attribut 'Gibtsnicht'", str(e))

    def test_unbekanntes_modul(self):
        e = self.fehler('klasse K(nirgends.Basis) { }', NameError)
        self.assertIn("'nirgends'", str(e))

    def test_pfad_ohne_klasse(self):
        e = self.fehler('lade "hilfe.deu" als h\nklasse K(h.zahl) { }', TypeError)
        self.assertIn("'h.zahl' ist keine Klasse", str(e))

    def test_syntaxfehler_bei_unvollstaendigem_pfad(self):
        with self.assertRaises(SyntaxError):
            lauf('klasse K(h.) { }')
        with self.assertRaises(SyntaxError):
            lauf('klasse K(h.Basis,) { }')


# ----------------------------------------------------- 2. Typ-Hinweise mit Punktpfad

class TestTypHinweiseMitPunktpfad(ModulTestCase):
    VORSPANN = 'lade "hilfe.deu" als h\nklasse Kind(h.Basis) { }\n'

    def test_sei_mit_punktpfad(self):
        ergebnis, _ = self.laufe(self.VORSPANN + 'sei k: h.Basis = neu h.Basis()\nk.wer()')
        self.assertEqual(ergebnis, 'basis')

    def test_konstante_mit_punktpfad(self):
        ergebnis, _ = self.laufe(self.VORSPANN + 'konstante k: h.Basis = neu h.Basis()\nk.hallo()')
        self.assertEqual(ergebnis, 'hallo aus Basis')

    def test_unterklasse_erfuellt_hinweis_der_basis(self):
        ergebnis, _ = self.laufe(self.VORSPANN + 'sei k: h.Basis = neu Kind()\nk.wer()')
        self.assertEqual(ergebnis, 'basis')

    def test_sei_falscher_typ(self):
        e = self.fehler(self.VORSPANN + 'sei k: h.Basis = "text"', TypeError)
        self.assertIn("Variable 'k': erwartet Typ 'h.Basis', bekam Zeichenkette", str(e))

    def test_basis_ist_keine_unterklasse(self):
        e = self.fehler(self.VORSPANN + 'sei k: Kind = neu h.Basis()', TypeError)
        self.assertIn("erwartet Typ 'Kind', bekam Basis", str(e))

    def test_unbekannte_klasse_im_pfad(self):
        e = self.fehler(self.VORSPANN + 'sei k: h.Gibtsnicht = 1', TypeError)
        self.assertIn("Unbekannter Typ-Hinweis: 'h.Gibtsnicht'", str(e))

    def test_unbekanntes_modul_im_pfad(self):
        e = self.fehler('sei k: nirgends.Basis = 1', TypeError)
        self.assertIn("Unbekannter Typ-Hinweis: 'nirgends.Basis'", str(e))

    def test_pfad_auf_nicht_klasse(self):
        e = self.fehler(self.VORSPANN + 'sei k: h.zahl = 1', TypeError)
        self.assertIn("Unbekannter Typ-Hinweis: 'h.zahl'", str(e))

    def test_neuzuweisung_wird_geprueft(self):
        ergebnis, _ = self.laufe(self.VORSPANN + 'sei k: h.Basis = neu h.Basis()\nk = neu Kind()\nk.wer()')
        self.assertEqual(ergebnis, 'basis')
        e = self.fehler(self.VORSPANN + 'sei k: h.Basis = neu h.Basis()\nk = 5', TypeError)
        self.assertIn("Variable 'k': erwartet Typ 'h.Basis', bekam Ganzzahl", str(e))

    def test_parameter_mit_punktpfad(self):
        code = self.VORSPANN + 'funktion kontrolle(k: h.Basis) { zurück k.wer() }\n'
        ergebnis, _ = self.laufe(code + 'kontrolle(neu Kind())')
        self.assertEqual(ergebnis, 'basis')
        e = self.fehler(code + 'kontrolle(5)', TypeError)
        self.assertIn("Parameter 'k': erwartet Typ 'h.Basis', bekam Ganzzahl", str(e))

    def test_parameter_mit_standardwert_und_punktpfad(self):
        code = self.VORSPANN + 'funktion kontrolle(k: h.Basis = neu h.Basis()) { zurück k.wer() }\n'
        ergebnis, _ = self.laufe(code + 'kontrolle()')
        self.assertEqual(ergebnis, 'basis')
        self.fehler(code + 'kontrolle("x")', TypeError)

    def test_methodenparameter_mit_punktpfad(self):
        code = self.VORSPANN + 'klasse Nutzer { funktion nimm(dies, k: h.Basis) { zurück k.wer() } }\n'
        ergebnis, _ = self.laufe(code + 'neu Nutzer().nimm(neu Kind())')
        self.assertEqual(ergebnis, 'basis')
        e = self.fehler(code + 'neu Nutzer().nimm(1)', TypeError)
        self.assertIn("Parameter 'k': erwartet Typ 'h.Basis'", str(e))

    def test_rueckgabetyp_mit_punktpfad(self):
        code = self.VORSPANN + '''
            funktion gut() -> h.Basis { zurück neu Kind() }
            funktion schlecht() -> h.Basis { zurück "text" }
            funktion nichts_zurueck() -> h.Basis { }
        '''
        ergebnis, _ = self.laufe(code + 'gut().wer()')
        self.assertEqual(ergebnis, 'basis')
        e = self.fehler(code + 'schlecht()', TypeError)
        self.assertIn("Rückgabewert von 'schlecht': erwartet Typ 'h.Basis', bekam Zeichenkette", str(e))
        e = self.fehler(code + 'nichts_zurueck()', TypeError)
        self.assertIn("Rückgabewert von 'nichts_zurueck': erwartet Typ 'h.Basis', bekam Nichts", str(e))

    def test_rueckgabetyp_ueber_mehrere_zeilen_in_klammern(self):
        ergebnis, _ = self.laufe(self.VORSPANN + '''
            sei fabriken = [
                funktion() -> h.Basis { zurück neu Kind() },
            ]
            fabriken[0]().wer()
        ''')
        self.assertEqual(ergebnis, 'basis')

    def test_kurzform_mit_punktpfad_bleibt_ausdruck(self):
        # '-> h.zahl' ohne '{' ist weiter die Kurzform und kein Rückgabetyp
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            sei f = funktion(x) -> h.zahl + x
            sei g = funktion(x) -> h.zahl
            [f(1), g(1)]
        ''')
        self.assertEqual(ergebnis, [8, 7])

    def test_hinweis_wird_in_der_definierenden_datei_aufgeloest(self):
        # 'h' kennt nur fabrik.deu, nicht das Hauptskript
        self.datei('fabrik.deu', 'lade "hilfe.deu" als h\n'
                                 'funktion kontrolle(k: h.Basis) -> h.Basis { zurück k }\n')
        code = 'lade "fabrik.deu" als f\n'
        ergebnis, _ = self.laufe(code + 'f.kontrolle(neu f.h.Basis()).wer()')
        self.assertEqual(ergebnis, 'basis')
        e = self.fehler(code + 'f.kontrolle(1)', TypeError)
        self.assertIn("Parameter 'k': erwartet Typ 'h.Basis', bekam Ganzzahl", str(e))


# ------------------------------- 3. Parameter-Hinweise gelten auch bei Neuzuweisung

class TestParameterHinweisBeiZuweisung(ModulTestCase):
    def test_gueltige_zuweisung_im_koerper(self):
        ergebnis, _ = self.laufe('funktion f(a: Ganzzahl) { a = 5\n a += 2\n zurück a }\nf(1)')
        self.assertEqual(ergebnis, 7)

    def test_falsche_zuweisung_hat_dieselbe_meldung_wie_sei(self):
        e_param = self.fehler('funktion f(a: Ganzzahl) { a = "x" }\nf(1)', TypeError)
        e_sei = self.fehler('sei a: Ganzzahl = 1\na = "x"', TypeError)
        meldung = "Variable 'a': erwartet Typ 'Ganzzahl', bekam Zeichenkette"
        self.assertIn(meldung, str(e_param))
        self.assertIn(meldung, str(e_sei))

    def test_zuweisung_in_verschachteltem_block(self):
        e = self.fehler('funktion f(a: Ganzzahl) { wenn wahr { a = "x" } }\nf(1)', TypeError)
        self.assertIn("Variable 'a': erwartet Typ 'Ganzzahl', bekam Zeichenkette", str(e))

    def test_zuweisung_in_schleife(self):
        e = self.fehler('funktion f(a: Ganzzahl) { für i in [1, 2] { a = "x" } }\nf(1)', TypeError)
        self.assertIn("erwartet Typ 'Ganzzahl'", str(e))

    def test_zuweisung_in_innerer_funktion(self):
        e = self.fehler('funktion f(a: Ganzzahl) { funktion g() { a = "x" }\n g() }\nf(1)', TypeError)
        self.assertIn("Variable 'a': erwartet Typ 'Ganzzahl'", str(e))

    def test_verbundzuweisung_prueft_den_hinweis(self):
        e = self.fehler('funktion f(a: Ganzzahl) { a += 0.5 }\nf(1)', TypeError)
        self.assertIn("Variable 'a': erwartet Typ 'Ganzzahl', bekam Kommazahl", str(e))

    def test_destrukturierende_zuweisung_prueft_den_hinweis(self):
        code = 'funktion f(a: Ganzzahl, b) { [a, b] = %s\n zurück [a, b] }\n'
        ergebnis, _ = self.laufe((code % '[5, "y"]') + 'f(1, 2)')
        self.assertEqual(ergebnis, [5, 'y'])
        e = self.fehler((code % '["x", 1]') + 'f(1, 2)', TypeError)
        self.assertIn("Variable 'a': erwartet Typ 'Ganzzahl', bekam Zeichenkette", str(e))

    def test_methodenparameter(self):
        code = 'klasse K { funktion m(dies, n: Ganzzahl) { n = %s\n zurück n } }\n'
        ergebnis, _ = self.laufe((code % '3') + 'neu K().m(1)')
        self.assertEqual(ergebnis, 3)
        self.fehler((code % '"x"') + 'neu K().m(1)', TypeError)

    def test_klassen_hinweis_mit_punktpfad_bei_zuweisung(self):
        vorspann = 'lade "hilfe.deu" als h\nfunktion f(k: h.Basis, neu_wert) { k = neu_wert\n zurück k.wer() }\n'
        ergebnis, _ = self.laufe(vorspann + 'f(neu h.Basis(), neu h.Basis())')
        self.assertEqual(ergebnis, 'basis')
        e = self.fehler(vorspann + 'f(neu h.Basis(), 5)', TypeError)
        self.assertIn("Variable 'k': erwartet Typ 'h.Basis', bekam Ganzzahl", str(e))

    def test_hinweis_wird_in_der_definitionsumgebung_aufgeloest(self):
        # Der Parameter 'h' verdeckt im Körper den Modulnamen; der Hinweis 'h.Basis' meint trotzdem das Modul
        ergebnis, _ = self.laufe('''
            lade "hilfe.deu" als h
            funktion f(h, k: h.Basis) { k = k\n zurück h }
            f(5, neu h.Basis())
        ''')
        self.assertEqual(ergebnis, 5)

    def test_kwargs_parameter_hinweis(self):
        code = 'funktion f(**opt: Woerterbuch) { opt = %s\n zurück opt }\n'
        ergebnis, _ = self.laufe((code % '{"a": 1}') + 'f(x=1)')
        self.assertEqual(ergebnis, {'a': 1})
        e = self.fehler((code % '5') + 'f(x=1)', TypeError)
        self.assertIn("Variable 'opt': erwartet Typ 'Woerterbuch', bekam Ganzzahl", str(e))

    def test_parameter_ohne_hinweis_bleibt_frei(self):
        ergebnis, _ = self.laufe('funktion f(a) { a = "x"\n zurück a }\nf(1)')
        self.assertEqual(ergebnis, 'x')

    def test_hinweis_gilt_pro_aufruf(self):
        # Ein früherer (gescheiterter) Aufruf hinterlässt nichts; jeder Aufruf prüft neu
        interpreter = Interpreter()
        lauf('funktion f(a: Ganzzahl, neu_wert) { a = neu_wert\n zurück a }', interpreter)
        with self.assertRaises(TypeError):
            lauf('f(1, "x")', interpreter)
        self.assertEqual(lauf('f(1, 2)', interpreter)[0], 2)
        with self.assertRaises(TypeError):
            lauf('f("x", 2)', interpreter)

    def test_hinweis_der_lokalen_variablen_unberuehrt(self):
        # 'sei' im Körper legt eine neue Bindung an (ohne Hinweis des gleichnamigen Parameters im Elternscope)
        ergebnis, _ = self.laufe('funktion f(a: Ganzzahl) { sei a = "x"\n zurück a }\nf(1)')
        self.assertEqual(ergebnis, 'x')

    def test_schleifenvariable_und_destrukturierung_kennen_keine_hinweise(self):
        # In 'für' und 'sei [..]' gibt es keine Typ-Hinweise: beides bindet frei, auch ohne Fehler
        ergebnis, _ = self.laufe('''
            funktion f() {
                sei r = []
                für [a, b] in [[1, "x"], ["y", 2]] { r.anhaengen(a) }
                sei [p, q] = ["s", 1]
                zurück [r, p, q]
            }
            f()
        ''')
        self.assertEqual(ergebnis, [[1, 'y'], 's', 1])


# ------------------------------------------- 4. Aufrufkette mit Dateiname

class TestAufrufketteMitDateiname(ModulTestCase):
    KETTE = '''\
funktion innen() {
    zurück 1 / 0
}
funktion aussen() {
    zurück innen()
}
'''
    HAUPT = 'lade "hilfe_kette.deu" als k\nsei x = 1\nk.aussen()\n'

    def test_stack_speichert_datei_der_aufrufstelle(self):
        pfad = self.datei('hilfe_kette.deu', self.KETTE)
        interpreter = Interpreter(ladepfad=self.ordner)
        with self.assertRaises(ZeroDivisionError):
            lauf(self.HAUPT, interpreter)
        self.assertEqual(interpreter._letzter_aufruf_stack, [
            AufrufEintrag('aussen', 3, None),     # im Hauptskript aufgerufen
            AufrufEintrag('innen', 5, pfad),      # in hilfe_kette.deu aufgerufen
        ])

    def test_kette_nennt_geladene_datei(self):
        self.datei('hilfe_kette.deu', self.KETTE)
        zeilen = self.cli(self.HAUPT).splitlines()
        self.assertIn("  in Funktion 'innen' (hilfe_kette.deu, Zeile 5)", zeilen)
        self.assertIn("  in Funktion 'aussen' (Zeile 3)", zeilen)        # Hauptskript: unverändert
        # innerster Aufruf zuerst
        self.assertLess(zeilen.index("  in Funktion 'innen' (hilfe_kette.deu, Zeile 5)"),
                        zeilen.index("  in Funktion 'aussen' (Zeile 3)"))

    def test_fehlerkopf_zeigt_weiter_die_geladene_datei(self):
        self.datei('hilfe_kette.deu', self.KETTE)
        zeilen = self.cli(self.HAUPT).splitlines()
        self.assertIn('  hilfe_kette.deu, Zeile 2:', zeilen)
        self.assertIn('        zurück 1 / 0', zeilen)

    def test_hauptskript_funktionen_ohne_dateinamen(self):
        code = ('funktion innen() {\n    zurück 1 / 0\n}\n'
                'funktion aussen() {\n    zurück innen()\n}\naussen()\n')
        zeilen = self.cli(code).splitlines()
        self.assertIn("  in Funktion 'innen' (Zeile 5)", zeilen)
        self.assertIn("  in Funktion 'aussen' (Zeile 7)", zeilen)
        self.assertFalse([z for z in zeilen if z.startswith('  in Funktion') and '.deu' in z])

    def test_dateiname_relativ_mit_schraegstrich(self):
        self.datei('unter/hilfe_kette.deu', self.KETTE)
        zeilen = self.cli('lade "unter/hilfe_kette.deu" als k\nk.aussen()\n').splitlines()
        self.assertIn("  in Funktion 'innen' (unter/hilfe_kette.deu, Zeile 5)", zeilen)
        self.assertIn("  in Funktion 'aussen' (Zeile 2)", zeilen)

    def test_aufruf_zwischen_zwei_geladenen_dateien(self):
        self.datei('a.deu', 'lade "b.deu" als b\nfunktion ruf() {\n    zurück b.boese()\n}\n')
        self.datei('b.deu', 'funktion boese() {\n    zurück 1 / 0\n}\n')
        zeilen = self.cli('lade "a.deu" als a\na.ruf()\n').splitlines()
        self.assertIn('  b.deu, Zeile 2:', zeilen)
        self.assertIn("  in Funktion 'boese' (a.deu, Zeile 3)", zeilen)
        self.assertIn("  in Funktion 'ruf' (Zeile 2)", zeilen)

    def test_zeile_der_aufrufstelle_nach_aufruf_wiederhergestellt(self):
        self.datei('hilfe_kette.deu', 'funktion eins() {\n    sei a = 1\n    sei b = 2\n    zurück a\n}\n'
                                      'funktion kaputt() {\n    zurück 1 / 0\n}\n')
        zeilen = self.cli('lade "hilfe_kette.deu" als k\n\nsei s = k.eins() + k.kaputt()\n').splitlines()
        # Aufgerufen wurde in Zeile 3 des Hauptskripts, nicht in Zeile 4 von hilfe_kette.deu
        self.assertIn("  in Funktion 'kaputt' (Zeile 3)", zeilen)

    def test_zeile_nach_aufruf_im_hauptskript_wiederhergestellt(self):
        code = ('funktion g() {\n    sei a = 1\n    zurück a\n}\n'
                'funktion h() { zurück 1 / 0 }\n'
                'sei x = g() + h()\n')
        zeilen = self.cli(code).splitlines()
        self.assertIn("  in Funktion 'h' (Zeile 6)", zeilen)

    def test_kommandozeile_zeigt_dateinamen_der_kette(self):
        self.datei('hilfe_kette.deu', self.KETTE)
        haupt = self.datei('haupt.deu', self.HAUPT)
        ergebnis = subprocess.run([sys.executable, '-m', 'deutsch', haupt], stdin=subprocess.DEVNULL,
                                  capture_output=True, cwd=PROJEKT_WURZEL, timeout=120)
        fehler = ergebnis.stderr.decode('utf-8', errors='replace').splitlines()
        self.assertEqual(ergebnis.returncode, 1)
        self.assertIn('  hilfe_kette.deu, Zeile 2:', fehler)
        self.assertIn("  in Funktion 'innen' (hilfe_kette.deu, Zeile 5)", fehler)
        self.assertIn("  in Funktion 'aussen' (Zeile 3)", fehler)


# ------------------------------------- 5. erneutes Werfen behält Datei und Zeile

class TestErneutesWerfen(ModulTestCase):
    MODUL = '''\
funktion teile(a) {
    zurück a / 0
}
funktion los() {
    werfe "kaputt"
}
'''
    ERNEUT = '''\
lade "wirf.deu" als w
versuche {
    w.%s
} fange f {
    werfe f
}
'''

    def setUp(self):
        super().setUp()
        self.wirf = self.datei('wirf.deu', self.MODUL)

    def test_python_fehler_aus_modul_behaelt_datei_und_zeile(self):
        e = self.fehler(self.ERNEUT % 'teile(1)', AusnahmeFehler)
        self.assertEqual(e.datei, self.wirf)
        self.assertEqual(e.zeile, 2)
        self.assertIn('wirf.deu, Zeile 2: Division durch Null', str(e))

    def test_geworfener_wert_aus_modul_behaelt_datei_und_zeile(self):
        e = self.fehler(self.ERNEUT % 'los()', AusnahmeFehler)
        self.assertEqual(e.datei, self.wirf)
        self.assertEqual(e.zeile, 5)
        self.assertEqual(e.wert, 'kaputt')
        self.assertIn('wirf.deu, Zeile 5: kaputt', str(e))

    def test_cli_zeigt_nach_erneutem_werfen_die_urspruengliche_quellzeile(self):
        text = self.cli(self.ERNEUT % 'teile(1)')
        zeilen = text.splitlines()
        self.assertIn('  wirf.deu, Zeile 2:', zeilen)
        self.assertIn('        zurück a / 0', zeilen)                   # Quellzeile aus wirf.deu
        self.assertNotIn('        werfe f', zeilen)                      # nicht die Zeile des erneuten Werfens
        self.assertIn('[AusnahmeFehler] wirf.deu, Zeile 2: Division durch Null', zeilen)
        self.assertIn("  in Funktion 'teile' (Zeile 3)", zeilen)        # Aufrufkette des ursprünglichen Fehlers

    def test_cli_zeigt_nach_erneutem_werfen_von_werfe_wert(self):
        zeilen = self.cli(self.ERNEUT % 'los()').splitlines()
        self.assertIn('  wirf.deu, Zeile 5:', zeilen)
        self.assertIn('        werfe "kaputt"', zeilen)

    def test_mehrfach_verschachteltes_erneutes_werfen(self):
        code = '''\
lade "wirf.deu" als w
versuche {
    versuche {
        w.teile(1)
    } fange f {
        werfe f
    }
} fange g {
    werfe g
}
'''
        e = self.fehler(code, AusnahmeFehler)
        self.assertEqual(e.datei, self.wirf)
        self.assertEqual(e.zeile, 2)
        self.assertIn('wirf.deu, Zeile 2:', self.cli(code))

    def test_erneutes_werfen_im_hauptskript_behaelt_urspruengliche_zeile(self):
        code = 'versuche {\n    werfe "x"\n} fange f {\n    sei y = 1\n    werfe f\n}\n'
        e = self.fehler(code, AusnahmeFehler)
        self.assertIsNone(e.datei)
        self.assertEqual(e.zeile, 2)
        self.assertEqual(e.wert, 'x')
        self.assertEqual(str(e), 'Zeile 2: x')

    def test_python_fehler_im_hauptskript_erneut_geworfen(self):
        code = 'versuche {\n    sei a = 1 / 0\n} fange f {\n    werfe f\n}\n'
        e = self.fehler(code, AusnahmeFehler)
        self.assertIsNone(e.datei)
        self.assertEqual(e.zeile, 2)
        zeilen = self.cli(code).splitlines()
        self.assertIn('  haupt.deu, Zeile 2:', zeilen)
        self.assertIn('        sei a = 1 / 0', zeilen)

    def test_erneutes_werfen_aus_geschachteltem_block_und_funktion(self):
        code = '''\
lade "wirf.deu" als w
versuche {
    w.teile(1)
} fange f {
    wenn wahr {
        funktion neu_werfen() { werfe f }
        neu_werfen()
    }
}
'''
        e = self.fehler(code, AusnahmeFehler)
        self.assertEqual(e.datei, self.wirf)
        self.assertEqual(e.zeile, 2)

    def test_veraenderter_wert_ist_ein_neuer_wurf_am_neuen_ort(self):
        code = ('lade "wirf.deu" als w\nversuche {\n    w.los()\n} fange f {\n    werfe f + "!"\n}\n')
        e = self.fehler(code, AusnahmeFehler)
        self.assertIsNone(e.datei)
        self.assertEqual(e.zeile, 5)
        self.assertEqual(e.wert, 'kaputt!')
        self.assertEqual(str(e), 'Zeile 5: kaputt!')

    def test_neu_zugewiesene_fehlervariable_ist_ein_neuer_wurf(self):
        code = ('lade "wirf.deu" als w\nversuche {\n    w.los()\n} fange f {\n    f = "ganz neu"\n    werfe f\n}\n')
        e = self.fehler(code, AusnahmeFehler)
        self.assertIsNone(e.datei)
        self.assertEqual(e.zeile, 6)
        self.assertEqual(e.wert, 'ganz neu')

    def test_anderer_wert_im_handler_bleibt_neuer_wurf(self):
        code = ('lade "wirf.deu" als w\nversuche {\n    w.los()\n} fange f {\n    werfe "anders"\n}\n')
        e = self.fehler(code, AusnahmeFehler)
        self.assertIsNone(e.datei)
        self.assertEqual(e.zeile, 5)
        self.assertEqual(e.wert, 'anders')

    def test_gefangener_fehler_kann_weiter_gefangen_werden(self):
        code = '''\
lade "wirf.deu" als w
sei ergebnis = nichts
versuche {
    versuche { w.los() } fange f { werfe f }
} fange g {
    ergebnis = g
}
ergebnis
'''
        ergebnis, _ = self.laufe(code)
        self.assertEqual(ergebnis, 'kaputt')


# ------------------------------- 6. Destrukturierung prüft Konstanten im selben Scope

class TestDestrukturierungUndKonstanten(unittest.TestCase):
    MELDUNG = "'PI' ist bereits als Konstante in diesem Geltungsbereich deklariert"

    def test_sei_einfach_und_destrukturierend_melden_dasselbe(self):
        with self.assertRaises(TypeError) as einfach:
            lauf('konstante PI = 3\nsei PI = 4')
        with self.assertRaises(TypeError) as muster:
            lauf('konstante PI = 3\nsei [PI, x] = [4, 5]')
        self.assertIn(self.MELDUNG, str(einfach.exception))
        self.assertIn(self.MELDUNG, str(muster.exception))

    def test_konstante_an_zweiter_stelle(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('konstante PI = 3\nsei [x, PI] = [4, 5]')
        self.assertIn(self.MELDUNG, str(ctx.exception))

    def test_verschachteltes_muster_und_rest(self):
        with self.assertRaises(TypeError):
            lauf('konstante PI = 3\nsei [a, [PI, b]] = [1, [2, 3]]')
        with self.assertRaises(TypeError):
            lauf('konstante PI = 3\nsei [a, *PI] = [1, 2, 3]')

    def test_nichts_wird_halb_gebunden(self):
        interpreter = Interpreter()
        lauf('konstante PI = 3', interpreter)
        with self.assertRaises(TypeError):
            lauf('sei [x, PI] = [1, 2]', interpreter)
        with self.assertRaises(NameError):   # x wurde nicht angelegt
            lauf('x', interpreter)
        self.assertEqual(lauf('PI', interpreter)[0], 3)

    def test_konstante_im_klassenkoerper(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('klasse K {\n    konstante A = 1\n    sei [A, B] = [1, 2]\n}')
        self.assertIn("'A' ist bereits als Konstante", str(ctx.exception))

    def test_andere_namen_im_selben_scope_gehen(self):
        ergebnis, _ = lauf('konstante PI = 3\nsei [a, b] = [1, 2]\n[PI, a, b]')
        self.assertEqual(ergebnis, [3, 1, 2])

    def test_neu_binden_gewoehnlicher_variablen_bleibt_erlaubt(self):
        ergebnis, _ = lauf('sei [a, b] = [1, 2]\nsei [a, b] = [3, 4]\n[a, b]')
        self.assertEqual(ergebnis, [3, 4])

    def test_innerer_scope_darf_konstante_verdecken(self):
        ergebnis, _ = lauf('''
            konstante PI = 3
            funktion f() { sei [PI, y] = [4, 5]\n zurück PI + y }
            [f(), PI]
        ''')
        self.assertEqual(ergebnis, [9, 3])

    def test_block_darf_konstante_verdecken(self):
        ergebnis, _ = lauf('konstante PI = 3\nwenn wahr { sei [PI, y] = [4, 5] }\nPI')
        self.assertEqual(ergebnis, 3)

    def test_zuweisung_an_konstante_per_muster_bleibt_fehler(self):
        with self.assertRaises(TypeError) as ctx:
            lauf('konstante PI = 3\nsei x = 0\n[x, PI] = [1, 2]')
        self.assertIn("'PI' ist eine Konstante und kann nicht neu zugewiesen werden", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
