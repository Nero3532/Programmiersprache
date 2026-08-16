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
    def __init__(self, quelltext: str):
        self.quelltext = quelltext
        self.pos = 0
        self.zeile = 1
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

    def _zahl(self):
        start = self.pos
        while self._aktuell() and self._aktuell().isdigit():
            self._weiter()
        ist_kommazahl = False
        if self._aktuell() == '.' and self._vorschau() and self._vorschau().isdigit():
            ist_kommazahl = True
            self._weiter()
            while self._aktuell() and self._aktuell().isdigit():
                self._weiter()
        if self._aktuell() in ('e', 'E'):
            offset = 1
            if self._vorschau(offset) in ('+', '-'):
                offset += 1
            if self._vorschau(offset) and self._vorschau(offset).isdigit():
                ist_kommazahl = True
                for _ in range(offset):
                    self._weiter()
                while self._aktuell() and self._aktuell().isdigit():
                    self._weiter()
        if ist_kommazahl:
            return Token(TokenTyp.KOMMAZAHL, float(self.quelltext[start:self.pos]), self.zeile)
        return Token(TokenTyp.GANZZAHL, int(self.quelltext[start:self.pos]), self.zeile)

    # --------------------------------------------------------------- Strings

    def _lese_string_inhalt(self, anf: str, dreifach: bool) -> list:
        """Liest String-Inhalt und gibt Teile zurück: [('text', str) | ('code', str)]."""
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
                    self._fehler("Nicht abgeschlossene Interpolation '{...}'")
                self._weiter()  # }
                teile.append(('code', ''.join(code).strip()))
                continue

            if c == '\n':
                self.zeile += 1
            aktueller_text.append(c)
            self._weiter()

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

            if c.isdigit():
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
                if self._vorschau() == '=':
                    self._weiter()
                    self.tokens.append(Token(TokenTyp.KLEINERGLEICH, '<=', self.zeile))
                else:
                    self.tokens.append(Token(TokenTyp.KLEINER, '<', self.zeile))
                self._weiter()
            elif c == '>':
                if self._vorschau() == '=':
                    self._weiter()
                    self.tokens.append(Token(TokenTyp.GROESSERGLEICH, '>=', self.zeile))
                else:
                    self.tokens.append(Token(TokenTyp.GROESSER, '>', self.zeile))
                self._weiter()
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
