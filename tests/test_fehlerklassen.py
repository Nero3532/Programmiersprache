# -*- coding: utf-8 -*-
"""Tests für eigene Fehlerklassen ('klasse MeinFehler(WertFehler) { … }', 'werfe neu …', 'fange (Klasse)')."""
import contextlib
import io
import os
import sys
import tempfile
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT_WURZEL)

from deutsch.interpreter import FEHLERARTEN, Interpreter
from deutsch.lexer import Lexer
from deutsch.parser import Parser
from main import _ausfuehren


def parse(code):
    return Parser(Lexer(code).tokenisieren()).parse()


def ausgabe(code, ladepfad=None):
    """Führt code aus und gibt die Zeilen von stdout zurück."""
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        Interpreter(ladepfad=ladepfad).ausfuehren(parse(code))
    return puffer.getvalue().splitlines()


def cli(code, ladepfad=None):
    """Fehlertext wie in der CLI (Fehlerkopf, Quellzeile, Aufrufkette)."""
    ergebnis, text = _ausfuehren(code, Interpreter(ladepfad=ladepfad), 'haupt.deu')
    assert text is not None, 'Es wurde ein Fehler erwartet'
    return text


MEIN = '''\
klasse MeinFehler(WertFehler) {
    funktion __init__(dies, text, code) { dies.nachricht = text
        dies.code = code }
}
'''


class TestWerfenUndFangen(unittest.TestCase):
    def test_eingebaute_fehlerklasse_ohne_neu(self):
        code = 'versuche { werfe WertFehler("x") } fange (WertFehler) f { drucke(f.nachricht, f.art) }'
        self.assertEqual(ausgabe(code), ['x WertFehler'])

    def test_eigene_klasse_mit_feldern_und_art_zeile_datei(self):
        code = MEIN + ('versuche {\n  werfe neu MeinFehler("kaputt", 3)\n} fange (MeinFehler) f {\n'
                       '  drucke(f.nachricht, f.art, f.zeile, f.datei, f.code)\n}')
        self.assertEqual(ausgabe(code), ['kaputt MeinFehler 6 nichts 3'])

    def test_gefangen_von_oberklasse_python_name_und_fehler(self):
        for typ in ('WertFehler', 'ValueError', 'Fehler', 'MeinFehler', 'TypFehler, MeinFehler'):
            code = MEIN + f'versuche {{ werfe neu MeinFehler("a", 1) }} fange ({typ}) f {{ drucke("ok") }}'
            self.assertEqual(ausgabe(code), ['ok'], typ)

    def test_nicht_gefangen_von_fremder_art_und_geschwister(self):
        for typ in ('TypFehler', 'Geschwister'):
            code = (MEIN + 'klasse Geschwister(WertFehler) { }\n'
                    f'versuche {{ versuche {{ werfe neu MeinFehler("a", 1) }} fange ({typ}) f {{ drucke("falsch") }} }}'
                    ' fange g { drucke("aussen") }')
            self.assertEqual(ausgabe(code), ['aussen'], typ)

    def test_mehrstufige_vererbung_und_methoden(self):
        code = (MEIN + 'klasse Tief(MeinFehler) { funktion hallo(dies) { zurück "hi " + dies.nachricht } }\n'
                'versuche { werfe neu Tief("t", 0) } fange (MeinFehler) f { drucke(f.hallo(), f.art) }')
        self.assertEqual(ausgabe(code), ['hi t Tief'])

    def test_klasse_ohne_init_nimmt_ersten_wert_als_nachricht(self):
        code = ('klasse Leer(Fehler) { }\n'
                'versuche { werfe neu Leer("m") } fange (Leer) f { drucke(f.nachricht) }\n'
                'versuche { werfe neu Leer() } fange (Leer) f { drucke(f.nachricht == "") }')
        self.assertEqual(ausgabe(code), ['m', 'wahr'])

    def test_beliebige_klasse_ist_fangbar(self):
        code = ('klasse Hund { }\nversuche { werfe neu Hund() } fange (Hund) h { drucke(typ(h)) }')
        self.assertEqual(ausgabe(code), ['Hund'])

    def test_ist_instanz(self):
        code = (MEIN + 'versuche { werfe neu MeinFehler("a", 1) } fange f {\n'
                '  drucke(ist_instanz(f, MeinFehler), ist_instanz(f, WertFehler), ist_instanz(f, Fehler),'
                ' ist_instanz(f, TypFehler))\n}\n'
                'versuche { 1 / 0 } fange g {\n'
                '  drucke(ist_instanz(g, DivisionDurchNullFehler), ist_instanz(g, Fehler),'
                ' ist_instanz(g, WertFehler), ist_instanz(g, MeinFehler))\n}')
        self.assertEqual(ausgabe(code), ['wahr wahr wahr falsch', 'wahr wahr falsch falsch'])

    def test_ist_instanz_mit_aufzaehlung_ist_mitgliedspruefung(self):
        code = ('aufzaehlung Farbe { rot, gruen }\naufzaehlung Q { a }\n'
                'drucke(ist_instanz(Farbe.rot, Farbe), ist_instanz(Q.a, Farbe), ist_instanz(1, Farbe))')
        self.assertEqual(ausgabe(code), ['wahr falsch falsch'])

    def test_ist_instanz_typfehler_bei_nichtklasse(self):
        self.assertEqual(ausgabe('versuche { ist_instanz(1, 2) } fange (TypFehler) f { drucke("tf") }'), ['tf'])

    def test_erneutes_werfen_der_instanz_behaelt_art_und_ort(self):
        code = MEIN + ('versuche {\n  versuche { werfe neu MeinFehler("k", 1) } fange f { werfe f }\n}'
                       ' fange (MeinFehler) g { drucke(g.zeile, g.code) }')
        self.assertEqual(ausgabe(code), ['6 1'])

    def test_fange_unbekannte_art_ist_namensfehler(self):
        code = 'versuche { versuche { werfe "x" } fange (Quatsch) f { } } fange (NamensFehler) g { drucke("nf") }'
        self.assertEqual(ausgabe(code), ['nf'])

    def test_fange_ueber_modul(self):
        with tempfile.TemporaryDirectory() as ordner:
            with open(os.path.join(ordner, 'm.deu'), 'w', encoding='utf-8') as f:
                f.write(MEIN)
            kopf = 'lade "m.deu" als m\n'
            self.assertEqual(ausgabe(kopf + 'versuche { werfe neu m.MeinFehler("q", 2) } '
                                     'fange (m.MeinFehler) f { drucke(f.nachricht, f.code) }', ladepfad=ordner),
                             ['q 2'])
            self.assertEqual(ausgabe(kopf + 'versuche { versuche { werfe "x" } fange (m.Quatsch) f { } } '
                                     'fange (NamensFehler) g { drucke("nf") }', ladepfad=ordner), ['nf'])

    def test_alle_arten_werfen_und_fangen(self):
        for name in FEHLERARTEN:
            code = (f'versuche {{ werfe {name}("m") }} fange ({name}) f {{ drucke(f.art, f.nachricht) }}\n'
                    f'versuche {{ werfe neu {name}("m") }} fange (Fehler) f {{ drucke(ist_instanz(f, {name})) }}')
            self.assertEqual(ausgabe(code), [f'{name} m', 'wahr'], name)

    def test_eigene_klasse_je_art_gefangen_von_python_namen(self):
        for name, py in FEHLERARTEN.items():
            code = (f'klasse E({name}) {{ }}\n'
                    f'versuche {{ werfe neu E("m") }} fange ({py.__name__}) f {{ drucke(f.art) }}')
            self.assertEqual(ausgabe(code), ['E'], name)


