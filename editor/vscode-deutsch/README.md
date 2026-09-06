# Deutsch für VS Code

Sprachunterstützung für die Programmiersprache [Deutsch](../../README.md).

## Was sie kann

**Syntaxhervorhebung** für `.deu`-Dateien: Schlüsselwörter, Zeichenketten samt Interpolation
`{ausdruck:format}` und Escapes, Zahlen, Kommentare, Funktions- und Klassennamen, Typ-Hinweise,
Methodenaufrufe und die eingebauten Funktionen.

**Über den Language Server** (`deutsch --lsp`) zusätzlich:

- Syntaxfehler direkt im Editor, mit den deutschen Meldungen des Interpreters
- Gliederung (Gliederungsansicht, Gehe-zu-Symbol) mit Klassen und deren Mitgliedern
- Vervollständigung – nach einem `.` nur die Methoden des jeweiligen Typs
- Kurzinfo mit Signaturen der eingebauten Methoden
- Gehe-zu-Definition für Funktionen, Klassen und Methoden

Der Editor kommentiert mit `#`, klammert automatisch und rückt nach `{` ein.

## Installation

Die Erweiterung ist nicht im Marketplace. Zum Ausprobieren:

```
cd editor/vscode-deutsch
npm install
code --extensionDevelopmentPath=.
```

Damit öffnet sich ein zweites VS-Code-Fenster, in dem die Erweiterung aktiv ist.

Für ein installierbares Paket:

```
npx @vscode/vsce package
code --install-extension deutsch-lang-0.1.0.vsix
```

## Language Server einrichten

Voreingestellt startet die Erweiterung `deutsch --lsp`. Das setzt voraus, dass das Projekt
installiert ist:

```
pip install -e .
```

Ohne Installation trägst du den Befehl direkt ein – Einstellung `deutsch.serverBefehl`:

```json
"deutsch.serverBefehl": ["python", "C:/Pfad/zum/Projekt/main.py", "--lsp"]
```

Schlägt der Start fehl, meldet die Erweiterung das einmalig und bietet an, die Einstellung zu
öffnen. Die Syntaxhervorhebung funktioniert davon unabhängig weiter, weil sie nicht vom
Server kommt.

Weitere Einstellungen: `deutsch.sprachserverAktiv` schaltet den Server ab,
`deutsch.ablaufverfolgung` protokolliert den Nachrichtenaustausch im Ausgabefenster.

## Warum zwei Grammatiken?

Im Projekt liegt unter [`editor/tree-sitter-deutsch`](../tree-sitter-deutsch) zusätzlich eine
tree-sitter-Grammatik. VS Code hebt aber nicht mit tree-sitter hervor, sondern mit TextMate –
deshalb hat diese Erweiterung ihre eigene Grammatik in `syntaxes/`. Die tree-sitter-Variante
bedient Neovim, Helix, Zed, Emacs und GitHub.

Beide beschreiben dieselbe Sprache, sind aber unabhängig gepflegt. Verbindlich ist in beiden
Fällen `deutsch/parser.py`.

## Tests

```
npm test
```

Prüft die Hervorhebung anhand von `test/hervorhebung.deu`: die Kommentarzeilen mit `^` darin
sind Zusicherungen, welcher Bereich an welcher Spalte welchen Scope tragen muss. Läuft in der
CI mit.
