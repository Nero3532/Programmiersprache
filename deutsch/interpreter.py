# -*- coding: utf-8 -*-
import os
import math
import inspect
import random
import json
import re
import time
import statistics
import hashlib
import base64
from datetime import datetime
from . import ast_knoten as ast
from .umgebung import Umgebung


# ---------------------------------------------------------------- Signale

class _ZurueckSignal(Exception):
    def __init__(self, wert): self.wert = wert

class _AbbrechenSignal(Exception):
    pass

class _WeiterSignal(Exception):
    pass

_KONTROLLSIGNALE = (_ZurueckSignal, _AbbrechenSignal, _WeiterSignal)

# Operator-Überladung: Klassen können diese Methoden definieren, um +/-/*/... selbst
# zu implementieren. Nur der linke Operand wird geprüft (keine __radd__-artige Umkehrung),
# und jeder Operator braucht seine eigene Methode (kein automatisches Ableiten von != aus ==).
_OPERATOR_METHODEN = {
    '+':  '__addiere__',
    '-':  '__subtrahiere__',
    '*':  '__multipliziere__',
    '/':  '__dividiere__',
    '//': '__ganzdividiere__',
    '%':  '__modulo__',
    '**': '__potenziere__',
    '==': '__gleich__',
    '!=': '__ungleich__',
    '<':  '__kleiner__',
    '>':  '__groesser__',
    '<=': '__kleinergleich__',
    '>=': '__groessergleich__',
}


class SchluesselFehler(KeyError):
    """KeyError zeigt seine Nachricht normalerweise in repr()-Anführungszeichen – hier nicht."""
    def __str__(self):
        return str(self.args[0]) if self.args else ''


class AusnahmeFehler(Exception):
    """Trägt einen beliebigen von 'werfe' geworfenen Deutsch-Wert durch den Python-Stack."""
    def __init__(self, wert, nachricht=None):
        self.wert = wert
        self.nachricht = nachricht

    def __str__(self):
        return self.nachricht if self.nachricht is not None else str(self.wert)


# ---------------------------------------------------------- Laufzeit-Typen

class DeutschFunktion:
    def __init__(self, definition: ast.FunktionDefinition, umgebung: Umgebung):
        self.definition = definition
        self.umgebung = umgebung

    def __repr__(self):
        return f'<Funktion {self.definition.name or "anonym"}>'


class GebundeneMethode:
    def __init__(self, instanz, funktion: DeutschFunktion):
        self.instanz = instanz
        self.funktion = funktion

    def __repr__(self):
        return f'<Methode {self.funktion.definition.name}>'


class DeutschNamensraum:
    """Ergebnis von 'lade "datei.deu" als name' – kapselt die Top-Level-Bindungen der Datei."""
    def __init__(self, name: str, bindungen: dict):
        self.name = name
        self.bindungen = bindungen

    def __repr__(self):
        return f'<Namensraum {self.name}>'


_NICHT_GEFUNDEN = object()

# Typen, die eine Folge von Werten liefern. 'Bereich' ist Pythons range und damit
# faul: bereich(1000000) belegt keinen Speicher fuer eine Million Elemente.
_SEQUENZ_TYPEN = (list, set, range)

# Markiert ein nicht übergebenes optionales Argument einer eingebauten Instanzmethode.
_OHNE_WERT = object()


def _arity_ermitteln(fn):
    """Erlaubte Argumentanzahl einer Methoden-Implementierung ohne das führende 'obj'.

    Gibt (min, max) zurück; max ist None bei *args."""
    parameter = list(inspect.signature(fn).parameters.values())[1:]
    minimum = maximum = 0
    for p in parameter:
        if p.kind is inspect.Parameter.VAR_POSITIONAL:
            return minimum, None
        if p.default is inspect.Parameter.empty:
            minimum += 1
        maximum += 1
    return minimum, maximum


class _EingebauteMethode:
    """Eingebaute Instanzmethode von Liste/Zeichenkette/Wörterbuch/Menge.

    Prüft die Argumentanzahl selbst, damit ein falscher Aufruf eine deutsche Meldung
    liefert statt Pythons roher '<lambda>() missing 1 required positional argument'."""
    __slots__ = ('name', 'typname', 'fn', 'min_args', 'max_args')

    def __init__(self, name: str, typname: str, fn):
        self.name = name
        self.typname = typname
        self.fn = fn
        self.min_args, self.max_args = _arity_ermitteln(fn)

    def _erwartet_text(self) -> str:
        if self.max_args is None:
            return f'mindestens {self.min_args}'
        if self.min_args == self.max_args:
            return str(self.min_args)
        return f'{self.min_args}–{self.max_args}'

    def binden(self, obj):
        return _GebundeneEingebauteMethode(self, obj)

    def argumentfehler(self, anzahl):
        return TypeError(
            f"'{self.typname}.{self.name}' erwartet {self._erwartet_text()} "
            f'Argument(e), bekam {anzahl}'
        )

    def __repr__(self):
        return f'<Methode {self.typname}.{self.name}>'


class _GebundeneEingebauteMethode:
    """An ihr Objekt gebundene eingebaute Methode – prüft beim Aufruf die Argumentanzahl."""
    __slots__ = ('methode', 'obj')

    def __init__(self, methode: _EingebauteMethode, obj):
        self.methode = methode
        self.obj = obj

    def __call__(self, *args):
        m = self.methode
        if len(args) < m.min_args or (m.max_args is not None and len(args) > m.max_args):
            raise m.argumentfehler(len(args))
        return m.fn(self.obj, *args)

    def __repr__(self):
        return repr(self.methode)


class DeutschKlasse:
    def __init__(self, name: str, eltern: list, methoden: dict, statische_methoden: dict = None):
        self.name = name
        self.eltern: list['DeutschKlasse'] = eltern
        self.methoden = methoden  # {name: DeutschFunktion}
        self.statische_methoden = statische_methoden or {}  # {name: DeutschFunktion}, kein 'dies'
        self.klassenattribute: dict = {}      # gesetzt nach __init__ in _besuche_KlassenDefinition
        self.konstante_attribute: set = set()  # Teilmenge von klassenattribute-Schlüsseln

    def suche_methode(self, name: str):
        if name in self.methoden:
            return self.methoden[name]
        for e in self.eltern:  # links-nach-rechts, Tiefensuche, erster Treffer gewinnt
            m = e.suche_methode(name)
            if m is not None:
                return m
        return None

    def suche_statische_methode(self, name: str):
        if name in self.statische_methoden:
            return self.statische_methoden[name]
        for e in self.eltern:
            m = e.suche_statische_methode(name)
            if m is not None:
                return m
        return None

    def _deklarierende_klasse(self, name: str):
        """Erste Klasse in der Suchreihenfolge, die 'name' als Klassenattribut deklariert."""
        if name in self.klassenattribute:
            return self
        for e in self.eltern:
            treffer = e._deklarierende_klasse(name)
            if treffer is not None:
                return treffer
        return None

    def konstante_deklaration(self, name: str):
        """Klasse, die 'name' als Konstante deklariert – sonst None. Berücksichtigt
        Vererbung, aber nur bis zur ersten Klasse, die 'name' überhaupt deklariert."""
        klasse = self._deklarierende_klasse(name)
        if klasse is not None and name in klasse.konstante_attribute:
            return klasse
        return None

    def suche_klassenattribut(self, name: str):
        if name in self.klassenattribute:
            return self.klassenattribute[name]
        for e in self.eltern:
            wert = e.suche_klassenattribut(name)
            if wert is not _NICHT_GEFUNDEN:
                return wert
        return _NICHT_GEFUNDEN

    def __repr__(self):
        return f'<Klasse {self.name}>'


class DeutschInstanz:
    def __init__(self, klasse: DeutschKlasse):
        self.klasse = klasse
        self.attribute: dict = {}

    def hole_attribut(self, name: str):
        if name in self.attribute:
            return self.attribute[name]
        methode = self.klasse.suche_methode(name)
        if methode is not None:
            return GebundeneMethode(self, methode)
        statische_methode = self.klasse.suche_statische_methode(name)
        if statische_methode is not None:
            return statische_methode  # unbound – kein 'dies' wird injiziert
        wert = self.klasse.suche_klassenattribut(name)
        if wert is not _NICHT_GEFUNDEN:
            return wert
        raise AttributeError(f"'{self.klasse.name}' hat kein Attribut '{name}'")

    def setze_attribut(self, name: str, wert):
        self.attribute[name] = wert

    def __repr__(self):
        return f'<{self.klasse.name} Objekt>'


# ------------------------------------------------------------- Interpreter

