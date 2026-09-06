# -*- coding: utf-8 -*-
"""
Statische Prüfung: findet Fehler, ohne das Programm auszuführen.

Grundsatz: **nur melden, was sicher ist.** Deutsch ist dynamisch typisiert, und ein
Prüfer mit Fehlalarmen wäre schlimmer als keiner. Wo ein Typ nicht ableitbar ist,
schweigt der Prüfer. Geprüft werden deshalb vor allem Dinge, die unabhängig vom
Datenfluss feststehen: unbekannte Namen, Argumentanzahlen, Typ-Hinweise, Mitglieder
der Standardbibliothek und Methoden auf eingebauten Typen.

Verwendung:
    deutsch --pruefe datei.deu
und über den Language Server, der die Befunde als Diagnosen anzeigt.
"""
import difflib
import os

from . import ast_knoten as ast
from .lexer import SCHLUESSELWOERTER

FEHLER = 'fehler'
WARNUNG = 'warnung'

# Typnamen, die als Typ-Hinweis erlaubt sind (dieselben wie zur Laufzeit)
EINGEBAUTE_TYPEN = {
    'Ganzzahl', 'Kommazahl', 'Zeichenkette', 'Wahrheitswert', 'Liste',
    'Woerterbuch', 'Wörterbuch', 'Menge', 'Bereich', 'Generator', 'Nichts', 'Funktion',
}

# Typ eines Literal-Knotens
_LITERALTYP = {
    ast.Ganzzahl: 'Ganzzahl',
    ast.Kommazahl: 'Kommazahl',
    ast.Zeichenkette: 'Zeichenkette',
    ast.InterpolierteZeichenkette: 'Zeichenkette',
    ast.FormatierterAusdruck: 'Zeichenkette',
    ast.Wahrheitswert: 'Wahrheitswert',
    ast.Nichts: 'Nichts',
    ast.Liste: 'Liste',
    ast.ListenAusdruck: 'Liste',
    ast.Woerterbuch: 'Woerterbuch',
    ast.WoerterbuchAusdruck: 'Woerterbuch',
    ast.MengenLiteral: 'Menge',
    ast.MengenAusdruck: 'Menge',
    ast.FunktionDefinition: 'Funktion',
}

# Ergebnistyp von Operatoren, soweit er feststeht
_VERGLEICHE = {'==', '!=', '<', '>', '<=', '>=', 'in', 'nicht in', 'und', 'oder'}

_ZAHLTYPEN = {'Ganzzahl', 'Kommazahl'}


class Befund:
    """Ein einzelner Fund mit Zeile (1-basiert) und Meldung."""
    __slots__ = ('zeile', 'meldung', 'art')

    def __init__(self, zeile: int, meldung: str, art: str = FEHLER):
        self.zeile = zeile
        self.meldung = meldung
        self.art = art

    def __repr__(self):
        return f'Befund(Z.{self.zeile}, {self.meldung!r}, {self.art})'


class _Umfeld:
    """Ein Geltungsbereich während der Prüfung."""

    def __init__(self, eltern=None):
        self.typen: dict[str, str | None] = {}   # Name -> bekannter Typ oder None
        self.konstanten: set[str] = set()
        self.eltern = eltern

    def deklariere(self, name: str, typ=None, konstant=False):
        self.typen[name] = typ
        if konstant:
            self.konstanten.add(name)

    def finde(self, name: str):
        umfeld = self
        while umfeld is not None:
            if name in umfeld.typen:
                return umfeld
            umfeld = umfeld.eltern
        return None

    def typ_von(self, name: str):
        umfeld = self.finde(name)
        return umfeld.typen[name] if umfeld else None

    def alle_namen(self) -> set:
        namen, umfeld = set(), self
        while umfeld is not None:
            namen.update(umfeld.typen)
            umfeld = umfeld.eltern
        return namen


