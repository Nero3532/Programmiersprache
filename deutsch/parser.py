# -*- coding: utf-8 -*-
import difflib

from .lexer import SCHLUESSELWOERTER
from .token_typen import TokenTyp
from . import ast_knoten as ast

# Was ein Klassenkörper einleiten darf (für die „meintest du …?"-Diagnose)
_KLASSENKOERPER_SCHLUESSELWOERTER = ['funktion', 'statisch', 'sei', 'konstante']

_VERBUND_OPS = {
    TokenTyp.PLUS_GLEICH:          '+',
    TokenTyp.MINUS_GLEICH:         '-',
    TokenTyp.STERN_GLEICH:         '*',
    TokenTyp.SCHRAEGSTRICH_GLEICH: '/',
    TokenTyp.PROZENT_GLEICH:       '%',
    TokenTyp.STERN_STERN_GLEICH:   '**',
    TokenTyp.SCHRAEGSTRICH_SCHRAEGSTRICH_GLEICH: '//',
    TokenTyp.KAUFMANNSUND_GLEICH:  '&',
    TokenTyp.SENKRECHT_GLEICH:     '|',
    TokenTyp.HUT_GLEICH:           '^',
    TokenTyp.KLEINER_KLEINER_GLEICH:   '<<',
    TokenTyp.GROESSER_GROESSER_GLEICH: '>>',
}

# Lesbare Namen der Token-Arten für Syntaxfehler: Symbole und Schlüsselwörter in Anführungszeichen,
# der Rest als Wort. Jede Token-Art hat einen Eintrag (ein Test prüft das).
_TOKEN_ANZEIGE = {
    TokenTyp.GANZZAHL: 'Zahl',
    TokenTyp.KOMMAZAHL: 'Zahl',
    TokenTyp.ZEICHENKETTE: 'Zeichenkette',
    TokenTyp.INTERP_ZEICHENKETTE: 'Zeichenkette',
    TokenTyp.BEZEICHNER: 'Name',
    TokenTyp.ZEILENENDE: 'Zeilenende',
    TokenTyp.DATEIENDE: 'Dateiende',
}
for _wort, _typ in SCHLUESSELWOERTER.items():  # bei 'für'/'fuer' und 'zurück'/'zurueck' gilt die erste Schreibweise
    _TOKEN_ANZEIGE.setdefault(_typ, f"'{_wort}'")
for _typ, _zeichen in {
    TokenTyp.PLUS: '+', TokenTyp.MINUS: '-', TokenTyp.STERN: '*', TokenTyp.SCHRAEGSTRICH: '/',
    TokenTyp.PROZENT: '%', TokenTyp.GLEICH: '=', TokenTyp.DOPPELGLEICH: '==', TokenTyp.UNGLEICH: '!=',
    TokenTyp.KLEINER: '<', TokenTyp.GROESSER: '>', TokenTyp.KLEINERGLEICH: '<=', TokenTyp.GROESSERGLEICH: '>=',
    TokenTyp.STERN_STERN: '**', TokenTyp.SCHRAEGSTRICH_SCHRAEGSTRICH: '//',
    TokenTyp.KAUFMANNSUND: '&', TokenTyp.SENKRECHT: '|', TokenTyp.HUT: '^', TokenTyp.TILDE: '~',
    TokenTyp.KLEINER_KLEINER: '<<', TokenTyp.GROESSER_GROESSER: '>>', TokenTyp.FRAGE_FRAGE: '??',
    TokenTyp.LPAREN: '(', TokenTyp.RPAREN: ')', TokenTyp.LGESCHWEIFTE: '{', TokenTyp.RGESCHWEIFTE: '}',
    TokenTyp.LECKIG: '[', TokenTyp.RECKIG: ']', TokenTyp.KOMMA: ',', TokenTyp.PUNKT: '.',
    TokenTyp.DOPPELPUNKT: ':', TokenTyp.SEMIKOLON: ';', TokenTyp.PFEIL: '->',
}.items():
    _TOKEN_ANZEIGE[_typ] = f"'{_zeichen}'"
for _typ, _zeichen in _VERBUND_OPS.items():
    _TOKEN_ANZEIGE[_typ] = f"'{_zeichen}='"
del _wort, _typ, _zeichen


def _art_anzeige(typ: TokenTyp) -> str:
    """Lesbarer Name einer erwarteten Token-Art: ')', 'sonst', Name, Zeilenende, Dateiende …"""
    return _TOKEN_ANZEIGE.get(typ, typ.name.lower())


def _token_anzeige(t) -> str:
    """Lesbare Anzeige eines gefundenen Tokens: sein Text in Anführungszeichen ('abc', '5', ')', 'fuer'),
    sonst die Art (Zeichenkette, Zeilenende, Dateiende)."""
    if t.typ in (TokenTyp.BEZEICHNER, TokenTyp.GANZZAHL, TokenTyp.KOMMAZAHL):
        return f"'{t.wert}'"
    if isinstance(t.wert, str) and t.typ not in (TokenTyp.ZEICHENKETTE, TokenTyp.ZEILENENDE):
        return f"'{t.wert}'"  # Symbol oder Schlüsselwort, so geschrieben wie im Code
    return _art_anzeige(t.typ)


