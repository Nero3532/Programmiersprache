# -*- coding: utf-8 -*-
from .token_typen import TokenTyp


SCHLUESSELWOERTER = {
    'sei':       TokenTyp.SEI,
    'wenn':      TokenTyp.WENN,
    'sonst':     TokenTyp.SONST,
    'solange':   TokenTyp.SOLANGE,
    'für':       TokenTyp.FUER,
    'fuer':      TokenTyp.FUER,
    'in':        TokenTyp.IN,
    'funktion':  TokenTyp.FUNKTION,
    'zurück':    TokenTyp.ZURUECK,
    'zurueck':   TokenTyp.ZURUECK,
    'wahr':      TokenTyp.WAHR,
    'falsch':    TokenTyp.FALSCH,
    'nichts':    TokenTyp.NICHTS,
    'und':       TokenTyp.UND,
    'oder':      TokenTyp.ODER,
    'nicht':     TokenTyp.NICHT,
    'klasse':    TokenTyp.KLASSE,
    'neu':       TokenTyp.NEU,
    'abbrechen': TokenTyp.ABBRECHEN,
    'weiter':    TokenTyp.WEITER,
    'versuche':  TokenTyp.VERSUCHE,
    'fange':     TokenTyp.FANGE,
    'endlich':   TokenTyp.ENDLICH,
    'lade':      TokenTyp.LADE,
    'passe':     TokenTyp.PASSE,
    'fall':      TokenTyp.FALL,
    'werfe':     TokenTyp.WERFE,
    'pruefe':    TokenTyp.PRUEFE,
    'konstante': TokenTyp.KONSTANTE,
    'statisch':  TokenTyp.STATISCH,
    'als':       TokenTyp.ALS,
}

# Zahlen mit Präfix: 0x.. / 0b.. / 0o..  ->  (Name für Fehlermeldungen, Basis, erlaubte Ziffern)
_ZAHL_BASEN = {
    'x': ('Hexadezimalzahl', 16, '0123456789abcdefABCDEF'),
    'b': ('Binärzahl', 2, '01'),
    'o': ('Oktalzahl', 8, '01234567'),
}

_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\',
            '"': '"', "'": "'", '{': '{', '}': '}'}


class Token:
    __slots__ = ('typ', 'wert', 'zeile')

    def __init__(self, typ, wert, zeile):
        self.typ = typ
        self.wert = wert
        self.zeile = zeile

    def __repr__(self):
        return f'Token({self.typ.name}, {self.wert!r}, Z.{self.zeile})'


