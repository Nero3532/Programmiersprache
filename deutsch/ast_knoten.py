# -*- coding: utf-8 -*-
"""AST-Knoten der Deutsch-Programmiersprache v2."""


class Knoten:
    __slots__ = ('zeile',)


# ------------------------------------------------------------------ Literale

class Ganzzahl(Knoten):
    __slots__ = ('wert',)
    def __init__(self, wert): self.wert = wert

class Kommazahl(Knoten):
    __slots__ = ('wert',)
    def __init__(self, wert): self.wert = wert

class Zeichenkette(Knoten):
    __slots__ = ('wert',)
    def __init__(self, wert): self.wert = wert

class InterpolierteZeichenkette(Knoten):
    """f-string-ähnliche Interpolation: "Hallo {name}!" """
    __slots__ = ('teile',)
    def __init__(self, teile): self.teile = teile  # [Knoten, ...]

class FormatierterAusdruck(Knoten):
    """Interpolations-Teil mit Format-Spezifizierer: "{wert:.2f}" """
    __slots__ = ('ausdruck', 'format_spec')
    def __init__(self, ausdruck, format_spec):
        self.ausdruck = ausdruck
        self.format_spec = format_spec  # str, z.B. '.2f'

class Wahrheitswert(Knoten):
    __slots__ = ('wert',)
    def __init__(self, wert): self.wert = wert

class Nichts(Knoten):
    __slots__ = ()

class Bezeichner(Knoten):
    __slots__ = ('name',)
    def __init__(self, name): self.name = name

class Liste(Knoten):
    __slots__ = ('elemente',)
    def __init__(self, elemente): self.elemente = elemente

class Woerterbuch(Knoten):
    __slots__ = ('paare',)
    def __init__(self, paare): self.paare = paare  # [(schlüssel_knoten, wert_knoten), ...]

class ListenAusdruck(Knoten):
    """List comprehension: [ausdruck für variable in iterable wenn bedingung]"""
    __slots__ = ('ausdruck', 'variable', 'iterable', 'bedingung')
    def __init__(self, ausdruck, variable, iterable, bedingung):
        self.ausdruck = ausdruck
        self.variable = variable
        self.iterable = iterable
        self.bedingung = bedingung  # None oder Knoten

# ---------------------------------------------------------------- Ausdrücke

class BinaereOperation(Knoten):
    __slots__ = ('links', 'operator', 'rechts')
    def __init__(self, links, operator, rechts):
        self.links = links
        self.operator = operator
        self.rechts = rechts

class UnaereOperation(Knoten):
    __slots__ = ('operator', 'operand')
    def __init__(self, operator, operand):
        self.operator = operator
        self.operand = operand

class VergleichsKette(Knoten):
    """a < b < c  ->  (a<b) und (b<c), jeder Operand wird nur einmal ausgewertet."""
    __slots__ = ('operanden', 'operatoren')
    def __init__(self, operanden, operatoren):
        self.operanden = operanden      # [Knoten, ...], Länge n+1
        self.operatoren = operatoren    # [str, ...], Länge n

class TernaerAusdruck(Knoten):
    """dann_wert wenn bedingung sonst sonst_wert"""
    __slots__ = ('dann_wert', 'bedingung', 'sonst_wert')
    def __init__(self, dann_wert, bedingung, sonst_wert):
        self.dann_wert = dann_wert
        self.bedingung = bedingung
        self.sonst_wert = sonst_wert

class MengenLiteral(Knoten):
    __slots__ = ('elemente',)
    def __init__(self, elemente): self.elemente = elemente

class FunktionAufruf(Knoten):
    __slots__ = ('funktion', 'argumente')
    def __init__(self, funktion, argumente):
        self.funktion = funktion
        self.argumente = argumente

class AttributZugriff(Knoten):
    __slots__ = ('objekt', 'attribut')
    def __init__(self, objekt, attribut):
        self.objekt = objekt
        self.attribut = attribut

class IndexZugriff(Knoten):
    __slots__ = ('objekt', 'index')
    def __init__(self, objekt, index):
        self.objekt = objekt
        self.index = index          # Knoten | SliceAusdruck

class SliceAusdruck(Knoten):
    """liste[start:stop:step] – jeder Teil optional (Knoten | None)."""
    __slots__ = ('start', 'stop', 'step')
    def __init__(self, start, stop, step):
        self.start = start
        self.stop = stop
        self.step = step

