# -*- coding: utf-8 -*-
"""
Tests für die Versionsnummer: pyproject.toml und deutsch.__version__ müssen gleich sein.

pyproject.toml wird per Regex gelesen, weil tomllib erst ab Python 3.11 verfügbar ist
und das Projekt ab Python 3.10 läuft.

Ausführen mit:
    python -m unittest discover -s tests -v
"""
import os
import re
import sys
import unittest

PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT_WURZEL)

import deutsch

PYPROJECT = os.path.join(PROJEKT_WURZEL, 'pyproject.toml')


def _pyproject_version():
    """Liest version aus dem Abschnitt [project] der pyproject.toml."""
    with open(PYPROJECT, 'r', encoding='utf-8') as f:
        text = f.read()
    abschnitt = re.search(r'^\[project\]\s*$(.*?)(?=^\[|\Z)', text,
                          re.MULTILINE | re.DOTALL)
    if abschnitt is None:
        raise AssertionError('Abschnitt [project] fehlt in pyproject.toml')
    zeile = re.search(r'^version\s*=\s*"([^"]+)"\s*$', abschnitt.group(1),
                      re.MULTILINE)
    if zeile is None:
        raise AssertionError('version fehlt in [project] der pyproject.toml')
    return zeile.group(1)


class VersionTest(unittest.TestCase):

    def test_pyproject_und_paket_version_gleich(self):
        self.assertEqual(_pyproject_version(), deutsch.__version__)


if __name__ == '__main__':
    unittest.main()