class Lexer:
    def __init__(self, quelltext: str, start_zeile: int = 1):
        self.quelltext = quelltext
        self.pos = 0
        self.zeile = start_zeile  # >1 für Teilausdrücke (Interpolation) mitten in einer Datei
        self.tokens: list[Token] = []

    # ---------------------------------------------------------------- Hilfsm.

    def _fehler(self, msg: str):
        raise SyntaxError(f'Zeile {self.zeile}: {msg}')

    def _aktuell(self):
        return self.quelltext[self.pos] if self.pos < len(self.quelltext) else None

    def _vorschau(self, offset: int = 1):
        p = self.pos + offset
        return self.quelltext[p] if p < len(self.quelltext) else None

    def _weiter(self):
        if self._aktuell() == '\n':
            self.zeile += 1
        self.pos += 1

    def _leerzeichen(self):
        while self._aktuell() in (' ', '\t', '\r'):
            self._weiter()

    def _kommentar(self):
        while self._aktuell() and self._aktuell() != '\n':
            self._weiter()

    # ------------------------------------------------------------------ Zahlen

    def _ziffernfolge(self, ist_ziffer) -> str:
        """Liest eine Ziffernfolge und gibt sie ohne Unterstriche zurück ('' wenn keine Ziffer folgt).

        Ein einzelner '_' ist nur zwischen zwei Ziffern erlaubt (1_000)."""
        ziffern = []
        while True:
            c = self._aktuell()
            if c is not None and ist_ziffer(c):
                ziffern.append(c)
                self._weiter()
            elif c == '_' and ziffern:
                naechstes = self._vorschau()
                if naechstes is None or not ist_ziffer(naechstes):
                    self._fehler("Ungültiger Unterstrich in Zahl: '_' darf nur "
                                 "einzeln zwischen zwei Ziffern stehen (z. B. 1_000)")
                self._weiter()
            else:
                break
        return ''.join(ziffern)

    def _zahl_mit_basis(self):
        self._weiter()  # '0'
        kennung = self._aktuell().lower()
        self._weiter()  # x / b / o
        name, basis, erlaubt = _ZAHL_BASEN[kennung]
        ziffern = self._ziffernfolge(lambda c: c in erlaubt)
        if not ziffern:
            self._fehler(f"Ungültiges Zahlenliteral '0{kennung}': {name} braucht mindestens eine Ziffer")
        c = self._aktuell()
        if c is not None and (c.isalnum() or c == '_'):
            self._fehler(f"Ungültiges Zeichen {c!r} in {name}")
        return Token(TokenTyp.GANZZAHL, int(ziffern, basis), self.zeile)

    def _zahl(self):
        if self._aktuell() == '0' and self._vorschau() is not None                 and self._vorschau().lower() in _ZAHL_BASEN:
            return self._zahl_mit_basis()
        text = self._ziffernfolge(str.isdecimal)
        ist_kommazahl = False
        if self._aktuell() == '.' and self._vorschau() and self._vorschau().isdecimal():
            ist_kommazahl = True
            self._weiter()
            text += '.' + self._ziffernfolge(str.isdecimal)
        if self._aktuell() in ('e', 'E'):
            offset = 1
            if self._vorschau(offset) in ('+', '-'):
                offset += 1
            if self._vorschau(offset) and self._vorschau(offset).isdecimal():
                ist_kommazahl = True
                vorzeichen = self._vorschau(1) if offset == 2 else ''
                for _ in range(offset):
                    self._weiter()
                text += 'e' + vorzeichen + self._ziffernfolge(str.isdecimal)
        if ist_kommazahl:
            return Token(TokenTyp.KOMMAZAHL, float(text), self.zeile)
        return Token(TokenTyp.GANZZAHL, int(text), self.zeile)

    # --------------------------------------------------------------- Strings

    def _lese_string_inhalt(self, anf: str, dreifach: bool) -> list:
        """Liest String-Inhalt und gibt Teile zurück: [('text', str) | ('code', str, zeile)].

        zeile = absolute Zeile, in der der Code-Text beginnt (für Fehler im Teilausdruck)."""
        teile = []
        aktueller_text = []
        hat_interp = False

        while True:
            c = self._aktuell()
            if c is None:
                self._fehler('Nicht abgeschlossene Zeichenkette')

            # Ende-Erkennung
            if dreifach:
                if c == anf and self._vorschau() == anf and self._vorschau(2) == anf:
                    self._weiter(); self._weiter(); self._weiter()
                    break
            else:
                if c == anf:
                    self._weiter()
                    break
                if c == '\n':
                    self._fehler('Nicht abgeschlossene Zeichenkette (kein Zeilenende erlaubt)')

            # Escape
            if c == '\\':
                self._weiter()
                esc = self._aktuell()
                if esc is None:
                    self._fehler('Nicht abgeschlossener Escape')
                aktueller_text.append(_ESCAPES.get(esc, '\\' + esc))
                self._weiter()
                continue

            # Interpolation {ausdruck}
            if c == '{':
                hat_interp = True
                if aktueller_text:
                    teile.append(('text', ''.join(aktueller_text)))
                    aktueller_text = []
                zeile_klammer = self.zeile
                self._weiter()  # {
                tiefe = 1
                code = []
                while self._aktuell() and tiefe > 0:
                    if self._aktuell() == '{':
                        tiefe += 1
                    elif self._aktuell() == '}':
                        tiefe -= 1
                        if tiefe == 0:
                            break
                    code.append(self._aktuell())
                    self._weiter()
                if not self._aktuell():
                    # Zeile des '{' nennen, nicht die des String-Endes
                    raise SyntaxError(f"Zeile {zeile_klammer}: Nicht abgeschlossene Interpolation '{{...}}'")
                self._weiter()  # }
                roh = ''.join(code)
                # führende Leerzeilen im Code verschieben den Beginn des Ausdrucks
                zeile_code = zeile_klammer + roh[:len(roh) - len(roh.lstrip())].count('\n')
                teile.append(('code', roh.strip(), zeile_code))
                continue

            aktueller_text.append(c)
            self._weiter()  # zählt Zeilenumbrüche selbst mit – nicht zusätzlich zählen

        if aktueller_text:
            teile.append(('text', ''.join(aktueller_text)))

        return teile, hat_interp

    def _zeichenkette(self, anf: str):
        self._weiter()  # erstes Anführungszeichen
        dreifach = False

        # Triple-Quote erkennen: "" oder ''
        if self._aktuell() == anf and self._vorschau() == anf:
            self._weiter()
            self._weiter()
            dreifach = True

        zeile_start = self.zeile
        teile, hat_interp = self._lese_string_inhalt(anf, dreifach)

        if not hat_interp:
            text = ''.join(t[1] for t in teile)
            return Token(TokenTyp.ZEICHENKETTE, text, zeile_start)
        return Token(TokenTyp.INTERP_ZEICHENKETTE, teile, zeile_start)

    # -------------------------------------------------------------- Bezeichner

    def _bezeichner(self):
        start = self.pos
        while self._aktuell() and (self._aktuell().isalnum() or self._aktuell() == '_'):
            self._weiter()
        name = self.quelltext[start:self.pos]
        typ = SCHLUESSELWOERTER.get(name, TokenTyp.BEZEICHNER)

        if typ == TokenTyp.WAHR:   return Token(typ, True, self.zeile)
        if typ == TokenTyp.FALSCH: return Token(typ, False, self.zeile)
        if typ == TokenTyp.NICHTS: return Token(typ, None, self.zeile)
        return Token(typ, name, self.zeile)

    # ---------------------------------------------------------------- Operator-Helfer

    def _op_mit_gleich(self, einfach: TokenTyp, zusammen: TokenTyp, zeichen: str):
        if self._vorschau() == '=':
            self._weiter()
            t = Token(zusammen, zeichen + '=', self.zeile)
        else:
            t = Token(einfach, zeichen, self.zeile)
        self._weiter()
        return t

    # --------------------------------------------------------------- Hauptlauf

    def tokenisieren(self) -> list[Token]:
        while self.pos < len(self.quelltext):
            self._leerzeichen()
            c = self._aktuell()
            if c is None:
                break

            if c == '#':
                self._kommentar()
                continue

            if c == '\n':
                self.tokens.append(Token(TokenTyp.ZEILENENDE, '\n', self.zeile))
                self._weiter()
                continue

            if c.isdecimal():
                self.tokens.append(self._zahl())
                continue

            if c in ('"', "'"):
                self.tokens.append(self._zeichenkette(c))
                continue

            if c.isalpha() or c == '_':
                self.tokens.append(self._bezeichner())
                continue

            # ---- Operatoren ----
            if c == '+':
                self.tokens.append(self._op_mit_gleich(TokenTyp.PLUS, TokenTyp.PLUS_GLEICH, '+'))
            elif c == '-':
                if self._vorschau() == '>':
                    self._weiter(); self._weiter()
                    self.tokens.append(Token(TokenTyp.PFEIL, '->', self.zeile))
                else:
                    self.tokens.append(self._op_mit_gleich(TokenTyp.MINUS, TokenTyp.MINUS_GLEICH, '-'))
            elif c == '*':
                if self._vorschau() == '*':
                    self._weiter(); self._weiter()
                    if self._aktuell() == '=':
                        self._weiter()
                        self.tokens.append(Token(TokenTyp.STERN_STERN_GLEICH, '**=', self.zeile))
                    else:
                        self.tokens.append(Token(TokenTyp.STERN_STERN, '**', self.zeile))
                else:
                    self.tokens.append(self._op_mit_gleich(TokenTyp.STERN, TokenTyp.STERN_GLEICH, '*'))
            elif c == '/':
                if self._vorschau() == '/':
                    self._weiter(); self._weiter()
                    if self._aktuell() == '=':
                        self._weiter()
                        self.tokens.append(Token(TokenTyp.SCHRAEGSTRICH_SCHRAEGSTRICH_GLEICH, '//=', self.zeile))
                    else:
                        self.tokens.append(Token(TokenTyp.SCHRAEGSTRICH_SCHRAEGSTRICH, '//', self.zeile))
                else:
                    self.tokens.append(self._op_mit_gleich(TokenTyp.SCHRAEGSTRICH, TokenTyp.SCHRAEGSTRICH_GLEICH, '/'))
            elif c == '%':
                self.tokens.append(self._op_mit_gleich(TokenTyp.PROZENT, TokenTyp.PROZENT_GLEICH, '%'))
            elif c == '=':
                if self._vorschau() == '=':
                    self._weiter()
                    self.tokens.append(Token(TokenTyp.DOPPELGLEICH, '==', self.zeile))
                else:
                    self.tokens.append(Token(TokenTyp.GLEICH, '=', self.zeile))
                self._weiter()
            elif c == '!':
                if self._vorschau() == '=':
                    self._weiter()
                    self.tokens.append(Token(TokenTyp.UNGLEICH, '!=', self.zeile))
                    self._weiter()
                else:
                    self._fehler("'!' alleine ist ungültig – meintest du '!='?")
            elif c == '<':
                if self._vorschau() == '<':
                    self._weiter(); self._weiter()
                    if self._aktuell() == '=':
                        self._weiter()
                        self.tokens.append(Token(TokenTyp.KLEINER_KLEINER_GLEICH, '<<=', self.zeile))
                    else:
                        self.tokens.append(Token(TokenTyp.KLEINER_KLEINER, '<<', self.zeile))
                else:
                    if self._vorschau() == '=':
                        self._weiter()
                        self.tokens.append(Token(TokenTyp.KLEINERGLEICH, '<=', self.zeile))
                    else:
                        self.tokens.append(Token(TokenTyp.KLEINER, '<', self.zeile))
                    self._weiter()
            elif c == '>':
                if self._vorschau() == '>':
                    self._weiter(); self._weiter()
                    if self._aktuell() == '=':
                        self._weiter()
                        self.tokens.append(Token(TokenTyp.GROESSER_GROESSER_GLEICH, '>>=', self.zeile))
                    else:
                        self.tokens.append(Token(TokenTyp.GROESSER_GROESSER, '>>', self.zeile))
                else:
                    if self._vorschau() == '=':
                        self._weiter()
                        self.tokens.append(Token(TokenTyp.GROESSERGLEICH, '>=', self.zeile))
                    else:
                        self.tokens.append(Token(TokenTyp.GROESSER, '>', self.zeile))
                    self._weiter()
            elif c == '&':
                self.tokens.append(self._op_mit_gleich(TokenTyp.KAUFMANNSUND, TokenTyp.KAUFMANNSUND_GLEICH, '&'))
            elif c == '|':
                self.tokens.append(self._op_mit_gleich(TokenTyp.SENKRECHT, TokenTyp.SENKRECHT_GLEICH, '|'))
            elif c == '^':
                self.tokens.append(self._op_mit_gleich(TokenTyp.HUT, TokenTyp.HUT_GLEICH, '^'))
            elif c == '~':
                self.tokens.append(Token(TokenTyp.TILDE, '~', self.zeile)); self._weiter()
            elif c == '?':
                if self._vorschau() == '?':
                    self._weiter(); self._weiter()
                    self.tokens.append(Token(TokenTyp.FRAGE_FRAGE, '??', self.zeile))
                else:
                    self._fehler("'?' alleine ist ungültig – meintest du '??' (Null-Koaleszenz)?")
            # ---- Trennzeichen ----
            elif c == '(':
                self.tokens.append(Token(TokenTyp.LPAREN, '(', self.zeile)); self._weiter()
            elif c == ')':
                self.tokens.append(Token(TokenTyp.RPAREN, ')', self.zeile)); self._weiter()
            elif c == '{':
                self.tokens.append(Token(TokenTyp.LGESCHWEIFTE, '{', self.zeile)); self._weiter()
            elif c == '}':
                self.tokens.append(Token(TokenTyp.RGESCHWEIFTE, '}', self.zeile)); self._weiter()
            elif c == '[':
                self.tokens.append(Token(TokenTyp.LECKIG, '[', self.zeile)); self._weiter()
            elif c == ']':
                self.tokens.append(Token(TokenTyp.RECKIG, ']', self.zeile)); self._weiter()
            elif c == ',':
                self.tokens.append(Token(TokenTyp.KOMMA, ',', self.zeile)); self._weiter()
            elif c == '.':
                self.tokens.append(Token(TokenTyp.PUNKT, '.', self.zeile)); self._weiter()
            elif c == ':':
                self.tokens.append(Token(TokenTyp.DOPPELPUNKT, ':', self.zeile)); self._weiter()
            elif c == ';':
                self.tokens.append(Token(TokenTyp.SEMIKOLON, ';', self.zeile)); self._weiter()
            else:
                self._fehler(f'Unbekanntes Zeichen: {c!r}')

        self.tokens.append(Token(TokenTyp.DATEIENDE, None, self.zeile))
        return self.tokens
