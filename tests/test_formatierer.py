# -*- coding: utf-8 -*-
"""Tests für den Formatierer (py -m deutsch --formatieren)."""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)

from deutsch import formatierer


def lauf(*args):
    return subprocess.run([sys.executable, '-m', 'deutsch', *args], cwd=WURZEL,
                          capture_output=True, text=True, encoding='utf-8')


class FormatiereTests(unittest.TestCase):
    def test_verschachtelt(self):
        q = 'funktion f(x) {\nwenn x {\ndrucke(1)\n}\n}\n'
        self.assertEqual(formatierer.formatiere(q),
                         'funktion f(x) {\n    wenn x {\n        drucke(1)\n    }\n}\n')

    def test_klammern_ueber_zeilen(self):
        q = 'sei a = [\n1,\n2\n]\ndrucke(\na\n)\n'
        self.assertEqual(formatierer.formatiere(q), 'sei a = [\n    1,\n    2\n]\ndrucke(\n    a\n)\n')

    def test_dreifach_unveraendert(self):
        q = 'sei t = """\n  a {\n\tb  \n"""\ndrucke(t)\n'
        self.assertEqual(formatierer.formatiere(q), q)

    def test_zeichenketten_und_kommentar_zaehlen_nicht(self):
        q = 'wenn wahr {\ndrucke("}{ {x}")\n# } {\n}\n'
        self.assertEqual(formatierer.formatiere(q),
                         'wenn wahr {\n    drucke("}{ {x}")\n    # } {\n}\n')

    def test_leerraum(self):
        q = 'a = 1   \n\n\n\n\n\tdrucke(1)\t\n\n\n'
        self.assertEqual(formatierer.formatiere(q), 'a = 1\n\n\ndrucke(1)\n')

    def test_idempotent(self):
        q = 'funktion f() {\nwenn 1 {\n  # x\ndrucke([\n1\n])\n}\n}\n'
        einmal = formatierer.formatiere(q)
        self.assertEqual(formatierer.formatiere(einmal), einmal)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.ordner, True)

    def datei(self, inhalt: bytes, name='t.deu'):
        pfad = os.path.join(self.ordner, name)
        with open(pfad, 'wb') as f:
            f.write(inhalt)
        return pfad

    def lesen(self, pfad):
        with open(pfad, 'rb') as f:
            return f.read()

    def test_kommentare_und_meldungen(self):
        p = self.datei('# kopf\nwenn wahr {\ndrucke(1)  # inline\n}\n'.encode())
        r = lauf('--formatieren', p)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, f'{p}: formatiert'))
        self.assertEqual(self.lesen(p), '# kopf\nwenn wahr {\n    drucke(1)  # inline\n}\n'.encode())
        r = lauf('--formatieren', p)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, f'{p}: bereits formatiert'))

    def test_crlf_bleibt(self):
        p = self.datei(b'wenn wahr {\r\ndrucke(1)\r\n}\r\n')
        self.assertEqual(lauf('--formatieren', p).returncode, 0)
        self.assertEqual(self.lesen(p), b'wenn wahr {\r\n    drucke(1)\r\n}\r\n')

    def test_syntaxfehler_unveraendert(self):
        roh = b'wenn wahr {\ndrucke(1\n'
        p = self.datei(roh)
        r = lauf('--formatieren', p)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.strip())
        self.assertEqual(self.lesen(p), roh)

    def test_schutz_ast_abweichung(self):
        roh = b'wenn wahr {\ndrucke(1)\n}\n'
        p = self.datei(roh)
        with mock.patch.object(formatierer, '_struktur', side_effect=[1, 2]):
            self.assertEqual(formatierer._formatieren_pruefen(roh.decode())[0], None)
            with mock.patch('builtins.print') as ausgabe:
                self.assertEqual(formatierer.datei_formatieren(p), 1)
        self.assertEqual(self.lesen(p), roh)

    def test_schutz_kommentar_abweichung(self):
        with mock.patch.object(formatierer, '_kommentare', side_effect=[['#a'], ['#b']]):
            self.assertIsNone(formatierer._formatieren_pruefen('drucke(1)\n')[0])

    def test_beispiele(self):
        for quelle in sorted(glob.glob(os.path.join(WURZEL, 'beispiele', '*.deu'))):
            with self.subTest(datei=os.path.basename(quelle)):
                kopie = os.path.join(self.ordner, os.path.basename(quelle))
                shutil.copy(quelle, kopie)
                r = lauf('--formatieren', kopie)
                self.assertEqual(r.returncode, 0, r.stderr)
                nach = self.lesen(kopie)
                self.assertEqual(lauf('--formatieren', kopie).stdout.strip(), f'{kopie}: bereits formatiert')
                self.assertEqual(self.lesen(kopie), nach)
                self.assertEqual(lauf('--pruefen', kopie).returncode, 0)


if __name__ == '__main__':
    unittest.main()
