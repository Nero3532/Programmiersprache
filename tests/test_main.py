# -*- coding: utf-8 -*-
"""
Tests für main.py: REPL-Klammerzählung, großer Stack / Rekursionstiefe, REPL-Ablauf,
Kommandozeilen-Optionen, REPL-Hilfe und 'python -m deutsch'.

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import _thread
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT_WURZEL)

from deutsch import __version__
from main import (BANNER, _fehler_anzeigen, eingabe_unvollstaendig, im_grossen_stack,
                  klammer_saldo)

MAIN_PY = os.path.join(PROJEKT_WURZEL, 'main.py')

REKURSION_5000 = '''\
funktion r(n) {
    wenn n == 0 { zurueck 0 }
    zurueck 1 + r(n - 1)
}
drucke(r(5000))
'''

ENDLOSREKURSION = '''\
funktion e(n) { zurueck 1 + e(n + 1) }
drucke(e(0))
'''


def _laufe(befehl: list, eingabe: str = None):
    """Startet befehl als Unterprozess. Gibt (exitcode, stdout, stderr) zurück."""
    ergebnis = subprocess.run(
        befehl,
        input=eingabe.encode('utf-8') if eingabe is not None else None,
        stdin=None if eingabe is not None else subprocess.DEVNULL,
        capture_output=True,
        cwd=PROJEKT_WURZEL,
        timeout=120,
    )
    def text(daten: bytes) -> str:
        return daten.decode('utf-8', errors='replace').replace('\r\n', '\n')

    return ergebnis.returncode, text(ergebnis.stdout), text(ergebnis.stderr)


def starte(*argumente, eingabe: str = None):
    """Startet main.py als Unterprozess. Gibt (exitcode, stdout, stderr) zurück."""
    return _laufe([sys.executable, MAIN_PY, *argumente], eingabe)


def starte_modul(*argumente, eingabe: str = None):
    """Startet 'python -m deutsch' im Projektordner. Gibt (exitcode, stdout, stderr) zurück."""
    return _laufe([sys.executable, '-m', 'deutsch', *argumente], eingabe)


def starte_pruefen(code: str):
    """Führt 'main.py --pruefen' auf einer temporären Datei mit code aus."""
    with tempfile.TemporaryDirectory() as ordner:
        pfad = os.path.join(ordner, 'test.deu')
        with open(pfad, 'w', encoding='utf-8') as f:
            f.write(code)
        return starte('--pruefen', pfad)


def starte_datei(code: str):
    """Schreibt code in eine temporäre .deu-Datei und führt sie mit main.py aus."""
    with tempfile.TemporaryDirectory() as ordner:
        pfad = os.path.join(ordner, 'test.deu')
        with open(pfad, 'w', encoding='utf-8') as f:
            f.write(code)
        return starte(pfad)


def starte_dateien(dateien: dict, hauptdatei: str):
    """Schreibt mehrere Dateien (Schlüssel: Pfad relativ zum Ordner, '/' als Trenner) in
    einen temporären Ordner und führt hauptdatei daraus mit main.py aus."""
    with tempfile.TemporaryDirectory() as ordner:
        for relpfad, code in dateien.items():
            pfad = os.path.join(ordner, *relpfad.split('/'))
            os.makedirs(os.path.dirname(pfad), exist_ok=True)
            with open(pfad, 'w', encoding='utf-8') as f:
                f.write(code)
        return starte(os.path.join(ordner, hauptdatei))


class TestKlammerzaehlung(unittest.TestCase):
    def test_normalfall(self):
        self.assertEqual(klammer_saldo('drucke(1)'), 0)
        self.assertEqual(klammer_saldo('wenn wahr {'), 1)
        self.assertEqual(klammer_saldo('wenn wahr { drucke(1) }'), 0)
        self.assertEqual(klammer_saldo('funktion f() { wenn wahr {'), 2)
        self.assertEqual(klammer_saldo('}'), -1)

    def test_unvollstaendig_nur_bei_offenem_block(self):
        self.assertTrue(eingabe_unvollstaendig('wenn wahr {'))
        self.assertFalse(eingabe_unvollstaendig('wenn wahr { drucke(1) }'))
        self.assertFalse(eingabe_unvollstaendig('drucke(1)'))
        # überzählige '}' warten nicht auf weitere Zeilen (Fehler kommt vom Parser)
        self.assertFalse(eingabe_unvollstaendig('}'))

    def test_klammer_in_string_zaehlt_nicht(self):
        self.assertEqual(klammer_saldo('drucke("{")'), 0)
        self.assertEqual(klammer_saldo("drucke('{')"), 0)
        self.assertEqual(klammer_saldo('drucke("}")'), 0)
        self.assertEqual(klammer_saldo('drucke("{{{")'), 0)
        self.assertFalse(eingabe_unvollstaendig('drucke("{")'))

    def test_escapte_anfuehrungszeichen_im_string(self):
        self.assertEqual(klammer_saldo(r'drucke("a\"{")'), 0)
        self.assertEqual(klammer_saldo(r"drucke('a\'{')"), 0)
        self.assertEqual(klammer_saldo(r'drucke("\\") {'), 1)

    def test_echter_block_nach_string(self):
        self.assertEqual(klammer_saldo('wenn x == "}" {'), 1)
        self.assertEqual(klammer_saldo('wenn x == "{" {'), 1)
        self.assertTrue(eingabe_unvollstaendig('wenn x == "{" {'))

    def test_dreifache_anfuehrungszeichen(self):
        self.assertEqual(klammer_saldo('drucke("""{ """)'), 0)
        self.assertEqual(klammer_saldo("drucke('''}''')"), 0)
        self.assertEqual(klammer_saldo('drucke("""a "b" { c""")'), 0)
        self.assertFalse(eingabe_unvollstaendig('drucke("""{""")'))

    def test_leere_zeichenkette(self):
        self.assertEqual(klammer_saldo('drucke("") {'), 1)
        self.assertEqual(klammer_saldo("sei a = '' + \"\" {"), 1)

    def test_mehrzeilige_dreifach_zeichenkette_wartet_auf_ende(self):
        self.assertTrue(eingabe_unvollstaendig('sei x = """abc'))
        self.assertTrue(eingabe_unvollstaendig('sei x = """abc\n{ def'))
        self.assertFalse(eingabe_unvollstaendig('sei x = """abc\n{ def"""'))
        self.assertEqual(klammer_saldo('sei x = """abc\n{ def'), 0)

    def test_einfache_zeichenkette_endet_am_zeilenende(self):
        # Vergessenes Anführungszeichen darf die REPL nicht festhalten ...
        self.assertFalse(eingabe_unvollstaendig('drucke("abc'))
        # ... und die Zählung der nächsten Zeile nicht verfälschen ('(' von drucke bleibt offen)
        self.assertEqual(klammer_saldo('drucke("abc\nwenn wahr {'), 2)

    def test_kommentar(self):
        self.assertEqual(klammer_saldo('drucke(1) # {'), 0)
        self.assertEqual(klammer_saldo('# }'), 0)
        self.assertEqual(klammer_saldo('wenn wahr { # Block offen'), 1)
        self.assertEqual(klammer_saldo("# it's { \"quoted"), 0)
        self.assertFalse(eingabe_unvollstaendig('drucke(1) # {'))

    def test_kommentar_endet_am_zeilenende(self):
        self.assertEqual(klammer_saldo('# {\nwenn wahr {'), 1)

    def test_hash_in_string_ist_kein_kommentar(self):
        self.assertEqual(klammer_saldo('drucke("#") {'), 1)
        self.assertEqual(klammer_saldo('drucke("# {")'), 0)
        self.assertEqual(klammer_saldo("sei x = '#' {"), 1)

    def test_mehrzeiliger_block_schritt_fuer_schritt(self):
        zeilen = ['funktion f() {', '    drucke("}")  # schließt nichts', '}']
        quelltext = ''
        erwartet = [True, True, False]
        for zeile, offen in zip(zeilen, erwartet):
            quelltext = zeile if not quelltext else quelltext + '\n' + zeile
            with self.subTest(zeile=zeile):
                self.assertEqual(eingabe_unvollstaendig(quelltext), offen)

    def test_runde_klammer_ueber_zwei_zeilen(self):
        self.assertEqual(klammer_saldo('drucke(1 +'), 1)
        self.assertTrue(eingabe_unvollstaendig('drucke(1 +'))
        self.assertEqual(klammer_saldo('drucke(1 +\n2'), 1)
        self.assertTrue(eingabe_unvollstaendig('drucke(1 +\n2'))
        self.assertFalse(eingabe_unvollstaendig('drucke(1 +\n2)'))

    def test_eckige_klammer_ueber_zwei_zeilen(self):
        self.assertEqual(klammer_saldo('sei l = [1,'), 1)
        self.assertTrue(eingabe_unvollstaendig('sei l = [1,'))
        self.assertFalse(eingabe_unvollstaendig('sei l = [1,\n2]'))
        self.assertFalse(eingabe_unvollstaendig('sei l = [1, 2]'))

    def test_gemischte_klammern_schritt_fuer_schritt(self):
        zeilen = ['sei g = f(funktion(x) {', '    zurueck x * 2', '})']
        quelltext = ''
        erwartet = [True, True, False]
        for zeile, offen in zip(zeilen, erwartet):
            quelltext = zeile if not quelltext else quelltext + '\n' + zeile
            with self.subTest(zeile=zeile):
                self.assertEqual(eingabe_unvollstaendig(quelltext), offen)
        self.assertEqual(klammer_saldo(quelltext), 0)

    def test_klammer_in_zeichenkette_und_kommentar_zaehlt_nicht_mit(self):
        self.assertEqual(klammer_saldo('drucke("(")'), 0)
        self.assertEqual(klammer_saldo("drucke('[')"), 0)
        self.assertEqual(klammer_saldo('drucke("([{")'), 0)
        self.assertEqual(klammer_saldo('drucke(1) # ('), 0)
        self.assertEqual(klammer_saldo('sei x = 1 # [ {'), 0)
        self.assertFalse(eingabe_unvollstaendig('drucke("(")'))
        self.assertFalse(eingabe_unvollstaendig('drucke(1) # ('))
        self.assertFalse(eingabe_unvollstaendig('sei x = "[" # {'))
        # Klammer in einer mehrzeiligen Zeichenkette zählt ebenfalls nicht
        self.assertFalse(eingabe_unvollstaendig('sei x = """(\n)"""'))

    def test_ueberzaehlige_schliessklammer_blockiert_nicht(self):
        # Die Eingabe ist schon fehlerhaft: sofort ausführen, nicht auf weitere Zeilen warten
        self.assertEqual(klammer_saldo(')'), -1)
        self.assertFalse(eingabe_unvollstaendig(')'))
        self.assertEqual(klammer_saldo('drucke(1))'), -1)
        self.assertFalse(eingabe_unvollstaendig('drucke(1))'))
        # eine spätere öffnende Klammer hebt die Überzählige nicht auf
        self.assertFalse(eingabe_unvollstaendig(') ('))
        self.assertFalse(eingabe_unvollstaendig('drucke(1) ) ( {'))

    def test_falsch_geschlossene_klammer_blockiert_nicht(self):
        self.assertFalse(eingabe_unvollstaendig('drucke(1]'))
        self.assertFalse(eingabe_unvollstaendig('wenn wahr (}'))
        self.assertFalse(eingabe_unvollstaendig('funktion f() {\n    drucke(1)\n)'))


class TestGrosserStack(unittest.TestCase):
    def test_ergebnis_wird_durchgereicht(self):
        self.assertEqual(im_grossen_stack(lambda a, b: a + b, 2, 3), 5)
        self.assertIsNone(im_grossen_stack(lambda: None))

    def test_ausnahmen_werden_durchgereicht(self):
        def werfe():
            raise ValueError('kaputt')

        with self.assertRaises(ValueError):
            im_grossen_stack(werfe)
        with self.assertRaises(SystemExit) as ctx:
            im_grossen_stack(sys.exit, 3)
        self.assertEqual(ctx.exception.code, 3)

    def test_laeuft_in_eigenem_thread_mit_hohem_limit(self):
        vorher_limit = sys.getrecursionlimit()
        vorher_stack = threading.stack_size()

        def messen():
            return (threading.current_thread() is threading.main_thread(),
                    sys.getrecursionlimit())

        ist_haupt, limit = im_grossen_stack(messen)
        self.assertFalse(ist_haupt)
        self.assertGreater(limit, 60000)  # r(5000) braucht ca. 58000 Python-Frames
        # Zustand des Aufrufers bleibt unverändert
        self.assertEqual(sys.getrecursionlimit(), vorher_limit)
        self.assertEqual(threading.stack_size(), vorher_stack)

    def test_tiefe_rekursion_klappt(self):
        def tief(n):
            return 0 if n == 0 else 1 + tief(n - 1)

        self.assertEqual(im_grossen_stack(tief, 50000), 50000)

    def test_endlosrekursion_ist_recursionerror_und_kein_absturz(self):
        def endlos(n):
            return 1 + endlos(n + 1)

        with self.assertRaises(RecursionError):
            im_grossen_stack(endlos, 0)

    @unittest.skipUnless(signal.getsignal(signal.SIGINT) is signal.default_int_handler,
                         'SIGINT-Handler ist ersetzt (z. B. unittest -c)')
    def test_strg_c_stoppt_laufenden_thread(self):
        beenden = threading.Event()
        laeuft = threading.Event()
        gestoppt = []

        def endlosschleife():
            laeuft.set()
            frist = time.monotonic() + 20
            try:
                while not beenden.is_set() and time.monotonic() < frist:
                    pass
            except KeyboardInterrupt:
                gestoppt.append(True)
                raise

        def strg_c_senden():
            laeuft.wait(10)
            time.sleep(0.2)
            _thread.interrupt_main()  # wie ein SIGINT durch Strg+C

        sender = threading.Thread(target=strg_c_senden, daemon=True)
        sender.start()
        try:
            with self.assertRaises(KeyboardInterrupt):
                im_grossen_stack(endlosschleife)
        finally:
            beenden.set()
            sender.join(5)
        self.assertEqual(gestoppt, [True])


class TestRekursionImProgramm(unittest.TestCase):
    """Startet main.py als Unterprozess (echter Aufruf wie in der Praxis)."""

    def test_rekursion_5000_als_datei(self):
        code, ausgabe, fehler = starte_datei(REKURSION_5000)
        self.assertEqual(fehler, '')
        self.assertEqual(ausgabe.strip(), '5000')
        self.assertEqual(code, 0)

    def test_rekursion_mit_umlaut_schluesselwort(self):
        code, ausgabe, fehler = starte_datei(REKURSION_5000.replace('zurueck', 'zurück'))
        self.assertEqual(ausgabe.strip(), '5000')
        self.assertEqual(code, 0)

    def test_endlosrekursion_liefert_deutsche_meldung(self):
        code, ausgabe, fehler = starte_datei(ENDLOSREKURSION)
        self.assertIn('Maximale Rekursionstiefe überschritten', fehler)
        self.assertNotIn('Traceback', fehler)
        self.assertEqual(code, 1)  # sauberer Fehler-Exitcode, kein Absturz (Segfault/0xC00000FD)
        self.assertEqual(ausgabe, '')

    def test_fehler_exitcode_bleibt_eins(self):
        code, ausgabe, fehler = starte_datei('drucke(1 / 0)\n')
        self.assertEqual(code, 1)
        self.assertNotEqual(fehler.strip(), '')

    def test_ausgabe_bleibt_wie_bisher(self):
        code, ausgabe, fehler = starte_datei('drucke("Grüße")\ndrucke(2 + 3)\n')
        self.assertEqual(code, 0)
        self.assertEqual(ausgabe.splitlines(), ['Grüße', '5'])

    def test_fehlende_datei_exitcode_eins(self):
        code, _, fehler = starte(os.path.join(PROJEKT_WURZEL, 'gibt_es_nicht.deu'))
        self.assertEqual(code, 1)
        self.assertIn('Datei nicht gefunden', fehler)


class TestRepl(unittest.TestCase):
    def test_klammer_im_string_haelt_repl_nicht_fest(self):
        code, ausgabe, _ = starte(eingabe='drucke("{")\ndrucke(1)\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertNotIn('... ', ausgabe)       # kein Fortsetzungs-Prompt
        self.assertIn('>>> 1', ausgabe)         # die Folgeeingabe wurde ausgeführt

    def test_echter_block_wird_mehrzeilig_gelesen(self):
        code, ausgabe, _ = starte(
            eingabe='wenn wahr {\ndrucke("a}b")\n}\ndrucke(7)\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertIn('a}b', ausgabe)
        self.assertIn('>>> 7', ausgabe)

    def test_offene_runde_klammer_fordert_folgezeile(self):
        code, ausgabe, _ = starte(eingabe='drucke(1 +\n2)\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertIn('... ', ausgabe)           # Folgezeile angefordert
        self.assertIn('3', ausgabe.split())      # und die Eingabe ausgeführt

    def test_ueberzaehlige_klammer_blockiert_repl_nicht(self):
        code, ausgabe, _ = starte(eingabe='drucke(1))\ndrucke(7)\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertNotIn('... ', ausgabe)        # keine Folgezeile angefordert
        self.assertIn('SyntaxError', ausgabe)    # Fehler sofort angezeigt
        self.assertIn('7', ausgabe.split())      # REPL läuft danach weiter

    def test_dreifach_zeichenkette_ueber_mehrere_zeilen(self):
        code, ausgabe, _ = starte(
            eingabe='sei x = """eins\nzwei \\{"""\ndrucke(x)\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertNotIn('Fehler', ausgabe)
        self.assertIn('eins\nzwei {', ausgabe)

    def test_rekursion_in_der_repl(self):
        eingabe = ('funktion r(n) { wenn n == 0 { zurueck 0 } zurueck 1 + r(n - 1) }\n'
                   'drucke(r(5000))\n'
                   'funktion e(n) { zurueck e(n + 1) }\n'
                   'e(0)\n'
                   'drucke(9)\n'
                   'beenden\n')
        code, ausgabe, _ = starte(eingabe=eingabe)
        self.assertEqual(code, 0)
        self.assertIn('>>> 5000', ausgabe)
        self.assertIn('Maximale Rekursionstiefe überschritten', ausgabe)
        self.assertIn('>>> 9', ausgabe)         # REPL lebt nach dem Fehler weiter


class TestFehlerInGeladenerDatei(unittest.TestCase):
    """Fehler in einer per 'lade' geladenen Datei nennen und zeigen diese Datei, nicht das Hauptskript."""

    def test_laufzeitfehler_zeigt_geladene_datei_und_zeile(self):
        code, ausgabe, fehler = starte_dateien({
            'hauptskript.deu': 'sei a = 1\nsei b = 2\nlade "unter/hilfe.deu"\ndrucke(a + b)\n',
            'unter/hilfe.deu': 'sei x = 1\nsei y = 2\ndrucke(1 / 0)\n',
        }, 'hauptskript.deu')
        zeilen = fehler.splitlines()
        self.assertEqual(code, 1)
        self.assertEqual(ausgabe, '')
        self.assertIn('  unter/hilfe.deu, Zeile 3:', zeilen)
        self.assertIn('    drucke(1 / 0)', zeilen)            # Quellzeile aus hilfe.deu
        self.assertNotIn('    lade "unter/hilfe.deu"', zeilen)  # nicht die Zeile 3 des Hauptskripts
        self.assertNotIn('hauptskript.deu, Zeile', fehler)

    def test_fehler_in_funktion_aus_geladener_datei(self):
        code, _, fehler = starte_dateien({
            'hauptskript.deu': 'lade "unter/hilfe.deu"\ndrucke(rechne(4))\n',
            'unter/hilfe.deu': 'funktion rechne(n) {\n    sei t = n * 2\n    zurück t / 0\n}\n',
        }, 'hauptskript.deu')
        self.assertEqual(code, 1)
        self.assertIn('  unter/hilfe.deu, Zeile 3:', fehler.splitlines())
        self.assertIn('zurück t / 0', fehler)

    def test_syntaxfehler_in_geladener_datei(self):
        code, _, fehler = starte_dateien({
            'hauptskript.deu': 'lade "unter/hilfe.deu"\n',
            'unter/hilfe.deu': 'sei x = 1\nsei = 2\n',
        }, 'hauptskript.deu')
        self.assertEqual(code, 1)
        self.assertIn('  unter/hilfe.deu, Zeile 2:', fehler.splitlines())
        self.assertIn('    sei = 2', fehler.splitlines())

    def test_fehler_im_hauptskript_zeigt_hauptskript(self):
        code, _, fehler = starte_dateien({'hauptskript.deu': 'sei a = 1\ndrucke(a / 0)\n'},
                                         'hauptskript.deu')
        self.assertEqual(code, 1)
        self.assertIn('hauptskript.deu, Zeile 2:', fehler)
        self.assertIn('    drucke(a / 0)', fehler.splitlines())


class TestFehlerAnzeige(unittest.TestCase):
    def test_zeile_attribut_hat_vorrang_vor_meldung(self):
        quelltext = 'eins\nzwei\ndrei'
        mit_attribut = RuntimeError('Zeile 3: kaputt')
        mit_attribut.zeile = 2
        self.assertIn('    zwei', _fehler_anzeigen(mit_attribut, quelltext, 'test.deu').splitlines())
        # ohne Attribut gilt weiter die Zeilennummer aus der Meldung
        ohne_attribut = RuntimeError('Zeile 3: kaputt')
        self.assertIn('    drei', _fehler_anzeigen(ohne_attribut, quelltext, 'test.deu').splitlines())


class TestBanner(unittest.TestCase):
    def test_alle_zeilen_gleich_breit(self):
        breiten = {len(zeile) for zeile in BANNER.split('\n')}
        self.assertEqual(len(breiten), 1, f'unterschiedliche Zeilenbreiten: {sorted(breiten)}')

    def test_zeigt_version_aus_paket(self):
        self.assertIn(f'Deutsch {__version__}', BANNER)
        self.assertNotIn('Deutsch 2.0', BANNER)


class TestOptionen(unittest.TestCase):
    def test_version(self):
        for option in ('--version', '-V'):
            with self.subTest(option=option):
                code, ausgabe, fehler = starte(option)
                self.assertEqual(code, 0)
                self.assertEqual(ausgabe.strip(), f'Deutsch {__version__}')
                self.assertEqual(fehler, '')

    def test_hilfe(self):
        for option in ('--hilfe', '-h', '--help'):
            with self.subTest(option=option):
                code, ausgabe, fehler = starte(option)
                self.assertEqual(code, 0)
                self.assertEqual(fehler, '')
                for erwartet in ('-c', '--pruefen', '--version', '--hilfe', '-h'):
                    self.assertIn(erwartet, ausgabe)

    def test_datei_bekommt_argumente(self):
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, 'args.deu')
            with open(pfad, 'w', encoding='utf-8') as f:
                f.write('drucke(kommandozeilen_argumente()[1])\n')
            code, ausgabe, _ = starte(pfad, 'eins', '--zwei')
        self.assertEqual(code, 0)
        self.assertEqual(ausgabe.strip(), '--zwei')

    def test_c_fuehrt_code_aus(self):
        code, ausgabe, fehler = starte('-c', 'drucke(1 + 2)')
        self.assertEqual((code, ausgabe.strip(), fehler), (0, '3', ''))

    def test_c_argumente(self):
        code, ausgabe, _ = starte('-c', 'drucke(kommandozeilen_argumente()[1])', 'eins', '--zwei')
        self.assertEqual(code, 0)
        self.assertEqual(ausgabe.strip(), '--zwei')

    def test_c_laufzeitfehler_exitcode_eins(self):
        code, ausgabe, fehler = starte('-c', 'drucke(1 / 0)')
        self.assertEqual(code, 1)
        self.assertEqual(ausgabe, '')
        self.assertIn('<kommandozeile>, Zeile 1:', fehler)
        self.assertIn('Division durch Null', fehler)

    def test_c_syntaxfehler_exitcode_eins(self):
        code, ausgabe, fehler = starte('-c', 'sei = 2')
        self.assertEqual(code, 1)
        self.assertEqual(ausgabe, '')
        self.assertIn('Zeile 1', fehler)

    def test_c_ohne_code_exitcode_zwei(self):
        code, ausgabe, fehler = starte('-c')
        self.assertEqual(code, 2)
        self.assertEqual(ausgabe, '')
        self.assertIn('Quelltext', fehler)


class TestPruefen(unittest.TestCase):
    def test_gueltige_datei_wird_nicht_ausgefuehrt(self):
        code, ausgabe, fehler = starte_pruefen(
            'drucke("laeuft")\ndrucke(1 / 0)\nlade "gibt_es_nicht.deu"\n')
        self.assertEqual(code, 0)
        self.assertEqual(fehler, '')
        self.assertTrue(ausgabe.strip().endswith(': keine Syntaxfehler'))
        self.assertNotIn('laeuft', ausgabe)

    def test_syntaxfehler_exitcode_eins(self):
        code, ausgabe, fehler = starte_pruefen('sei a = 1\nsei = 2\n')
        self.assertEqual(code, 1)
        self.assertEqual(ausgabe, '')
        self.assertIn('Zeile 2', fehler)
        self.assertIn('    sei = 2', fehler.splitlines())

    def test_fehlende_datei_exitcode_eins(self):
        code, _, fehler = starte('--pruefen', os.path.join(PROJEKT_WURZEL, 'gibt_es_nicht.deu'))
        self.assertEqual(code, 1)
        self.assertIn('Datei nicht gefunden', fehler)

    def test_ohne_datei_exitcode_zwei(self):
        code, ausgabe, fehler = starte('--pruefen')
        self.assertEqual(code, 2)
        self.assertEqual(ausgabe, '')
        self.assertIn('Datei', fehler)


class TestUnbekannteOption(unittest.TestCase):
    def test_lange_option_exitcode_zwei(self):
        code, ausgabe, fehler = starte('--xyz')
        self.assertEqual(code, 2)
        self.assertEqual(ausgabe, '')
        self.assertIn("unbekannte Option '--xyz'", fehler)
        self.assertIn('--hilfe', fehler)
        self.assertNotIn('Traceback', fehler)

    def test_kurze_option_exitcode_zwei(self):
        code, _, fehler = starte('-x')
        self.assertEqual(code, 2)
        self.assertIn("unbekannte Option '-x'", fehler)


class TestReplHilfe(unittest.TestCase):
    def test_hilfe_zeigt_uebersicht(self):
        code, ausgabe, _ = starte(eingabe='hilfe\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertIn('Befehle in der REPL', ausgabe)
        self.assertIn('Mehrzeilige Eingabe', ausgabe)
        self.assertNotIn('Fehler', ausgabe)

    def test_variable_hilfe_hat_vorrang(self):
        code, ausgabe, _ = starte(eingabe='sei hilfe = 5\nhilfe\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertIn('>>> 5', ausgabe)
        self.assertNotIn('Befehle in der REPL', ausgabe)

    def test_funktion_hilfe_hat_vorrang(self):
        code, ausgabe, _ = starte(eingabe='funktion hilfe() { zurueck 42 }\nhilfe()\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertIn('>>> 42', ausgabe)
        self.assertNotIn('Befehle in der REPL', ausgabe)

    def test_banner_zeigt_version(self):
        code, ausgabe, _ = starte(eingabe='beenden\n')
        self.assertEqual(code, 0)
        self.assertIn(f'Deutsch {__version__}', ausgabe)


class TestModulAufruf(unittest.TestCase):
    """'python -m deutsch' verhält sich wie main.py."""

    def test_version(self):
        code, ausgabe, fehler = starte_modul('--version')
        self.assertEqual(code, 0)
        self.assertEqual(ausgabe.strip(), f'Deutsch {__version__}')
        self.assertEqual(fehler, '')

    def test_hilfe(self):
        code, ausgabe, _ = starte_modul('--hilfe')
        self.assertEqual(code, 0)
        self.assertIn('--pruefen', ausgabe)

    def test_datei_ausfuehren(self):
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, 'modul.deu')
            with open(pfad, 'w', encoding='utf-8') as f:
                f.write('drucke("aus dem Modul")\n')
            code, ausgabe, fehler = starte_modul(pfad)
        self.assertEqual(code, 0)
        self.assertEqual(ausgabe.strip(), 'aus dem Modul')
        self.assertEqual(fehler, '')

    def test_laufzeitfehler_exitcode_eins(self):
        code, ausgabe, fehler = starte_modul('-c', 'drucke(1 / 0)')
        self.assertEqual(code, 1)
        self.assertEqual(ausgabe, '')
        self.assertIn('Division durch Null', fehler)

    def test_pruefen_fehlende_datei_exitcode_eins(self):
        code, _, fehler = starte_modul('--pruefen', 'gibt_es_nicht.deu')
        self.assertEqual(code, 1)
        self.assertIn('Datei nicht gefunden', fehler)

    def test_unbekannte_option_exitcode_zwei(self):
        code, _, fehler = starte_modul('--xyz')
        self.assertEqual(code, 2)
        self.assertIn("unbekannte Option '--xyz'", fehler)

    def test_repl_hilfe(self):
        code, ausgabe, _ = starte_modul(eingabe='hilfe\nbeenden\n')
        self.assertEqual(code, 0)
        self.assertIn('Befehle in der REPL', ausgabe)


if __name__ == '__main__':
    unittest.main()