class TestGestaltDerFehlervariable(unittest.TestCase):
    def test_python_fehler_ist_text_mit_attributen(self):
        code = ('versuche { 1/0 } fange f {\n'
                '  drucke(f == "Zeile 1: Division durch Null", f.nachricht, f.zeile, f.art, f.datei)\n'
                '  drucke(typ(f), f + "!", laenge(f) > 0, f.gross())\n}')
        self.assertEqual(ausgabe(code), ['wahr Division durch Null 1 DivisionDurchNullFehler nichts',
                                         'Zeichenkette Zeile 1: Division durch Null! wahr ZEILE 1: DIVISION DURCH NULL'])

    def test_werfe_text_bleibt_text(self):
        code = 'versuche { werfe "boese" } fange f { drucke(f == "boese", f.nachricht, f.art, typ(f)) }'
        self.assertEqual(ausgabe(code), ['wahr boese AusnahmeFehler Zeichenkette'])

    def test_werfe_andere_werte_roh(self):
        code = ('versuche { werfe 42 } fange f { drucke(f == 42, typ(f)) }\n'
                'versuche { werfe [1, 2] } fange f { drucke(f) }')
        self.assertEqual(ausgabe(code), ['wahr Ganzzahl', '[1, 2]'])

    def test_ist_als_woerterbuchschluessel_und_in_text_nutzbar(self):
        code = ('versuche { 1/0 } fange f {\n  sei d = {f: 1}\n  drucke(d[f], "x" + f, "{f}")\n}')
        self.assertEqual(ausgabe(code), ['1 xZeile 1: Division durch Null Zeile 1: Division durch Null'])

    def test_nachricht_der_instanz_in_drucke_und_text(self):
        code = MEIN + ('versuche { werfe neu MeinFehler("kaputt", 3) } fange f { drucke(f)\n'
                       '  drucke("a: " + zeichenkette(f)) }')
        self.assertEqual(ausgabe(code), ['kaputt', 'a: kaputt'])

    def test_text_methode_der_klasse_gewinnt(self):
        code = ('klasse E(Fehler) { funktion __text__(dies) { zurück "eigen" } }\n'
                'versuche { werfe neu E("x") } fange f { drucke(f) }')
        self.assertEqual(ausgabe(code), ['eigen'])

    def test_reservierte_attribute_ueberschreiben_nutzerfelder(self):
        code = ('klasse E(Fehler) { funktion __init__(dies, t) { dies.art = "mein" } }\n'
                'versuche { werfe neu E("x") } fange f { drucke(f.art) }')
        self.assertEqual(ausgabe(code), ['E'])

    def test_fehlervariable_nicht_beschreibbar(self):
        code = 'versuche { 1/0 } fange f { versuche { f.nachricht = "x" } fange (TypFehler) g { drucke("tf") } }'
        self.assertEqual(ausgabe(code), ['tf'])

    def test_zeichenkettenmethode_und_unbekanntes_attribut(self):
        code = ('versuche { 1/0 } fange f { drucke(f.ersetze("Zeile", "Z"))\n'
                '  versuche { f.quatsch } fange (AttributFehler) g { drucke("af") } }')
        self.assertEqual(ausgabe(code), ['Z 1: Division durch Null', 'af'])

    def test_str_unterklasse_in_json_sortierung_und_mit_in(self):
        # Restrisiko: Code, der 'str' prüft, muss die DeutschFehler-Zeichenkette weiter annehmen
        code = ('versuche { 1/0 } fange f {\n'
                '  drucke(f in "x Zeile 1: Division durch Null", sortiere([f, "a"]), f.teile(" ")[0])\n}')
        self.assertEqual(ausgabe(code), ['wahr [Zeile 1: Division durch Null, a] Zeile'])

    def test_tiefe_kopie_behaelt_attribute(self):
        code = 'versuche { 1/0 } fange f { sei k = tiefe_kopie(f)\n drucke(k == f, k.zeile) }'
        self.assertEqual(ausgabe(code), ['wahr 1'])


