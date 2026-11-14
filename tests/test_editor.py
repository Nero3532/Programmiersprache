"""Selbstprüfung der VS-Code-Erweiterung (editor/vscode)."""
import json, re, unittest
from pathlib import Path

from deutsch.interpreter import FEHLERARTEN
from deutsch.lexer import SCHLUESSELWOERTER

ORDNER = Path(__file__).resolve().parent.parent / 'editor' / 'vscode'


def _laden(rel):
    return json.loads((ORDNER / rel).read_text(encoding='utf-8'))


def _muster(knoten):
    if isinstance(knoten, dict):
        for k, v in knoten.items():
            if k in ('match', 'begin', 'end') and isinstance(v, str):
                yield v
            else:
                yield from _muster(v)
    elif isinstance(knoten, list):
        for v in knoten:
            yield from _muster(v)


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.gram = _laden('syntaxes/deutsch.tmLanguage.json')
        self.text = '\n'.join(_muster(self.gram))

    def test_json_gueltig(self):
        for f in ('package.json', 'language-configuration.json'):
            _laden(f)
        self.assertEqual(_laden('package.json')['contributes']['languages'][0]['id'], 'deutsch')

    def test_schluesselwoerter(self):
        for w in SCHLUESSELWOERTER:
            self.assertRegex(self.text, r'(?<![\wäöüß])' + re.escape(w) + r'(?![\wäöüß])', w)

    def test_fehlerarten(self):
        for w in FEHLERARTEN:
            self.assertRegex(self.text, r'(?<!\w)' + w + r'(?!\w)', w)

    def test_regex_kompilierbar(self):
        for m in _muster(self.gram):
            if r'\p{' in m:  # Oniguruma-Syntax
                continue
            re.compile(m)


if __name__ == '__main__':
    unittest.main()
