# -*- coding: utf-8 -*-
"""
Bytecode-Compiler und Stapelmaschine für Funktionskörper.

Warum: der Baum-Interpreter schlägt für jeden Knoten eine Besuchermethode nach und
sucht jede Variable über eine Kette von Wörterbüchern. Beides fällt hier weg – der
Compiler löst lokale Variablen einmalig in Steckplätze auf, und die Maschine läuft
eine flache Befehlsliste ab.

Was er nicht kann, kompiliert er nicht: `_kompilierbar` prüft den Körper vorher, und
alles Übrige läuft unverändert über den Baum-Interpreter. Dadurch kann die Maschine
die Sprache nicht halb unterstützen – entweder ganz oder gar nicht je Funktion.

Die Laufzeit selbst (Operatoren, Aufrufe, Attributzugriff, Fehlermeldungen) stammt
weiterhin aus dem Interpreter; ersetzt wird nur die Ablaufsteuerung.
"""
from . import ast_knoten as ast

# ------------------------------------------------------------------ Befehle
(
    LADE_KONST, LADE_LOKAL, SETZE_LOKAL, LADE_NAME, SETZE_NAME, DEKLARIERE_NAME,
    BINAER, UNAER_MINUS, NICHT, VERGLEICHSKETTE,
    SPRUNG, SPRUNG_FALSCH, SPRUNG_FALSCH_BEHALTE, SPRUNG_WAHR_BEHALTE,
    AUFRUF, AUFRUF_KW, NEU_INSTANZ, RUECKGABE, WERFE, PRUEFE,
    BAUE_LISTE, BAUE_WOERTERBUCH, BAUE_MENGE, BAUE_TEXT, FORMATIERE, BAUE_SCHNITT,
    ATTRIBUT, SETZE_ATTRIBUT, INDEX, SETZE_INDEX,
    ITERATOR, NAECHSTES, ENTPACKE, ENTPACKE_ARG,
    POP, DUPLIZIERE, DUPLIZIERE2, TYP_PRUEFEN,
    AUFRUF_ENTPACKT, NEU_ENTPACKT,
) = range(40)

# Anweisungen und Ausdrücke, die die Maschine (noch) nicht kennt. Kommt eine davon
# im Körper vor, bleibt die Funktion beim Baum-Interpreter.
_NICHT_KOMPILIERBAR = (
    ast.FunktionDefinition,      # verschachtelte Funktion: bräuchte echte Closures
    ast.KlassenDefinition,
    ast.VersucheAnweisung,
    ast.PasseAnweisung,
    ast.ErgibtAnweisung,
    ast.LadeAnweisung,
    ast.ListenAusdruck,
    ast.MengenAusdruck,
    ast.WoerterbuchAusdruck,
)


class Codeobjekt:
    """Übersetzter Funktionskörper."""
    __slots__ = ('name', 'befehle', 'konstanten', 'namen', 'anzahl_lokale', 'zeilen')

    def __init__(self, name, befehle, konstanten, namen, anzahl_lokale, zeilen):
        self.name = name
        self.befehle = befehle          # flache Liste [befehl, argument, befehl, ...]
        self.konstanten = konstanten
        self.namen = namen
        self.anzahl_lokale = anzahl_lokale
        self.zeilen = zeilen            # Befehlsindex -> Quellzeile

    def __repr__(self):
        return f'<Code {self.name}, {len(self.befehle) // 2} Befehle>'


class _NichtUebersetzbar(Exception):
    """Wird intern geworfen, wenn der Körper doch nicht übersetzt werden kann."""


def kompilierbar(definition) -> bool:
    """Enthält der Körper nur Konstrukte, die die Maschine beherrscht?"""
    return _pruefe_knoten(definition.koerper) and not definition.ist_generator