class NeuInstanz(Knoten):
    __slots__ = ('name', 'argumente')
    def __init__(self, name, argumente):
        self.name = name
        self.argumente = argumente

# -------------------------------------------------------------- Anweisungen

class Programm(Knoten):
    __slots__ = ('anweisungen',)
    def __init__(self, anweisungen): self.anweisungen = anweisungen

class Block(Knoten):
    __slots__ = ('anweisungen',)
    def __init__(self, anweisungen): self.anweisungen = anweisungen

class VariableDeklaration(Knoten):
    __slots__ = ('name', 'typhinweis', 'wert')
    def __init__(self, name, wert, typhinweis=None):
        self.name = name
        self.typhinweis = typhinweis  # str | None – nur zur Info
        self.wert = wert

class DestrukturierendeDeklaration(Knoten):
    """sei [a, b, c] = ausdruck"""
    __slots__ = ('namen', 'wert')
    def __init__(self, namen, wert):
        self.namen = namen  # [str, ...]
        self.wert = wert

class Zuweisung(Knoten):
    __slots__ = ('ziel', 'wert')
    def __init__(self, ziel, wert):
        self.ziel = ziel   # Bezeichner | AttributZugriff | IndexZugriff
        self.wert = wert

class VerbundZuweisung(Knoten):
    """x += 1 wird als eigenständiger Knoten gespeichert (kein Desugar im Parser)."""
    __slots__ = ('ziel', 'operator', 'wert')
    def __init__(self, ziel, operator, wert):
        self.ziel = ziel
        self.operator = operator  # '+', '-', '*', '/', '%'
        self.wert = wert

class WennAnweisung(Knoten):
    __slots__ = ('bedingung', 'dann', 'sonst_wenn', 'sonst')
    def __init__(self, bedingung, dann, sonst_wenn, sonst):
        self.bedingung = bedingung
        self.dann = dann
        self.sonst_wenn = sonst_wenn  # [(bedingung, block), ...]
        self.sonst = sonst

class SolangeAnweisung(Knoten):
    __slots__ = ('bedingung', 'koerper')
    def __init__(self, bedingung, koerper):
        self.bedingung = bedingung
        self.koerper = koerper

class FuerAnweisung(Knoten):
    __slots__ = ('variable', 'iterable', 'koerper')
    def __init__(self, variable, iterable, koerper):
        self.variable = variable
        self.iterable = iterable
        self.koerper = koerper

class FunktionDefinition(Knoten):
    """
    parameter: [(name, default_expr|None, is_variadic), ...]
    typhinweis: str | None  (Rückgabetyp, ignoriert zur Laufzeit)
    """
    __slots__ = ('name', 'parameter', 'koerper', 'typhinweis')
    def __init__(self, name, parameter, koerper, typhinweis=None):
        self.name = name
        self.parameter = parameter
        self.koerper = koerper
        self.typhinweis = typhinweis

class ZurueckAnweisung(Knoten):
    __slots__ = ('wert',)
    def __init__(self, wert): self.wert = wert

class AbbrechenAnweisung(Knoten):
    __slots__ = ()

class WeiterAnweisung(Knoten):
    __slots__ = ()

class KlassenDefinition(Knoten):
    __slots__ = ('name', 'eltern', 'methoden')
    def __init__(self, name, eltern, methoden):
        self.name = name
        self.eltern = eltern      # Elternklassen-Namen (list[str])
        self.methoden = methoden  # [FunktionDefinition, ...]

class VersucheAnweisung(Knoten):
    __slots__ = ('koerper', 'fange_name', 'fange_koerper', 'endlich_koerper')
    def __init__(self, koerper, fange_name, fange_koerper, endlich_koerper):
        self.koerper = koerper
        self.fange_name = fange_name           # str | None
        self.fange_koerper = fange_koerper     # Block | None
        self.endlich_koerper = endlich_koerper # Block | None

class LadeAnweisung(Knoten):
    __slots__ = ('pfad',)
    def __init__(self, pfad): self.pfad = pfad  # Ausdruck der einen Pfad ergibt

class WerfeAnweisung(Knoten):
    __slots__ = ('wert',)
    def __init__(self, wert): self.wert = wert

class PasseAnweisung(Knoten):
    __slots__ = ('ausdruck', 'faelle', 'sonst')
    def __init__(self, ausdruck, faelle, sonst):
        self.ausdruck = ausdruck
        self.faelle = faelle  # [([Knoten, ...], Block), ...]
        self.sonst = sonst    # Block | None