def _format_spec_trennen(code: str):
    """Trennt 'ausdruck:formatspec' am ersten Top-Level-':'.

    Ignoriert ':' innerhalb von (), [], {} (Slices, Dict-/Mengen-Literale)
    und innerhalb von Anführungszeichen. Gibt (ausdruck_text, spec|None) zurück.
    """
    tiefe = 0
    anfuehrung = None
    for i, c in enumerate(code):
        if anfuehrung:
            if c == anfuehrung and (i == 0 or code[i - 1] != '\\'):
                anfuehrung = None
            continue
        if c in ('"', "'"):
            anfuehrung = c
        elif c in '([{':
            tiefe += 1
        elif c in ')]}':
            tiefe -= 1
        elif c == ':' and tiefe == 0:
            return code[:i].strip(), code[i + 1:].strip()
    return code.strip(), None


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        # Oberstes Element True: Zeilenumbrüche werden ignoriert (innerhalb von '( … )').
        # Ein '{ … }'-Block darin schaltet auf False zurück: dort trennen Zeilenumbrüche Anweisungen.
        self._umbrueche_ignorieren = [False]

    # ---------------------------------------------------------------- Hilfsm.

    def _fehler(self, msg: str, mit_gefunden: bool = True, zeile: int = None):
        """Wirft einen Syntaxfehler 'Zeile N: msg (gefunden: …)' für das aktuelle Token.
        mit_gefunden=False lässt die Angabe des gefundenen Tokens weg (wenn msg es schon nennt);
        zeile überschreibt die Zeile des aktuellen Tokens."""
        t = self._aktuell()
        gefunden = f' (gefunden: {_token_anzeige(t)})' if mit_gefunden else ''
        raise SyntaxError(f'Zeile {t.zeile if zeile is None else zeile}: {msg}{gefunden}')

    def _ueberspringe_umbrueche(self, p: int) -> int:
        while self.tokens[p].typ == TokenTyp.ZEILENENDE:  # letztes Token ist DATEIENDE
            p += 1
        return p

    def _aktuell(self):
        if self._umbrueche_ignorieren[-1]:
            self.pos = self._ueberspringe_umbrueche(self.pos)
        return self.tokens[self.pos]

    def _vorschau(self, offset: int = 1):
        if self._umbrueche_ignorieren[-1]:
            p = self._ueberspringe_umbrueche(self.pos)
            for _ in range(offset):
                if self.tokens[p].typ == TokenTyp.DATEIENDE:
                    break
                p = self._ueberspringe_umbrueche(p + 1)
            return self.tokens[p]
        p = self.pos + offset
        return self.tokens[min(p, len(self.tokens) - 1)]

    def _in_klammern(self, lesen):
        """Das '(' ist schon verbraucht: ruft lesen() auf und verbraucht danach ')'.
        Zeilenumbrüche dazwischen (auch nach ',' und vor ')') werden ignoriert."""
        self._umbrueche_ignorieren.append(True)
        ergebnis = lesen()
        self._verbrauche(TokenTyp.RPAREN)
        self._umbrueche_ignorieren.pop()
        return ergebnis

    def _verbrauche(self, typ: TokenTyp):
        t = self._aktuell()
        if t.typ != typ:
            self._fehler(f'{_art_anzeige(typ)} erwartet')
        self.pos += 1
        return t

    def _punktpfad_lesen(self) -> str:
        """Liest einen Namen oder Punktpfad 'modul.Klasse' (Typ-Hinweis, Basisklasse) als Text."""
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        while self._aktuell().typ == TokenTyp.PUNKT:
            self.pos += 1
            name += '.' + self._verbrauche(TokenTyp.BEZEICHNER).wert
        return name

    def _punktpfad_vor_block(self) -> bool:
        """True, wenn ab hier ein Name oder Punktpfad ('Typ', 'modul.Klasse') direkt vor einem '{' steht."""
        if self._aktuell().typ != TokenTyp.BEZEICHNER:
            return False
        offset = 1
        while self._vorschau(offset).typ == TokenTyp.PUNKT and self._vorschau(offset + 1).typ == TokenTyp.BEZEICHNER:
            offset += 2
        return self._vorschau(offset).typ == TokenTyp.LGESCHWEIFTE

    def _ueberspringen_leerzeilen(self):
        while self._aktuell().typ == TokenTyp.ZEILENENDE:
            self.pos += 1

    def _optionale_trennzeichen(self):
        while self._aktuell().typ in (TokenTyp.ZEILENENDE, TokenTyp.SEMIKOLON):
            self.pos += 1

    # ------------------------------------------------------------------ Parse

    def parse(self) -> ast.Programm:
        anweisungen = []
        self._ueberspringen_leerzeilen()
        while self._aktuell().typ != TokenTyp.DATEIENDE:
            anw = self._anweisung()
            if anw is not None:
                anweisungen.append(anw)
            self._optionale_trennzeichen()
        return ast.Programm(anweisungen)

    def _block(self) -> ast.Block:
        self._verbrauche(TokenTyp.LGESCHWEIFTE)
        # Im Block (auch in einer Klammer wie 'f(funktion() { … })') trennen Zeilenumbrüche Anweisungen
        self._umbrueche_ignorieren.append(False)
        self._ueberspringen_leerzeilen()
        anweisungen = []
        while self._aktuell().typ not in (TokenTyp.RGESCHWEIFTE, TokenTyp.DATEIENDE):
            anw = self._anweisung()
            if anw is not None:
                anweisungen.append(anw)
            self._optionale_trennzeichen()
        self._verbrauche(TokenTyp.RGESCHWEIFTE)
        self._umbrueche_ignorieren.pop()
        return ast.Block(anweisungen)

    def _anweisung(self):
        zeile = self._aktuell().zeile
        typ = self._aktuell().typ

        if typ == TokenTyp.ZEILENENDE:
            self.pos += 1
            return None

        if typ == TokenTyp.SEI:       anw = self._variable_deklaration()
        elif typ == TokenTyp.KONSTANTE: anw = self._konstante_deklaration()
        elif typ == TokenTyp.WENN:      anw = self._wenn_anweisung()
        elif typ == TokenTyp.SOLANGE:   anw = self._solange_anweisung()
        elif typ == TokenTyp.FUER:      anw = self._fuer_anweisung()
        elif typ == TokenTyp.FUNKTION:  anw = self._funktion_definition()
        elif typ == TokenTyp.KLASSE:    anw = self._klassen_definition()
        elif typ == TokenTyp.ZURUECK:   anw = self._zurueck_anweisung()
        elif typ == TokenTyp.VERSUCHE:  anw = self._versuche_anweisung()
        elif typ == TokenTyp.LADE:      anw = self._lade_anweisung()
        elif typ == TokenTyp.PASSE:     anw = self._passe_anweisung()
        elif typ == TokenTyp.WERFE:     anw = self._werfe_anweisung()
        elif typ == TokenTyp.PRUEFE:    anw = self._pruefe_anweisung()
        elif typ == TokenTyp.ABBRECHEN:
            self.pos += 1; anw = ast.AbbrechenAnweisung()
        elif typ == TokenTyp.WEITER:
            self.pos += 1; anw = ast.WeiterAnweisung()
        else:
            anw = self._ausdrucks_anweisung()

        anw.zeile = zeile
        return anw

    # ---------------------------------------------------------- Deklarationen

    def _variable_deklaration(self):
        self._verbrauche(TokenTyp.SEI)
        # Destrukturierung: sei [a, b, c] = ausdruck
        if self._aktuell().typ == TokenTyp.LECKIG:
            return self._destrukturierende_deklaration()
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        # Optionaler Typ-Hinweis: sei x: Ganzzahl = ...  (auch mit Punktpfad: sei k: modul.Klasse = ...)
        typhinweis = None
        if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
            self.pos += 1
            typhinweis = self._punktpfad_lesen()
        self._verbrauche(TokenTyp.GLEICH)
        wert = self._ausdruck()
        self._keine_kette_nach_deklaration('sei')
        return ast.VariableDeklaration(name, wert, typhinweis)

    def _keine_kette_nach_deklaration(self, wort: str):
        """'sei a = b = 0' gibt es nicht: ein zweites '=' nach dem Wert ist ein Syntaxfehler mit Hinweis."""
        if self._aktuell().typ == TokenTyp.GLEICH:
            self._fehler(f"Kettenzuweisung wie '{wort} a = b = 0' gibt es nicht – lege jede Variable "
                         f"einzeln mit '{wort}' an (z. B. '{wort} a = 0' und '{wort} b = 0')")

    def _konstante_deklaration(self):
        self._verbrauche(TokenTyp.KONSTANTE)
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        typhinweis = None
        if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
            self.pos += 1
            typhinweis = self._punktpfad_lesen()
        self._verbrauche(TokenTyp.GLEICH)
        wert = self._ausdruck()
        self._keine_kette_nach_deklaration('konstante')
        return ast.VariableDeklaration(name, wert, typhinweis, ist_konstante=True)

    def _destrukturierende_deklaration(self):
        muster = self._namensmuster_lesen()
        self._verbrauche(TokenTyp.GLEICH)
        wert = self._ausdruck()
        self._keine_kette_nach_deklaration('sei')
        return ast.DestrukturierendeDeklaration(muster, wert)

    def _namensmuster_lesen(self):
        """Liest ein Muster aus Namen '[a, *rest, [b, c]]' (das '[' steht noch) für 'sei' und 'für'.
        Höchstens ein '*'-Eintrag; Muster dürfen verschachtelt sein; ein abschließendes Komma ist erlaubt.
        Zeilenumbrüche innerhalb der Klammern werden ignoriert (auch in verschachtelten Mustern)."""
        self._verbrauche(TokenTyp.LECKIG)
        self._umbrueche_ignorieren.append(True)
        ziele = []
        rest = None
        while True:
            if self._aktuell().typ == TokenTyp.STERN:
                if rest is not None:
                    self._fehler("Ein Muster darf höchstens ein '*' (Rest) enthalten")
                self.pos += 1
                rest = len(ziele)
                ziele.append(self._verbrauche(TokenTyp.BEZEICHNER).wert)
            elif self._aktuell().typ == TokenTyp.LECKIG:
                ziele.append(self._namensmuster_lesen())
            else:
                ziele.append(self._verbrauche(TokenTyp.BEZEICHNER).wert)
            if self._aktuell().typ != TokenTyp.KOMMA:
                break
            self.pos += 1
            if self._aktuell().typ == TokenTyp.RECKIG:
                break  # abschließendes Komma: sei [a, b,] = …
        self._verbrauche(TokenTyp.RECKIG)
        self._umbrueche_ignorieren.pop()
        return ast.Muster(ziele, rest)

    def _parameter_lesen(self):
        """Gibt ([(name, default_expr|None, is_variadic, typhinweis|None), ...], kwargs_parameter|None) zurück.
        kwargs_parameter ist (name, typhinweis|None) des '**name'-Parameters (wie in Python: nur einer,
        als letzter Parameter, ohne Standardwert)."""
        params = []
        kwargs_parameter = None
        if self._aktuell().typ == TokenTyp.RPAREN:
            return params, kwargs_parameter

        while True:
            variadic = False
            doppelstern = False
            if self._aktuell().typ == TokenTyp.STERN_STERN:
                doppelstern = True
                self.pos += 1
            elif self._aktuell().typ == TokenTyp.STERN:
                variadic = True
                self.pos += 1

            name_token = self._verbrauche(TokenTyp.BEZEICHNER)
            name = name_token.wert
            if any(p[0] == name for p in params) or (kwargs_parameter and kwargs_parameter[0] == name):
                self._fehler(f"Der Parametername '{name}' ist doppelt vergeben",
                             mit_gefunden=False, zeile=name_token.zeile)

            # Optionaler Typ-Hinweis: name: Typ  (auch mit Punktpfad: name: modul.Klasse)
            typhinweis = None
            if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
                self.pos += 1
                typhinweis = self._punktpfad_lesen()

            default = None
            if self._aktuell().typ == TokenTyp.GLEICH:
                if variadic:
                    self._fehler('Variadische Parameter dürfen keinen Standardwert haben')
                if doppelstern:
                    self._fehler('Ein **-Parameter darf keinen Standardwert haben')
                self.pos += 1
                default = self._ausdruck()

            if doppelstern:
                kwargs_parameter = (name, typhinweis)
                # **name muss letzter Parameter sein; ein abschließendes Komma ist erlaubt
                if self._aktuell().typ == TokenTyp.KOMMA:
                    folgt_ende = self._vorschau().typ == TokenTyp.RPAREN
                    self.pos += 1
                    if not folgt_ende:
                        self._fehler('Ein **-Parameter muss der letzte Parameter sein (und es ist nur einer erlaubt)')
                break

            params.append((name, default, variadic, typhinweis))

            if variadic:
                # *args darf nur noch von **kwargs gefolgt werden; ein abschließendes Komma ist erlaubt
                if self._aktuell().typ == TokenTyp.KOMMA:
                    folgt = self._vorschau().typ
                    if folgt == TokenTyp.RPAREN:
                        self.pos += 1
                    elif folgt == TokenTyp.STERN_STERN:
                        self.pos += 1
                        continue
                    else:
                        self.pos += 1
                        self._fehler(f"Nach dem Rest-Parameter '*{name}' darf nur noch ein "
                                     f"'**name'-Parameter folgen")
                break

            if self._aktuell().typ != TokenTyp.KOMMA:
                break
            self.pos += 1
            if self._aktuell().typ == TokenTyp.RPAREN:
                break  # abschließendes Komma: funktion f(a, b,)

        return params, kwargs_parameter

    def _funktion_definition(self):
        # Anweisungsform — Name Pflicht
        self._verbrauche(TokenTyp.FUNKTION)
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        return self._funktion_rumpf(name)

    def _funktion_ausdruck(self):
        # Ausdrucksform (Lambda) — Name optional
        self._verbrauche(TokenTyp.FUNKTION)
        name = None
        if self._aktuell().typ == TokenTyp.BEZEICHNER:
            name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        return self._funktion_rumpf(name)

    def _funktion_rumpf(self, name):
        self._verbrauche(TokenTyp.LPAREN)
        parameter, kwargs_parameter = self._in_klammern(self._parameter_lesen)

        # '->' leitet entweder einen Rückgabetyp ein ('-> Typ { … }') oder die Kurzform
        # ('-> ausdruck', gleichbedeutend mit '{ zurück ausdruck }').  Unterschied: ein Typname
        # (auch Punktpfad 'modul.Klasse') steht direkt vor dem '{' des Rumpfs; ein Ausdruck wird
        # nie von '{' gefolgt.
        typhinweis = None
        if self._aktuell().typ == TokenTyp.PFEIL:
            self.pos += 1
            if self._punktpfad_vor_block():
                typhinweis = self._punktpfad_lesen()
            else:
                return self._kurzform_rumpf(name, parameter, kwargs_parameter)

        koerper = self._block()
        return ast.FunktionDefinition(name, parameter, koerper, typhinweis, kwargs_parameter)

    def _kurzform_rumpf(self, name, parameter, kwargs_parameter=None):
        """Rumpf der Kurzform 'funktion(x) -> ausdruck' (das '->' ist schon verbraucht).
        Der Ausdruck reicht so weit wie möglich (wie Pythons lambda) und endet erst an einem
        Token, das ihn nicht fortsetzt, z. B. ',' oder ')' eines umgebenden Aufrufs."""
        self._ueberspringen_leerzeilen()
        t = self._aktuell()
        if t.typ in (TokenTyp.DATEIENDE, TokenTyp.RPAREN, TokenTyp.RECKIG, TokenTyp.RGESCHWEIFTE,
                     TokenTyp.KOMMA, TokenTyp.SEMIKOLON):
            self._fehler("Nach '->' fehlt der Funktionsrumpf (ein Ausdruck, oder ein Rückgabetyp "
                         "vor '{ … }')")
        ausdruck = self._ausdruck()
        zurueck = ast.ZurueckAnweisung(ausdruck)
        zurueck.zeile = t.zeile
        return ast.FunktionDefinition(name, parameter, ast.Block([zurueck]), None, kwargs_parameter)

    def _klassen_definition(self):
        self._verbrauche(TokenTyp.KLASSE)
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        eltern = []
        if self._aktuell().typ == TokenTyp.LPAREN:
            self.pos += 1
            eltern.append(self._punktpfad_lesen())  # Name oder Punktpfad 'modul.Basis'
            while self._aktuell().typ == TokenTyp.KOMMA:
                self.pos += 1
                eltern.append(self._punktpfad_lesen())
            self._verbrauche(TokenTyp.RPAREN)
        self._verbrauche(TokenTyp.LGESCHWEIFTE)
        self._optionale_trennzeichen()
        methoden = []
        statische_methoden = []
        klassenattribute = []
        while self._aktuell().typ not in (TokenTyp.RGESCHWEIFTE, TokenTyp.DATEIENDE):
            if self._aktuell().typ == TokenTyp.FUNKTION:
                methoden.append(self._funktion_definition())
            elif self._aktuell().typ == TokenTyp.STATISCH:
                self.pos += 1
                statische_methoden.append(self._funktion_definition())
            elif self._aktuell().typ == TokenTyp.SEI:
                klassenattribute.append(self._variable_deklaration())
            elif self._aktuell().typ == TokenTyp.KONSTANTE:
                klassenattribute.append(self._konstante_deklaration())
            else:
                self._klassenkoerper_fehler()
            self._optionale_trennzeichen()
        self._verbrauche(TokenTyp.RGESCHWEIFTE)
        return ast.KlassenDefinition(name, eltern, methoden, statische_methoden, klassenattribute)

    def _klassenkoerper_fehler(self):
        """Meldet ein Token, das im Klassenkörper nicht erlaubt ist."""
        t = self._aktuell()
        msg = (f"Im Klassenkörper nicht erlaubt: {_token_anzeige(t)} – erlaubt sind nur "
               f"'funktion', 'statisch funktion', 'sei' und 'konstante'")
        if t.typ == TokenTyp.BEZEICHNER:
            treffer = difflib.get_close_matches(
                t.wert, _KLASSENKOERPER_SCHLUESSELWOERTER, n=1, cutoff=0.6)
            if treffer:
                msg += f" – meintest du '{treffer[0]}'?"
        raise SyntaxError(f'Zeile {t.zeile}: {msg}')

    # ------------------------------------------------------- Kontrollfluss

    def _wenn_anweisung(self):
        self._verbrauche(TokenTyp.WENN)
        bedingung = self._ausdruck()
        dann = self._block()
        sonst_wenn = []
        sonst = None
        self._ueberspringen_leerzeilen()
        while self._aktuell().typ == TokenTyp.SONST:
            self.pos += 1
            self._ueberspringen_leerzeilen()
            if self._aktuell().typ == TokenTyp.WENN:
                self.pos += 1
                sw_bed = self._ausdruck()
                sw_block = self._block()
                sonst_wenn.append((sw_bed, sw_block))
                self._ueberspringen_leerzeilen()
            else:
                sonst = self._block()
                break
        return ast.WennAnweisung(bedingung, dann, sonst_wenn, sonst)

    def _solange_anweisung(self):
        self._verbrauche(TokenTyp.SOLANGE)
        bedingung = self._ausdruck()
        koerper = self._block()
        return ast.SolangeAnweisung(bedingung, koerper)

    def _schleifenvariable_lesen(self):
        """Liest 'name' oder ein Destrukturierungs-Muster '[a, *rest, [b, c]]' als Schleifenvariable."""
        if self._aktuell().typ == TokenTyp.LECKIG:
            return self._namensmuster_lesen()
        return self._verbrauche(TokenTyp.BEZEICHNER).wert

    def _fuer_anweisung(self):
        self._verbrauche(TokenTyp.FUER)
        variable = self._schleifenvariable_lesen()
        self._verbrauche(TokenTyp.IN)
        iterable = self._ausdruck()
        koerper = self._block()
        return ast.FuerAnweisung(variable, iterable, koerper)

    def _zurueck_anweisung(self):
        self._verbrauche(TokenTyp.ZURUECK)
        if self._aktuell().typ in (
            TokenTyp.ZEILENENDE, TokenTyp.SEMIKOLON,
            TokenTyp.RGESCHWEIFTE, TokenTyp.DATEIENDE,
        ):
            return ast.ZurueckAnweisung(ast.Nichts())
        return ast.ZurueckAnweisung(self._ausdruck())

    def _werfe_anweisung(self):
        self._verbrauche(TokenTyp.WERFE)
        return ast.WerfeAnweisung(self._ausdruck())

    def _pruefe_anweisung(self):
        self._verbrauche(TokenTyp.PRUEFE)
        bedingung = self._ausdruck()
        meldung = None
        if self._aktuell().typ == TokenTyp.KOMMA:
            self.pos += 1
            meldung = self._ausdruck()
        return ast.PruefeAnweisung(bedingung, meldung)

    def _versuche_anweisung(self):
        self._verbrauche(TokenTyp.VERSUCHE)
        koerper = self._block()
        self._ueberspringen_leerzeilen()

        fange_typen = None
        fange_name = None
        fange_koerper = None
        endlich_koerper = None

        if self._aktuell().typ == TokenTyp.FANGE:
            self.pos += 1
            # optionaler Typ-Filter: fange (TypeError, ValueError) fehler { ... }
            if self._aktuell().typ == TokenTyp.LPAREN:
                self.pos += 1
                fange_typen = [self._verbrauche(TokenTyp.BEZEICHNER).wert]
                while self._aktuell().typ == TokenTyp.KOMMA:
                    self.pos += 1
                    fange_typen.append(self._verbrauche(TokenTyp.BEZEICHNER).wert)
                self._verbrauche(TokenTyp.RPAREN)
            # optionaler Variablenname: fange fehler { ... }
            if self._aktuell().typ == TokenTyp.BEZEICHNER:
                fange_name = self._aktuell().wert
                self.pos += 1
            fange_koerper = self._block()
            self._ueberspringen_leerzeilen()

        if self._aktuell().typ == TokenTyp.ENDLICH:
            self.pos += 1
            endlich_koerper = self._block()

        if fange_koerper is None and endlich_koerper is None:
            self._fehler("'versuche' braucht mindestens 'fange' oder 'endlich'")

        return ast.VersucheAnweisung(koerper, fange_typen, fange_name, fange_koerper, endlich_koerper)

    def _lade_anweisung(self):
        self._verbrauche(TokenTyp.LADE)
        pfad = self._ausdruck()
        als_name = None
        if self._aktuell().typ == TokenTyp.ALS:
            self.pos += 1
            als_name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        return ast.LadeAnweisung(pfad, als_name)

    def _passe_anweisung(self):
        self._verbrauche(TokenTyp.PASSE)
        ausdruck = self._ausdruck()
        self._verbrauche(TokenTyp.LGESCHWEIFTE)
        self._ueberspringen_leerzeilen()
        faelle, sonst = [], None
        while self._aktuell().typ not in (TokenTyp.RGESCHWEIFTE, TokenTyp.DATEIENDE):
            if self._aktuell().typ == TokenTyp.FALL:
                self.pos += 1
                werte = [self._ausdruck()]
                while self._aktuell().typ == TokenTyp.KOMMA:
                    self.pos += 1
                    werte.append(self._ausdruck())
                self._verbrauche(TokenTyp.DOPPELPUNKT)
                faelle.append((werte, self._block()))
            elif self._aktuell().typ == TokenTyp.SONST:
                self.pos += 1
                self._verbrauche(TokenTyp.DOPPELPUNKT)
                sonst = self._block()
            else:
                self._fehler("'fall' oder 'sonst' erwartet")
            self._ueberspringen_leerzeilen()
        self._verbrauche(TokenTyp.RGESCHWEIFTE)
        return ast.PasseAnweisung(ausdruck, faelle, sonst)

    # ------------------------------------------------------- Ausdr.-Anweis.

    def _ausdrucks_anweisung(self):
        zeile = self._aktuell().zeile
        ausdruck = self._ausdruck()

        # Verbund-Zuweisung: x += 1, liste[i] -= 2, obj.attr *= 3
        if self._aktuell().typ in _VERBUND_OPS:
            op = _VERBUND_OPS[self._aktuell().typ]
            self.pos += 1
            wert = self._ausdruck()
            if not isinstance(ausdruck, (ast.Bezeichner, ast.AttributZugriff, ast.IndexZugriff)):
                self._fehler('Ungültige Verbund-Zuweisung')
            return ast.VerbundZuweisung(ausdruck, op, wert)

        # Zuweisung: x = ..., obj.attr = ..., liste[i] = ..., [a, *r] = ..., Kette a = b = ...
        if self._aktuell().typ == TokenTyp.GLEICH:
            teile = [ausdruck]
            while self._aktuell().typ == TokenTyp.GLEICH:
                self.pos += 1
                teile.append(self._ausdruck())
            wert = teile.pop()
            ziele = [self._zuweisungsziel(z, zeile) for z in teile]
            if len(ziele) == 1:
                return ast.Zuweisung(ziele[0], wert)
            return ast.KettenZuweisung(ziele, wert)

        return ausdruck

    def _zuweisungsziel(self, knoten, zeile):
        """Prüft ein Zuweisungsziel; eine Listen-Schreibweise '[a, b]' wird zum Muster.
        zeile: Zeile, in der die Anweisung beginnt (für die Fehlermeldung)."""
        if isinstance(knoten, (ast.Bezeichner, ast.AttributZugriff, ast.IndexZugriff)):
            return knoten
        if isinstance(knoten, ast.Liste):
            return self._muster_aus_liste(knoten, zeile)
        self._fehler('Ungültige Zuweisung')

    @staticmethod
    def _muster_aus_liste(liste, zeile):
        """Wandelt die als Liste geparste linke Seite '[a, *rest, [b, c]]' in ein Muster um."""
        def fehler(msg):
            raise SyntaxError(f'Zeile {zeile}: Ungültige Zuweisung: {msg}')

        einfach = (ast.Bezeichner, ast.AttributZugriff, ast.IndexZugriff)
        ziele = []
        rest = None
        for element in liste.elemente:
            if isinstance(element, ast.Entpacken):
                if rest is not None:
                    fehler("Ein Muster darf höchstens ein '*' (Rest) enthalten")
                if not isinstance(element.ausdruck, einfach):
                    fehler("Hinter '*' muss ein Name, Attribut oder Index stehen")
                rest = len(ziele)
                ziele.append(element.ausdruck)
            elif isinstance(element, ast.Liste):
                ziele.append(Parser._muster_aus_liste(element, zeile))
            elif isinstance(element, einfach):
                ziele.append(element)
            else:
                fehler('Im Muster sind nur Namen, Attribute, Indizes und verschachtelte Listen erlaubt')
        if not ziele:
            fehler('Das Muster ist leer')
        return ast.Muster(ziele, rest)

    # ---------------------------------------------------------------- Ausdr.

    def _ausdruck(self):
        ausdruck = self._koaleszenz()
        # Ternär: dann_wert wenn bedingung sonst sonst_wert
        if self._aktuell().typ == TokenTyp.WENN:
            self.pos += 1
            bedingung = self._koaleszenz()
            self._verbrauche(TokenTyp.SONST)
            sonst_wert = self._ausdruck()  # rechtsassoziativ, erlaubt Verkettung
            return ast.TernaerAusdruck(ausdruck, bedingung, sonst_wert)
        return ausdruck

    def _koaleszenz(self):
        # a ?? b: schwächer als 'oder', stärker als der Ternär-Ausdruck
        links = self._oder()
        while self._aktuell().typ == TokenTyp.FRAGE_FRAGE:
            self.pos += 1
            rechts = self._oder()
            links = ast.BinaereOperation(links, '??', rechts)
        return links

    def _oder(self):
        links = self._und()
        while self._aktuell().typ == TokenTyp.ODER:
            self.pos += 1
            rechts = self._und()
            links = ast.BinaereOperation(links, 'oder', rechts)
        return links

    def _und(self):
        links = self._nicht()
        while self._aktuell().typ == TokenTyp.UND:
            self.pos += 1
            rechts = self._nicht()
            links = ast.BinaereOperation(links, 'und', rechts)
        return links

    def _nicht(self):
        # Vorrang wie in Python: 'nicht' bindet schwächer als Vergleiche und
        # 'in'/'nicht in', aber stärker als 'und'.  'nicht 1 == 2' = 'nicht (1 == 2)'
        if self._aktuell().typ == TokenTyp.NICHT:
            self.pos += 1
            return ast.UnaereOperation('nicht', self._nicht())
        return self._vergleich()

    def _vergleich(self):
        operanden = [self._bit_oder()]
        operatoren = []
        ops = {
            TokenTyp.DOPPELGLEICH:   '==',
            TokenTyp.UNGLEICH:       '!=',
            TokenTyp.KLEINER:        '<',
            TokenTyp.GROESSER:       '>',
            TokenTyp.KLEINERGLEICH:  '<=',
            TokenTyp.GROESSERGLEICH: '>=',
            TokenTyp.IN:             'in',
        }
        while True:
            # 'x nicht in y' – infix, unterscheidet sich vom Präfix 'nicht (x in y)'
            if self._aktuell().typ == TokenTyp.NICHT and self._vorschau().typ == TokenTyp.IN:
                self.pos += 1
                self._verbrauche(TokenTyp.IN)  # (in Klammern kann ein Zeilenumbruch dazwischen stehen)
                operatoren.append('nicht in')
                operanden.append(self._bit_oder())
                continue
            if self._aktuell().typ in ops:
                operatoren.append(ops[self._aktuell().typ])
                self.pos += 1
                operanden.append(self._bit_oder())
                continue
            break
        if not operatoren:
            return operanden[0]
        if len(operatoren) == 1:
            return ast.BinaereOperation(operanden[0], operatoren[0], operanden[1])
        # Verkettung: a < b < c  ==  (a<b) und (b<c), jeder Operand nur einmal ausgewertet
        return ast.VergleichsKette(operanden, operatoren)

    # Vorrang wie in Python: '|' < '^' < '&' < '<<' '>>' < '+' '-'
    def _bit_oder(self):
        links = self._bit_xoder()
        while self._aktuell().typ == TokenTyp.SENKRECHT:
            self.pos += 1
            rechts = self._bit_xoder()
            links = ast.BinaereOperation(links, '|', rechts)
        return links

    def _bit_xoder(self):
        links = self._bit_und()
        while self._aktuell().typ == TokenTyp.HUT:
            self.pos += 1
            rechts = self._bit_und()
            links = ast.BinaereOperation(links, '^', rechts)
        return links

    def _bit_und(self):
        links = self._schiebung()
        while self._aktuell().typ == TokenTyp.KAUFMANNSUND:
            self.pos += 1
            rechts = self._schiebung()
            links = ast.BinaereOperation(links, '&', rechts)
        return links

    def _schiebung(self):
        links = self._addition()
        while self._aktuell().typ in (TokenTyp.KLEINER_KLEINER, TokenTyp.GROESSER_GROESSER):
            op = self._aktuell().wert
            self.pos += 1
            rechts = self._addition()
            links = ast.BinaereOperation(links, op, rechts)
        return links

    def _addition(self):
        links = self._multiplikation()
        while self._aktuell().typ in (TokenTyp.PLUS, TokenTyp.MINUS):
            op = self._aktuell().wert
            self.pos += 1
            rechts = self._multiplikation()
            links = ast.BinaereOperation(links, op, rechts)
        return links

    def _multiplikation(self):
        links = self._unaer()
        while self._aktuell().typ in (TokenTyp.STERN, TokenTyp.SCHRAEGSTRICH,
                                       TokenTyp.SCHRAEGSTRICH_SCHRAEGSTRICH, TokenTyp.PROZENT):
            op = self._aktuell().wert
            self.pos += 1
            rechts = self._unaer()
            links = ast.BinaereOperation(links, op, rechts)
        return links

    def _unaer(self):
        if self._aktuell().typ in (TokenTyp.MINUS, TokenTyp.TILDE):
            op = self._aktuell().wert
            self.pos += 1
            return ast.UnaereOperation(op, self._unaer())
        return self._potenz()

    def _potenz(self):
        links = self._aufruf()
        if self._aktuell().typ == TokenTyp.STERN_STERN:
            self.pos += 1
            rechts = self._unaer()   # rechtsassoziativ, erlaubt 2**-1
            return ast.BinaereOperation(links, '**', rechts)
        return links

    def _argumente_lesen(self):
        """Liest Aufruf-Argumente. Gibt (positionale_args, [(name, wert), ...]) zurück.
        Positionale Argumente (auch '*liste', als ast.Entpacken) müssen vor Keyword-Argumenten stehen;
        '**woerterbuch' steht unter den Keyword-Argumenten als (None, ausdruck)."""
        args = []
        kwargs = []
        if self._aktuell().typ == TokenTyp.RPAREN:
            return args, kwargs
        while True:
            if self._aktuell().typ == TokenTyp.STERN_STERN:
                self.pos += 1
                kwargs.append((None, self._ausdruck()))
            elif self._aktuell().typ == TokenTyp.STERN:
                if kwargs:
                    self._fehler("Entpackte Argumente ('*') müssen vor Keyword-Argumenten stehen")
                self.pos += 1
                args.append(ast.Entpacken(self._ausdruck()))
            elif self._aktuell().typ == TokenTyp.BEZEICHNER and self._vorschau().typ == TokenTyp.GLEICH:
                name = self._aktuell().wert
                if any(n == name for n, _ in kwargs):
                    self._fehler(f"Keyword-Argument '{name}' mehrfach angegeben")
                self.pos += 1
                self._verbrauche(TokenTyp.GLEICH)  # (in Klammern kann ein Zeilenumbruch dazwischen stehen)
                kwargs.append((name, self._ausdruck()))
            else:
                if kwargs:
                    self._fehler('Positionale Argumente müssen vor Keyword-Argumenten stehen')
                args.append(self._ausdruck())
            if self._aktuell().typ != TokenTyp.KOMMA:
                break
            self.pos += 1
            if self._aktuell().typ == TokenTyp.RPAREN:
                break  # abschließendes Komma: f(a, b,)
        return args, kwargs

    def _aufruf(self):
        knoten = self._primaer()
        while True:
            if self._aktuell().typ == TokenTyp.LPAREN:
                self.pos += 1
                args, kwargs = self._in_klammern(self._argumente_lesen)
                knoten = ast.FunktionAufruf(knoten, args, kwargs)
            elif self._aktuell().typ == TokenTyp.PUNKT:
                self.pos += 1
                attr = self._verbrauche(TokenTyp.BEZEICHNER).wert
                knoten = ast.AttributZugriff(knoten, attr)
            elif self._aktuell().typ == TokenTyp.LECKIG:
                self.pos += 1
                idx = self._index_oder_slice()
                self._verbrauche(TokenTyp.RECKIG)
                knoten = ast.IndexZugriff(knoten, idx)
            else:
                break
        return knoten

    def _index_oder_slice(self):
        start = None
        if self._aktuell().typ != TokenTyp.DOPPELPUNKT:
            start = self._ausdruck()
        if self._aktuell().typ != TokenTyp.DOPPELPUNKT:
            return start
        self.pos += 1
        stop = None
        if self._aktuell().typ not in (TokenTyp.RECKIG, TokenTyp.DOPPELPUNKT):
            stop = self._ausdruck()
        step = None
        if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
            self.pos += 1
            if self._aktuell().typ != TokenTyp.RECKIG:
                step = self._ausdruck()
        return ast.SliceAusdruck(start, stop, step)

    def _primaer(self):
        t = self._aktuell()

        if t.typ == TokenTyp.GANZZAHL:
            self.pos += 1; return ast.Ganzzahl(t.wert)
        if t.typ == TokenTyp.KOMMAZAHL:
            self.pos += 1; return ast.Kommazahl(t.wert)
        if t.typ == TokenTyp.ZEICHENKETTE:
            self.pos += 1; return ast.Zeichenkette(t.wert)
        if t.typ == TokenTyp.INTERP_ZEICHENKETTE:
            return self._interp_zeichenkette(t)
        if t.typ == TokenTyp.WAHR:
            self.pos += 1; return ast.Wahrheitswert(True)
        if t.typ == TokenTyp.FALSCH:
            self.pos += 1; return ast.Wahrheitswert(False)
        if t.typ == TokenTyp.NICHTS:
            self.pos += 1; return ast.Nichts()
        if t.typ == TokenTyp.BEZEICHNER:
            self.pos += 1; return ast.Bezeichner(t.wert)
        if t.typ == TokenTyp.LPAREN:
            self.pos += 1
            return self._in_klammern(self._ausdruck)
        if t.typ == TokenTyp.LECKIG:
            return self._listen_literal()
        if t.typ == TokenTyp.LGESCHWEIFTE:
            return self._woerterbuch_literal()
        if t.typ == TokenTyp.NEU:
            return self._neu_instanz()
        if t.typ == TokenTyp.FUNKTION:
            return self._funktion_ausdruck()

        if t.typ == TokenTyp.NICHT:
            # 'nicht' steht über den Vergleichen (wie in Python) und darf daher
            # nicht direkt als Operand eines Operators stehen: 'a == nicht b'
            self._fehler("'nicht' ist als Operand nicht erlaubt – setze Klammern, "
                         "z. B. 'a == (nicht b)'")

        self._fehler('Ausdruck erwartet')

    def _interp_zeichenkette(self, token):
        """Parst eine interpolierte Zeichenkette – Sub-Parser für Code-Teile."""
        from .lexer import Lexer  # lokaler Import – kein zirkulärer Import
        self.pos += 1
        teile = []
        for teil in token.wert:
            art, inhalt = teil[0], teil[1]
            if art == 'text':
                if inhalt:
                    teile.append(ast.Zeichenkette(inhalt))
            else:
                ausdruck_text, format_spec = _format_spec_trennen(inhalt)
                # Teilausdruck mit absoluter Zeilennummer lexen (Fehler nennen die echte Zeile)
                sub_tokens = Lexer(ausdruck_text, start_zeile=teil[2]).tokenisieren()
                sub_parser = Parser(sub_tokens)
                ausdruck = sub_parser._ausdruck()
                sub_parser._interpolation_ende_pruefen(inhalt)
                if format_spec is not None:
                    ausdruck = ast.FormatierterAusdruck(ausdruck, format_spec)
                teile.append(ausdruck)
        if not teile:
            return ast.Zeichenkette('')
        if len(teile) == 1 and isinstance(teile[0], ast.Zeichenkette):
            return teile[0]
        return ast.InterpolierteZeichenkette(teile)

    def _interpolation_ende_pruefen(self, inhalt: str):
        """Sub-Parser einer '{…}'-Interpolation: nach dem Ausdruck darf nichts mehr folgen
        ('{1 2}' ist ein Syntaxfehler, kein stilles Ignorieren des Rests)."""
        self._ueberspringen_leerzeilen()
        t = self._aktuell()
        if t.typ == TokenTyp.DATEIENDE:
            return
        if t.typ in (TokenTyp.ZEICHENKETTE, TokenTyp.INTERP_ZEICHENKETTE):
            gefunden = 'Zeichenkette'
        elif isinstance(t.wert, bool):
            gefunden = 'wahr' if t.wert else 'falsch'
        elif t.wert is None:
            gefunden = t.typ.name.lower()
        else:
            gefunden = str(t.wert)
        raise SyntaxError(
            f"Zeile {t.zeile}: Ungültiger Ausdruck in der Interpolation '{{{inhalt.strip()}}}': "
            f"nach dem Ausdruck folgt unerwartet '{gefunden}'"
        )

    def _listen_element(self):
        """Ein Listenelement: ein Ausdruck oder '*ausdruck' (Entpacken)."""
        if self._aktuell().typ == TokenTyp.STERN:
            self.pos += 1
            return ast.Entpacken(self._ausdruck())
        return self._ausdruck()

    def _listen_literal(self):
        self._verbrauche(TokenTyp.LECKIG)
        self._ueberspringen_leerzeilen()

        if self._aktuell().typ == TokenTyp.RECKIG:
            self.pos += 1
            return ast.Liste([])

        erster = self._listen_element()

        # List comprehension: [ausdruck für var in iterable wenn bed]
        if self._aktuell().typ == TokenTyp.FUER:
            if isinstance(erster, ast.Entpacken):
                self._fehler("Entpacken mit '*' ist in einer Listen-Comprehension nicht möglich")
            self.pos += 1
            variable = self._schleifenvariable_lesen()
            self._verbrauche(TokenTyp.IN)
            # _koaleszenz() statt _ausdruck(): verhindert, dass das nachfolgende
            # 'wenn'-Filter der Comprehension als Ternär-Beginn gelesen wird
            iterable = self._koaleszenz()
            bedingung = None
            if self._aktuell().typ == TokenTyp.WENN:
                self.pos += 1
                bedingung = self._ausdruck()
            self._ueberspringen_leerzeilen()
            self._verbrauche(TokenTyp.RECKIG)
            return ast.ListenAusdruck(erster, variable, iterable, bedingung)

        # Normale Liste
        elemente = [erster]
        while self._aktuell().typ == TokenTyp.KOMMA:
            self.pos += 1
            self._ueberspringen_leerzeilen()
            if self._aktuell().typ == TokenTyp.RECKIG:
                break
            elemente.append(self._listen_element())
        self._ueberspringen_leerzeilen()
        self._verbrauche(TokenTyp.RECKIG)
        return ast.Liste(elemente)

    def _geschweifter_eintrag(self):
        """Ein Eintrag in '{ … }': ('wb_entpacken', ausdruck) für '**x', ('m_entpacken', ausdruck) für '*x',
        ('paar', schluessel, wert) für 'k: v' oder ('element', ausdruck)."""
        if self._aktuell().typ == TokenTyp.STERN_STERN:
            self.pos += 1
            return ('wb_entpacken', self._ausdruck())
        if self._aktuell().typ == TokenTyp.STERN:
            self.pos += 1
            return ('m_entpacken', self._ausdruck())
        schluessel = self._ausdruck()
        if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
            self.pos += 1
            return ('paar', schluessel, self._ausdruck())
        return ('element', schluessel)

    def _woerterbuch_literal(self):
        self._verbrauche(TokenTyp.LGESCHWEIFTE)
        self._ueberspringen_leerzeilen()
        if self._aktuell().typ == TokenTyp.RGESCHWEIFTE:
            self.pos += 1
            return ast.Woerterbuch([])  # {} ist ein leeres Wörterbuch (wie in Python)

        # Der erste Eintrag bestimmt die Art: {k: v, **x} Wörterbuch, {a, b, *x} Menge
        eintraege = [self._geschweifter_eintrag()]
        ist_woerterbuch = eintraege[0][0] in ('paar', 'wb_entpacken')
        while self._aktuell().typ == TokenTyp.KOMMA:
            self.pos += 1
            self._ueberspringen_leerzeilen()
            if self._aktuell().typ == TokenTyp.RGESCHWEIFTE:
                break
            eintrag = self._geschweifter_eintrag()
            if (eintrag[0] in ('paar', 'wb_entpacken')) != ist_woerterbuch:
                if ist_woerterbuch:
                    self._fehler("In einem Wörterbuch sind nur 'schlüssel: wert' und '**ausdruck' erlaubt")
                self._fehler("In einer Menge sind nur einzelne Elemente und '*ausdruck' erlaubt")
            eintraege.append(eintrag)
        self._ueberspringen_leerzeilen()
        self._verbrauche(TokenTyp.RGESCHWEIFTE)

        if ist_woerterbuch:
            # '**x' steht als (None, x) zwischen den Paaren
            return ast.Woerterbuch([(None, e[1]) if e[0] == 'wb_entpacken' else (e[1], e[2]) for e in eintraege])
        return ast.MengenLiteral([ast.Entpacken(e[1]) if e[0] == 'm_entpacken' else e[1] for e in eintraege])

    def _neu_instanz(self):
        self._verbrauche(TokenTyp.NEU)
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        klasse = ast.Bezeichner(name)
        # Punktpfad: neu modul.Klasse(...) bzw. neu a.b.Klasse(...)
        while self._aktuell().typ == TokenTyp.PUNKT:
            self.pos += 1
            teil = self._verbrauche(TokenTyp.BEZEICHNER).wert
            name += '.' + teil
            klasse = ast.AttributZugriff(klasse, teil)
        self._verbrauche(TokenTyp.LPAREN)
        args, kwargs = self._in_klammern(self._argumente_lesen)
        return ast.NeuInstanz(name, args, kwargs, klasse)
