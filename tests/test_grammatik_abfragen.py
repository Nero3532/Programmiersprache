# -*- coding: utf-8 -*-
"""
Prüft die tree-sitter-Abfragen gegen die Knotentypen der Grammatik.

Ein Tippfehler in queries/*.scm fällt sonst erst auf, wenn `tree-sitter test`
läuft – und das braucht einen C-Compiler. Diese Prüfung kommt mit dem
eingecheckten src/node-types.json aus.
"""
import io
import json
import os
import re
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAMMATIK = os.path.join(PROJEKT_WURZEL, 'editor', 'tree-sitter-deutsch')
ABFRAGEN = os.path.join(GRAMMATIK, 'queries')
KNOTENTYPEN = os.path.join(GRAMMATIK, 'src', 'node-types.json')

# Prädikate wie (#any-of? @cap "drucke" ...) enthalten Zeichenketten-Argumente,
# keine Knotentypen – sie werden vor der Prüfung entfernt.
_PRAEDIKAT_START = '(#'


def _lies(pfad: str) -> str:
    with io.open(pfad, encoding='utf-8') as datei:
        return datei.read()


def _knotentypen():
    """(benannte Knoten, anonyme Token) aus node-types.json."""
    eintraege = json.loads(_lies(KNOTENTYPEN))
    benannt, anonym = set(), set()

    def aufnehmen(typ):
        (benannt if typ.get('named') else anonym).add(typ['type'])

    for eintrag in eintraege:
        aufnehmen(eintrag)
        for untertyp in eintrag.get('subtypes', []):
            aufnehmen(untertyp)
        for feld in (eintrag.get('fields') or {}).values():
            for typ in feld.get('types', []):
                aufnehmen(typ)
        kinder = eintrag.get('children')
        if kinder:
            for typ in kinder.get('types', []):
                aufnehmen(typ)
    return benannt, anonym


def _ohne_praedikate(text: str) -> str:
    """Entfernt geklammerte Prädikat-Ausdrücke samt ihrer Zeichenketten-Argumente."""
    ergebnis, i = [], 0
    while i < len(text):
        if text.startswith(_PRAEDIKAT_START, i):
            tiefe = 0
            while i < len(text):
                if text[i] == '(':
                    tiefe += 1
                elif text[i] == ')':
                    tiefe -= 1
                    if tiefe == 0:
                        i += 1
                        break
                i += 1
        else:
            ergebnis.append(text[i])
            i += 1
    return ''.join(ergebnis)


def _ohne_kommentare(text: str) -> str:
    return '\n'.join(zeile.split(';')[0] for zeile in text.split('\n'))


class TestGrammatikAbfragen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(KNOTENTYPEN):
            raise unittest.SkipTest('node-types.json fehlt – erst `tree-sitter generate`')
        cls.benannt, cls.anonym = _knotentypen()

    def _abfragedateien(self):
        return sorted(
            os.path.join(ABFRAGEN, n) for n in os.listdir(ABFRAGEN) if n.endswith('.scm')
        )

    def test_abfragedateien_vorhanden(self):
        namen = {os.path.basename(p) for p in self._abfragedateien()}
        self.assertEqual(namen, {'highlights.scm', 'locals.scm', 'folds.scm'})

    def test_grammatik_kennt_die_erwarteten_knoten(self):
        for name in ('quelldatei', 'funktion_definition', 'klassen_definition',
                     'wenn_anweisung', 'fuer_anweisung', 'binaere_operation',
                     'zeichenkette', 'interpolation', 'neu_ausdruck'):
            self.assertIn(name, self.benannt)

    def test_alle_benannten_knoten_in_abfragen_existieren(self):
        for pfad in self._abfragedateien():
            text = _ohne_praedikate(_ohne_kommentare(_lies(pfad)))
            for nr, zeile in enumerate(text.split('\n'), 1):
                for name in re.findall(r'\(\s*([a-z][a-zäöüß0-9_]*)', zeile):
                    with self.subTest(datei=os.path.basename(pfad), zeile=nr, knoten=name):
                        self.assertIn(name, self.benannt,
                                      f'unbekannter Knotentyp ({name})')

    def test_alle_anonymen_token_in_abfragen_existieren(self):
        for pfad in self._abfragedateien():
            text = _ohne_praedikate(_ohne_kommentare(_lies(pfad)))
            for nr, zeile in enumerate(text.split('\n'), 1):
                for token in re.findall(r'"([^"]+)"', zeile):
                    with self.subTest(datei=os.path.basename(pfad), zeile=nr, token=token):
                        self.assertIn(token, self.anonym,
                                      f'unbekanntes Token "{token}" – Regeln aus einem '
                                      f'einzigen String werden zu Blattknoten und müssen '
                                      f'benannt abgefragt werden')

    def test_praedikat_argumente_werden_nicht_als_knoten_gelesen(self):
        # Schutz vor Fehlalarmen: die Namen der eingebauten Funktionen stehen in
        # #any-of?-Prädikaten und sind keine Knotentypen.
        roh = _lies(os.path.join(ABFRAGEN, 'highlights.scm'))
        self.assertIn('#any-of?', roh)
        self.assertNotIn('drucke', _ohne_praedikate(roh))

    def test_eingebaute_funktionen_der_abfrage_existieren_wirklich(self):
        """Die in highlights.scm hervorgehobenen Namen müssen echte Eingebaute sein."""
        import sys
        sys.path.insert(0, PROJEKT_WURZEL)
        from deutsch.interpreter import Interpreter

        roh = _lies(os.path.join(ABFRAGEN, 'highlights.scm'))
        block = roh.split('@function.builtin')[-1].split('))')[0]
        genannt = set(re.findall(r'"([^"]+)"', block))
        vorhanden = set(Interpreter().global_umgebung.variablen)
        self.assertTrue(genannt, 'kein #any-of?-Block gefunden')
        self.assertEqual(genannt - vorhanden, set(),
                         'in der Hervorhebung genannte Funktionen gibt es nicht')


if __name__ == '__main__':
    unittest.main()
