# -*- coding: utf-8 -*-
"""Linter v1: statische Prüfung über den AST (keine Ausführung, kein Interpreter-Zustand).

Regeln (lieber auslassen als falsch melden):
  a) unbekannter Name, b) unbenutzte 'sei'-Variable in Funktionen/Methoden, c) unerreichbarer Code.
"""
import difflib

from . import ast_knoten as ast
from .interpreter import FEHLERARTEN, _ENGLISCHE_FEHLERNAMEN, Interpreter

_SPRUNG = (ast.ZurueckAnweisung, ast.AbbrechenAnweisung, ast.WeiterAnweisung, ast.WerfeAnweisung)
_SLOTS: dict = {}


def _kinder(k):
    """Alle Unterknoten eines Knotens (durch Listen/Tupel hindurch)."""
    felder = _SLOTS.get(type(k))
    if felder is None:
        felder = _SLOTS[type(k)] = [s for c in type(k).__mro__ for s in getattr(c, '__slots__', ())
                                    if s != 'zeile']
    stapel = [getattr(k, s, None) for s in felder]
    while stapel:
        e = stapel.pop()
        if isinstance(e, ast.Knoten):
            yield e
        elif isinstance(e, (list, tuple)):
            stapel.extend(e)


def _muster_namen(m):
    """Gebundene Namen (str) eines Musters bzw. einer einfachen Variable."""
    if isinstance(m, str):
        yield m
    elif isinstance(m, ast.Muster):
        for z in m.ziele:
            yield from _muster_namen(z)


def _gebunden(k):
    """Namen, die dieser Knoten selbst bindet."""
    if isinstance(k, ast.VariableDeklaration):
        yield k.name
    elif isinstance(k, ast.DestrukturierendeDeklaration):
        yield from _muster_namen(k.muster)
    elif isinstance(k, (ast.FuerAnweisung, ast.ListenAusdruck)):
        yield from _muster_namen(k.variable)
    elif isinstance(k, ast.FunktionDefinition):
        if k.name:
            yield k.name
        for p in k.parameter:
            yield p[0]
        if k.kwargs_parameter:
            yield k.kwargs_parameter[0]
    elif isinstance(k, (ast.KlassenDefinition, ast.AufzaehlungsDefinition)):
        yield k.name
    elif isinstance(k, ast.VersucheAnweisung):
        if k.fange_name:
            yield k.fange_name
    elif isinstance(k, ast.LadeAnweisung):
        if k.als_name:
            yield k.als_name


def _lesende_bezeichner(k):
    """Alle gelesenen Bezeichner unter k (inkl. verschachtelter Funktionen) mit Anweisungszeile.
    Reine Zuweisungsziele 'x = …' zählen nicht als Lesen."""
    ergebnis = []

    def gehe(n, zeile):
        zeile = getattr(n, 'zeile', None) or zeile
        if isinstance(n, ast.Bezeichner):
            ergebnis.append((n.name, zeile))
            return
        if isinstance(n, (ast.Zuweisung, ast.KettenZuweisung)):
            ziele = [n.ziel] if isinstance(n, ast.Zuweisung) else n.ziele
            for z in ziele:
                ziel_gehen(z, zeile)
            gehe(n.wert, zeile)
            return
        for kind in _kinder(n):
            gehe(kind, zeile)

    def ziel_gehen(z, zeile):
        if isinstance(z, ast.Bezeichner):
            return
        if isinstance(z, ast.Muster):
            for e in z.ziele:
                ziel_gehen(e, zeile)
        elif isinstance(z, ast.Knoten):
            gehe(z, zeile)

    gehe(k, None)
    return ergebnis


def _alle(k):
    yield k
    for kind in _kinder(k):
        yield from _alle(kind)


def _eingebaute_namen():
    return set(Interpreter().global_umgebung.variablen) | set(FEHLERARTEN) | set(_ENGLISCHE_FEHLERNAMEN)


def pruefe(programm):
    """Liefert sortierte Liste (zeile, text)."""
    funde = []
    knoten = list(_alle(programm))

    # a) unbekannter Name – Namen aus 'lade' ohne 'als' sind unsichtbar: dann Regel auslassen
    if not any(isinstance(k, ast.LadeAnweisung) and not k.als_name for k in knoten):
        eigene = set().union(*(_gebunden(k) for k in knoten))
        eingebaut = _eingebaute_namen()
        bekannt = eingebaut | eigene
        for name, zeile in _lesende_bezeichner(programm):
            if name not in bekannt:
                text = f"unbekannter Name '{name}'"
                # wie umgebung.py (cutoff 0.6), aber Programmnamen zuerst; Eingebautes nur bei klarem Treffer
                treffer = (difflib.get_close_matches(name, sorted(eigene), n=1, cutoff=0.6)
                           or difflib.get_close_matches(name, sorted(eingebaut), n=1, cutoff=0.8))
                if treffer:
                    text += f" – meintest du '{treffer[0]}'?"
                funde.append((zeile or 0, text))

    # b) unbenutzte 'sei'-Variable je Funktion/Methode (nur diese, nicht verschachtelte Funktionen)
    for k in knoten:
        if not isinstance(k, ast.FunktionDefinition):
            continue
        gelesen = {n for n, _ in _lesende_bezeichner(k.koerper)}
        stapel = [k.koerper]
        while stapel:
            for kind in _kinder(stapel.pop()):
                if isinstance(kind, ast.FunktionDefinition):
                    continue
                if (isinstance(kind, ast.VariableDeklaration) and not kind.ist_konstante
                        and not kind.name.startswith('_') and kind.name not in gelesen):
                    funde.append((getattr(kind, 'zeile', None) or 0,
                                  f"Variable '{kind.name}' wird angelegt, aber nie gelesen"))
                stapel.append(kind)

    # c) unerreichbarer Code: Anweisung nach zurück/abbrechen/weiter/werfe im selben Block
    for k in knoten:
        if isinstance(k, (ast.Block, ast.Programm)):
            a = k.anweisungen
            for i, anw in enumerate(a[:-1]):
                if isinstance(anw, _SPRUNG):
                    funde.append((getattr(a[i + 1], 'zeile', None) or 0, 'unerreichbarer Code'))
                    break

    return sorted(set(funde))