def _bekannte_umgebung():
    """Namen, Module und Methoden der Standardbibliothek – einmal aufgebaut."""
    global _BEKANNT
    if _BEKANNT is None:
        from .interpreter import Interpreter, DeutschNamensraum
        interpreter = Interpreter()
        global_ = interpreter.global_umgebung.variablen
        module = {n: set(v.bindungen) for n, v in global_.items()
                  if isinstance(v, DeutschNamensraum)}
        _BEKANNT = {
            'global': {n for n in global_ if n not in module},
            'module': module,
            'methoden': {
                'Liste': set(interpreter._listen_methoden),
                'Zeichenkette': set(interpreter._string_methoden),
                'Woerterbuch': set(interpreter._woerterbuch_methoden),
                'Wörterbuch': set(interpreter._woerterbuch_methoden),
                'Menge': set(interpreter._menge_methoden),
                'Bereich': set(interpreter._bereich_methoden),
            },
        }
    return _BEKANNT


_BEKANNT = None


class Pruefer:
    """Läuft den Baum ab und sammelt Befunde."""

    def __init__(self, ladepfad: str | None = None):
        self.befunde: list[Befund] = []
        self.zeile = 1
        self._ladepfad = ladepfad
        self._geladen: set[str] = set()
        # Konnte eine geladene Datei nicht gelesen werden, wissen wir nicht mehr,
        # welche Namen es gibt – dann werden unbekannte Namen nicht mehr gemeldet.
        self.namen_unsicher = False
        bekannt = _bekannte_umgebung()
        self.module = bekannt['module']
        self.methoden = bekannt['methoden']
        self.global_umfeld = _Umfeld()
        for name in bekannt['global']:
            self.global_umfeld.deklariere(name)
        for name in self.module:
            self.global_umfeld.deklariere(name, f'Modul({name})')
        # Im Dokument definierte Klassen: Name -> {Methodenname: FunktionDefinition}
        self.klassen: dict[str, dict] = {}
        self.funktionen: dict[str, ast.FunktionDefinition] = {}

    # ---------------------------------------------------------------- Melden

    def _melde(self, knoten, meldung: str, art: str = FEHLER):
        zeile = getattr(knoten, 'zeile', None) or self.zeile
        self.befunde.append(Befund(zeile, meldung, art))

    def _vorschlag(self, name: str, kandidaten) -> str:
        treffer = difflib.get_close_matches(name, sorted(kandidaten), n=1, cutoff=0.6)
        return f" – meintest du '{treffer[0]}'?" if treffer else ''

    # ------------------------------------------------------------- Einstieg

    def pruefe(self, programm: ast.Programm) -> list:
        self._block_pruefen(programm.anweisungen, self.global_umfeld)
        return sorted(self.befunde, key=lambda b: b.zeile)

    def _block_pruefen(self, anweisungen, umfeld):
        # Funktionen und Klassen vorziehen: sie dürfen sich gegenseitig und in
        # beliebiger Reihenfolge sehen, genau wie zur Laufzeit
        for anweisung in anweisungen:
            if isinstance(anweisung, ast.FunktionDefinition) and anweisung.name:
                umfeld.deklariere(anweisung.name, 'Funktion')
                self.funktionen.setdefault(anweisung.name, anweisung)
            elif isinstance(anweisung, ast.KlassenDefinition):
                umfeld.deklariere(anweisung.name, f'Klasse({anweisung.name})')
                self.klassen.setdefault(anweisung.name, {
                    m.name: m for m in list(anweisung.methoden) + list(anweisung.statische_methoden)
                })
        for anweisung in anweisungen:
            self._anweisung_pruefen(anweisung, umfeld)

    # ---------------------------------------------------------- Anweisungen

    def _anweisung_pruefen(self, knoten, umfeld):
        zeile = getattr(knoten, 'zeile', None)
        if zeile:
            self.zeile = zeile
        typ = type(knoten)

        if typ is ast.VariableDeklaration:
            self._deklaration_pruefen(knoten, umfeld)
        elif typ is ast.DestrukturierendeDeklaration:
            self._ausdruck_typ(knoten.wert, umfeld)
            for name in knoten.namen:
                umfeld.deklariere(name)
        elif typ is ast.Zuweisung:
            self._zuweisung_pruefen(knoten, umfeld)
        elif typ is ast.VerbundZuweisung:
            self._ziel_pruefen(knoten.ziel, umfeld, verbund=True)
            self._ausdruck_typ(knoten.wert, umfeld)
        elif typ is ast.FunktionDefinition:
            self._funktion_pruefen(knoten, umfeld)
        elif typ is ast.KlassenDefinition:
            self._klasse_pruefen(knoten, umfeld)
        elif typ is ast.Block:
            self._block_pruefen(knoten.anweisungen, _Umfeld(umfeld))
        elif typ is ast.WennAnweisung:
            self._ausdruck_typ(knoten.bedingung, umfeld)
            self._anweisung_pruefen(knoten.dann, umfeld)
            for bedingung, block in knoten.sonst_wenn:
                self._ausdruck_typ(bedingung, umfeld)
                self._anweisung_pruefen(block, umfeld)
            if knoten.sonst:
                self._anweisung_pruefen(knoten.sonst, umfeld)
        elif typ is ast.SolangeAnweisung:
            self._ausdruck_typ(knoten.bedingung, umfeld)
            self._anweisung_pruefen(knoten.koerper, umfeld)
        elif typ is ast.FuerAnweisung:
            self._ausdruck_typ(knoten.iterable, umfeld)
            schleife = _Umfeld(umfeld)
            self._schleifenvariable(knoten.variable, schleife)
            self._anweisung_pruefen(knoten.koerper, schleife)
        elif typ is ast.PasseAnweisung:
            self._ausdruck_typ(knoten.ausdruck, umfeld)
            for werte, block in knoten.faelle:
                for wert in werte:
                    self._ausdruck_typ(wert, umfeld)
                self._anweisung_pruefen(block, umfeld)
            if knoten.sonst:
                self._anweisung_pruefen(knoten.sonst, umfeld)
        elif typ is ast.VersucheAnweisung:
            self._anweisung_pruefen(knoten.koerper, umfeld)
            if knoten.fange_koerper is not None:
                fange = _Umfeld(umfeld)
                if knoten.fange_name:
                    fange.deklariere(knoten.fange_name)
                self._anweisung_pruefen(knoten.fange_koerper, fange)
            if knoten.endlich_koerper is not None:
                self._anweisung_pruefen(knoten.endlich_koerper, umfeld)
        elif typ is ast.LadeAnweisung:
            self._ausdruck_typ(knoten.pfad, umfeld)
            if knoten.als_name:
                # Namensraum: Inhalt unbekannt, deshalb keine Attributprüfung darauf
                umfeld.deklariere(knoten.als_name, f'Modul({knoten.als_name})')
            else:
                self._geladene_datei_uebernehmen(knoten, umfeld)
        elif typ in (ast.ZurueckAnweisung, ast.ErgibtAnweisung, ast.WerfeAnweisung):
            self._ausdruck_typ(knoten.wert, umfeld)
        elif typ is ast.PruefeAnweisung:
            self._ausdruck_typ(knoten.bedingung, umfeld)
            if knoten.meldung is not None:
                self._ausdruck_typ(knoten.meldung, umfeld)
        elif typ in (ast.AbbrechenAnweisung, ast.WeiterAnweisung):
            pass
        else:
            self._ausdruck_typ(knoten, umfeld)

    def _geladene_datei_uebernehmen(self, knoten, umfeld):
        """'lade "datei.deu"' bringt deren Top-Level-Namen in den globalen Bereich.

        Ohne das würde jeder Aufruf einer geladenen Funktion als unbekannter Name
        gemeldet. Lässt sich die Datei nicht lesen, schweigt der Prüfer fortan zu
        unbekannten Namen, statt zu raten.
        """
        if not isinstance(knoten.pfad, ast.Zeichenkette) or self._ladepfad is None:
            self.namen_unsicher = True
            return
        pfad = os.path.normpath(os.path.join(self._ladepfad, knoten.pfad.wert))
        if pfad in self._geladen:
            return
        self._geladen.add(pfad)
        try:
            from .lexer import Lexer
            from .parser import Parser
            with io_open(pfad) as datei:
                quelltext = datei.read()
            baum = Parser(Lexer(quelltext).tokenisieren()).parse()
        except Exception:
            self.namen_unsicher = True
            return
        for anweisung in baum.anweisungen:
            if isinstance(anweisung, ast.FunktionDefinition) and anweisung.name:
                umfeld.deklariere(anweisung.name, 'Funktion')
                self.funktionen.setdefault(anweisung.name, anweisung)
            elif isinstance(anweisung, ast.KlassenDefinition):
                umfeld.deklariere(anweisung.name, f'Klasse({anweisung.name})')
                self.klassen.setdefault(anweisung.name, {
                    m.name: m for m in list(anweisung.methoden) + list(anweisung.statische_methoden)
                })
            elif isinstance(anweisung, ast.VariableDeklaration):
                umfeld.deklariere(anweisung.name, anweisung.typhinweis)
            elif isinstance(anweisung, ast.DestrukturierendeDeklaration):
                for name in anweisung.namen:
                    umfeld.deklariere(name)
            elif isinstance(anweisung, ast.LadeAnweisung) and not anweisung.als_name:
                self._geladene_datei_uebernehmen(anweisung, umfeld)

    def _schleifenvariable(self, variable, umfeld):
        if isinstance(variable, list):
            for name in variable:
                umfeld.deklariere(name)
        else:
            umfeld.deklariere(variable)

    def _deklaration_pruefen(self, knoten, umfeld):
        werttyp = self._ausdruck_typ(knoten.wert, umfeld)
        hinweis = knoten.typhinweis
        if hinweis is not None:
            gueltig = self._typhinweis_pruefen(knoten, hinweis, umfeld)
            if gueltig and not self._passt(werttyp, hinweis, umfeld):
                self._melde(knoten, f"Variable '{knoten.name}': erwartet Typ '{hinweis}', "
                                    f'bekommt {werttyp}')
        if knoten.name in umfeld.konstanten:
            self._melde(knoten, f"'{knoten.name}' ist bereits als Konstante in diesem "
                                'Geltungsbereich deklariert')
        umfeld.deklariere(knoten.name, hinweis or werttyp, knoten.ist_konstante)

    def _zuweisung_pruefen(self, knoten, umfeld):
        self._ausdruck_typ(knoten.wert, umfeld)
        self._ziel_pruefen(knoten.ziel, umfeld)

    def _ziel_pruefen(self, ziel, umfeld, verbund=False):
        if isinstance(ziel, ast.Bezeichner):
            gefunden = umfeld.finde(ziel.name)
            if gefunden is None:
                if self.namen_unsicher:
                    return
                self._melde(ziel, f"Variable '{ziel.name}' wurde nicht deklariert "
                                  "(benutze 'sei')" + self._vorschlag(ziel.name, umfeld.alle_namen()))
            elif ziel.name in gefunden.konstanten:
                self._melde(ziel, f"'{ziel.name}' ist eine Konstante und kann nicht neu "
                                  'zugewiesen werden')
        else:
            self._ausdruck_typ(ziel, umfeld)

    def _typhinweis_pruefen(self, knoten, hinweis, umfeld) -> bool:
        """Meldet einen unbekannten Typ-Hinweis und sagt, ob er brauchbar ist."""
        if hinweis in EINGEBAUTE_TYPEN or hinweis in self.klassen:
            return True
        typ = umfeld.typ_von(hinweis)
        if isinstance(typ, str) and typ.startswith('Klasse('):
            return True
        kandidaten = EINGEBAUTE_TYPEN | set(self.klassen)
        self._melde(knoten, f"Unbekannter Typ-Hinweis: '{hinweis}'"
                            + self._vorschlag(hinweis, kandidaten))
        return False

    # ------------------------------------------------------------- Funktionen

    def _funktion_pruefen(self, knoten, umfeld, dies=False):
        if knoten.name:
            umfeld.deklariere(knoten.name, 'Funktion')
        innen = _Umfeld(umfeld)
        if dies:
            innen.deklariere('dies')
        for name, standard, _variadisch, hinweis in knoten.parameter:
            if hinweis is not None:
                self._typhinweis_pruefen(knoten, hinweis, umfeld)
            if standard is not None:
                self._ausdruck_typ(standard, umfeld)
            innen.deklariere(name, hinweis)
        rueckgabe_gueltig = True
        if knoten.typhinweis is not None:
            rueckgabe_gueltig = self._typhinweis_pruefen(knoten, knoten.typhinweis, umfeld)
        self._anweisung_pruefen(knoten.koerper, innen)
        if knoten.typhinweis and rueckgabe_gueltig and not knoten.ist_generator:
            self._rueckgaben_pruefen(knoten, innen)

    def _rueckgaben_pruefen(self, knoten, umfeld):
        for zurueck in _sammle(knoten.koerper, ast.ZurueckAnweisung):
            typ = self._ausdruck_typ(zurueck.wert, umfeld, still=True)
            if not self._passt(typ, knoten.typhinweis, umfeld):
                self._melde(zurueck, f"Rückgabewert von '{knoten.name or '<anonym>'}': "
                                     f"erwartet Typ '{knoten.typhinweis}', gibt {typ} zurück")

    def _klasse_pruefen(self, knoten, umfeld):
        for eltern_name in knoten.eltern:
            if umfeld.finde(eltern_name) is None and not self.namen_unsicher:
                self._melde(knoten, f"Unbekannte Elternklasse: '{eltern_name}'"
                                    + self._vorschlag(eltern_name, umfeld.alle_namen()))
        klassen_umfeld = _Umfeld(umfeld)
        for attribut in knoten.klassenattribute:
            self._anweisung_pruefen(attribut, klassen_umfeld)
        for methode in knoten.methoden:
            self._funktion_pruefen(methode, klassen_umfeld, dies=True)
        for methode in knoten.statische_methoden:
            self._funktion_pruefen(methode, klassen_umfeld)

    # --------------------------------------------------------------- Ausdrücke

    def _ausdruck_typ(self, knoten, umfeld, still=False):
        """Prüft einen Ausdruck und gibt seinen Typ zurück – None, wenn unbekannt."""
        if knoten is None:
            return None
        typ = type(knoten)

        if typ in _LITERALTYP:
            if typ is ast.InterpolierteZeichenkette:
                for teil in knoten.teile:
                    self._ausdruck_typ(teil, umfeld, still)
            elif typ is ast.FormatierterAusdruck:
                self._ausdruck_typ(knoten.ausdruck, umfeld, still)
            elif typ is ast.Liste:
                for element in knoten.elemente:
                    self._ausdruck_typ(element, umfeld, still)
            elif typ is ast.MengenLiteral:
                for element in knoten.elemente:
                    self._ausdruck_typ(element, umfeld, still)
            elif typ is ast.Woerterbuch:
                for schluessel, wert in knoten.paare:
                    self._ausdruck_typ(schluessel, umfeld, still)
                    self._ausdruck_typ(wert, umfeld, still)
            elif typ in (ast.ListenAusdruck, ast.MengenAusdruck, ast.WoerterbuchAusdruck):
                self._abstraktion_pruefen(knoten, umfeld, still)
            elif typ is ast.FunktionDefinition:
                self._funktion_pruefen(knoten, umfeld)
            return _LITERALTYP[typ]

        if typ is ast.Bezeichner:
            if umfeld.finde(knoten.name) is None and not still and not self.namen_unsicher:
                self._melde(knoten, f"Unbekannte Variable oder Funktion: '{knoten.name}'"
                                    + self._vorschlag(knoten.name, umfeld.alle_namen()))
                return None
            return umfeld.typ_von(knoten.name)

        if typ is ast.BinaereOperation:
            links = self._ausdruck_typ(knoten.links, umfeld, still)
            rechts = self._ausdruck_typ(knoten.rechts, umfeld, still)
            if knoten.operator in _VERGLEICHE:
                return 'Wahrheitswert'
            if knoten.operator == '+' and 'Zeichenkette' in (links, rechts):
                return 'Zeichenkette'
            if links in _ZAHLTYPEN and rechts in _ZAHLTYPEN:
                if knoten.operator == '/':
                    return 'Kommazahl'
                return 'Kommazahl' if 'Kommazahl' in (links, rechts) else 'Ganzzahl'
            return None

        if typ is ast.VergleichsKette:
            for operand in knoten.operanden:
                self._ausdruck_typ(operand, umfeld, still)
            return 'Wahrheitswert'

        if typ is ast.UnaereOperation:
            innen = self._ausdruck_typ(knoten.operand, umfeld, still)
            return 'Wahrheitswert' if knoten.operator == 'nicht' else innen

        if typ is ast.TernaerAusdruck:
            self._ausdruck_typ(knoten.bedingung, umfeld, still)
            dann = self._ausdruck_typ(knoten.dann_wert, umfeld, still)
            sonst = self._ausdruck_typ(knoten.sonst_wert, umfeld, still)
            return dann if dann == sonst else None

        if typ is ast.KlammerAusdruck if hasattr(ast, 'KlammerAusdruck') else False:
            return self._ausdruck_typ(knoten.ausdruck, umfeld, still)

        if typ is ast.AttributZugriff:
            return self._attribut_pruefen(knoten, umfeld, still)

        if typ is ast.IndexZugriff:
            self._ausdruck_typ(knoten.objekt, umfeld, still)
            if isinstance(knoten.index, ast.SliceAusdruck):
                for teil in (knoten.index.start, knoten.index.stop, knoten.index.step):
                    self._ausdruck_typ(teil, umfeld, still)
            else:
                self._ausdruck_typ(knoten.index, umfeld, still)
            return None

        if typ is ast.EntpackterAusdruck:
            self._ausdruck_typ(knoten.ausdruck, umfeld, still)
            return None

        if typ is ast.FunktionAufruf:
            return self._aufruf_pruefen(knoten, umfeld, still)

        if typ is ast.NeuInstanz:
            return self._neu_pruefen(knoten, umfeld, still)

        return None

    def _abstraktion_pruefen(self, knoten, umfeld, still):
        innen = _Umfeld(umfeld)
        for variable, iterable, bedingung in knoten.klauseln:
            self._ausdruck_typ(iterable, innen, still)
            self._schleifenvariable(variable, innen)
            if bedingung is not None:
                self._ausdruck_typ(bedingung, innen, still)
        if isinstance(knoten, ast.WoerterbuchAusdruck):
            self._ausdruck_typ(knoten.schluessel, innen, still)
            self._ausdruck_typ(knoten.wert, innen, still)
        else:
            self._ausdruck_typ(knoten.ausdruck, innen, still)

    def _attribut_pruefen(self, knoten, umfeld, still):
        objekttyp = self._ausdruck_typ(knoten.objekt, umfeld, still)
        if still or objekttyp is None:
            return None
        # Modul der Standardbibliothek
        if objekttyp.startswith('Modul('):
            modulname = objekttyp[6:-1]
            mitglieder = self.module.get(modulname)
            if mitglieder is not None and knoten.attribut not in mitglieder:
                self._melde(knoten, f"Namensraum '{modulname}' hat kein Attribut "
                                    f"'{knoten.attribut}'"
                                    + self._vorschlag(knoten.attribut, mitglieder))
            return None
        # Eingebauter Typ mit festem Methodensatz
        methoden = self.methoden.get(objekttyp)
        if methoden is not None and knoten.attribut not in methoden:
            self._melde(knoten, f"{objekttyp} hat kein Attribut '{knoten.attribut}'"
                                + self._vorschlag(knoten.attribut, methoden))
        return None

    def _aufruf_pruefen(self, knoten, umfeld, still):
        for argument in knoten.argumente:
            self._ausdruck_typ(argument, umfeld, still)
        for _name, wert in knoten.keyword_argumente:
            self._ausdruck_typ(wert, umfeld, still)
        ziel = knoten.funktion
        self._ausdruck_typ(ziel, umfeld, still)
        if still or not isinstance(ziel, ast.Bezeichner):
            return None
        definition = self.funktionen.get(ziel.name)
        if definition is None or umfeld.typ_von(ziel.name) != 'Funktion':
            return None
        self._signatur_pruefen(knoten, definition, ziel.name)
        return definition.typhinweis

    def _neu_pruefen(self, knoten, umfeld, still):
        for argument in knoten.argumente:
            self._ausdruck_typ(argument, umfeld, still)
        for _name, wert in knoten.keyword_argumente:
            self._ausdruck_typ(wert, umfeld, still)
        wurzel = knoten.name.split('.')[0]
        if not still and not self.namen_unsicher and umfeld.finde(wurzel) is None:
            self._melde(knoten, f"Unbekannte Variable oder Funktion: '{wurzel}'"
                                + self._vorschlag(wurzel, umfeld.alle_namen()))
            return None
        if '.' not in knoten.name and knoten.name in self.klassen:
            init = self.klassen[knoten.name].get('__init__')
            if init is not None and not still:
                self._signatur_pruefen(knoten, init, f'{knoten.name}.__init__', dies=True)
            return knoten.name
        return None

    def _signatur_pruefen(self, aufruf, definition, name, dies=False):
        parameter = list(definition.parameter)
        if dies and parameter:
            parameter = parameter[1:]          # 'dies' wird automatisch übergeben
        if any(entpackt(a) for a in aufruf.argumente):
            return                              # Anzahl steht erst zur Laufzeit fest
        namen = [p[0] for p in parameter]
        variadisch = any(p[2] for p in parameter)
        pflicht = [p[0] for p in parameter if p[1] is None and not p[2]]
        gegeben = len(aufruf.argumente)
        schluessel = {n for n, _ in aufruf.keyword_argumente}

        unbekannt = schluessel - set(namen)
        if unbekannt:
            self._melde(aufruf, f"'{name}' hat keinen Parameter "
                                f"'{sorted(unbekannt)[0]}'"
                                + self._vorschlag(sorted(unbekannt)[0], namen))
            return
        if not variadisch and gegeben > len(namen):
            self._melde(aufruf, f"'{name}' erwartet höchstens {len(namen)} Argument(e), "
                                f'bekommt {gegeben}')
            return
        fehlend = [p for i, p in enumerate(pflicht) if i >= gegeben and p not in schluessel]
        if fehlend:
            self._melde(aufruf, f"'{name}': Pflichtargument(e) fehlen: {', '.join(fehlend)}")

    # ------------------------------------------------------------- Typregeln

    def _passt(self, typ, hinweis, umfeld) -> bool:
        """Verträgt sich ein bekannter Typ mit einem Hinweis? Unbekannt gilt als passend."""
        if typ is None or hinweis is None:
            return True
        if typ == hinweis:
            return True
        if hinweis == 'Kommazahl' and typ == 'Ganzzahl':
            return True                          # Ganzzahl ist eine gültige Kommazahl
        if hinweis in ('Woerterbuch', 'Wörterbuch') and typ in ('Woerterbuch', 'Wörterbuch'):
            return True
        if typ.startswith(('Klasse(', 'Modul(')):
            return hinweis == 'Funktion' if typ.startswith('Klasse(') else False
        if hinweis in self.klassen:
            # Vererbung wird hier nicht verfolgt: nur melden, wenn der Wert
            # sicher kein Klassenexemplar ist
            return typ not in EINGEBAUTE_TYPEN
        return False


