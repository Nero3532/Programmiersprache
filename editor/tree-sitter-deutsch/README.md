# tree-sitter-deutsch

tree-sitter-Grammatik für die Programmiersprache [Deutsch](../../README.md).

Sie liefert die Grundlage für Syntaxhervorhebung, Faltung und strukturelle Navigation
in Editoren (Neovim, Helix, Zed, Emacs, GitHub-Linguist).

## Aufbau

```
grammar.js            Grammatik
src/                  generierter Parser (parser.c, grammar.json, node-types.json)
queries/
  highlights.scm      Syntaxhervorhebung
  locals.scm          Geltungsbereiche und Bindungen
  folds.scm           faltbare Bereiche
test/corpus/          Korpus-Tests
```

`src/` ist eingecheckt, damit Nutzer die Grammatik ohne die tree-sitter-CLI einbinden können.

## Bauen und testen

```
npm install
npx tree-sitter generate      # schreibt src/ neu – braucht keinen C-Compiler
npx tree-sitter test          # führt test/corpus aus – braucht einen C-Compiler
npx tree-sitter parse datei.deu
```

Unter Windows sucht die CLI `cl.exe`; nötig sind entweder die Visual-Studio-Workload
„Desktopentwicklung mit C++" oder LLVM (`clang-cl`, dann `set CC=clang-cl`).

## Verhältnis zum Interpreter

Verbindlich ist immer `deutsch/parser.py`. Diese Grammatik dient der Werkzeug­unterstützung
und ist an einer Stelle bewusst großzügiger:

**Zeilenenden sind keine Trennzeichen.** Der echte Parser trennt Anweisungen an Zeilenenden
und Semikolons; hier zählt Leerraum durchgehend als ignorierbar. Ohne diese Vereinfachung
bräuchte die Grammatik einen externen Scanner in C, was das Einbinden deutlich erschwert.

Ein Sonderfall verdient Erwähnung, weil er in echtem Code ständig vorkommt:

```
sei it = f(i)
wenn bedingung { … }
```

Ohne Zeilenenden ist `wenn` hier mehrdeutig – es kann den Ternär `a wenn b sonst c`
fortsetzen oder eine neue Anweisung beginnen. Statt das per Vorrangregel zu erzwingen
(was eine der beiden Lesarten immer kaputtmacht), ist der Konflikt deklariert: tree-sitters
GLR verfolgt beide Zweige, und der falsche stirbt kurz darauf am fehlenden `sonst`
beziehungsweise am Block. Nach `werfe` und in Zuweisungen gilt dasselbe. Nach `zurück`,
`pruefe` und `lade` gewinnt dagegen der Ternär – dort ist ein direkt folgendes `wenn`
praktisch immer der Ternär.

Praktische Folge davon, dass Zeilenenden fehlen: einzelne Konstrukte werden anders
gruppiert, als der Interpreter sie liest.

```
sei x = 5
-3
```

Der Interpreter sieht zwei Anweisungen, die Grammatik liest `5 - 3`. Für Hervorhebung und
Navigation ist das ohne Bedeutung; für Fehlermeldungen ist ohnehin der Language Server
zuständig (`deutsch --lsp`), der den echten Parser benutzt.

Zwei weitere bewusste Vereinfachungen:

- In dreifach gequoteten Zeichenketten (`"""…"""`) wird die Interpolation nicht
  aufgeschlüsselt – der String ist ein einzelnes Token. In einfach gequoteten
  Zeichenketten wird `{ausdruck:format}` vollständig als Baum abgebildet.
- Vergleichsketten (`1 < x < 10`) erscheinen als links-assoziativ verschachtelte
  Operationen; dass der Interpreter daraus eine echte Kette macht, ist Semantik.

## Knotennamen

Die Regeln tragen deutsche Namen, passend zum Rest des Projekts: `variable_deklaration`,
`funktion_definition`, `klassen_koerper`, `wenn_anweisung`, `fuer_anweisung`,
`listen_abstraktion`, `binaere_operation`, `attribut_zugriff`, `neu_ausdruck` und so weiter.
Die vollständige Liste steht in `src/node-types.json`.