class Interpreter:
    def __init__(self, ladepfad: str | None = None, argumente: list | None = None):
        self.global_umgebung = Umgebung()
        self._ladepfad = ladepfad or os.getcwd()
        self._cli_argumente = list(argumente) if argumente else []
        self._aktuelle_zeile: int | None = None
        self._aufruf_stack: list[tuple[str, int]] = []
        self._letzter_aufruf_stack: list = []
        self._lade_stack: list[str] = []
        self._dispatch = self._dispatch_aufbauen()
        self._listen_methoden = self._listen_methoden_aufbauen()
        self._string_methoden = self._string_methoden_aufbauen()
        self._woerterbuch_methoden = self._woerterbuch_methoden_aufbauen()
        self._menge_methoden = self._menge_methoden_aufbauen()
        self._bereich_methoden = self._bereich_methoden_aufbauen()
        self._eingebaute_laden()

    def _dispatch_aufbauen(self) -> dict:
        """Cacht Knotentyp -> Besuchermethode, statt bei jedem Besuch getattr(f'...') zu machen."""
        dispatch = {}
        for name in dir(self.__class__):
            if not name.startswith('_besuche_'):
                continue
            knoten_klasse = getattr(ast, name[len('_besuche_'):], None)
            if knoten_klasse is not None:
                dispatch[knoten_klasse] = getattr(self, name)
        return dispatch

    # Eingebaute Instanz-Methoden für Liste/Zeichenkette/Wörterbuch/Menge werden hier
    # EINMAL aufgebaut (statt bei jedem .attribut-Zugriff neu) – jede Funktion nimmt
    # 'obj' als expliziten ersten Parameter statt ihn per Closure einzufangen, damit
    # dieselbe Funktion für jede Instanz wiederverwendet und beim Zugriff nur noch
    # gebunden wird (siehe _EingebauteMethode.binden).
    # _methoden_registrieren liest die erlaubte Argumentanzahl aus der Signatur ab,
    # damit falsche Aufrufe eine deutsche Meldung statt Python-Interna liefern –
    # optionale Argumente deshalb als echte Defaults schreiben, nicht als *args.

    @staticmethod
    def _methoden_registrieren(typname: str, methoden: dict) -> dict:
        return {name: _EingebauteMethode(name, typname, fn) for name, fn in methoden.items()}

    def _listen_methoden_aufbauen(self):
        return self._methoden_registrieren('Liste', {
            'anhaengen': lambda obj, x: (obj.append(x), None)[1],
            'anhängen':  lambda obj, x: (obj.append(x), None)[1],
            'laenge':    lambda obj: len(obj),
            'länge':     lambda obj: len(obj),
            'entferne':  lambda obj, index=_OHNE_WERT: self._liste_entferne(obj, index),
            'enthält':   lambda obj, x: self._enthalten_in(x, obj),
            'umkehren':  lambda obj: (obj.reverse(), None)[1],
            'sortiere':  lambda obj: self._sortiert(obj, in_place=True),
            'erste':     lambda obj: obj[0] if obj else None,
            'letzte':    lambda obj: obj[-1] if obj else None,
            'kopiere':   lambda obj: list(obj),
            'flach':     lambda obj: [e for sub in obj for e in (sub if isinstance(sub, list) else [sub])],
            'index_von': lambda obj, x: self._index_von(obj, x, 'Liste'),
            'zaehle':    lambda obj, x: self._zaehle(obj, x, 'Liste'),
            'einfuegen': lambda obj, index, wert: self._liste_einfuegen(obj, index, wert),
            'erweitere': lambda obj, andere: self._liste_erweitere(obj, andere),
        })

    def _string_methoden_aufbauen(self):
        return self._methoden_registrieren('Zeichenkette', {
            'gross':         lambda obj: obj.upper(),
            'groß':          lambda obj: obj.upper(),
            'klein':         lambda obj: obj.lower(),
            'laenge':        lambda obj: len(obj),
            'länge':         lambda obj: len(obj),
            'teile':         lambda obj, trenner=_OHNE_WERT: self._string_teile(obj, trenner),
            'enthält':       lambda obj, x: self._string_enthaelt(obj, x),
            'ersetze':       lambda obj, alt, neu: self._string_ersetze(obj, alt, neu),
            'trimmen':       lambda obj: obj.strip(),
            'links_trimmen': lambda obj: obj.lstrip(),
            'rechts_trimmen':lambda obj: obj.rstrip(),
            'beginnt_mit':   lambda obj, x: self._string_praefix(obj, x, 'beginnt_mit'),
            'endet_mit':     lambda obj, x: self._string_praefix(obj, x, 'endet_mit'),
            'grossschreibe': lambda obj: obj.capitalize(),
            'großschreibe':  lambda obj: obj.capitalize(),
            'zeichen':       lambda obj: list(obj),
            'wiederhole':    lambda obj, n: self._string_wiederhole(obj, n),
            'zahl':          lambda obj: self._string_zahl(obj),
            'index_von':     lambda obj, x: self._index_von(obj, x, 'Zeichenkette'),
            'zaehle':        lambda obj, x: self._zaehle(obj, x, 'Zeichenkette'),
            'ist_ziffer':    lambda obj: obj.isdigit(),
            'ist_buchstabe': lambda obj: obj.isalpha(),
            'ist_leerraum':  lambda obj: obj.isspace(),
        })

    def _woerterbuch_methoden_aufbauen(self):
        return self._methoden_registrieren('Wörterbuch', {
            'schluessel': lambda obj: list(obj.keys()),
            'schlüssel':  lambda obj: list(obj.keys()),
            'werte':      lambda obj: list(obj.values()),
            'paare':      lambda obj: [[k, v] for k, v in obj.items()],
            'enthält':    lambda obj, x: self._enthaelt_hashbar(obj, x, 'Wörterbuch'),
            'entferne':   lambda obj, x: self._woerterbuch_entferne(obj, x),
            'laenge':     lambda obj: len(obj),
            'länge':      lambda obj: len(obj),
            'hole':       lambda obj, schluessel, standard=None: self._woerterbuch_hole(obj, schluessel, standard),
            'kopiere':    lambda obj: dict(obj),
        })

    def _bereich_methoden_aufbauen(self):
        return self._methoden_registrieren('Bereich', {
            'laenge':  lambda obj: len(obj),
            'länge':   lambda obj: len(obj),
            'enthält': lambda obj, x: self._enthalten_in(x, obj),
            'liste':   lambda obj: list(obj),
            'erste':   lambda obj: obj[0] if len(obj) else None,
            'letzte':  lambda obj: obj[-1] if len(obj) else None,
        })

    def _menge_methoden_aufbauen(self):
        return self._methoden_registrieren('Menge', {
            'laenge':       lambda obj: len(obj),
            'länge':        lambda obj: len(obj),
            'enthält':      lambda obj, x: self._enthaelt_hashbar(obj, x, 'Menge'),
            'hinzufuegen':  lambda obj, x: self._menge_hinzufuegen(obj, x),
            'hinzufügen':   lambda obj, x: self._menge_hinzufuegen(obj, x),
            'entferne':     lambda obj, x: self._menge_entfernen(obj, x),
            'vereinigung':  lambda obj, andere: self._menge_op(obj, andere, 'vereinigung', lambda a, b: a | b),
            'schnittmenge': lambda obj, andere: self._menge_op(obj, andere, 'schnittmenge', lambda a, b: a & b),
            'differenz':    lambda obj, andere: self._menge_op(obj, andere, 'differenz', lambda a, b: a - b),
            'kopiere':      lambda obj: set(obj),
            'teilmenge_von':          lambda obj, andere: self._menge_op(obj, andere, 'teilmenge_von', lambda a, b: a <= b),
            'obermenge_von':          lambda obj, andere: self._menge_op(obj, andere, 'obermenge_von', lambda a, b: a >= b),
            'symmetrische_differenz': lambda obj, andere: self._menge_op(obj, andere, 'symmetrische_differenz', lambda a, b: a ^ b),
        })

    # ---------------------------------------------------------- Eingebaute

    def _eingebaute_laden(self):
        """Kern global, alles Fachliche in einem Namensraum (mathe, datei, json, ...)."""
        g = self.global_umgebung
        g.setze('drucke',        self._eb_drucke)
        g.setze('eingabe',       self._eb_eingabe)
        g.setze('laenge',        self._eb_laenge)
        g.setze('länge',         self._eb_laenge)
        g.setze('typ',           self._eb_typ)
        g.setze('ganzzahl',      self._eb_ganzzahl)
        g.setze('kommazahl',     self._eb_kommazahl)
        g.setze('zeichenkette',  self._eb_zeichenkette)
        g.setze('wahrheitswert', self._eb_wahrheitswert)
        g.setze('bereich',       self._eb_bereich)
        g.setze('sortiere',      self._eb_sortiere)
        g.setze('anhaengen',     self._eb_anhaengen)
        g.setze('anhängen',      self._eb_anhaengen)
        g.setze('entferne',      self._eb_entferne)
        g.setze('umkehren',      self._eb_umkehren)
        g.setze('verbinde',      self._eb_verbinde)
        g.setze('max',           self._eb_max)
        g.setze('min',           self._eb_min)
        g.setze('abs',           self._eb_abs)
        g.setze('runde',         self._eb_runde)
        g.setze('liste',         self._eb_liste)
        g.setze('woerterbuch',   self._eb_woerterbuch)
        g.setze('wörterbuch',    self._eb_woerterbuch)
        g.setze('menge',         self._eb_menge)
        g.setze('summe',         self._eb_summe)
        g.setze('alle',          self._eb_alle)
        g.setze('einige',        self._eb_einige)
        g.setze('aufzaehlen',    self._eb_aufzaehlen)
        g.setze('zippe',         self._eb_zippe)
        g.setze('tiefe_kopie',   self._eb_tiefe_kopie)
        g.setze('wahr',          True)
        g.setze('falsch',        False)
        g.setze('nichts',        None)

        for modulname, mitglieder in self._standardbibliothek().items():
            g.setze(modulname, DeutschNamensraum(modulname, mitglieder))

    def _standardbibliothek(self) -> dict:
        """Die nach Themen gruppierten Module.

        Zugriff wie bei einem geladenen Modul: mathe.wurzel(2), datei.lesen(pfad).
        Global bleibt nur das allgemeine Vokabular, das in jedem Programm vorkommt.
        """
        return {
            'mathe': {
                'pi': math.pi,
                'e': math.e,
                'wurzel': self._eb_wurzel,
                'sinus': self._eb_sinus,
                'kosinus': self._eb_kosinus,
                'tangens': self._eb_tangens,
                'logarithmus': self._eb_logarithmus,
                'exponential': self._eb_exponential,
                'boden': self._eb_boden,
                'decke': self._eb_decke,
                'ggt': self._eb_ggt,
                'kgv': self._eb_kgv,
                'vorzeichen': self._eb_vorzeichen,
            },
            'zufall': {
                'komma': self._eb_zufall,
                'zahl': self._eb_zufallszahl,
                'mische': self._eb_mische,
            },
            'statistik': {
                'mittelwert': self._eb_mittelwert,
                'median': self._eb_median,
                'stdabweichung': self._eb_stdabweichung,
            },
            'datei': {
                'lesen': self._eb_datei_lesen,
                'schreiben': self._eb_datei_schreiben,
                'anhaengen': self._eb_datei_anhaengen,
                'anhängen': self._eb_datei_anhaengen,
            },
            'pfad': {
                'existiert': self._eb_pfad_existiert,
                'dateien': self._eb_dateien_auflisten,
                'ordner_erstellen': self._eb_ordner_erstellen,
            },
            'json': {
                'lesen': self._eb_json_lesen,
                'schreiben': self._eb_json_schreiben,
            },
            'regex': {
                'passt_zu': self._eb_passt_zu,
                'ersetze': self._eb_regex_ersetze,
                'finde': self._eb_regex_finde,
                'finde_alle': self._eb_regex_finde_alle,
            },
            'zeit': {
                'jetzt': self._eb_jetzt,
                'formatieren': self._eb_datum_formatieren,
            },
            'kodierung': {
                'sha256': self._eb_hash_sha256,
                'base64_kodieren': self._eb_base64_kodieren,
                'base64_dekodieren': self._eb_base64_dekodieren,
            },
            'system': {
                'argumente': self._eb_kommandozeilen_argumente,
                'umgebungsvariable': self._eb_umgebungsvariable,
            },
        }

    def _eb_drucke(self, *args):
        print(' '.join(self._zu_text(a) for a in args))
        return None

    def _eb_eingabe(self, *args):
        return input(self._zu_text(args[0]) if args else '')

    def _eb_laenge(self, *args):
        self._pruefe_args('länge', args, 1)
        obj = args[0]
        if isinstance(obj, (list, dict, str, set, range)):
            return len(obj)
        raise TypeError(f"'länge' nicht unterstützt für {self._typname(obj)}")

    def _eb_typ(self, *args):
        self._pruefe_args('typ', args, 1)
        return self._typname(args[0])

    def _eb_ganzzahl(self, *args):
        self._pruefe_args('ganzzahl', args, 1)
        try:
            return int(args[0])
        except (ValueError, TypeError):
            raise ValueError(f"Kann '{args[0]}' nicht in Ganzzahl umwandeln")

    def _eb_kommazahl(self, *args):
        self._pruefe_args('kommazahl', args, 1)
        try:
            return float(args[0])
        except (ValueError, TypeError):
            raise ValueError(f"Kann '{args[0]}' nicht in Kommazahl umwandeln")

    def _eb_zeichenkette(self, *args):
        self._pruefe_args('zeichenkette', args, 1)
        return self._zu_text(args[0])

    def _eb_wahrheitswert(self, *args):
        self._pruefe_args('wahrheitswert', args, 1)
        return self._ist_wahr(args[0])

    def _eb_bereich(self, *args):
        if not 1 <= len(args) <= 3:
            raise TypeError("'bereich' erwartet 1–3 Argumente")
        grenzen = [self._ganzzahl_pruefen(a, 'bereich') for a in args]
        if len(grenzen) == 3 and grenzen[2] == 0:
            raise ValueError("'bereich' erwartet eine Schrittweite ungleich 0")
        # range ist faul: kein Speicher fuer die Elemente, dafuer Laenge, Index,
        # Schnitt und 'in' in konstanter Zeit. Mit liste(...) wird daraus eine Liste.
        return range(*grenzen)

    def _eb_sortiere(self, *args):
        self._pruefe_args('sortiere', args, 1)
        if not isinstance(args[0], _SEQUENZ_TYPEN):
            raise TypeError("'sortiere' erwartet eine Liste, Menge oder Bereich")
        return self._sortiert(list(args[0]))

    @staticmethod
    def _sortiert(liste, in_place=False):
        """Sortiert numerisch/lexikografisch, fällt bei gemischten Typen auf Text zurück."""
        try:
            ergebnis = sorted(liste)
        except TypeError:
            ergebnis = sorted(liste, key=str)
        if in_place:
            liste[:] = ergebnis
            return None
        return ergebnis

    def _index_von(self, obj, x, typname):
        if isinstance(obj, list) and self._hat_gleich_ueberladung(x):
            for i, element in enumerate(obj):
                if self._werte_gleich(x, element):
                    return i
            raise ValueError(f"'{self._zu_text(x)}' nicht gefunden in {typname}")
        try:
            return obj.index(x)
        except ValueError:
            raise ValueError(f"'{x}' nicht gefunden in {typname}")
        except TypeError:
            raise TypeError(f"'index_von' erwartet den gleichen Typ wie {typname}, bekam {self._typname(x)}")

    def _zaehle(self, obj, x, typname):
        if isinstance(obj, list) and self._hat_gleich_ueberladung(x):
            return sum(1 for element in obj if self._werte_gleich(x, element))
        try:
            return obj.count(x)
        except TypeError:
            raise TypeError(f"'zaehle' erwartet den gleichen Typ wie {typname}, bekam {self._typname(x)}")

    def _liste_einfuegen(self, obj, index, wert):
        try:
            obj.insert(int(index), wert)
        except (ValueError, TypeError):
            raise TypeError(f"'einfuegen' erwartet einen Ganzzahl-Index, bekam {self._typname(index)}")
        return None

    def _liste_erweitere(self, obj, andere):
        if not isinstance(andere, _SEQUENZ_TYPEN):
            raise TypeError(f"'erweitere' erwartet eine Liste, Menge oder Bereich, bekam {self._typname(andere)}")
        obj.extend(andere)
        return None

    def _liste_entferne(self, obj, index):
        if not obj:
            raise IndexError("'entferne' auf einer leeren Liste nicht möglich")
        if index is _OHNE_WERT:
            return obj.pop()
        try:
            i = int(index)
        except (ValueError, TypeError):
            raise TypeError(f"'entferne' erwartet einen Ganzzahl-Index, bekam {self._typname(index)}")
        try:
            return obj.pop(i)
        except IndexError:
            raise IndexError(f'Index {i} ist außerhalb des Bereichs')

    def _string_teile(self, obj, trenner):
        if trenner is _OHNE_WERT:
            return obj.split()
        if not isinstance(trenner, str):
            raise TypeError(f"'teile' erwartet eine Zeichenkette als Trenner, bekam {self._typname(trenner)}")
        if not trenner:
            raise ValueError("'teile' erwartet einen nicht-leeren Trenner")
        return obj.split(trenner)

    def _string_enthaelt(self, obj, x):
        if not isinstance(x, str):
            raise TypeError(f"'enthält' erwartet eine Zeichenkette, bekam {self._typname(x)}")
        return x in obj

    def _string_ersetze(self, obj, alt, neu):
        for wert in (alt, neu):
            if not isinstance(wert, str):
                raise TypeError(f"'ersetze' erwartet Zeichenketten, bekam {self._typname(wert)}")
        return obj.replace(alt, neu)

    def _string_praefix(self, obj, x, name):
        if not isinstance(x, str):
            raise TypeError(f"'{name}' erwartet eine Zeichenkette, bekam {self._typname(x)}")
        return obj.startswith(x) if name == 'beginnt_mit' else obj.endswith(x)

    def _string_wiederhole(self, obj, n):
        try:
            anzahl = int(n)
        except (ValueError, TypeError):
            raise TypeError(f"'wiederhole' erwartet eine Ganzzahl, bekam {self._typname(n)}")
        return obj * anzahl

    def _string_zahl(self, obj):
        try:
            return int(obj) if obj.lstrip('-').isdigit() else float(obj)
        except ValueError:
            raise ValueError(f"Kann '{obj}' nicht in eine Zahl umwandeln")

    def _enthaelt_hashbar(self, obj, x, typname):
        try:
            return x in obj
        except TypeError:
            raise TypeError(
                f"'enthält' erwartet einen hashbaren Wert für {typname}, bekam {self._typname(x)}"
            )

    def _woerterbuch_hole(self, obj, schluessel, standard):
        try:
            return obj.get(schluessel, standard)
        except TypeError:
            raise TypeError(
                f"'hole' erwartet einen hashbaren Schlüssel, bekam {self._typname(schluessel)}"
            )

    def _eb_anhaengen(self, *args):
        self._pruefe_args('anhängen', args, 2)
        liste, elem = args
        if not isinstance(liste, list):
            raise TypeError("Erstes Argument von 'anhängen' muss eine Liste sein")
        liste.append(elem)
        return None

    def _eb_entferne(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("'entferne' erwartet 1–2 Argumente")
        liste = args[0]
        if not isinstance(liste, list):
            raise TypeError("Erstes Argument von 'entferne' muss eine Liste sein")
        return self._liste_entferne(liste, args[1] if len(args) == 2 else _OHNE_WERT)

    def _eb_umkehren(self, *args):
        self._pruefe_args('umkehren', args, 1)
        if not isinstance(args[0], list):
            raise TypeError("'umkehren' erwartet eine Liste")
        args[0].reverse()
        return None

    def _eb_verbinde(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("'verbinde' erwartet 1–2 Argumente")
        liste = args[0]
        trenn = self._zu_text(args[1]) if len(args) == 2 else ''
        if not isinstance(liste, list):
            raise TypeError("Erstes Argument von 'verbinde' muss eine Liste sein")
        return trenn.join(self._zu_text(e) for e in liste)

    def _eb_max(self, *args):
        return self._eb_extremum('max', max, args)

    def _eb_min(self, *args):
        return self._eb_extremum('min', min, args)

    def _eb_extremum(self, name, fn, args):
        if not args:
            raise TypeError(f"'{name}' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], _SEQUENZ_TYPEN) else list(args)
        if not werte:
            raise ValueError(f"'{name}' erwartet eine nicht-leere Liste, Menge oder Bereich")
        try:
            return fn(werte)
        except TypeError:
            raise TypeError(f"'{name}' kann Werte gemischter Typen nicht vergleichen")

    def _eb_abs(self, *args):
        self._pruefe_args('abs', args, 1)
        return abs(self._zahl_pruefen(args[0], 'abs'))

    def _eb_runde(self, *args):
        if len(args) not in (1, 2): raise TypeError("'runde' erwartet 1–2 Argumente")
        zahl = self._zahl_pruefen(args[0], 'runde')
        stellen = self._ganzzahl_pruefen(args[1], 'runde') if len(args) == 2 else 0
        if stellen > 0:
            return round(float(zahl), stellen)
        # stellen <= 0 rundet auf ganze Zehner/Hunderter/... – Ergebnis ist eine Ganzzahl
        return int(round(zahl, stellen))

    def _eb_liste(self, *args):
        self._pruefe_args('liste', args, 1)
        try:
            return list(args[0])
        except TypeError:
            raise TypeError(f"'{self._typname(args[0])}' kann nicht in Liste umgewandelt werden")

    def _eb_wurzel(self, *args):
        self._pruefe_args('mathe.wurzel', args, 1)
        try:
            return math.sqrt(args[0])
        except ValueError:
            raise ValueError(f"'mathe.wurzel' nicht definiert für negative Zahl {args[0]}")
        except TypeError:
            raise TypeError(f"'mathe.wurzel' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_sinus(self, *args):
        self._pruefe_args('mathe.sinus', args, 1)
        try:
            return math.sin(args[0])
        except TypeError:
            raise TypeError(f"'mathe.sinus' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_kosinus(self, *args):
        self._pruefe_args('mathe.kosinus', args, 1)
        try:
            return math.cos(args[0])
        except TypeError:
            raise TypeError(f"'mathe.kosinus' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_tangens(self, *args):
        self._pruefe_args('mathe.tangens', args, 1)
        try:
            return math.tan(args[0])
        except TypeError:
            raise TypeError(f"'mathe.tangens' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_exponential(self, *args):
        self._pruefe_args('mathe.exponential', args, 1)
        try:
            return math.exp(args[0])
        except TypeError:
            raise TypeError(f"'mathe.exponential' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_ggt(self, *args):
        if not args:
            raise TypeError("'mathe.ggt' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], _SEQUENZ_TYPEN) else list(args)
        try:
            return math.gcd(*[int(w) for w in werte])
        except (TypeError, ValueError):
            raise TypeError("'mathe.ggt' erwartet Ganzzahlen")

    def _eb_kgv(self, *args):
        if not args:
            raise TypeError("'mathe.kgv' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], _SEQUENZ_TYPEN) else list(args)
        try:
            return math.lcm(*[int(w) for w in werte])
        except (TypeError, ValueError):
            raise TypeError("'mathe.kgv' erwartet Ganzzahlen")

    def _eb_vorzeichen(self, *args):
        self._pruefe_args('mathe.vorzeichen', args, 1)
        try:
            wert = args[0]
            return (wert > 0) - (wert < 0)
        except TypeError:
            raise TypeError(f"'mathe.vorzeichen' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_logarithmus(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("'mathe.logarithmus' erwartet 1–2 Argumente")
        self._zahl_pruefen(args[0], 'mathe.logarithmus')
        if len(args) == 2:
            basis = self._zahl_pruefen(args[1], 'mathe.logarithmus')
            if basis <= 0 or basis == 1:
                raise ValueError(
                    f"'mathe.logarithmus' erwartet eine Basis größer 0 und ungleich 1, "
                    f'bekam {self._zu_text(basis)}'
                )
        try:
            return math.log(args[0]) if len(args) == 1 else math.log(args[0], args[1])
        except ValueError:
            raise ValueError(f"'mathe.logarithmus' nicht definiert für {args[0]}")

    def _eb_datei_lesen(self, *args):
        self._pruefe_args('datei.lesen', args, 1)
        pfad = self._zu_text(args[0])
        try:
            with open(self._pfad_aufloesen(pfad), 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Datei nicht gefunden: '{pfad}'")
        except IsADirectoryError:
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Lesen von '{pfad}'")
        except UnicodeDecodeError:
            raise ValueError(f"'{pfad}' ist keine gültige UTF-8-Textdatei")

    def _eb_datei_schreiben(self, *args):
        self._pruefe_args('datei.schreiben', args, 2)
        pfad, inhalt = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            with open(self._pfad_aufloesen(pfad), 'w', encoding='utf-8') as f:
                f.write(inhalt)
        except FileNotFoundError:
            raise FileNotFoundError(f"Verzeichnis für '{pfad}' existiert nicht")
        except IsADirectoryError:
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Schreiben von '{pfad}'")
        return None

    def _eb_datei_anhaengen(self, *args):
        self._pruefe_args('datei.anhängen', args, 2)
        pfad, inhalt = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            with open(self._pfad_aufloesen(pfad), 'a', encoding='utf-8') as f:
                f.write(inhalt)
        except FileNotFoundError:
            raise FileNotFoundError(f"Verzeichnis für '{pfad}' existiert nicht")
        except IsADirectoryError:
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Schreiben von '{pfad}'")
        return None

    def _eb_boden(self, *args):
        self._pruefe_args('mathe.boden', args, 1)
        try:
            return math.floor(args[0])
        except TypeError:
            raise TypeError(f"'mathe.boden' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_decke(self, *args):
        self._pruefe_args('mathe.decke', args, 1)
        try:
            return math.ceil(args[0])
        except TypeError:
            raise TypeError(f"'mathe.decke' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_zufall(self, *args):
        self._pruefe_args('zufall.komma', args, 0)
        return random.random()

    def _eb_zufallszahl(self, *args):
        self._pruefe_args('zufall.zahl', args, 2)
        try:
            lo, hi = int(args[0]), int(args[1])
        except (ValueError, TypeError):
            raise TypeError("'zufall.zahl' erwartet zwei Ganzzahlen")
        if lo > hi:
            raise ValueError(f"'zufall.zahl' erwartet erstes Argument <= zweites, bekam {lo} > {hi}")
        return random.randint(lo, hi)

    def _eb_mische(self, *args):
        self._pruefe_args('zufall.mische', args, 1)
        if not isinstance(args[0], list):
            raise TypeError("'zufall.mische' erwartet eine Liste")
        random.shuffle(args[0])
        return None

    def _eb_summe(self, *args):
        werte = args[0] if len(args) == 1 and isinstance(args[0], _SEQUENZ_TYPEN) else list(args)
        try:
            return sum(werte)
        except TypeError:
            raise TypeError("'summe' erwartet Zahlen")

    def _eb_alle(self, *args):
        self._pruefe_args('alle', args, 1)
        if not isinstance(args[0], _SEQUENZ_TYPEN):
            raise TypeError("'alle' erwartet eine Liste, Menge oder Bereich")
        return all(self._ist_wahr(e) for e in args[0])

    def _eb_einige(self, *args):
        self._pruefe_args('einige', args, 1)
        if not isinstance(args[0], _SEQUENZ_TYPEN):
            raise TypeError("'einige' erwartet eine Liste, Menge oder Bereich")
        return any(self._ist_wahr(e) for e in args[0])

    def _eb_aufzaehlen(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("'aufzaehlen' erwartet 1–2 Argumente")
        if not isinstance(args[0], _SEQUENZ_TYPEN):
            raise TypeError("'aufzaehlen' erwartet eine Liste, Menge oder Bereich")
        start = self._ganzzahl_pruefen(args[1], 'aufzaehlen') if len(args) == 2 else 0
        return [[i, e] for i, e in enumerate(args[0], start=start)]

    def _eb_zippe(self, *args):
        if len(args) < 1:
            raise TypeError("'zippe' erwartet mindestens 1 Argument")
        for a in args:
            if not isinstance(a, (list, str, range)):
                raise TypeError("'zippe' erwartet Listen, Zeichenketten oder Bereiche")
        return [list(t) for t in zip(*args)]

    def _eb_json_lesen(self, *args):
        self._pruefe_args('json.lesen', args, 1)
        pfad = self._zu_text(args[0])
        try:
            with open(self._pfad_aufloesen(pfad), 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Datei nicht gefunden: '{pfad}'")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ungültiges JSON in '{pfad}': {e}")

    def _eb_json_schreiben(self, *args):
        self._pruefe_args('json.schreiben', args, 2)
        pfad, wert = self._zu_text(args[0]), args[1]

        def _konvertiere(o):
            if isinstance(o, set):
                return self._sortiert(list(o))
            raise TypeError(f"'{self._typname(o)}' kann nicht als JSON gespeichert werden")

        try:
            with open(self._pfad_aufloesen(pfad), 'w', encoding='utf-8') as f:
                json.dump(wert, f, default=_konvertiere, ensure_ascii=False, indent=2)
        except FileNotFoundError:
            raise FileNotFoundError(f"Verzeichnis für '{pfad}' existiert nicht")
        except IsADirectoryError:
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Schreiben von '{pfad}'")
        return None

    def _eb_kommandozeilen_argumente(self, *args):
        self._pruefe_args('system.argumente', args, 0)
        return list(self._cli_argumente)

    def _eb_passt_zu(self, *args):
        self._pruefe_args('regex.passt_zu', args, 2)
        muster, text = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            return re.search(muster, text) is not None
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")

    def _eb_regex_ersetze(self, *args):
        self._pruefe_args('regex.ersetze', args, 3)
        muster, ersatz, text = (self._zu_text(a) for a in args)
        try:
            return re.sub(muster, ersatz, text)
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")

    def _eb_regex_finde(self, *args):
        self._pruefe_args('regex.finde', args, 2)
        muster, text = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            treffer = re.search(muster, text)
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")
        return treffer.group(0) if treffer else None

    def _eb_regex_finde_alle(self, *args):
        self._pruefe_args('regex.finde_alle', args, 2)
        muster, text = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            treffer = re.findall(muster, text)
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")
        return [list(t) if isinstance(t, tuple) else t for t in treffer]

    def _eb_jetzt(self, *args):
        self._pruefe_args('zeit.jetzt', args, 0)
        return time.time()

    def _eb_datum_formatieren(self, *args):
        self._pruefe_args('zeit.formatieren', args, 2)
        zeitstempel, format_str = args[0], self._zu_text(args[1])
        self._zahl_pruefen(zeitstempel, 'zeit.formatieren')
        try:
            return datetime.fromtimestamp(zeitstempel).strftime(format_str)
        except (ValueError, OSError, OverflowError):
            raise ValueError(
                f"Ungültiger Zeitstempel für 'zeit.formatieren': {self._zu_text(zeitstempel)}"
            )

    def _eb_mittelwert(self, *args):
        self._pruefe_args('statistik.mittelwert', args, 1)
        if not isinstance(args[0], _SEQUENZ_TYPEN):
            raise TypeError("'statistik.mittelwert' erwartet eine Liste, Menge oder Bereich")
        try:
            return statistics.mean(args[0])
        except statistics.StatisticsError:
            raise ValueError("'statistik.mittelwert' erwartet eine nicht-leere Liste")

    def _eb_median(self, *args):
        self._pruefe_args('statistik.median', args, 1)
        if not isinstance(args[0], _SEQUENZ_TYPEN):
            raise TypeError("'statistik.median' erwartet eine Liste, Menge oder Bereich")
        try:
            return statistics.median(args[0])
        except statistics.StatisticsError:
            raise ValueError("'statistik.median' erwartet eine nicht-leere Liste")

    def _eb_stdabweichung(self, *args):
        self._pruefe_args('statistik.stdabweichung', args, 1)
        if not isinstance(args[0], _SEQUENZ_TYPEN):
            raise TypeError("'statistik.stdabweichung' erwartet eine Liste, Menge oder Bereich")
        try:
            return statistics.pstdev(args[0])
        except statistics.StatisticsError:
            raise ValueError("'statistik.stdabweichung' erwartet eine nicht-leere Liste")

    def _eb_tiefe_kopie(self, *args):
        self._pruefe_args('tiefe_kopie', args, 1)
        return self._tiefe_kopie_wert(args[0])

    def _tiefe_kopie_wert(self, wert):
        if isinstance(wert, list):
            return [self._tiefe_kopie_wert(e) for e in wert]
        if isinstance(wert, dict):
            return {self._tiefe_kopie_wert(k): self._tiefe_kopie_wert(v) for k, v in wert.items()}
        if isinstance(wert, set):
            return {self._tiefe_kopie_wert(e) for e in wert}
        if isinstance(wert, DeutschInstanz):
            neu = DeutschInstanz(wert.klasse)
            neu.attribute = {k: self._tiefe_kopie_wert(v) for k, v in wert.attribute.items()}
            return neu
        return wert  # Zahlen, Zeichenketten, Wahrheitswerte, Nichts, Funktionen: unveränderlich/geteilt

    def _eb_umgebungsvariable(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("'system.umgebungsvariable' erwartet 1–2 Argumente")
        name = self._zu_text(args[0])
        if len(args) == 2:
            return os.environ.get(name, args[1])
        return os.environ.get(name)

    def _eb_pfad_existiert(self, *args):
        self._pruefe_args('pfad.existiert', args, 1)
        return os.path.exists(self._pfad_aufloesen(self._zu_text(args[0])))

    def _eb_dateien_auflisten(self, *args):
        self._pruefe_args('pfad.dateien', args, 1)
        pfad = self._zu_text(args[0])
        try:
            return sorted(os.listdir(self._pfad_aufloesen(pfad)))
        except FileNotFoundError:
            raise FileNotFoundError(f"Ordner nicht gefunden: '{pfad}'")
        except NotADirectoryError:
            raise NotADirectoryError(f"'{pfad}' ist kein Ordner")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Lesen von '{pfad}'")

    def _eb_ordner_erstellen(self, *args):
        self._pruefe_args('pfad.ordner_erstellen', args, 1)
        pfad = self._zu_text(args[0])
        try:
            os.makedirs(self._pfad_aufloesen(pfad), exist_ok=True)
        except FileExistsError:
            raise FileExistsError(f"'{pfad}' existiert bereits als Datei, kann nicht als Ordner erstellt werden")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Erstellen von '{pfad}'")
        return None

    def _eb_hash_sha256(self, *args):
        self._pruefe_args('kodierung.sha256', args, 1)
        return hashlib.sha256(self._zu_text(args[0]).encode('utf-8')).hexdigest()

    def _eb_base64_kodieren(self, *args):
        self._pruefe_args('kodierung.base64_kodieren', args, 1)
        return base64.b64encode(self._zu_text(args[0]).encode('utf-8')).decode('ascii')

    def _eb_base64_dekodieren(self, *args):
        self._pruefe_args('kodierung.base64_dekodieren', args, 1)
        text = self._zu_text(args[0])
        try:
            return base64.b64decode(text, validate=True).decode('utf-8')
        except Exception:
            raise ValueError(f"'{text}' ist kein gültiger Base64-Text")

    def _eb_woerterbuch(self, *args):
        self._pruefe_args('wörterbuch', args, 1)
        obj = args[0]
        if isinstance(obj, list):
            return {self._zu_text(p[0]): p[1] for p in obj if isinstance(p, list) and len(p) == 2}
        raise TypeError(f"'wörterbuch' erwartet eine Liste von [schlüssel, wert] Paaren")

    def _eb_menge(self, *args):
        if len(args) == 0:
            return set()
        self._pruefe_args('menge', args, 1)
        try:
            return set(args[0])
        except TypeError:
            raise TypeError(f"'{self._typname(args[0])}' kann nicht in Menge umgewandelt werden")

    @staticmethod
    def _menge_hinzufuegen(obj, x):
        try:
            obj.add(x)
        except TypeError:
            raise TypeError('Mengen-Elemente müssen hashbar sein (keine Listen/Wörterbücher)')
        return None

    @staticmethod
    def _menge_entfernen(obj, x):
        try:
            obj.remove(x)
        except TypeError:
            raise TypeError('Mengen-Elemente müssen hashbar sein (keine Listen/Wörterbücher)')
        except KeyError:
            raise SchluesselFehler(f"'{x}' ist nicht in der Menge enthalten")
        return None

    def _menge_op(self, a, b, name, fn):
        if not isinstance(b, set):
            raise TypeError(f"'{name}' erwartet eine Menge, bekam {self._typname(b)}")
        return fn(a, b)

    # ------------------------------------------------------------ Hilfsmeth.

    @staticmethod
    def _pruefe_args(name, args, n):
        if len(args) != n:
            raise TypeError(f"'{name}' erwartet {n} Argument(e), bekam {len(args)}")

    def _zahl_pruefen(self, wert, funktion: str):
        """Stellt sicher, dass ein Argument eine Zahl ist – sonst käme Pythons rohe Meldung."""
        if not isinstance(wert, (int, float)):
            raise TypeError(f"'{funktion}' erwartet eine Zahl, bekam {self._typname(wert)}")
        return wert

    def _ganzzahl_pruefen(self, wert, funktion: str):
        if not isinstance(wert, (int, float)):
            raise TypeError(f"'{funktion}' erwartet eine Ganzzahl, bekam {self._typname(wert)}")
        return int(wert)

    def _typname(self, wert) -> str:
        if wert is None:              return 'Nichts'
        if isinstance(wert, bool):    return 'Wahrheitswert'
        if isinstance(wert, int):     return 'Ganzzahl'
        if isinstance(wert, float):   return 'Kommazahl'
        if isinstance(wert, str):     return 'Zeichenkette'
        if isinstance(wert, list):    return 'Liste'
        if isinstance(wert, dict):    return 'Woerterbuch'
        if isinstance(wert, set):     return 'Menge'
        if isinstance(wert, range):   return 'Bereich'
        if isinstance(wert, DeutschInstanz): return wert.klasse.name
        if isinstance(wert, DeutschKlasse):  return f'Klasse({wert.name})'
        if isinstance(wert, DeutschNamensraum): return f'Namensraum({wert.name})'
        if isinstance(wert, (DeutschFunktion, GebundeneMethode, type(lambda: None))): return 'Funktion'
        if callable(wert):            return 'Funktion'
        return type(wert).__name__

    def _zu_text(self, wert) -> str:
        if wert is None:    return 'nichts'
        if wert is True:    return 'wahr'
        if wert is False:   return 'falsch'
        if isinstance(wert, float):
            if wert != wert or wert in (float('inf'), float('-inf')):  # NaN / Unendlich
                return str(wert)
            return str(int(wert)) if wert == int(wert) and abs(wert) < 1e15 else str(wert)
        if isinstance(wert, list):
            return '[' + ', '.join(self._zu_text(e) for e in wert) + ']'
        if isinstance(wert, dict):
            teile = ', '.join(f'{self._zu_text(k)}: {self._zu_text(v)}' for k, v in wert.items())
            return '{' + teile + '}'
        if isinstance(wert, range):
            if wert.step == 1:
                return f'bereich({wert.start}, {wert.stop})'
            return f'bereich({wert.start}, {wert.stop}, {wert.step})'
        if isinstance(wert, set):
            if not wert:
                return 'menge()'
            return '{' + ', '.join(self._zu_text(e) for e in self._sortiert(list(wert))) + '}'
        if isinstance(wert, DeutschInstanz):
            m = wert.klasse.suche_methode('__text__')
            if m:
                return str(self._funktion_aufrufen(m, [wert]))
            return repr(wert)
        return str(wert)

    def _ist_wahr(self, wert) -> bool:
        if wert is None or wert is False: return False
        if isinstance(wert, (int, float)): return wert != 0
        if isinstance(wert, (str, list, dict, set, range)): return len(wert) > 0
        return True

    # ------------------------------------------------------------ Ausführen

    def ausfuehren(self, knoten, umgebung=None):
        if umgebung is None:
            umgebung = self.global_umgebung
            self._letzter_aufruf_stack = []
        return self._besuche(knoten, umgebung)

    def _besuche(self, knoten, umgebung):
        methode = self._dispatch.get(type(knoten))
        if methode is None:
            raise NotImplementedError(f'Kein Besucher für {type(knoten).__name__}')
        return methode(knoten, umgebung)

    # ---------------------------------------------------------- Besucher

    def _besuche_Programm(self, k, u):
        ergebnis = None
        for anw in k.anweisungen:
            ergebnis = self._besuche_anweisung(anw, u)
        return ergebnis

    def _besuche_Block(self, k, u):
        block_u = Umgebung(u)
        ergebnis = None
        for anw in k.anweisungen:
            ergebnis = self._besuche_anweisung(anw, block_u)
        return ergebnis

    def _besuche_anweisung(self, anw, u):
        """Führt eine Anweisung aus und reichert Laufzeitfehler mit ihrer Zeile an."""
        zeile = getattr(anw, 'zeile', None)
        if zeile is not None:
            self._aktuelle_zeile = zeile
        try:
            return self._besuche(anw, u)
        except _KONTROLLSIGNALE:
            raise
        except SyntaxError:
            raise
        except Exception as e:
            if isinstance(e, AusnahmeFehler):
                if zeile is not None and 'Zeile' not in str(e):
                    self._letzter_aufruf_stack = list(self._aufruf_stack)
                    raise AusnahmeFehler(e.wert, nachricht=f'Zeile {zeile}: {e}') from e
                raise
            if zeile is not None and 'Zeile' not in str(e):
                self._letzter_aufruf_stack = list(self._aufruf_stack)
                raise type(e)(f'Zeile {zeile}: {e}') from e
            raise

    # Literale
    def _besuche_Ganzzahl(self,     k, u): return k.wert
    def _besuche_Kommazahl(self,    k, u): return k.wert
    def _besuche_Zeichenkette(self, k, u): return k.wert
    def _besuche_Wahrheitswert(self,k, u): return k.wert
    def _besuche_Nichts(self,       k, u): return None

    def _besuche_InterpolierteZeichenkette(self, k, u):
        teile = []
        for teil in k.teile:
            if isinstance(teil, ast.FormatierterAusdruck):
                wert = self._besuche(teil.ausdruck, u)
                try:
                    teile.append(format(wert, teil.format_spec))
                except (ValueError, TypeError):
                    raise ValueError(
                        f"Ungültiges Format '{teil.format_spec}' für {self._typname(wert)}"
                    )
            else:
                teile.append(self._zu_text(self._besuche(teil, u)))
        return ''.join(teile)

    def _besuche_Bezeichner(self, k, u):
        return u.hole(k.name)

    def _besuche_Liste(self, k, u):
        return [self._besuche(e, u) for e in k.elemente]

    def _besuche_Woerterbuch(self, k, u):
        ergebnis = {}
        for schluessel_knoten, wert_knoten in k.paare:
            schluessel = self._besuche(schluessel_knoten, u)
            wert = self._besuche(wert_knoten, u)
            try:
                ergebnis[schluessel] = wert
            except TypeError:
                raise TypeError(
                    'Wörterbuch-Schlüssel müssen hashbar sein (keine Listen/Wörterbücher), '
                    f'bekam {self._typname(schluessel)}'
                )
        return ergebnis

    def _besuche_MengenLiteral(self, k, u):
        elemente = [self._besuche(e, u) for e in k.elemente]
        try:
            return set(elemente)
        except TypeError:
            raise TypeError('Mengen-Elemente müssen hashbar sein (keine Listen/Wörterbücher)')

    def _abstraktions_umgebungen(self, klauseln, u):
        """Liefert für jede Kombination der Klauseln eine Umgebung mit den Bindungen.

        Klauseln werden von links nach rechts abgearbeitet; eine spätere sieht die
        Variablen der früheren."""
        def durchlaufen(index, umgebung):
            if index == len(klauseln):
                yield umgebung
                return
            variable, iterable_knoten, bedingung = klauseln[index]
            iterable = self._pruefe_iterierbar(
                self._besuche(iterable_knoten, umgebung), 'Abstraktion')
            for elem in iterable:
                iter_u = Umgebung(umgebung)
                self._schleifenvariable_binden(variable, elem, iter_u)
                if bedingung is not None and not self._ist_wahr(self._besuche(bedingung, iter_u)):
                    continue
                yield from durchlaufen(index + 1, iter_u)

        return durchlaufen(0, u)

    def _besuche_ListenAusdruck(self, k, u):
        return [self._besuche(k.ausdruck, iter_u)
                for iter_u in self._abstraktions_umgebungen(k.klauseln, u)]

    def _besuche_MengenAusdruck(self, k, u):
        ergebnis = set()
        for iter_u in self._abstraktions_umgebungen(k.klauseln, u):
            wert = self._besuche(k.ausdruck, iter_u)
            try:
                ergebnis.add(wert)
            except TypeError:
                raise TypeError(
                    'Mengen-Elemente müssen hashbar sein (keine Listen/Wörterbücher), '
                    f'bekam {self._typname(wert)}'
                )
        return ergebnis

    def _besuche_WoerterbuchAusdruck(self, k, u):
        ergebnis = {}
        for iter_u in self._abstraktions_umgebungen(k.klauseln, u):
            schluessel = self._besuche(k.schluessel, iter_u)
            wert = self._besuche(k.wert, iter_u)
            try:
                ergebnis[schluessel] = wert
            except TypeError:
                raise TypeError(
                    'Wörterbuch-Schlüssel müssen hashbar sein (keine Listen/Wörterbücher), '
                    f'bekam {self._typname(schluessel)}'
                )
        return ergebnis

    def _pruefe_iterierbar(self, wert, kontext: str):
        if not isinstance(wert, (list, str, dict, set, range)):
            raise TypeError(
                f'{kontext} erwartet etwas Iterierbares (Liste, Zeichenkette, Wörterbuch, '
                f'Menge oder Bereich), bekam {self._typname(wert)}'
            )
        return wert

    def _schleifenvariable_binden(self, variable, elem, u):
        """variable: str (einfache Bindung) | list[str] (Destrukturierung)."""
        if isinstance(variable, list):
            if not isinstance(elem, (list, tuple)):
                raise TypeError(f"Destrukturierung erwartet eine Liste, bekam {self._typname(elem)}")
            if len(elem) != len(variable):
                raise TypeError(
                    f"Destrukturierung erwartet {len(variable)} Werte, bekam {len(elem)}"
                )
            for name, wert in zip(variable, elem):
                u.setze(name, wert)
        else:
            u.setze(variable, elem)

    # Typ-Hinweise
    def _pruefe_typ(self, wert, typhinweis, kontext_msg, u):
        if typhinweis is None:
            return
        primitive = {
            'Ganzzahl':      lambda w: isinstance(w, int) and not isinstance(w, bool),
            'Kommazahl':     lambda w: isinstance(w, (int, float)) and not isinstance(w, bool),
            'Zeichenkette':  lambda w: isinstance(w, str),
            'Wahrheitswert': lambda w: isinstance(w, bool),
            'Liste':         lambda w: isinstance(w, list),
            'Woerterbuch':   lambda w: isinstance(w, dict),
            'Wörterbuch':    lambda w: isinstance(w, dict),
            'Menge':         lambda w: isinstance(w, set),
            'Bereich':       lambda w: isinstance(w, range),
            'Nichts':        lambda w: w is None,
            'Funktion':      lambda w: isinstance(w, (DeutschFunktion, GebundeneMethode)) or callable(w),
        }
        if typhinweis in primitive:
            ok = primitive[typhinweis](wert)
        elif u.existiert(typhinweis) and isinstance(u.hole(typhinweis), DeutschKlasse):
            ziel = u.hole(typhinweis)
            ok = isinstance(wert, DeutschInstanz) and self._ist_instanz_von(wert.klasse, ziel)
        else:
            raise TypeError(f"Unbekannter Typ-Hinweis: '{typhinweis}'")
        if not ok:
            raise TypeError(f"{kontext_msg}: erwartet Typ '{typhinweis}', bekam {self._typname(wert)}")

    def _ist_instanz_von(self, klasse, ziel):
        if klasse is ziel:
            return True
        return any(self._ist_instanz_von(e, ziel) for e in klasse.eltern)

    # Variablen
    def _besuche_VariableDeklaration(self, k, u):
        wert = self._besuche(k.wert, u)
        self._pruefe_typ(wert, k.typhinweis, f"Variable '{k.name}'", u)
        if k.name in u.konstanten:
            raise TypeError(f"'{k.name}' ist bereits als Konstante in diesem Geltungsbereich deklariert")
        if k.ist_konstante:
            u.setze_konstante(k.name, wert)
        else:
            u.setze(k.name, wert)
        return wert

    def _besuche_DestrukturierendeDeklaration(self, k, u):
        wert = self._besuche(k.wert, u)
        if not isinstance(wert, (list, tuple)):
            raise TypeError(f"Destrukturierung erwartet eine Liste, bekam {self._typname(wert)}")
        if len(wert) != len(k.namen):
            raise TypeError(
                f"Destrukturierung erwartet {len(k.namen)} Werte, bekam {len(wert)}"
            )
        for name, einzelwert in zip(k.namen, wert):
            u.setze(name, einzelwert)
        return wert

    def _besuche_Zuweisung(self, k, u):
        wert = self._besuche(k.wert, u)
        self._ziel_setzen(k.ziel, wert, u)
        return wert

    def _besuche_VerbundZuweisung(self, k, u):
        alter_wert = self._besuche(k.ziel, u)
        delta = self._besuche(k.wert, u)
        neuer_wert = self._binaerer_operator(k.operator, alter_wert, delta)
        self._ziel_setzen(k.ziel, neuer_wert, u)
        return neuer_wert

    def _ziel_setzen(self, ziel, wert, u):
        if isinstance(ziel, ast.Bezeichner):
            # Zuweisung deklariert nicht – 'weise_zu' meldet unbekannte Namen als Fehler,
            # damit ein Tippfehler keine stille neue Variable anlegt
            u.weise_zu(ziel.name, wert)
        elif isinstance(ziel, ast.AttributZugriff):
            obj = self._besuche(ziel.objekt, u)
            if isinstance(obj, DeutschInstanz):
                # Eine Klassenkonstante darf auch nicht pro Instanz überdeckt werden,
                # sonst liefe 'dies.MAX = 1' am Konstanten-Versprechen vorbei
                besitzer = obj.klasse.konstante_deklaration(ziel.attribut)
                if besitzer is not None:
                    raise TypeError(
                        f"'{ziel.attribut}' ist eine Konstante der Klasse '{besitzer.name}' "
                        'und kann nicht pro Instanz überdeckt werden'
                    )
                obj.setze_attribut(ziel.attribut, wert)
            elif isinstance(obj, DeutschKlasse):
                besitzer = obj.konstante_deklaration(ziel.attribut)
                if besitzer is not None:
                    raise TypeError(
                        f"'{ziel.attribut}' ist eine Konstante der Klasse '{besitzer.name}' "
                        'und kann nicht neu zugewiesen werden'
                    )
                obj.klassenattribute[ziel.attribut] = wert
            else:
                raise TypeError(f"Kann Attribut von '{self._typname(obj)}' nicht setzen")
        elif isinstance(ziel, ast.IndexZugriff):
            if isinstance(ziel.index, ast.SliceAusdruck):
                raise TypeError('Slice-Zuweisung wird nicht unterstützt')
            obj = self._besuche(ziel.objekt, u)
            if isinstance(obj, str):
                raise TypeError('Zeichenketten sind unveränderlich – Index-Zuweisung nicht möglich')
            if isinstance(obj, range):
                raise TypeError('Bereiche sind unveränderlich – Index-Zuweisung nicht möglich')
            idx = self._besuche(ziel.index, u)
            try:
                obj[idx] = wert
            except IndexError:
                raise IndexError(f'Index {idx} ist außerhalb des Bereichs')
            except TypeError:
                raise TypeError(f"Ungültiger Index-Typ '{self._typname(idx)}' für {self._typname(obj)}")

    # Operationen
    def _besuche_BinaereOperation(self, k, u):
        # Kurzschluss
        if k.operator == 'und':
            l = self._besuche(k.links, u)
            return l if not self._ist_wahr(l) else self._besuche(k.rechts, u)
        if k.operator == 'oder':
            l = self._besuche(k.links, u)
            return l if self._ist_wahr(l) else self._besuche(k.rechts, u)

        l = self._besuche(k.links, u)
        r = self._besuche(k.rechts, u)
        return self._binaerer_operator(k.operator, l, r)

    def _binaerer_operator(self, op, l, r):
        if isinstance(l, DeutschInstanz):
            methoden_name = _OPERATOR_METHODEN.get(op)
            if methoden_name is not None:
                m = l.klasse.suche_methode(methoden_name)
                if m is not None:
                    return self._funktion_aufrufen(m, [l, r])
        try:
            if op == '+':
                if isinstance(l, str) or isinstance(r, str):
                    return self._zu_text(l) + self._zu_text(r)
                return l + r
            if op == '-':   return l - r
            if op == '*':   return l * r
            if op == '/':
                if r == 0: raise ZeroDivisionError('Division durch Null')
                return l / r
            if op == '//':
                if r == 0: raise ZeroDivisionError('Ganzzahldivision durch Null')
                return l // r
            if op == '**':
                if l == 0 and isinstance(r, (int, float)) and r < 0:
                    raise ZeroDivisionError('Null kann nicht mit negativem Exponenten potenziert werden')
                return l ** r
            if op == '%':
                if r == 0: raise ZeroDivisionError('Modulo durch Null')
                return l % r
            if op == '==':  return l == r
            if op == '!=':  return l != r
            if op == '<':   return l < r
            if op == '>':   return l > r
            if op == '<=':  return l <= r
            if op == '>=':  return l >= r
            if op == 'in':  return self._enthalten_in(l, r)
            if op == 'nicht in': return not self._enthalten_in(l, r)
        except TypeError:
            raise TypeError(
                f"Operator '{op}' nicht unterstützt für {self._typname(l)} und {self._typname(r)}"
            )
        raise RuntimeError(f'Unbekannter Operator: {op!r}')

    def _hat_gleich_ueberladung(self, wert) -> bool:
        return (isinstance(wert, DeutschInstanz)
                and wert.klasse.suche_methode('__gleich__') is not None)

    def _werte_gleich(self, a, b) -> bool:
        """Gleichheit wie beim '=='-Operator, inklusive überladener __gleich__-Methode."""
        if self._hat_gleich_ueberladung(a):
            return self._ist_wahr(self._binaerer_operator('==', a, b))
        return a == b

    def _enthalten_in(self, wert, container):
        """Mitgliedschaft für 'in' und '.enthält()'. In Listen zählt eine überladene
        __gleich__-Methode des gesuchten Werts (er ist der linke Operand). Mengen und
        Wörterbücher bleiben hash-basiert – dafür bräuchte es zusätzlich __hash__."""
        if isinstance(container, list) and self._hat_gleich_ueberladung(wert):
            return any(self._werte_gleich(wert, element) for element in container)
        return wert in container

    def _besuche_UnaereOperation(self, k, u):
        val = self._besuche(k.operand, u)
        if k.operator == '-':
            try:
                return -val
            except TypeError:
                raise TypeError(f"Operator '-' nicht unterstützt für {self._typname(val)}")
        if k.operator == 'nicht': return not self._ist_wahr(val)
        raise RuntimeError(f'Unbekannter unärer Operator: {k.operator!r}')

    def _besuche_VergleichsKette(self, k, u):
        links_wert = self._besuche(k.operanden[0], u)
        for i, op in enumerate(k.operatoren):
            rechts_wert = self._besuche(k.operanden[i + 1], u)
            if not self._ist_wahr(self._binaerer_operator(op, links_wert, rechts_wert)):
                return False
            links_wert = rechts_wert
        return True

    def _besuche_TernaerAusdruck(self, k, u):
        if self._ist_wahr(self._besuche(k.bedingung, u)):
            return self._besuche(k.dann_wert, u)
        return self._besuche(k.sonst_wert, u)

    # Kontrollfluss
    def _besuche_WennAnweisung(self, k, u):
        if self._ist_wahr(self._besuche(k.bedingung, u)):
            return self._besuche(k.dann, u)
        for bed, block in k.sonst_wenn:
            if self._ist_wahr(self._besuche(bed, u)):
                return self._besuche(block, u)
        if k.sonst:
            return self._besuche(k.sonst, u)
        return None

    def _besuche_SolangeAnweisung(self, k, u):
        while self._ist_wahr(self._besuche(k.bedingung, u)):
            try:
                self._besuche(k.koerper, u)
            except _AbbrechenSignal: break
            except _WeiterSignal:    continue
        return None

    def _besuche_FuerAnweisung(self, k, u):
        iterable = self._pruefe_iterierbar(self._besuche(k.iterable, u), "'für'")
        schleifen_u = Umgebung(u)
        for elem in iterable:
            self._schleifenvariable_binden(k.variable, elem, schleifen_u)
            try:
                self._besuche(k.koerper, schleifen_u)
            except _AbbrechenSignal: break
            except _WeiterSignal:    continue
        return None

    def _besuche_ZurueckAnweisung(self, k, u):
        raise _ZurueckSignal(self._besuche(k.wert, u))

    def _besuche_WerfeAnweisung(self, k, u):
        raise AusnahmeFehler(self._besuche(k.wert, u))

    def _besuche_PruefeAnweisung(self, k, u):
        if not self._ist_wahr(self._besuche(k.bedingung, u)):
            if k.meldung is not None:
                raise AssertionError(self._zu_text(self._besuche(k.meldung, u)))
            raise AssertionError('Prüfung fehlgeschlagen')
        return None

    def _besuche_AbbrechenAnweisung(self, k, u): raise _AbbrechenSignal()
    def _besuche_WeiterAnweisung(self, k, u):    raise _WeiterSignal()

    def _besuche_VersucheAnweisung(self, k, u):
        try:
            self._besuche(k.koerper, u)
        except _KONTROLLSIGNALE:
            raise  # Kontrollfluss-Signale niemals abfangen
        except Exception as e:
            if k.fange_koerper is not None and self._fehlertyp_passt(e, k.fange_typen):
                fange_u = Umgebung(u)
                if k.fange_name:
                    wert = e.wert if isinstance(e, AusnahmeFehler) else str(e)
                    fange_u.setze(k.fange_name, wert)
                self._besuche(k.fange_koerper, fange_u)
            else:
                raise
        finally:
            if k.endlich_koerper is not None:
                self._besuche(k.endlich_koerper, u)
        return None

    @staticmethod
    def _fehlertyp_passt(e, fange_typen):
        """Prüft ob fange_typen (str-Namen, z.B. 'TypeError') den Fehler oder eine seiner
        Basisklassen matcht. None bedeutet: alles fangen (Standardverhalten)."""
        if fange_typen is None:
            return True
        namen = {klasse.__name__ for klasse in type(e).__mro__}
        return not namen.isdisjoint(fange_typen)

    def _pfad_aufloesen(self, pfad: str) -> str:
        if not os.path.isabs(pfad):
            pfad = os.path.join(self._ladepfad, pfad)
        return os.path.normpath(pfad)

    def _besuche_PasseAnweisung(self, k, u):
        subjekt = self._besuche(k.ausdruck, u)
        for werte, block in k.faelle:
            if any(self._werte_gleich(subjekt, self._besuche(w, u)) for w in werte):
                return self._besuche(block, u)
        if k.sonst is not None:
            return self._besuche(k.sonst, u)
        return None

    def _besuche_LadeAnweisung(self, k, u):
        from .lexer import Lexer
        from .parser import Parser
        rohpfad = self._besuche(k.pfad, u)
        if not isinstance(rohpfad, str):
            raise TypeError(f"'lade' erwartet einen Pfad als Zeichenkette, bekam {self._typname(rohpfad)}")
        pfad = self._pfad_aufloesen(rohpfad)
        if pfad in self._lade_stack:
            kette = ' -> '.join(os.path.basename(p) for p in self._lade_stack + [pfad])
            raise ImportError(f"Zyklischer 'lade'-Import erkannt: {kette}")
        self._lade_stack.append(pfad)
        try:
            try:
                with open(pfad, 'r', encoding='utf-8') as f:
                    quelltext = f.read()
            except FileNotFoundError:
                raise FileNotFoundError(f"Datei zum Laden nicht gefunden: '{rohpfad}'")
            except IsADirectoryError:
                raise IsADirectoryError(f"'{rohpfad}' ist ein Ordner, keine Datei")
            except PermissionError:
                raise PermissionError(f"Keine Berechtigung zum Lesen von '{rohpfad}'")
            except UnicodeDecodeError:
                raise ValueError(f"'{rohpfad}' ist keine gültige UTF-8-Textdatei")
            tokens = Lexer(quelltext).tokenisieren()
            baum = Parser(tokens).parse()
            if k.als_name is not None:
                # Isolierter Scope: Top-Level-Bindungen landen im Namensraum, nicht im globalen Scope
                namensraum_u = Umgebung(self.global_umgebung)
                self.ausfuehren(baum, namensraum_u)
                namensraum = DeutschNamensraum(k.als_name, dict(namensraum_u.variablen))
                u.setze(k.als_name, namensraum)
                return namensraum
            # Ohne 'als': im globalen Scope ausführen, damit geladene Definitionen sichtbar sind
            return self.ausfuehren(baum, self.global_umgebung)
        finally:
            self._lade_stack.pop()

    # Funktionen
    def _besuche_FunktionDefinition(self, k, u):
        fn = DeutschFunktion(k, u)
        if k.name is not None:
            u.setze(k.name, fn)
        return fn

    def _besuche_FunktionAufruf(self, k, u):
        fn = self._besuche(k.funktion, u)
        args = [self._besuche(a, u) for a in k.argumente]
        kwargs = {name: self._besuche(w, u) for name, w in k.keyword_argumente}
        return self._aufrufen(fn, args, kwargs)

    def _aufrufen(self, fn, args, kwargs=None):
        kwargs = kwargs or {}
        if isinstance(fn, DeutschFunktion):
            return self._funktion_aufrufen(fn, args, kwargs)
        if isinstance(fn, GebundeneMethode):
            return self._funktion_aufrufen(fn.funktion, [fn.instanz] + args, kwargs)
        if callable(fn):
            if kwargs:
                raise TypeError("Eingebaute Funktionen unterstützen keine Keyword-Argumente")
            return fn(*args)
        raise TypeError(f"'{self._zu_text(fn)}' ist nicht aufrufbar")

    def _funktion_aufrufen(self, fn: DeutschFunktion, args: list, kwargs: dict = None):
        kwargs = kwargs or {}
        fn_name = fn.definition.name or '<anonym>'
        params = fn.definition.parameter  # [(name, default, variadic, typhinweis), ...]

        # Parameterstruktur analysieren
        variadic_idx = next((i for i, (_, _, v, _) in enumerate(params) if v), None)
        param_namen = [p[0] for p in params]
        n_gesamt = len(params) - (1 if variadic_idx is not None else 0)  # ohne variadic

        unbekannt = set(kwargs) - set(param_namen)
        if unbekannt:
            raise TypeError(f"'{fn_name}' hat keinen Parameter '{next(iter(unbekannt))}'")
        if variadic_idx is not None and param_namen[variadic_idx] in kwargs:
            raise TypeError(
                f"Variadischer Parameter '{param_namen[variadic_idx]}' kann nicht per Keyword gesetzt werden"
            )
        if variadic_idx is None and len(args) > n_gesamt:
            raise TypeError(
                f"'{fn_name}' erwartet höchstens {n_gesamt} Argument(e), "
                f"bekam {len(args)}"
            )

        fn_u = Umgebung(fn.umgebung)
        fehlende = []
        for i, (p_name, p_default, p_variadic, p_typ) in enumerate(params):
            if p_variadic:
                fn_u.setze(p_name, list(args[i:]))
                break
            if i < len(args):
                if p_name in kwargs:
                    raise TypeError(
                        f"'{fn_name}' erhielt mehrere Werte für Parameter '{p_name}'"
                    )
                wert = args[i]
            elif p_name in kwargs:
                wert = kwargs[p_name]
            elif p_default is not None:
                wert = self._besuche(p_default, fn.umgebung)
            else:
                fehlende.append(p_name)
                continue
            self._pruefe_typ(wert, p_typ, f"Parameter '{p_name}'", fn.umgebung)
            fn_u.setze(p_name, wert)

        if fehlende:
            raise TypeError(f"'{fn_name}': Pflichtargument(e) fehlen: {', '.join(fehlende)}")

        self._aufruf_stack.append((fn_name, self._aktuelle_zeile))
        try:
            kontext = f"Rückgabewert von '{fn_name}'"
            try:
                self._besuche(fn.definition.koerper, fn_u)
            except _ZurueckSignal as r:
                self._pruefe_typ(r.wert, fn.definition.typhinweis, kontext, fn.umgebung)
                return r.wert
            self._pruefe_typ(None, fn.definition.typhinweis, kontext, fn.umgebung)
            return None
        finally:
            self._aufruf_stack.pop()

    # Klassen
    def _besuche_KlassenDefinition(self, k, u):
        eltern = []
        for eltern_name in k.eltern:
            eltern_klasse = u.hole(eltern_name)
            if not isinstance(eltern_klasse, DeutschKlasse):
                raise TypeError(f"'{eltern_name}' ist keine Klasse")
            eltern.append(eltern_klasse)
        methoden = {m.name: DeutschFunktion(m, u) for m in k.methoden}
        statische_methoden = {m.name: DeutschFunktion(m, u) for m in k.statische_methoden}
        klasse = DeutschKlasse(k.name, eltern, methoden, statische_methoden)
        u.setze(k.name, klasse)
        # Klassenattribute (sei/konstante im Klassenkörper) in einem eigenen Scope auswerten,
        # damit sei/konstante-Semantik (inkl. Typ-Hinweise, Destrukturierung) automatisch gilt
        klassen_u = Umgebung(u)
        for deklaration in k.klassenattribute:
            self._besuche(deklaration, klassen_u)
        klasse.klassenattribute = dict(klassen_u.variablen)
        klasse.konstante_attribute = set(klassen_u.konstanten)
        return klasse

    def _besuche_NeuInstanz(self, k, u):
        klasse = self._besuche(k.klasse, u)
        if not isinstance(klasse, DeutschKlasse):
            raise TypeError(f"'{k.name}' ist keine Klasse")
        instanz = DeutschInstanz(klasse)
        args = [self._besuche(a, u) for a in k.argumente]
        kwargs = {name: self._besuche(w, u) for name, w in k.keyword_argumente}
        init = klasse.suche_methode('__init__')
        if init:
            self._funktion_aufrufen(init, [instanz] + args, kwargs)
        return instanz

    # Attribut- und Index-Zugriff
    def _besuche_AttributZugriff(self, k, u):
        obj = self._besuche(k.objekt, u)

        if isinstance(obj, DeutschInstanz):
            return obj.hole_attribut(k.attribut)

        if isinstance(obj, DeutschNamensraum):
            if k.attribut in obj.bindungen:
                return obj.bindungen[k.attribut]
            raise AttributeError(f"Namensraum '{obj.name}' hat kein Attribut '{k.attribut}'")

        if isinstance(obj, DeutschKlasse):
            m = obj.suche_methode(k.attribut)
            if m: return m
            sm = obj.suche_statische_methode(k.attribut)
            if sm: return sm
            wert = obj.suche_klassenattribut(k.attribut)
            if wert is not _NICHT_GEFUNDEN:
                return wert
            raise AttributeError(f"Klasse '{obj.name}' hat kein Attribut '{k.attribut}'")

        # Eingebaute Methoden für Liste/Zeichenkette/Wörterbuch/Menge – Dicts werden
        # einmalig in __init__ aufgebaut, hier nur Lookup + partial-Bindung von obj.
        if isinstance(obj, list):
            methode = self._listen_methoden.get(k.attribut)
            if methode is None:
                raise AttributeError(f"Liste hat kein Attribut '{k.attribut}'")
            return methode.binden(obj)

        if isinstance(obj, str):
            methode = self._string_methoden.get(k.attribut)
            if methode is None:
                raise AttributeError(f"Zeichenkette hat kein Attribut '{k.attribut}'")
            return methode.binden(obj)

        if isinstance(obj, dict):
            methode = self._woerterbuch_methoden.get(k.attribut)
            if methode is None:
                raise AttributeError(f"Wörterbuch hat kein Attribut '{k.attribut}'")
            return methode.binden(obj)

        if isinstance(obj, set):
            methode = self._menge_methoden.get(k.attribut)
            if methode is None:
                raise AttributeError(f"Menge hat kein Attribut '{k.attribut}'")
            return methode.binden(obj)

        if isinstance(obj, range):
            methode = self._bereich_methoden.get(k.attribut)
            if methode is None:
                raise AttributeError(f"Bereich hat kein Attribut '{k.attribut}'")
            return methode.binden(obj)

        raise AttributeError(f"Typ '{self._typname(obj)}' hat kein Attribut '{k.attribut}'")

    @staticmethod
    def _woerterbuch_entferne(obj, schluessel):
        try:
            return obj.pop(schluessel)
        except TypeError:
            raise TypeError('Wörterbuch-Schlüssel müssen hashbar sein (keine Listen/Wörterbücher)')
        except KeyError:
            raise SchluesselFehler(f"Schlüssel '{schluessel}' nicht im Wörterbuch")

    def _slice_bauen(self, slice_knoten, u):
        start = self._besuche(slice_knoten.start, u) if slice_knoten.start is not None else None
        stop = self._besuche(slice_knoten.stop, u) if slice_knoten.stop is not None else None
        step = self._besuche(slice_knoten.step, u) if slice_knoten.step is not None else None
        if step == 0:
            raise ValueError('Slice-Schrittweite darf nicht 0 sein')
        return slice(start, stop, step)

    def _besuche_IndexZugriff(self, k, u):
        obj = self._besuche(k.objekt, u)
        ist_slice = isinstance(k.index, ast.SliceAusdruck)
        if ist_slice:
            if isinstance(obj, dict):
                raise TypeError('Wörterbücher unterstützen kein Slicing')
            idx = self._slice_bauen(k.index, u)
        else:
            idx = self._besuche(k.index, u)
        try:
            return obj[idx]
        except IndexError:
            raise IndexError(f'Index {idx} ist außerhalb des Bereichs')
        except KeyError:
            raise SchluesselFehler(f"Schlüssel '{idx}' nicht im Wörterbuch")
        except TypeError:
            if ist_slice:
                raise TypeError('Slice-Grenzen müssen Ganzzahlen sein')
            raise TypeError(f"Ungültiger Index-Typ '{self._typname(idx)}' für {self._typname(obj)}")