def entpackt(knoten) -> bool:
    return isinstance(knoten, ast.EntpackterAusdruck)


def _sammle(knoten, gesucht, treffer=None):
    """Alle Knoten eines Typs im Baum – ohne in geschachtelte Funktionen zu steigen."""
    if treffer is None:
        treffer = []
    if isinstance(knoten, gesucht):
        treffer.append(knoten)
        return treffer
    if isinstance(knoten, ast.FunktionDefinition):
        return treffer
    for feld in getattr(type(knoten), '__slots__', ()):
        wert = getattr(knoten, feld, None)
        if isinstance(wert, ast.Knoten):
            _sammle(wert, gesucht, treffer)
        elif isinstance(wert, (list, tuple)):
            for eintrag in wert:
                if isinstance(eintrag, ast.Knoten):
                    _sammle(eintrag, gesucht, treffer)
                elif isinstance(eintrag, (list, tuple)):
                    for tiefer in eintrag:
                        if isinstance(tiefer, ast.Knoten):
                            _sammle(tiefer, gesucht, treffer)
    return treffer


def io_open(pfad: str):
    import io as _io
    return _io.open(pfad, encoding='utf-8')


def pruefe(programm: ast.Programm, ladepfad: str | None = None) -> list:
    """Prüft ein geparstes Programm und gibt die Befunde zeilenweise sortiert zurück.

    ladepfad ist das Verzeichnis, relativ zu dem 'lade' aufgelöst wird.
    """
    return Pruefer(ladepfad).pruefe(programm)