class TestErneutesWerfenUndKopf(unittest.TestCase):
    def test_cli_kopf_zeigt_eigene_klasse(self):
        text = cli(MEIN + 'werfe neu MeinFehler("boese", 1)')
        self.assertIn('[MeinFehler] Zeile 5: boese', text.splitlines())

    def test_cli_kopf_eingebaute_klasse_ohne_neu(self):
        self.assertIn('[WertFehler] Zeile 1: x', cli('werfe WertFehler("x")').splitlines())

    def test_erneutes_werfen_nach_python_fehler_behaelt_art_und_zeile(self):
        code = 'versuche {\n  1 / 0\n} fange f {\n  werfe f\n}'
        text = cli(code).splitlines()
        self.assertIn('[DivisionDurchNullFehler] Zeile 2: Division durch Null', text)
        self.assertIn('      1 / 0', text)

    def test_erneut_geworfener_python_fehler_ist_weiter_fangbar_als_seine_art(self):
        code = ('versuche { versuche { 1/0 } fange f { werfe f } } fange (DivisionDurchNullFehler) g { drucke(g) }')
        self.assertEqual(ausgabe(code), ['Zeile 1: Division durch Null'])

    def test_rekursionsfehler_geworfen_behaelt_meldung(self):
        self.assertIn('[RekursionsFehler] Zeile 1: x', cli('werfe RekursionsFehler("x")').splitlines())

    def test_syntaxfehler_geworfen_bekommt_ort(self):
        text = cli('werfe SyntaxFehler("x")').splitlines()
        self.assertIn('[SyntaxFehler] Zeile 1: x', text)

    def test_dateifehler_und_schluesselfehler_instanz(self):
        for name in ('DateiFehler', 'SchluesselFehler'):
            self.assertIn(f'[{name}] Zeile 1: x', cli(f'werfe {name}("x")').splitlines(), name)

    def test_echter_rekursionsfehler_bleibt_feste_meldung(self):
        text = cli('funktion f() { zurück f() }\nf()')
        self.assertIn('[RekursionsFehler] Maximale Rekursionstiefe überschritten', text)

    def test_nachricht_in_der_meldung_auch_ohne_zeilenzuordnung(self):
        # Fehler ohne eigene Nachricht: leere Meldung statt Absturz
        self.assertIn('[Fehler] Zeile 1: ', cli('werfe Fehler()').splitlines())


class TestAufrufOhneNeu(unittest.TestCase):
    def test_normale_klasse_ohne_neu_ist_typfehler_mit_hinweis(self):
        code = ('klasse Hund { }\nversuche { Hund() } fange (TypFehler) f { drucke(f.nachricht) }')
        self.assertEqual(ausgabe(code), ["'Hund' ist eine Klasse und nicht aufrufbar – nutze 'neu Hund(...)'"])

    def test_fehlerklassen_sind_klassen_mit_vererbung(self):
        code = 'drucke(typ(WertFehler), ist_instanz(WertFehler("a"), Fehler), ist_instanz(Fehler("a"), WertFehler))'
        self.assertEqual(ausgabe(code), ['Klasse(WertFehler) wahr falsch'])

    def test_eigene_klasse_ohne_neu_aufrufbar(self):
        code = MEIN + 'versuche { werfe MeinFehler("a", 7) } fange f { drucke(f.code) }'
        self.assertEqual(ausgabe(code), ['7'])


if __name__ == '__main__':
    unittest.main()
