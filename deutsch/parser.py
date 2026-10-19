# -*- coding: utf-8 -*-
import difflib

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

    def _fehler(self, msg: str):
        t = self._aktuell()
        raise SyntaxError(f'Zeile {t.zeile}: {msg} (gefunden: {t.typ.name!r})')

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
            self._fehler(f'{typ.name!r} erwartet')
        self.pos += 1
        return t

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
        # Optionaler Typ-Hinweis: sei x: Ganzzahl = ...
        typhinweis = None
        if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
            self.pos += 1
            typhinweis = self._verbrauche(TokenTyp.BEZEICHNER).wert
        self._verbrauche(TokenTyp.GLEICH)
        wert = self._ausdruck()
        return ast.VariableDeklaration(name, wert, typhinweis)

    def _konstante_deklaration(self):
        self._verbrauche(TokenTyp.KONSTANTE)
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        typhinweis = None
        if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
            self.pos += 1
            typhinweis = self._verbrauche(TokenTyp.BEZEICHNER).wert
        self._verbrauche(TokenTyp.GLEICH)
        wert = self._ausdruck()
        return ast.VariableDeklaration(name, wert, typhinweis, ist_konstante=True)

    def _destrukturierende_deklaration(self):
        self._verbrauche(TokenTyp.LECKIG)
        namen = [self._verbrauche(TokenTyp.BEZEICHNER).wert]
        while self._aktuell().typ == TokenTyp.KOMMA:
            self.pos += 1
            namen.append(self._verbrauche(TokenTyp.BEZEICHNER).wert)
        self._verbrauche(TokenTyp.RECKIG)
        self._verbrauche(TokenTyp.GLEICH)
        wert = self._ausdruck()
        return ast.DestrukturierendeDeklaration(namen, wert)

    def _parameter_lesen(self):
        """Gibt [(name, default_expr|None, is_variadic, typhinweis|None)] zurück."""
        params = []
        if self._aktuell().typ == TokenTyp.RPAREN:
            return params

        while True:
            variadic = False
            if self._aktuell().typ == TokenTyp.STERN:
                variadic = True
                self.pos += 1

            name = self._verbrauche(TokenTyp.BEZEICHNER).wert

            # Optionaler Typ-Hinweis: name: Typ
            typhinweis = None
            if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
                self.pos += 1
                typhinweis = self._verbrauche(TokenTyp.BEZEICHNER).wert

            default = None
            if self._aktuell().typ == TokenTyp.GLEICH:
                if variadic:
                    self._fehler('Variadische Parameter dürfen keinen Standardwert haben')
                self.pos += 1
                default = self._ausdruck()

            params.append((name, default, variadic, typhinweis))

            if variadic:
                # *args muss letzter Parameter sein; ein abschließendes Komma ist erlaubt
                if self._aktuell().typ == TokenTyp.KOMMA and self._vorschau().typ == TokenTyp.RPAREN:
                    self.pos += 1
                break

            if self._aktuell().typ != TokenTyp.KOMMA:
                break
            self.pos += 1
            if self._aktuell().typ == TokenTyp.RPAREN:
                break  # abschließendes Komma: funktion f(a, b,)

        return params

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
        parameter = self._in_klammern(self._parameter_lesen)

        # '->' leitet entweder einen Rückgabetyp ein ('-> Typ { … }') oder die Kurzform
        # ('-> ausdruck', gleichbedeutend mit '{ zurück ausdruck }').  Unterschied: ein Typname
        # steht direkt vor dem '{' des Rumpfs; ein Ausdruck wird nie von '{' gefolgt.
        typhinweis = None
        if self._aktuell().typ == TokenTyp.PFEIL:
            self.pos += 1
            if self._aktuell().typ == TokenTyp.BEZEICHNER and self._vorschau().typ == TokenTyp.LGESCHWEIFTE:
                typhinweis = self._verbrauche(TokenTyp.BEZEICHNER).wert
            else:
                return self._kurzform_rumpf(name, parameter)

        koerper = self._block()
        return ast.FunktionDefinition(name, parameter, koerper, typhinweis)

    def _kurzform_rumpf(self, name, parameter):
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
        return ast.FunktionDefinition(name, parameter, ast.Block([zurueck]), None)

    def _klassen_definition(self):
        self._verbrauche(TokenTyp.KLASSE)
        name = self._verbrauche(TokenTyp.BEZEICHNER).wert
        eltern = []
        if self._aktuell().typ == TokenTyp.LPAREN:
            self.pos += 1
            eltern.append(self._verbrauche(TokenTyp.BEZEICHNER).wert)
            while self._aktuell().typ == TokenTyp.KOMMA:
                self.pos += 1
                eltern.append(self._verbrauche(TokenTyp.BEZEICHNER).wert)
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
        if t.typ == TokenTyp.ZEICHENKETTE:
            gefunden = 'Zeichenkette'
        elif isinstance(t.wert, str):
            gefunden = t.wert
        else:
            gefunden = t.typ.name
        msg = (f"Im Klassenkörper nicht erlaubt: '{gefunden}' – erlaubt sind nur "
               f"'funktion', 'statisch funktion', 'sei' und 'konstante'")
        if t.typ == TokenTyp.BEZEICHNER:
            treffer = difflib.get_close_matches(
                gefunden, _KLASSENKOERPER_SCHLUESSELWOERTER, n=1, cutoff=0.6)
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
        """Liest 'name' oder '[name, name, ...]' (Destrukturierung) als Schleifenvariable."""
        if self._aktuell().typ == TokenTyp.LECKIG:
            self.pos += 1
            namen = [self._verbrauche(TokenTyp.BEZEICHNER).wert]
            while self._aktuell().typ == TokenTyp.KOMMA:
                self.pos += 1
                namen.append(self._verbrauche(TokenTyp.BEZEICHNER).wert)
            self._verbrauche(TokenTyp.RECKIG)
            return namen
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
        ausdruck = self._ausdruck()

        # Verbund-Zuweisung: x += 1, liste[i] -= 2, obj.attr *= 3
        if self._aktuell().typ in _VERBUND_OPS:
            op = _VERBUND_OPS[self._aktuell().typ]
            self.pos += 1
            wert = self._ausdruck()
            if not isinstance(ausdruck, (ast.Bezeichner, ast.AttributZugriff, ast.IndexZugriff)):
                self._fehler('Ungültige Verbund-Zuweisung')
            return ast.VerbundZuweisung(ausdruck, op, wert)

        # Normale Zuweisung: x = ..., obj.attr = ..., liste[i] = ...
        if self._aktuell().typ == TokenTyp.GLEICH:
            self.pos += 1
            wert = self._ausdruck()
            if isinstance(ausdruck, (ast.Bezeichner, ast.AttributZugriff, ast.IndexZugriff)):
                return ast.Zuweisung(ausdruck, wert)
            self._fehler('Ungültige Zuweisung')

        return ausdruck

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
        Positionale Argumente müssen vor Keyword-Argumenten stehen (wie in Python)."""
        args = []
        kwargs = []
        if self._aktuell().typ == TokenTyp.RPAREN:
            return args, kwargs
        while True:
            if self._aktuell().typ == TokenTyp.BEZEICHNER and self._vorschau().typ == TokenTyp.GLEICH:
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

        self._fehler(f'Unerwartetes Token {t.typ.name!r}')

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

    def _listen_literal(self):
        self._verbrauche(TokenTyp.LECKIG)
        self._ueberspringen_leerzeilen()

        if self._aktuell().typ == TokenTyp.RECKIG:
            self.pos += 1
            return ast.Liste([])

        erster = self._ausdruck()

        # List comprehension: [ausdruck für var in iterable wenn bed]
        if self._aktuell().typ == TokenTyp.FUER:
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
            elemente.append(self._ausdruck())
        self._ueberspringen_leerzeilen()
        self._verbrauche(TokenTyp.RECKIG)
        return ast.Liste(elemente)

    def _woerterbuch_literal(self):
        self._verbrauche(TokenTyp.LGESCHWEIFTE)
        self._ueberspringen_leerzeilen()
        if self._aktuell().typ == TokenTyp.RGESCHWEIFTE:
            self.pos += 1
            return ast.Woerterbuch([])  # {} ist ein leeres Wörterbuch (wie in Python)

        erster = self._ausdruck()

        if self._aktuell().typ == TokenTyp.DOPPELPUNKT:
            # Wörterbuch: {schlüssel: wert, ...}
            self.pos += 1
            v = self._ausdruck()
            paare = [(erster, v)]
            while self._aktuell().typ == TokenTyp.KOMMA:
                self.pos += 1
                self._ueberspringen_leerzeilen()
                if self._aktuell().typ == TokenTyp.RGESCHWEIFTE:
                    break
                k = self._ausdruck()
                self._verbrauche(TokenTyp.DOPPELPUNKT)
                v = self._ausdruck()
                paare.append((k, v))
            self._ueberspringen_leerzeilen()
            self._verbrauche(TokenTyp.RGESCHWEIFTE)
            return ast.Woerterbuch(paare)

        # Menge: {elem, elem, ...}
        elemente = [erster]
        while self._aktuell().typ == TokenTyp.KOMMA:
            self.pos += 1
            self._ueberspringen_leerzeilen()
            if self._aktuell().typ == TokenTyp.RGESCHWEIFTE:
                break
            elemente.append(self._ausdruck())
        self._ueberspringen_leerzeilen()
        self._verbrauche(TokenTyp.RGESCHWEIFTE)
        return ast.MengenLiteral(elemente)

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