def _pruefe_knoten(knoten) -> bool:
    if isinstance(knoten, _NICHT_KOMPILIERBAR):
        return False
    # 'konstante' im Funktionskörper: die Umgebung schützt sie, ein Steckplatz nicht
    if isinstance(knoten, ast.VariableDeklaration) and knoten.ist_konstante:
        return False
    for feld in getattr(type(knoten), '__slots__', ()):
        wert = getattr(knoten, feld, None)
        if isinstance(wert, ast.Knoten):
            if not _pruefe_knoten(wert):
                return False
        elif isinstance(wert, (list, tuple)):
            for eintrag in wert:
                if isinstance(eintrag, ast.Knoten):
                    if not _pruefe_knoten(eintrag):
                        return False
                elif isinstance(eintrag, (list, tuple)):
                    for tiefer in eintrag:
                        if isinstance(tiefer, ast.Knoten) and not _pruefe_knoten(tiefer):
                            return False
    return True


# ------------------------------------------------------------------ Compiler

class Kompilierer:
    """Übersetzt einen Funktionskörper in ein Codeobjekt."""

    def __init__(self, definition):
        self.definition = definition
        self.befehle: list[int] = []
        self.konstanten: list = []
        self._konst_index: dict = {}
        self.namen: list[str] = []
        self._namen_index: dict = {}
        self.zeilen: dict[int, int] = {}
        self.zeile = 0
        # Steckplätze: Kette von Blöcken, damit 'sei' in einem Block schattet
        self._bloecke: list[dict] = [{}]
        self.anzahl_lokale = 0
        self._schleifen: list[dict] = []

    # ------------------------------------------------------------- Bausteine

    def _aus(self, befehl: int, argument: int = 0):
        self.zeilen[len(self.befehle) // 2] = self.zeile
        self.befehle.append(befehl)
        self.befehle.append(argument)
        return len(self.befehle) - 2

    def _konstante(self, wert) -> int:
        schluessel = (type(wert).__name__, wert if isinstance(wert, (int, float, str, bool)) else id(wert))
        if schluessel not in self._konst_index:
            self._konst_index[schluessel] = len(self.konstanten)
            self.konstanten.append(wert)
        return self._konst_index[schluessel]

    def _name(self, name: str) -> int:
        if name not in self._namen_index:
            self._namen_index[name] = len(self.namen)
            self.namen.append(name)
        return self._namen_index[name]

    def _neuer_platz(self, name: str) -> int:
        platz = self.anzahl_lokale
        self.anzahl_lokale += 1
        self._bloecke[-1][name] = platz
        return platz

    def _platz(self, name: str):
        for block in reversed(self._bloecke):
            if name in block:
                return block[name]
        return None

    def _ziel(self, stelle: int):
        """Setzt das Sprungziel eines zuvor ausgegebenen Sprungs auf das Ende."""
        self.befehle[stelle + 1] = len(self.befehle) // 2

    # ------------------------------------------------------------- Einstieg

    def kompiliere(self) -> Codeobjekt:
        for name, _standard, _variadisch, _typ in self.definition.parameter:
            self._neuer_platz(name)
        self._anweisungen(self.definition.koerper.anweisungen)
        self._aus(LADE_KONST, self._konstante(None))
        self._aus(RUECKGABE)
        return Codeobjekt(self.definition.name or '<anonym>', self.befehle, self.konstanten,
                          self.namen, self.anzahl_lokale, self.zeilen)

    def _anweisungen(self, anweisungen):
        for anweisung in anweisungen:
            self._anweisung(anweisung)

    # ----------------------------------------------------------- Anweisungen

    def _anweisung(self, knoten):
        zeile = getattr(knoten, 'zeile', None)
        if zeile:
            self.zeile = zeile
        typ = type(knoten)

        if typ is ast.Block:
            self._bloecke.append({})
            self._anweisungen(knoten.anweisungen)
            self._bloecke.pop()

        elif typ is ast.VariableDeklaration:
            self._ausdruck(knoten.wert)
            if knoten.typhinweis:
                self._aus(TYP_PRUEFEN, self._konstante((knoten.typhinweis, knoten.name)))
            if knoten.ist_konstante:
                # Konstanten liegen in der Umgebung, damit weise_zu sie schützt
                self._aus(DEKLARIERE_NAME, self._name(knoten.name))
            else:
                self._aus(SETZE_LOKAL, self._neuer_platz(knoten.name))

        elif typ is ast.DestrukturierendeDeklaration:
            self._ausdruck(knoten.wert)
            self._aus(ENTPACKE, len(knoten.namen))
            for name in knoten.namen:
                self._aus(SETZE_LOKAL, self._neuer_platz(name))

        elif typ is ast.Zuweisung:
            self._zuweisung(knoten.ziel, knoten.wert)

        elif typ is ast.VerbundZuweisung:
            self._verbund(knoten)

        elif typ is ast.WennAnweisung:
            self._wenn(knoten)

        elif typ is ast.SolangeAnweisung:
            self._solange(knoten)

        elif typ is ast.FuerAnweisung:
            self._fuer(knoten)

        elif typ is ast.ZurueckAnweisung:
            self._ausdruck(knoten.wert)
            self._aus(RUECKGABE)

        elif typ is ast.AbbrechenAnweisung:
            if not self._schleifen:
                raise _NichtUebersetzbar()
            self._schleifen[-1]['abbrechen'].append(self._aus(SPRUNG))

        elif typ is ast.WeiterAnweisung:
            if not self._schleifen:
                raise _NichtUebersetzbar()
            self._schleifen[-1]['weiter'].append(self._aus(SPRUNG))

        elif typ is ast.WerfeAnweisung:
            self._ausdruck(knoten.wert)
            self._aus(WERFE)

        elif typ is ast.PruefeAnweisung:
            self._ausdruck(knoten.bedingung)
            if knoten.meldung is not None:
                self._ausdruck(knoten.meldung)
                self._aus(PRUEFE, 1)
            else:
                self._aus(PRUEFE, 0)

        else:
            self._ausdruck(knoten)
            self._aus(POP)

    def _zuweisung(self, ziel, wert):
        if isinstance(ziel, ast.Bezeichner):
            self._ausdruck(wert)
            platz = self._platz(ziel.name)
            if platz is None:
                self._aus(SETZE_NAME, self._name(ziel.name))
            else:
                self._aus(SETZE_LOKAL, platz)
        elif isinstance(ziel, ast.AttributZugriff):
            self._ausdruck(ziel.objekt)
            self._ausdruck(wert)
            self._aus(SETZE_ATTRIBUT, self._name(ziel.attribut))
        elif isinstance(ziel, ast.IndexZugriff):
            self._ausdruck(ziel.objekt)
            self._index_ausdruck(ziel.index)
            self._ausdruck(wert)
            self._aus(SETZE_INDEX, 1 if isinstance(ziel.index, ast.SliceAusdruck) else 0)
        else:
            raise _NichtUebersetzbar()

    def _verbund(self, knoten):
        ziel, operator = knoten.ziel, knoten.operator
        if isinstance(ziel, ast.Bezeichner):
            platz = self._platz(ziel.name)
            if platz is None:
                self._aus(LADE_NAME, self._name(ziel.name))
                self._ausdruck(knoten.wert)
                self._aus(BINAER, self._konstante(operator))
                self._aus(SETZE_NAME, self._name(ziel.name))
            else:
                self._aus(LADE_LOKAL, platz)
                self._ausdruck(knoten.wert)
                self._aus(BINAER, self._konstante(operator))
                self._aus(SETZE_LOKAL, platz)
        elif isinstance(ziel, ast.AttributZugriff):
            self._ausdruck(ziel.objekt)
            self._aus(DUPLIZIERE)
            self._aus(ATTRIBUT, self._name(ziel.attribut))
            self._ausdruck(knoten.wert)
            self._aus(BINAER, self._konstante(operator))
            self._aus(SETZE_ATTRIBUT, self._name(ziel.attribut))
        elif isinstance(ziel, ast.IndexZugriff):
            self._ausdruck(ziel.objekt)
            self._index_ausdruck(ziel.index)
            self._aus(DUPLIZIERE2)
            self._aus(INDEX, 1 if isinstance(ziel.index, ast.SliceAusdruck) else 0)
            self._ausdruck(knoten.wert)
            self._aus(BINAER, self._konstante(operator))
            self._aus(SETZE_INDEX, 1 if isinstance(ziel.index, ast.SliceAusdruck) else 0)
        else:
            raise _NichtUebersetzbar()

    def _wenn(self, knoten):
        enden = []
        self._ausdruck(knoten.bedingung)
        sprung = self._aus(SPRUNG_FALSCH)
        self._anweisung(knoten.dann)
        enden.append(self._aus(SPRUNG))
        self._ziel(sprung)
        for bedingung, block in knoten.sonst_wenn:
            self._ausdruck(bedingung)
            sprung = self._aus(SPRUNG_FALSCH)
            self._anweisung(block)
            enden.append(self._aus(SPRUNG))
            self._ziel(sprung)
        if knoten.sonst:
            self._anweisung(knoten.sonst)
        for stelle in enden:
            self._ziel(stelle)

    def _solange(self, knoten):
        anfang = len(self.befehle) // 2
        self._ausdruck(knoten.bedingung)
        ende = self._aus(SPRUNG_FALSCH)
        self._schleifen.append({'abbrechen': [], 'weiter': []})
        self._anweisung(knoten.koerper)
        rahmen = self._schleifen.pop()
        for stelle in rahmen['weiter']:
            self.befehle[stelle + 1] = anfang
        self.befehle[self._aus(SPRUNG) + 1] = anfang
        self._ziel(ende)
        for stelle in rahmen['abbrechen']:
            self._ziel(stelle)

    def _fuer(self, knoten):
        self._ausdruck(knoten.iterable)
        self._aus(ITERATOR)
        anfang = len(self.befehle) // 2
        ende = self._aus(NAECHSTES)
        self._bloecke.append({})
        if isinstance(knoten.variable, list):
            self._aus(ENTPACKE, len(knoten.variable))
            for name in knoten.variable:
                self._aus(SETZE_LOKAL, self._neuer_platz(name))
        else:
            self._aus(SETZE_LOKAL, self._neuer_platz(knoten.variable))
        self._schleifen.append({'abbrechen': [], 'weiter': []})
        self._anweisung(knoten.koerper)
        rahmen = self._schleifen.pop()
        self._bloecke.pop()
        for stelle in rahmen['weiter']:
            self.befehle[stelle + 1] = anfang
        self.befehle[self._aus(SPRUNG) + 1] = anfang
        self._ziel(ende)
        for stelle in rahmen['abbrechen']:
            self._ziel(stelle)             # auch 'abbrechen' landet vor dem POP,
        self._aus(POP)                     # sonst bliebe der Iterator liegen

    # ------------------------------------------------------------ Ausdrücke

    def _ausdruck(self, knoten):
        zeile = getattr(knoten, 'zeile', None)
        if zeile:
            self.zeile = zeile
        typ = type(knoten)

        if typ is ast.Ganzzahl or typ is ast.Kommazahl or typ is ast.Zeichenkette:
            self._aus(LADE_KONST, self._konstante(knoten.wert))
        elif typ is ast.Wahrheitswert:
            self._aus(LADE_KONST, self._konstante(knoten.wert))
        elif typ is ast.Nichts:
            self._aus(LADE_KONST, self._konstante(None))

        elif typ is ast.Bezeichner:
            platz = self._platz(knoten.name)
            if platz is None:
                self._aus(LADE_NAME, self._name(knoten.name))
            else:
                self._aus(LADE_LOKAL, platz)

        elif typ is ast.BinaereOperation:
            if knoten.operator == 'und':
                self._ausdruck(knoten.links)
                sprung = self._aus(SPRUNG_FALSCH_BEHALTE)
                self._aus(POP)
                self._ausdruck(knoten.rechts)
                self._ziel(sprung)
            elif knoten.operator == 'oder':
                self._ausdruck(knoten.links)
                sprung = self._aus(SPRUNG_WAHR_BEHALTE)
                self._aus(POP)
                self._ausdruck(knoten.rechts)
                self._ziel(sprung)
            else:
                self._ausdruck(knoten.links)
                self._ausdruck(knoten.rechts)
                self._aus(BINAER, self._konstante(knoten.operator))

        elif typ is ast.VergleichsKette:
            for operand in knoten.operanden:
                self._ausdruck(operand)
            self._aus(VERGLEICHSKETTE, self._konstante(tuple(knoten.operatoren)))

        elif typ is ast.UnaereOperation:
            self._ausdruck(knoten.operand)
            self._aus(NICHT if knoten.operator == 'nicht' else UNAER_MINUS)

        elif typ is ast.TernaerAusdruck:
            self._ausdruck(knoten.bedingung)
            sonst = self._aus(SPRUNG_FALSCH)
            self._ausdruck(knoten.dann_wert)
            ende = self._aus(SPRUNG)
            self._ziel(sonst)
            self._ausdruck(knoten.sonst_wert)
            self._ziel(ende)

        elif typ is ast.Liste:
            for element in knoten.elemente:
                self._ausdruck(element)
            self._aus(BAUE_LISTE, len(knoten.elemente))

        elif typ is ast.MengenLiteral:
            for element in knoten.elemente:
                self._ausdruck(element)
            self._aus(BAUE_MENGE, len(knoten.elemente))

        elif typ is ast.Woerterbuch:
            for schluessel, wert in knoten.paare:
                self._ausdruck(schluessel)
                self._ausdruck(wert)
            self._aus(BAUE_WOERTERBUCH, len(knoten.paare))

        elif typ is ast.InterpolierteZeichenkette:
            for teil in knoten.teile:
                self._ausdruck(teil)
            self._aus(BAUE_TEXT, len(knoten.teile))

        elif typ is ast.FormatierterAusdruck:
            self._ausdruck(knoten.ausdruck)
            self._aus(FORMATIERE, self._konstante(knoten.format_spec))

        elif typ is ast.AttributZugriff:
            self._ausdruck(knoten.objekt)
            self._aus(ATTRIBUT, self._name(knoten.attribut))

        elif typ is ast.IndexZugriff:
            self._ausdruck(knoten.objekt)
            self._index_ausdruck(knoten.index)
            self._aus(INDEX, 1 if isinstance(knoten.index, ast.SliceAusdruck) else 0)

        elif typ is ast.FunktionAufruf:
            self._aufruf(knoten)

        elif typ is ast.NeuInstanz:
            self._ausdruck(knoten.klasse)
            schluessel = tuple(n for n, _ in knoten.keyword_argumente)
            if self._hat_entpackung(knoten):
                anzahl = self._argumente_teile(knoten)
                self._aus(NEU_ENTPACKT, self._konstante((anzahl, schluessel, knoten.name)))
            else:
                self._argumente_einfach(knoten)
                self._aus(NEU_INSTANZ, self._konstante(
                    (len(knoten.argumente), schluessel, knoten.name)))

        else:
            raise _NichtUebersetzbar()

    def _index_ausdruck(self, index):
        if isinstance(index, ast.SliceAusdruck):
            for teil in (index.start, index.stop, index.step):
                if teil is None:
                    self._aus(LADE_KONST, self._konstante(None))
                else:
                    self._ausdruck(teil)
            self._aus(BAUE_SCHNITT)
        else:
            self._ausdruck(index)

    def _argumente_einfach(self, knoten):
        for argument in knoten.argumente:
            self._ausdruck(argument)
        for _name, wert in knoten.keyword_argumente:
            self._ausdruck(wert)

    def _argumente_teile(self, knoten) -> int:
        """Für Aufrufe mit '*': jedes Argument wird zu einer Teilliste, die die
        Maschine flach zusammenzieht."""
        for argument in knoten.argumente:
            if isinstance(argument, ast.EntpackterAusdruck):
                self._ausdruck(argument.ausdruck)
                self._aus(ENTPACKE_ARG)
            else:
                self._ausdruck(argument)
                self._aus(BAUE_LISTE, 1)
        for _name, wert in knoten.keyword_argumente:
            self._ausdruck(wert)
        return len(knoten.argumente)

    def _hat_entpackung(self, knoten) -> bool:
        return any(isinstance(a, ast.EntpackterAusdruck) for a in knoten.argumente)

    def _aufruf(self, knoten):
        self._ausdruck(knoten.funktion)
        schluessel = tuple(n for n, _ in knoten.keyword_argumente)
        if self._hat_entpackung(knoten):
            anzahl = self._argumente_teile(knoten)
            self._aus(AUFRUF_ENTPACKT, self._konstante((anzahl, schluessel)))
        elif schluessel:
            self._argumente_einfach(knoten)
            self._aus(AUFRUF_KW, self._konstante((len(knoten.argumente), schluessel)))
        else:
            self._argumente_einfach(knoten)
            self._aus(AUFRUF, len(knoten.argumente))


def kompiliere(definition):
    """Übersetzt einen Funktionskörper – None, wenn er nicht übersetzbar ist."""
    if not kompilierbar(definition):
        return None
    try:
        return Kompilierer(definition).kompiliere()
    except _NichtUebersetzbar:
        return None
    except RecursionError:
        return None


# ------------------------------------------------------------------ Maschine

def fuehre_aus(interpreter, code: Codeobjekt, lokale: list, umgebung):
    """Führt ein Codeobjekt aus und gibt den Rückgabewert zurück."""
    befehle = code.befehle
    konstanten = code.konstanten
    namen = code.namen
    stapel = []
    hole = stapel.pop
    lege = stapel.append
    zeiger = 0
    anzahl = len(befehle)

    try:
      while zeiger < anzahl:
        befehl = befehle[zeiger]
        argument = befehle[zeiger + 1]
        zeiger += 2

        if True:
            if befehl == LADE_LOKAL:
                lege(lokale[argument])
            elif befehl == LADE_KONST:
                lege(konstanten[argument])
            elif befehl == SETZE_LOKAL:
                lokale[argument] = hole()
            elif befehl == BINAER:
                rechts = hole()
                links = hole()
                # Schnellpfad: reine Ganzzahlen brauchen weder Überladung noch
                # Sonderregeln. 'type(...) is int' schließt Wahrheitswerte aus.
                if type(links) is int and type(rechts) is int:
                    operator = konstanten[argument]
                    if operator == '+':
                        lege(links + rechts)
                        continue
                    if operator == '-':
                        lege(links - rechts)
                        continue
                    if operator == '*':
                        lege(links * rechts)
                        continue
                    if operator == '<':
                        lege(links < rechts)
                        continue
                    if operator == '>':
                        lege(links > rechts)
                        continue
                    if operator == '==':
                        lege(links == rechts)
                        continue
                    if operator == '<=':
                        lege(links <= rechts)
                        continue
                    if operator == '>=':
                        lege(links >= rechts)
                        continue
                    if operator == '!=':
                        lege(links != rechts)
                        continue
                    lege(interpreter._binaerer_operator(operator, links, rechts))
                    continue
                lege(interpreter._binaerer_operator(konstanten[argument], links, rechts))
            elif befehl == SPRUNG_FALSCH:
                if not interpreter._ist_wahr(hole()):
                    zeiger = argument * 2
            elif befehl == SPRUNG:
                zeiger = argument * 2
            elif befehl == LADE_NAME:
                lege(umgebung.hole(namen[argument]))
            elif befehl == AUFRUF:
                args = stapel[-argument:] if argument else []
                if argument:
                    del stapel[-argument:]
                lege(interpreter._aufrufen(stapel.pop(), args))
            elif befehl == NAECHSTES:
                try:
                    lege(next(stapel[-1]))
                except StopIteration:
                    zeiger = argument * 2
            elif befehl == RUECKGABE:
                return hole()
            elif befehl == ATTRIBUT:
                lege(interpreter._attribut(hole(), namen[argument]))
            elif befehl == INDEX:
                schluessel = hole()
                lege(interpreter._index(hole(), schluessel, bool(argument)))
            elif befehl == POP:
                hole()
            elif befehl == SETZE_NAME:
                umgebung.weise_zu(namen[argument], hole())
            elif befehl == DEKLARIERE_NAME:
                umgebung.setze_konstante(namen[argument], hole())
            elif befehl == ITERATOR:
                lege(iter(interpreter._pruefe_iterierbar(hole(), "'für'")))
            elif befehl == BAUE_LISTE:
                if argument:
                    elemente = stapel[-argument:]
                    del stapel[-argument:]
                    lege(elemente)
                else:
                    lege([])
            elif befehl == BAUE_TEXT:
                teile = stapel[-argument:] if argument else []
                if argument:
                    del stapel[-argument:]
                lege(''.join(t if isinstance(t, str) else interpreter._zu_text(t)
                             for t in teile))
            elif befehl == VERGLEICHSKETTE:
                operatoren = konstanten[argument]
                werte = stapel[-(len(operatoren) + 1):]
                del stapel[-(len(operatoren) + 1):]
                lege(_kette(interpreter, werte, operatoren))
            elif befehl == NICHT:
                lege(not interpreter._ist_wahr(hole()))
            elif befehl == UNAER_MINUS:
                lege(interpreter._unaeres_minus(hole()))
            elif befehl == SPRUNG_FALSCH_BEHALTE:
                if not interpreter._ist_wahr(stapel[-1]):
                    zeiger = argument * 2
            elif befehl == SPRUNG_WAHR_BEHALTE:
                if interpreter._ist_wahr(stapel[-1]):
                    zeiger = argument * 2
            elif befehl == AUFRUF_KW:
                anzahl_args, schluessel = konstanten[argument]
                lege(_aufrufen(interpreter, stapel, anzahl_args, schluessel, False))
            elif befehl == AUFRUF_ENTPACKT:
                anzahl_args, schluessel = konstanten[argument]
                lege(_aufrufen(interpreter, stapel, anzahl_args, schluessel, True))
            elif befehl == SETZE_ATTRIBUT:
                wert = hole()
                interpreter._attribut_setzen(hole(), namen[argument], wert)
            elif befehl == SETZE_INDEX:
                wert = hole()
                schluessel = hole()
                interpreter._index_setzen(hole(), schluessel, wert, bool(argument))
            elif befehl == BAUE_WOERTERBUCH:
                lege(_woerterbuch(interpreter, stapel, argument))
            elif befehl == BAUE_MENGE:
                lege(_menge(interpreter, stapel, argument))
            elif befehl == BAUE_SCHNITT:
                schritt, stopp, start = hole(), hole(), hole()
                if schritt == 0:
                    raise ValueError('Slice-Schrittweite darf nicht 0 sein')
                lege(slice(start, stopp, schritt))
            elif befehl == FORMATIERE:
                lege(interpreter._formatieren(hole(), konstanten[argument]))
            elif befehl == ENTPACKE:
                lege_entpackt(interpreter, stapel, argument)
            elif befehl == ENTPACKE_ARG:
                lege(list(interpreter._pruefe_iterierbar(hole(), "Entpacken mit '*'")))
            elif befehl == DUPLIZIERE:
                lege(stapel[-1])
            elif befehl == DUPLIZIERE2:
                lege(stapel[-2])
                lege(stapel[-2])
            elif befehl == NEU_INSTANZ:
                anzahl_args, schluessel, anzeigename = konstanten[argument]
                lege(_neu(interpreter, stapel, anzahl_args, schluessel, anzeigename, False))
            elif befehl == NEU_ENTPACKT:
                anzahl_args, schluessel, anzeigename = konstanten[argument]
                lege(_neu(interpreter, stapel, anzahl_args, schluessel, anzeigename, True))
            elif befehl == TYP_PRUEFEN:
                hinweis, name = konstanten[argument]
                interpreter._pruefe_typ(stapel[-1], hinweis, f"Variable '{name}'", umgebung)
            elif befehl == WERFE:
                raise interpreter._ausnahme(hole())
            elif befehl == PRUEFE:
                meldung = hole() if argument else None
                interpreter._pruefen(hole(), meldung)
            else:
                raise RuntimeError(f'Unbekannter Befehl: {befehl}')
    except Exception as fehler:
        zeile = code.zeilen.get(zeiger // 2 - 1)
        if zeile:
            interpreter._aktuelle_zeile = zeile
        interpreter._mit_zeile(fehler, zeile)

    return None


def _kette(interpreter, werte, operatoren):
    links = werte[0]
    for i, operator in enumerate(operatoren):
        rechts = werte[i + 1]
        if not interpreter._ist_wahr(interpreter._binaerer_operator(operator, links, rechts)):
            return False
        links = rechts
    return True


def _argumente_vom_stapel(stapel, anzahl, schluessel, entpackt):
    kwargs = {}
    if schluessel:
        werte = stapel[-len(schluessel):]
        del stapel[-len(schluessel):]
        kwargs = dict(zip(schluessel, werte))
    roh = stapel[-anzahl:] if anzahl else []
    if anzahl:
        del stapel[-anzahl:]
    args = [wert for teil in roh for wert in teil] if entpackt else roh
    return args, kwargs


def _aufrufen(interpreter, stapel, anzahl, schluessel, entpackt):
    args, kwargs = _argumente_vom_stapel(stapel, anzahl, schluessel, entpackt)
    return interpreter._aufrufen(stapel.pop(), args, kwargs)


def _neu(interpreter, stapel, anzahl, schluessel, anzeigename, entpackt):
    args, kwargs = _argumente_vom_stapel(stapel, anzahl, schluessel, entpackt)
    return interpreter._instanz_erzeugen(stapel.pop(), args, kwargs, anzeigename)


def _woerterbuch(interpreter, stapel, anzahl):
    ergebnis = {}
    if anzahl:
        paare = stapel[-anzahl * 2:]
        del stapel[-anzahl * 2:]
        for i in range(0, len(paare), 2):
            interpreter._woerterbuch_eintragen(ergebnis, paare[i], paare[i + 1])
    return ergebnis


def _menge(interpreter, stapel, anzahl):
    elemente = stapel[-anzahl:] if anzahl else []
    if anzahl:
        del stapel[-anzahl:]
    return interpreter._menge_bauen(elemente)


def lege_entpackt(interpreter, stapel, anzahl):
    wert = stapel.pop()
    if not isinstance(wert, (list, tuple)):
        raise TypeError(
            f'Destrukturierung erwartet eine Liste, bekam {interpreter._typname(wert)}')
    if len(wert) != anzahl:
        raise TypeError(f'Destrukturierung erwartet {anzahl} Werte, bekam {len(wert)}')
    stapel.extend(reversed(wert))
