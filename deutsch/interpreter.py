# -*- coding: utf-8 -*-
import os
import math
import functools
import inspect
import random
import json
import re
import time
import statistics
import hashlib
import base64
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
from . import ast_knoten as ast
from .umgebung import Umgebung


# ---------------------------------------------------------------- Signale

class _ZurueckSignal(Exception):
    def __init__(self, wert, zeile=None):
        self.wert = wert
        self.zeile = zeile

class _AbbrechenSignal(Exception):
    def __init__(self, zeile=None):
        self.zeile = zeile

class _WeiterSignal(Exception):
    def __init__(self, zeile=None):
        self.zeile = zeile

_KONTROLLSIGNALE = (_ZurueckSignal, _AbbrechenSignal, _WeiterSignal)


def _signal_fehler(signal, datei: str | None = None, dateiname: str | None = None) -> RuntimeError:
    """Übersetzt ein Kontrollfluss-Signal, das seinen gültigen Bereich verlassen hat
    ('abbrechen'/'weiter' ohne Schleife in der Funktion, 'zurück' ohne Funktion), in einen Fehler.
    datei/dateiname: Pfad bzw. Anzeigename der geladenen Datei, in der das Signal ausgelöst wurde."""
    if isinstance(signal, _ZurueckSignal):
        text = "'zurück' außerhalb einer Funktion"
    elif isinstance(signal, _AbbrechenSignal):
        text = "'abbrechen' außerhalb einer Schleife"
    else:
        text = "'weiter' außerhalb einer Schleife"
    if signal.zeile is not None:
        ort = f'{dateiname}, Zeile {signal.zeile}' if dateiname else f'Zeile {signal.zeile}'
        text = f'{ort}: {text}'
    fehler = RuntimeError(text)
    fehler.datei = datei
    fehler.zeile = signal.zeile
    return fehler

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

# Bit-Operatoren (nur Ganzzahlen bzw. Mengen, keine Überladung durch Klassen)
_BIT_OPERATOREN = ('&', '|', '^', '<<', '>>')


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
    def __init__(self, definition: ast.FunktionDefinition, umgebung: Umgebung, datei: str | None = None):
        self.definition = definition
        self.umgebung = umgebung
        self.datei = datei  # absoluter Pfad der Datei, in der die Funktion steht (None = Hauptskript/REPL)

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


def _mit_keywords(fn):
    """Markiert eine eingebaute Funktion oder Methode, die Keyword-Argumente annimmt
    (z. B. sortiere(liste, schluessel=f)). Alle anderen Eingebauten lehnen Keywords ab."""
    fn._akzeptiert_keywords = True
    return fn


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
        # Datei, deren Code gerade läuft (absoluter Pfad); None = Hauptskript bzw. REPL.
        # Wechselt bei 'lade' und beim Aufruf einer Funktion aus einer geladenen Datei.
        self._aktuelle_datei: str | None = None
        self._dispatch = self._dispatch_aufbauen()
        self._listen_methoden = self._listen_methoden_aufbauen()
        self._string_methoden = self._string_methoden_aufbauen()
        self._woerterbuch_methoden = self._woerterbuch_methoden_aufbauen()
        self._menge_methoden = self._menge_methoden_aufbauen()
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
    # dieselbe Funktion für jede Instanz per functools.partial(fn, obj) wiederverwendet wird.

    def _listen_methoden_aufbauen(self):
        return {
            'anhaengen': lambda obj, *a: (obj.append(a[0]), None)[1],
            'anhängen':  lambda obj, *a: (obj.append(a[0]), None)[1],
            'laenge':    lambda obj: len(obj),
            'länge':     lambda obj: len(obj),
            'entferne':  lambda obj, *a: self._liste_entferne(obj, *a),
            'enthält':   lambda obj, x: x in obj,
            'umkehren':  lambda obj: (obj.reverse(), None)[1],
            'sortiere':  _mit_keywords(lambda obj, /, *a, **kw: self._liste_sortiere(obj, a, kw)),
            'erste':     lambda obj: obj[0] if obj else None,
            'letzte':    lambda obj: obj[-1] if obj else None,
            'kopiere':   lambda obj: list(obj),
            'flach':     lambda obj: [e for sub in obj for e in (sub if isinstance(sub, list) else [sub])],
            'index_von': lambda obj, x: self._index_von(obj, x, 'Liste'),
            'zaehle':    lambda obj, x: self._zaehle(obj, x, 'Liste'),
            'einfuegen': lambda obj, index, wert: self._liste_einfuegen(obj, index, wert),
            'erweitere': lambda obj, andere: self._liste_erweitere(obj, andere),
            'abbilden':  lambda obj, *a: self._liste_abbilden(obj, a),
            'filtere':   lambda obj, *a: self._liste_filtere(obj, a),
            'reduziere': lambda obj, *a: self._liste_reduziere(obj, a),
            'eindeutig': lambda obj: self._liste_eindeutig(obj),
            'max':       _mit_keywords(lambda obj, /, *a, **kw: self._liste_extremum(obj, a, kw, max, 'max')),
            'min':       _mit_keywords(lambda obj, /, *a, **kw: self._liste_extremum(obj, a, kw, min, 'min')),
        }

    def _string_methoden_aufbauen(self):
        return {
            'gross':         lambda obj: obj.upper(),
            'groß':          lambda obj: obj.upper(),
            'klein':         lambda obj: obj.lower(),
            'laenge':        lambda obj: len(obj),
            'länge':         lambda obj: len(obj),
            'teile':         lambda obj, *a: obj.split(a[0]) if a else obj.split(),
            'enthält':       lambda obj, x: x in obj,
            'ersetze':       lambda obj, *a: self._text_ersetze(obj, a),
            'links_auffuellen': _mit_keywords(lambda obj, /, *a, **kw:
                                self._text_auffuellen('links_auffuellen', obj, a, kw, str.rjust)),
            'links_auffüllen':  _mit_keywords(lambda obj, /, *a, **kw:
                                self._text_auffuellen('links_auffüllen', obj, a, kw, str.rjust)),
            'rechts_auffuellen': _mit_keywords(lambda obj, /, *a, **kw:
                                 self._text_auffuellen('rechts_auffuellen', obj, a, kw, str.ljust)),
            'rechts_auffüllen':  _mit_keywords(lambda obj, /, *a, **kw:
                                 self._text_auffuellen('rechts_auffüllen', obj, a, kw, str.ljust)),
            'zentrieren':    _mit_keywords(lambda obj, /, *a, **kw:
                             self._text_auffuellen('zentrieren', obj, a, kw, str.center)),
            'trimmen':       lambda obj: obj.strip(),
            'links_trimmen': lambda obj: obj.lstrip(),
            'rechts_trimmen':lambda obj: obj.rstrip(),
            'beginnt_mit':   lambda obj, x: obj.startswith(x),
            'endet_mit':     lambda obj, x: obj.endswith(x),
            'grossschreibe': lambda obj: obj.capitalize(),
            'großschreibe':  lambda obj: obj.capitalize(),
            'zeichen':       lambda obj: list(obj),
            'wiederhole':    lambda obj, n: obj * int(n),
            'zahl':          lambda obj: self._zeichenkette_zu_zahl(obj),
            'index_von':     lambda obj, x: self._index_von(obj, x, 'Zeichenkette'),
            'zaehle':        lambda obj, x: self._zaehle(obj, x, 'Zeichenkette'),
            'ist_ziffer':    lambda obj: obj.isdigit(),
            'ist_buchstabe': lambda obj: obj.isalpha(),
            'ist_leerraum':  lambda obj: obj.isspace(),
        }

    def _woerterbuch_methoden_aufbauen(self):
        return {
            'schluessel': lambda obj: list(obj.keys()),
            'schlüssel':  lambda obj: list(obj.keys()),
            'werte':      lambda obj: list(obj.values()),
            'paare':      lambda obj: [[k, v] for k, v in obj.items()],
            'enthält':    lambda obj, x: x in obj,
            'entferne':   lambda obj, x: self._woerterbuch_entferne(obj, x),
            'laenge':     lambda obj: len(obj),
            'länge':      lambda obj: len(obj),
            'hole':       lambda obj, k, *d: obj.get(k, d[0] if d else None),
            'kopiere':    lambda obj: dict(obj),
            'zusammenfuehren': lambda obj, *a: self._woerterbuecher_zusammenfuehren('zusammenfuehren', (obj,) + a),
            'zusammenführen':  lambda obj, *a: self._woerterbuecher_zusammenfuehren('zusammenführen', (obj,) + a),
        }

    def _menge_methoden_aufbauen(self):
        return {
            'laenge':       lambda obj: len(obj),
            'länge':        lambda obj: len(obj),
            'enthält':      lambda obj, x: x in obj,
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
        }

    # ---------------------------------------------------------- Eingebaute

    def _eingebaute_laden(self):
        g = self.global_umgebung
        g.setze('drucke',       self._eb_drucke)
        g.setze('eingabe',      self._eb_eingabe)
        g.setze('laenge',       self._eb_laenge)
        g.setze('länge',        self._eb_laenge)
        g.setze('typ',          self._eb_typ)
        g.setze('ganzzahl',     self._eb_ganzzahl)
        g.setze('kommazahl',    self._eb_kommazahl)
        g.setze('zeichenkette', self._eb_zeichenkette)
        g.setze('wahrheitswert', self._eb_wahrheitswert)
        g.setze('bereich',      self._eb_bereich)
        g.setze('sortiere',     self._eb_sortiere)
        g.setze('abbilden',     self._eb_abbilden)
        g.setze('filtere',      self._eb_filtere)
        g.setze('reduziere',    self._eb_reduziere)
        g.setze('anhaengen',    self._eb_anhaengen)
        g.setze('anhängen',     self._eb_anhaengen)
        g.setze('entferne',     self._eb_entferne)
        g.setze('umkehren',     self._eb_umkehren)
        g.setze('verbinde',     self._eb_verbinde)
        g.setze('max',          self._eb_max)
        g.setze('min',          self._eb_min)
        g.setze('abs',          self._eb_abs)
        g.setze('runde',        self._eb_runde)
        g.setze('liste',        self._eb_liste)
        g.setze('woerterbuch',  self._eb_woerterbuch)
        g.setze('wörterbuch',   self._eb_woerterbuch)
        g.setze('menge',        self._eb_menge)
        g.setze('wahr',         True)
        g.setze('falsch',       False)
        g.setze('nichts',       None)
        g.setze('pi',           math.pi)
        g.setze('e',            math.e)
        g.setze('wurzel',       self._eb_wurzel)
        g.setze('sinus',        self._eb_sinus)
        g.setze('kosinus',      self._eb_kosinus)
        g.setze('tangens',      self._eb_tangens)
        g.setze('logarithmus',  self._eb_logarithmus)
        g.setze('exponential',  self._eb_exponential)
        g.setze('ggt',          self._eb_ggt)
        g.setze('kgv',          self._eb_kgv)
        g.setze('vorzeichen',   self._eb_vorzeichen)
        g.setze('datei_lesen',      self._eb_datei_lesen)
        g.setze('datei_schreiben',  self._eb_datei_schreiben)
        g.setze('datei_anhaengen',  self._eb_datei_anhaengen)
        g.setze('datei_anhängen',   self._eb_datei_anhaengen)
        g.setze('boden',            self._eb_boden)
        g.setze('decke',            self._eb_decke)
        g.setze('zufall',           self._eb_zufall)
        g.setze('zufallszahl',      self._eb_zufallszahl)
        g.setze('mische',           self._eb_mische)
        g.setze('summe',            self._eb_summe)
        g.setze('alle',             self._eb_alle)
        g.setze('einige',           self._eb_einige)
        g.setze('aufzaehlen',       self._eb_aufzaehlen)
        g.setze('zippe',            self._eb_zippe)
        g.setze('json_lesen',       self._eb_json_lesen)
        g.setze('json_schreiben',   self._eb_json_schreiben)
        g.setze('kommandozeilen_argumente', self._eb_kommandozeilen_argumente)
        g.setze('passt_zu',         self._eb_passt_zu)
        g.setze('regex_ersetze',    self._eb_regex_ersetze)
        g.setze('regex_finde',      self._eb_regex_finde)
        g.setze('regex_finde_alle', self._eb_regex_finde_alle)
        g.setze('jetzt',             self._eb_jetzt)
        g.setze('datum_formatieren', self._eb_datum_formatieren)
        g.setze('mittelwert',        self._eb_mittelwert)
        g.setze('median',            self._eb_median)
        g.setze('stdabweichung',     self._eb_stdabweichung)
        g.setze('tiefe_kopie',       self._eb_tiefe_kopie)
        g.setze('umgebungsvariable', self._eb_umgebungsvariable)
        g.setze('pfad_existiert',    self._eb_pfad_existiert)
        g.setze('dateien_auflisten', self._eb_dateien_auflisten)
        g.setze('ordner_erstellen',  self._eb_ordner_erstellen)
        g.setze('hash_sha256',       self._eb_hash_sha256)
        g.setze('base64_kodieren',   self._eb_base64_kodieren)
        g.setze('base64_dekodieren', self._eb_base64_dekodieren)
        g.setze('pfad_verbinden',    self._eb_pfad_verbinden)
        g.setze('dateiname',         self._eb_dateiname)
        g.setze('ordnername',        self._eb_ordnername)
        g.setze('endung',            self._eb_endung)
        g.setze('ist_datei',         self._eb_ist_datei)
        g.setze('ist_ordner',        self._eb_ist_ordner)
        g.setze('datei_loeschen',    self._eb_datei_loeschen)
        g.setze('datei_löschen',     self._eb_datei_loeschen)
        g.setze('umbenennen',        self._eb_umbenennen)
        g.setze('zeilen_lesen',      self._eb_zeilen_lesen)
        g.setze('eindeutig',         self._eb_eindeutig)
        g.setze('gruppiere',         self._eb_gruppiere)
        g.setze('zusammenfuehren',   self._eb_zusammenfuehren)
        g.setze('zusammenführen',    self._eb_zusammenfuehren)
        g.setze('arcsin',            self._eb_arcsin)
        g.setze('arccos',            self._eb_arccos)
        g.setze('arctan',            self._eb_arctan)
        g.setze('arctan2',           self._eb_arctan2)
        g.setze('warte',             self._eb_warte)
        g.setze('datum_lesen',       self._eb_datum_lesen)

    def _eb_drucke(self, *args):
        print(' '.join(self._zu_text(a) for a in args))
        return None

    def _eb_eingabe(self, *args):
        try:
            return input(self._zu_text(args[0]) if args else '')
        except EOFError:
            raise EOFError('Eingabe nicht möglich: Dateiende erreicht, die Eingabe ist geschlossen') from None

    def _eb_laenge(self, *args):
        self._pruefe_args('länge', args, 1)
        obj = args[0]
        if isinstance(obj, (list, dict, str, set)):
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
        if len(args) == 1:   return list(range(int(args[0])))
        if len(args) == 2:   return list(range(int(args[0]), int(args[1])))
        if len(args) == 3:   return list(range(int(args[0]), int(args[1]), int(args[2])))
        raise TypeError("'bereich' erwartet 1–3 Argumente")

    @_mit_keywords
    def _eb_sortiere(self, /, *args, **kwargs):
        schluessel, umgekehrt = self._sortier_optionen('sortiere', kwargs)
        self._pruefe_args('sortiere', args, 1)
        if not isinstance(args[0], (list, set)):
            raise TypeError("'sortiere' erwartet eine Liste oder Menge")
        return self._sortiere_mit(list(args[0]), schluessel, umgekehrt)

    def _liste_sortiere(self, obj, args, kwargs):
        """liste.sortiere([schluessel=f][, umgekehrt=wahr]) – sortiert in place, gibt nichts zurück."""
        if args:
            raise TypeError("'sortiere' nimmt nur die Keyword-Argumente 'schluessel' und 'umgekehrt' an")
        schluessel, umgekehrt = self._sortier_optionen('sortiere', kwargs)
        obj[:] = self._sortiere_mit(list(obj), schluessel, umgekehrt)  # bei Fehler im Schlüssel bleibt obj unverändert
        return None

    def _sortier_optionen(self, name, kwargs):
        """Liest schluessel=/schlüssel= (alle) und umgekehrt= (nur 'sortiere'). Gibt (schluessel|None, umgekehrt) zurück.
        schluessel=nichts bedeutet: kein Schlüssel."""
        schluessel, umgekehrt, schluessel_gesetzt = None, False, False
        for k, v in kwargs.items():
            if k in ('schluessel', 'schlüssel'):
                if schluessel_gesetzt:
                    raise TypeError(f"'{name}': 'schluessel' und 'schlüssel' sind dasselbe Argument "
                                    f"und dürfen nicht beide angegeben werden")
                schluessel_gesetzt = True
                if v is not None:
                    self._pruefe_funktion(name, v, 1, f"für '{k}'")
                    schluessel = v
            elif k == 'umgekehrt' and name == 'sortiere':
                umgekehrt = self._ist_wahr(v)
            else:
                raise TypeError(f"'{name}' hat kein Parameter '{k}'")
        return schluessel, umgekehrt

    def _sortiere_mit(self, liste, schluessel, umgekehrt):
        """Neue, sortierte Liste. Ohne Schlüssel und ohne 'umgekehrt' exakt das bisherige Verhalten.
        Gleiche Schlüssel behalten ihre ursprüngliche Reihenfolge (auch bei 'umgekehrt')."""
        if schluessel is None and not umgekehrt:
            return self._sortiert(liste)
        if schluessel is None:
            try:
                return sorted(liste, reverse=umgekehrt)
            except TypeError:
                return sorted(liste, key=str, reverse=umgekehrt)
        schluessel_werte = [self._aufrufen(schluessel, [e]) for e in liste]
        try:
            reihenfolge = sorted(range(len(liste)), key=schluessel_werte.__getitem__, reverse=umgekehrt)
        except TypeError:  # nicht vergleichbare Schlüssel (gemischte Typen): wie ohne Schlüssel nach Text
            reihenfolge = sorted(range(len(liste)), key=lambda i: self._zu_text(schluessel_werte[i]),
                                 reverse=umgekehrt)
        return [liste[i] for i in reihenfolge]

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
        try:
            return obj.index(x)
        except ValueError:
            raise ValueError(f"'{x}' nicht gefunden in {typname}")
        except TypeError:
            raise TypeError(f"'index_von' erwartet den gleichen Typ wie {typname}, bekam {self._typname(x)}")

    def _zaehle(self, obj, x, typname):
        try:
            return obj.count(x)
        except TypeError:
            raise TypeError(f"'zaehle' erwartet den gleichen Typ wie {typname}, bekam {self._typname(x)}")

    def _zeichenkette_zu_zahl(self, text):
        try:
            return int(text) if text.lstrip('-').isdigit() else float(text)
        except ValueError:
            raise ValueError(f"Kann '{text}' nicht in Zahl umwandeln")

    def _text_auffuellen(self, name, obj, args, kwargs, fn):
        """links_auffuellen / rechts_auffuellen / zentrieren: breite und optional zeichen (positional oder als Keyword).
        fn ist str.rjust, str.ljust bzw. str.center."""
        unbekannt = [k for k in kwargs if k != 'zeichen']
        if unbekannt:
            raise TypeError(f"'{name}' hat kein Parameter '{unbekannt[0]}'")
        if not 1 <= len(args) <= 2:
            raise TypeError(f"'{name}' erwartet 1–2 Argumente, bekam {len(args)}")
        if len(args) == 2 and 'zeichen' in kwargs:
            raise TypeError(f"'{name}': 'zeichen' ist mehrfach angegeben")
        breite = args[0]
        zeichen = args[1] if len(args) == 2 else kwargs.get('zeichen', ' ')
        if not isinstance(breite, int):
            raise TypeError(f"'{name}' erwartet eine Ganzzahl als Breite, bekam {self._typname(breite)}")
        if not isinstance(zeichen, str):
            raise TypeError(f"'{name}' erwartet ein Füllzeichen als Zeichenkette, bekam {self._typname(zeichen)}")
        if len(zeichen) != 1:
            raise ValueError(f"'{name}': Das Füllzeichen muss genau 1 Zeichen lang sein, bekam {len(zeichen)}")
        return fn(obj, breite, zeichen)

    def _text_ersetze(self, obj, args):
        """text.ersetze(alt, neu[, anzahl]): ersetzt alle Vorkommen oder höchstens 'anzahl' viele."""
        if not 2 <= len(args) <= 3:
            raise TypeError(f"'ersetze' erwartet 2–3 Argumente, bekam {len(args)}")
        alt, neu = args[0], args[1]
        if not isinstance(alt, str) or not isinstance(neu, str):
            raise TypeError(f"'ersetze' erwartet Zeichenketten als erstes und zweites Argument, "
                            f"bekam {self._typname(alt)} und {self._typname(neu)}")
        if len(args) == 2:
            return obj.replace(alt, neu)
        anzahl = args[2]
        if not isinstance(anzahl, int):
            raise TypeError(f"'ersetze' erwartet eine Ganzzahl als Anzahl, bekam {self._typname(anzahl)}")
        if anzahl < 0:
            raise ValueError(f"'ersetze' erwartet eine Anzahl von 0 oder mehr, bekam {anzahl}")
        return obj.replace(alt, neu, anzahl)

    def _liste_entferne(self, liste, *index):
        """Gemeinsame Logik für entferne(liste[, index]) und liste.entferne([index])."""
        if not index:
            if not liste:
                raise IndexError("'entferne' kann nicht aus einer leeren Liste entfernen")
            return liste.pop()
        try:
            position = int(index[0])
        except (ValueError, TypeError):
            raise TypeError(f"'entferne' erwartet einen Ganzzahl-Index, bekam {self._typname(index[0])}")
        try:
            return liste.pop(position)
        except IndexError:
            raise IndexError(f'Index {position} ist außerhalb des Bereichs')

    def _vergleichs_extremum(self, fn, werte, name, schluessel=None):
        """max/min über werte (mit schluessel: über die Schlüsselwerte, bei Gleichstand gewinnt der erste).
        Nicht vergleichbare Typen (z. B. Ganzzahl und Zeichenkette) → deutsche Meldung."""
        if schluessel is not None:
            vergleichswerte = [self._aufrufen(schluessel, [w]) for w in werte]
            try:
                return werte[fn(range(len(werte)), key=vergleichswerte.__getitem__)]
            except TypeError:
                typen = list(dict.fromkeys(self._typname(w) for w in vergleichswerte))
                raise TypeError(f"'{name}' kann Schlüsselwerte dieser Typen nicht vergleichen: {', '.join(typen)}")
        try:
            return fn(werte)
        except TypeError:
            typen = list(dict.fromkeys(self._typname(w) for w in werte))
            raise TypeError(f"'{name}' kann Werte dieser Typen nicht vergleichen: {', '.join(typen)}")

    def _iteriere(self, wert):
        """Wie iter(), aber mit deutscher Meldung für nicht iterierbare Werte (z. B. Klasseninstanzen)."""
        try:
            return iter(wert)
        except TypeError:
            raise TypeError(f"'{self._typname(wert)}' ist nicht iterierbar") from None

    def _liste_einfuegen(self, obj, index, wert):
        try:
            obj.insert(int(index), wert)
        except (ValueError, TypeError):
            raise TypeError(f"'einfuegen' erwartet einen Ganzzahl-Index, bekam {self._typname(index)}")
        return None

    def _liste_erweitere(self, obj, andere):
        if not isinstance(andere, (list, set)):
            raise TypeError(f"'erweitere' erwartet eine Liste oder Menge, bekam {self._typname(andere)}")
        obj.extend(andere)
        return None

    def _liste_extremum(self, liste, args, kwargs, fn, name):
        """liste.max([schluessel=f]) und liste.min(...): wie die gleichnamigen Builtins, die Liste ist der Empfänger."""
        if args:
            raise TypeError(f"'{name}' nimmt keine Positionsargumente an, nur das Keyword 'schluessel'")
        schluessel, _ = self._sortier_optionen(name, kwargs)
        if not liste:
            raise ValueError(f"'{name}' erwartet eine nicht-leere Liste")
        return self._vergleichs_extremum(fn, liste, name, schluessel)

    @staticmethod
    def _liste_eindeutig(liste):
        """Neue Liste ohne Dubletten; das erste Auftreten bestimmt die Reihenfolge.
        Unhashbare Werte (Listen, Wörterbücher) werden über == verglichen."""
        ergebnis, gesehen = [], set()
        for e in liste:
            try:
                if e in gesehen:
                    continue
                gesehen.add(e)
            except TypeError:
                if e in ergebnis:
                    continue
            ergebnis.append(e)
        return ergebnis

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
        return self._liste_entferne(liste, *args[1:])

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

    @_mit_keywords
    def _eb_max(self, /, *args, **kwargs):
        schluessel, _ = self._sortier_optionen('max', kwargs)
        if not args: raise TypeError("'max' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
        if not werte: raise ValueError("'max' erwartet eine nicht-leere Liste")
        return self._vergleichs_extremum(max, werte, 'max', schluessel)

    @_mit_keywords
    def _eb_min(self, /, *args, **kwargs):
        schluessel, _ = self._sortier_optionen('min', kwargs)
        if not args: raise TypeError("'min' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
        if not werte: raise ValueError("'min' erwartet eine nicht-leere Liste")
        return self._vergleichs_extremum(min, werte, 'min', schluessel)

    def _eb_eindeutig(self, *args):
        self._pruefe_args('eindeutig', args, 1)
        if not isinstance(args[0], list):
            raise TypeError(f"'eindeutig' erwartet eine Liste, bekam {self._typname(args[0])}")
        return self._liste_eindeutig(args[0])

    # ----------------------------------------------- Funktionen höherer Ordnung

    def _eb_abbilden(self, *args):
        self._pruefe_args('abbilden', args, 2)
        return self._hof_abbilden(args[0], args[1], 'als 2. Argument')

    def _eb_filtere(self, *args):
        self._pruefe_args('filtere', args, 2)
        return self._hof_filtere(args[0], args[1], 'als 2. Argument')

    def _eb_reduziere(self, *args):
        if len(args) not in (2, 3):
            raise TypeError(f"'reduziere' erwartet 2–3 Argumente, bekam {len(args)}")
        return self._hof_reduziere(args[0], args[1], args[2:], 'als 2. Argument')

    def _liste_abbilden(self, obj, args):
        self._pruefe_args('abbilden', args, 1)
        return self._hof_abbilden(obj, args[0], 'als Argument')

    def _liste_filtere(self, obj, args):
        self._pruefe_args('filtere', args, 1)
        return self._hof_filtere(obj, args[0], 'als Argument')

    def _liste_reduziere(self, obj, args):
        if len(args) not in (1, 2):
            raise TypeError(f"'reduziere' erwartet 1–2 Argumente, bekam {len(args)}")
        return self._hof_reduziere(obj, args[0], args[1:], 'als Argument')

    def _hof_abbilden(self, sammlung, f, wo_f):
        elemente = self._hof_elemente('abbilden', sammlung)
        self._pruefe_funktion('abbilden', f, 1, wo_f)
        return [self._aufrufen(f, [e]) for e in elemente]

    def _hof_filtere(self, sammlung, f, wo_f):
        elemente = self._hof_elemente('filtere', sammlung)
        self._pruefe_funktion('filtere', f, 1, wo_f)
        return [e for e in elemente if self._ist_wahr(self._aufrufen(f, [e]))]

    def _hof_reduziere(self, sammlung, f, start, wo_f):
        """start: leeres Tupel (kein Startwert) oder (wert,) – 'nichts' ist ein gültiger Startwert."""
        elemente = self._hof_elemente('reduziere', sammlung)
        self._pruefe_funktion('reduziere', f, 2, wo_f)
        if start:
            ergebnis = start[0]
        elif elemente:
            ergebnis, elemente = elemente[0], elemente[1:]
        else:
            raise ValueError("'reduziere' kann eine leere Sammlung nicht ohne Startwert reduzieren")
        for e in elemente:
            ergebnis = self._aufrufen(f, [ergebnis, e])
        return ergebnis

    def _eb_gruppiere(self, *args):
        self._pruefe_args('gruppiere', args, 2)
        return self._hof_gruppiere(args[0], args[1], 'als 2. Argument')

    def _hof_gruppiere(self, sammlung, f, wo_f):
        """Wörterbuch: Schlüssel f(e) -> Liste aller Elemente e mit diesem Schlüssel (in ihrer Reihenfolge)."""
        elemente = self._hof_elemente('gruppiere', sammlung)
        self._pruefe_funktion('gruppiere', f, 1, wo_f)
        ergebnis = {}
        for e in elemente:
            schluessel = self._aufrufen(f, [e])
            try:
                ergebnis.setdefault(schluessel, []).append(e)
            except TypeError:  # unhashbarer Schlüssel, z. B. eine Liste
                raise TypeError(f"'gruppiere' erwartet als Schlüssel einen unveränderlichen Wert, "
                                f"bekam {self._typname(schluessel)}") from None
        return ergebnis

    def _hof_elemente(self, name, sammlung):
        """Elemente einer Liste, Menge (sortiert, damit das Ergebnis stabil ist) oder Zeichenkette als neue Liste."""
        if isinstance(sammlung, (list, str)):
            return list(sammlung)
        if isinstance(sammlung, set):
            return self._sortiert(list(sammlung))
        raise TypeError(f"'{name}' erwartet als erstes eine Liste, Menge oder Zeichenkette, "
                        f"bekam {self._typname(sammlung)}")

    @staticmethod
    def _argumente_text(n, dativ=False):
        if n == 1:
            return '1 Argument'
        return f'{n} Argumenten' if dativ else f'{n} Argumente'

    def _pruefe_funktion(self, name, f, n, wo):
        """Stellt vorab sicher, dass f eine Funktion ist, die mit n Argumenten aufrufbar ist,
        damit die Meldung auf Deutsch kommt (statt erst beim Aufruf, ggf. als Python-Fehler)."""
        if isinstance(f, DeutschFunktion):
            bereich = self._parameter_bereich(f.definition.parameter, 0)
        elif isinstance(f, GebundeneMethode):
            bereich = self._parameter_bereich(f.funktion.definition.parameter, 1)  # 'dies' ist schon belegt
        elif callable(f):
            bereich = self._python_bereich(f)
        else:
            raise TypeError(f"'{name}' erwartet {wo} eine Funktion, bekam {self._typname(f)}")
        if bereich is None:
            return
        minimum, maximum = bereich
        if n < minimum or (maximum is not None and n > maximum):
            if maximum is None:
                soll = f'mindestens {self._argumente_text(minimum)}'
            elif minimum == maximum:
                soll = f'genau {self._argumente_text(minimum)}'
            else:
                soll = f'{minimum} bis {self._argumente_text(maximum)}'
            raise TypeError(f"'{name}': Die übergebene Funktion erwartet {soll}, "
                            f"wird hier aber mit {self._argumente_text(n, dativ=True)} aufgerufen")

    @staticmethod
    def _parameter_bereich(parameter, abzug):
        """(Minimum, Maximum|None) der positionalen Argumente einer Deutsch-Funktion; abzug: schon belegte vorne."""
        feste = [p for p in parameter if not p[2]]
        minimum = max((i + 1 for i, p in enumerate(feste) if p[1] is None), default=0)
        maximum = None if len(feste) != len(parameter) else len(feste)
        return max(minimum - abzug, 0), (None if maximum is None else max(maximum - abzug, 0))

    @staticmethod
    def _python_bereich(f):
        """Wie _parameter_bereich für eingebaute Funktionen; None, wenn die Signatur unbekannt ist."""
        try:
            signatur = inspect.signature(f)
        except (ValueError, TypeError):
            return None
        minimum, maximum = 0, 0
        for p in signatur.parameters.values():
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                if maximum is not None:
                    maximum += 1
                if p.default is p.empty:
                    minimum += 1
            elif p.kind is p.VAR_POSITIONAL:
                maximum = None
        return minimum, maximum

    def _eb_abs(self, *args):
        self._pruefe_args('abs', args, 1)
        try:
            return abs(args[0])
        except TypeError:
            raise TypeError(f"'abs' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_runde(self, *args):
        """Kaufmännisch: ab ,5 vom Nullpunkt weg. Ohne Stellen oder mit Stellen <= 0 eine Ganzzahl, sonst eine Kommazahl."""
        if len(args) not in (1, 2):
            raise TypeError(f"'runde' erwartet 1–2 Argumente, bekam {len(args)}")
        zahl = args[0]
        if not isinstance(zahl, (int, float)):
            raise TypeError(f"'runde' erwartet eine Zahl, bekam {self._typname(zahl)}")
        stellen = 0
        if len(args) == 2:
            stellen = args[1]
            if not isinstance(stellen, int):
                raise TypeError(f"'runde' erwartet eine Ganzzahl als Stellenzahl, bekam {self._typname(stellen)}")
        if isinstance(zahl, float) and not math.isfinite(zahl):
            raise ValueError(f"'runde' erwartet eine endliche Zahl, bekam {self._zu_text(zahl)}")
        if isinstance(zahl, bool):  # Python rechnet mit wahr/falsch wie mit 1/0; str() würde 'True' liefern
            zahl = int(zahl)
        gerundet = self._runde_dezimal(zahl, stellen)
        if stellen > 0:
            return float(gerundet) + 0.0  # + 0.0: aus -0.0 wird 0.0
        return int(gerundet)

    @staticmethod
    def _runde_dezimal(zahl, stellen):
        """Rundet auf der Dezimaldarstellung (str) der Zahl, ROUND_HALF_UP. Gibt ein Decimal zurück."""
        ganzstellen = len(str(int(abs(zahl))))
        # Außerhalb dieser Grenzen ändert sich das Ergebnis nicht, nur die Zwischenwerte würden riesig:
        # Stellen unter -(Ganzstellen+1) ergeben immer 0, ab 400 Nachkommastellen ist die Zahl schon exakt.
        stellen = min(max(stellen, -(ganzstellen + 1)), 400)
        with localcontext() as kontext:
            kontext.prec = ganzstellen + max(stellen, 0) + 5
            quantum = Decimal(1).scaleb(-stellen)
            return Decimal(str(zahl)).quantize(quantum, rounding=ROUND_HALF_UP)

    def _eb_liste(self, *args):
        self._pruefe_args('liste', args, 1)
        try:
            return list(args[0])
        except TypeError:
            raise TypeError(f"'{self._typname(args[0])}' kann nicht in Liste umgewandelt werden")

    def _eb_wurzel(self, *args):
        self._pruefe_args('wurzel', args, 1)
        try:
            return math.sqrt(args[0])
        except ValueError:
            raise ValueError(f"'wurzel' nicht definiert für negative Zahl {args[0]}")
        except TypeError:
            raise TypeError(f"'wurzel' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_sinus(self, *args):
        self._pruefe_args('sinus', args, 1)
        try:
            return math.sin(args[0])
        except TypeError:
            raise TypeError(f"'sinus' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_kosinus(self, *args):
        self._pruefe_args('kosinus', args, 1)
        try:
            return math.cos(args[0])
        except TypeError:
            raise TypeError(f"'kosinus' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_tangens(self, *args):
        self._pruefe_args('tangens', args, 1)
        try:
            return math.tan(args[0])
        except TypeError:
            raise TypeError(f"'tangens' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_exponential(self, *args):
        self._pruefe_args('exponential', args, 1)
        try:
            return math.exp(args[0])
        except TypeError:
            raise TypeError(f"'exponential' erwartet eine Zahl, bekam {self._typname(args[0])}")
        except OverflowError:
            raise OverflowError(f"'exponential' ergibt für {self._zu_text(args[0])} eine zu große Zahl")

    def _eb_arcsin(self, *args):
        self._pruefe_args('arcsin', args, 1)
        return self._arkusfunktion('arcsin', math.asin, args[0])

    def _eb_arccos(self, *args):
        self._pruefe_args('arccos', args, 1)
        return self._arkusfunktion('arccos', math.acos, args[0])

    def _eb_arctan(self, *args):
        self._pruefe_args('arctan', args, 1)
        return self._arkusfunktion('arctan', math.atan, args[0])

    def _eb_arctan2(self, *args):
        self._pruefe_args('arctan2', args, 2)
        try:
            return math.atan2(args[0], args[1])
        except TypeError:
            raise TypeError(f"'arctan2' erwartet zwei Zahlen, bekam {self._typname(args[0])} und {self._typname(args[1])}")

    def _arkusfunktion(self, name, fn, wert):
        try:
            return fn(wert)
        except TypeError:
            raise TypeError(f"'{name}' erwartet eine Zahl, bekam {self._typname(wert)}")
        except ValueError:  # nur arcsin/arccos: Definitionsbereich -1 bis 1
            raise ValueError(f"'{name}' nicht definiert für {self._zu_text(wert)}, erlaubt sind Werte von -1 bis 1")

    def _eb_ggt(self, *args):
        if not args:
            raise TypeError("'ggt' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], (list, set)) else list(args)
        try:
            return math.gcd(*[int(w) for w in werte])
        except (TypeError, ValueError):
            raise TypeError("'ggt' erwartet Ganzzahlen")

    def _eb_kgv(self, *args):
        if not args:
            raise TypeError("'kgv' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], (list, set)) else list(args)
        try:
            return math.lcm(*[int(w) for w in werte])
        except (TypeError, ValueError):
            raise TypeError("'kgv' erwartet Ganzzahlen")

    def _eb_vorzeichen(self, *args):
        self._pruefe_args('vorzeichen', args, 1)
        try:
            wert = args[0]
            return (wert > 0) - (wert < 0)
        except TypeError:
            raise TypeError(f"'vorzeichen' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_logarithmus(self, *args):
        if len(args) not in (1, 2):
            raise TypeError(f"'logarithmus' erwartet 1–2 Argumente, bekam {len(args)}")
        try:
            return math.log(args[0]) if len(args) == 1 else math.log(args[0], args[1])
        except ZeroDivisionError:  # nur bei Basis 1: log(Basis) ist 0
            raise ZeroDivisionError(f"'logarithmus' ist mit Basis {self._zu_text(args[1])} nicht definiert")
        except ValueError:
            raise ValueError(f"'logarithmus' nicht definiert für {self._zu_text(args[0])}")
        except TypeError:
            falsch = next((a for a in args if not isinstance(a, (int, float))), args[0])
            raise TypeError(f"'logarithmus' erwartet eine Zahl, bekam {self._typname(falsch)}")

    def _eb_datei_lesen(self, *args):
        self._pruefe_args('datei_lesen', args, 1)
        return self._lese_datei(self._zu_text(args[0]), lambda f: f.read())

    def _lese_datei(self, pfad: str, lese):
        """Gemeinsame Fehlerübersetzung für datei_lesen und zeilen_lesen.
        lese(f) liest aus der bereits geöffneten Datei."""
        voller_pfad = self._pfad_vorpruefen(pfad)
        try:
            with open(voller_pfad, 'r', encoding='utf-8') as f:
                return lese(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Datei nicht gefunden: '{pfad}'")
        except IsADirectoryError:
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Lesen von '{pfad}'")
        except UnicodeDecodeError:
            raise ValueError(f"'{pfad}' ist keine gültige UTF-8-Textdatei")
        except OSError:
            raise OSError(f"'{pfad}' konnte nicht gelesen werden")

    def _schreibe_datei(self, pfad: str, modus: str, schreibe):
        """Gemeinsame Fehlerübersetzung für datei_schreiben, datei_anhängen und json_schreiben.
        schreibe(f) schreibt in die bereits geöffnete Datei."""
        voller_pfad = self._pfad_vorpruefen(pfad)
        try:
            with open(voller_pfad, modus, encoding='utf-8') as f:
                schreibe(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Verzeichnis für '{pfad}' existiert nicht")
        except IsADirectoryError:
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Schreiben von '{pfad}'")
        except OSError:
            raise OSError(f"'{pfad}' konnte nicht geschrieben werden")
        except UnicodeEncodeError:
            raise ValueError(f"Inhalt für '{pfad}' enthält Zeichen, die sich nicht als UTF-8 speichern lassen")

    def _eb_datei_schreiben(self, *args):
        self._pruefe_args('datei_schreiben', args, 2)
        pfad, inhalt = self._zu_text(args[0]), self._zu_text(args[1])
        self._schreibe_datei(pfad, 'w', lambda f: f.write(inhalt))
        return None

    def _eb_datei_anhaengen(self, *args):
        self._pruefe_args('datei_anhängen', args, 2)
        pfad, inhalt = self._zu_text(args[0]), self._zu_text(args[1])
        self._schreibe_datei(pfad, 'a', lambda f: f.write(inhalt))
        return None

    def _eb_zeilen_lesen(self, *args):
        self._pruefe_args('zeilen_lesen', args, 1)
        return self._lese_datei(self._zu_text(args[0]), lambda f: [zeile.rstrip('\n') for zeile in f])

    def _eb_datei_loeschen(self, *args):
        self._pruefe_args('datei_loeschen', args, 1)
        pfad = self._zu_text(args[0])
        voller_pfad = self._pfad_vorpruefen(pfad)  # Ordner meldet das vorab als 'ist ein Ordner, keine Datei'
        try:
            os.remove(voller_pfad)
        except FileNotFoundError:
            raise FileNotFoundError(f"Datei nicht gefunden: '{pfad}'")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Löschen von '{pfad}'")
        except OSError:
            raise OSError(f"'{pfad}' konnte nicht gelöscht werden")
        return None

    def _eb_umbenennen(self, *args):
        self._pruefe_args('umbenennen', args, 2)
        alt, neu = self._zu_text(args[0]), self._zu_text(args[1])
        voller_alt = self._pfad_vorpruefen(alt, ordner_erlaubt=True)
        voller_neu = self._pfad_vorpruefen(neu, ordner_erlaubt=True)
        if not os.path.lexists(voller_alt):
            raise FileNotFoundError(f"Datei oder Ordner nicht gefunden: '{alt}'")
        if os.path.lexists(voller_neu):  # os.rename würde unter Linux still überschreiben
            raise FileExistsError(f"'{neu}' existiert bereits")
        try:
            os.rename(voller_alt, voller_neu)
        except FileNotFoundError:
            raise FileNotFoundError(f"Zielordner für '{neu}' existiert nicht")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Umbenennen von '{alt}'")
        except OSError:
            raise OSError(f"'{alt}' konnte nicht umbenannt werden")
        return None

    def _eb_pfad_verbinden(self, *args):
        if not args:
            raise TypeError("'pfad_verbinden' erwartet mindestens 1 Argument")
        return os.path.join(*[self._zu_text(a) for a in args])

    def _eb_dateiname(self, *args):
        self._pruefe_args('dateiname', args, 1)
        return os.path.basename(self._zu_text(args[0]))

    def _eb_ordnername(self, *args):
        """Pfad des enthaltenden Ordners ('a/b/c.txt' -> 'a/b', wie os.path.dirname); leer, wenn kein Ordneranteil da ist.
        Passt zu pfad_verbinden(ordnername(p), dateiname(p))."""
        self._pruefe_args('ordnername', args, 1)
        return os.path.dirname(self._zu_text(args[0]))

    def _eb_endung(self, *args):
        self._pruefe_args('endung', args, 1)
        return os.path.splitext(self._zu_text(args[0]))[1]

    def _eb_ist_datei(self, *args):
        self._pruefe_args('ist_datei', args, 1)
        return os.path.isfile(self._pfad_aufloesen(self._zu_text(args[0])))

    def _eb_ist_ordner(self, *args):
        self._pruefe_args('ist_ordner', args, 1)
        return os.path.isdir(self._pfad_aufloesen(self._zu_text(args[0])))

    def _eb_boden(self, *args):
        self._pruefe_args('boden', args, 1)
        try:
            return math.floor(args[0])
        except TypeError:
            raise TypeError(f"'boden' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_decke(self, *args):
        self._pruefe_args('decke', args, 1)
        try:
            return math.ceil(args[0])
        except TypeError:
            raise TypeError(f"'decke' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_zufall(self, *args):
        self._pruefe_args('zufall', args, 0)
        return random.random()

    def _eb_zufallszahl(self, *args):
        self._pruefe_args('zufallszahl', args, 2)
        try:
            lo, hi = int(args[0]), int(args[1])
        except (ValueError, TypeError):
            raise TypeError("'zufallszahl' erwartet zwei Ganzzahlen")
        if lo > hi:
            raise ValueError(f"'zufallszahl' erwartet erstes Argument <= zweites, bekam {lo} > {hi}")
        return random.randint(lo, hi)

    def _eb_mische(self, *args):
        self._pruefe_args('mische', args, 1)
        if not isinstance(args[0], list):
            raise TypeError("'mische' erwartet eine Liste")
        random.shuffle(args[0])
        return None

    def _eb_summe(self, *args):
        werte = args[0] if len(args) == 1 and isinstance(args[0], (list, set)) else list(args)
        try:
            return sum(werte)
        except TypeError:
            raise TypeError("'summe' erwartet Zahlen")

    def _eb_alle(self, *args):
        self._pruefe_args('alle', args, 1)
        if not isinstance(args[0], (list, set)):
            raise TypeError("'alle' erwartet eine Liste oder Menge")
        return all(self._ist_wahr(e) for e in args[0])

    def _eb_einige(self, *args):
        self._pruefe_args('einige', args, 1)
        if not isinstance(args[0], (list, set)):
            raise TypeError("'einige' erwartet eine Liste oder Menge")
        return any(self._ist_wahr(e) for e in args[0])

    def _eb_aufzaehlen(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("'aufzaehlen' erwartet 1–2 Argumente")
        if not isinstance(args[0], (list, set)):
            raise TypeError("'aufzaehlen' erwartet eine Liste oder Menge")
        start = int(args[1]) if len(args) == 2 else 0
        return [[i, e] for i, e in enumerate(args[0], start=start)]

    def _eb_zippe(self, *args):
        if len(args) < 1:
            raise TypeError("'zippe' erwartet mindestens 1 Argument")
        for a in args:
            if not isinstance(a, (list, str)):
                raise TypeError("'zippe' erwartet Listen oder Zeichenketten")
        return [list(t) for t in zip(*args)]

    def _eb_json_lesen(self, *args):
        self._pruefe_args('json_lesen', args, 1)
        pfad = self._zu_text(args[0])
        voller_pfad = self._pfad_vorpruefen(pfad)
        try:
            with open(voller_pfad, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Datei nicht gefunden: '{pfad}'")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Lesen von '{pfad}'")
        except UnicodeDecodeError:
            raise ValueError(f"'{pfad}' ist keine gültige UTF-8-Textdatei")
        except json.JSONDecodeError as e:
            # Keine Zeilenangabe im Text: 'Zeile' würde die Zeilennummer des Skripts unterdrücken
            raise ValueError(f"Ungültiges JSON in '{pfad}' (Zeichen {e.pos})")
        except RecursionError:
            raise RecursionError(f"JSON in '{pfad}' ist zu tief verschachtelt")
        except OSError:
            raise OSError(f"'{pfad}' konnte nicht gelesen werden")

    def _eb_json_schreiben(self, *args):
        self._pruefe_args('json_schreiben', args, 2)
        pfad, wert = self._zu_text(args[0]), args[1]
        # Erst prüfen und umwandeln, dann die Datei anlegen: ein Fehler mitten im Schreiben
        # ließe sonst eine halbe JSON-Datei zurück
        try:
            bereit = self._json_bereit(wert)
        except RecursionError:
            raise RecursionError('Wert ist zu tief verschachtelt, um als JSON gespeichert zu werden')
        self._schreibe_datei(pfad, 'w', lambda f: json.dump(bereit, f, ensure_ascii=False, indent=2))
        return None

    def _eb_kommandozeilen_argumente(self, *args):
        self._pruefe_args('kommandozeilen_argumente', args, 0)
        return list(self._cli_argumente)

    def _eb_passt_zu(self, *args):
        self._pruefe_args('passt_zu', args, 2)
        muster, text = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            return re.search(muster, text) is not None
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")

    def _eb_regex_ersetze(self, *args):
        self._pruefe_args('regex_ersetze', args, 3)
        muster, ersatz, text = (self._zu_text(a) for a in args)
        try:
            return re.sub(muster, ersatz, text)
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")

    def _eb_regex_finde(self, *args):
        self._pruefe_args('regex_finde', args, 2)
        muster, text = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            treffer = re.search(muster, text)
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")
        return treffer.group(0) if treffer else None

    def _eb_regex_finde_alle(self, *args):
        self._pruefe_args('regex_finde_alle', args, 2)
        muster, text = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            treffer = re.findall(muster, text)
        except re.error as e:
            raise ValueError(f"Ungültiges Muster '{muster}': {e}")
        return [list(t) if isinstance(t, tuple) else t for t in treffer]

    def _eb_jetzt(self, *args):
        self._pruefe_args('jetzt', args, 0)
        return time.time()

    def _eb_datum_formatieren(self, *args):
        self._pruefe_args('datum_formatieren', args, 2)
        zeitstempel, format_str = args[0], self._zu_text(args[1])
        try:
            return datetime.fromtimestamp(zeitstempel).strftime(format_str)
        except (TypeError, ValueError, OSError) as e:
            raise ValueError(f"Ungültiger Zeitstempel oder Format: {e}")

    def _eb_datum_lesen(self, *args):
        """Gegenstück zu datum_formatieren: Text nach Formatangabe -> Zeitstempel (lokale Zeit, wie jetzt())."""
        self._pruefe_args('datum_lesen', args, 2)
        text, format_str = self._zu_text(args[0]), self._zu_text(args[1])
        try:
            return datetime.strptime(text, format_str).timestamp()
        except ValueError:
            raise ValueError(f"'{text}' passt nicht zum Format '{format_str}'")
        except (OverflowError, OSError):
            raise ValueError(f"'{text}' liegt außerhalb des darstellbaren Datumsbereichs")

    def _eb_warte(self, *args):
        self._pruefe_args('warte', args, 1)
        sekunden = args[0]
        if not isinstance(sekunden, (int, float)):
            raise TypeError(f"'warte' erwartet eine Zahl, bekam {self._typname(sekunden)}")
        if not 0 <= sekunden < float('inf'):  # NaN fällt hier auch heraus
            raise ValueError(f"'warte' erwartet eine Zeit von 0 oder mehr Sekunden, bekam {self._zu_text(sekunden)}")
        time.sleep(sekunden)
        return None

    def _eb_mittelwert(self, *args):
        self._pruefe_args('mittelwert', args, 1)
        if not isinstance(args[0], (list, set)):
            raise TypeError("'mittelwert' erwartet eine Liste oder Menge")
        try:
            return statistics.mean(args[0])
        except statistics.StatisticsError:
            raise ValueError("'mittelwert' erwartet eine nicht-leere Liste")

    def _eb_median(self, *args):
        self._pruefe_args('median', args, 1)
        if not isinstance(args[0], (list, set)):
            raise TypeError("'median' erwartet eine Liste oder Menge")
        try:
            return statistics.median(args[0])
        except statistics.StatisticsError:
            raise ValueError("'median' erwartet eine nicht-leere Liste")

    def _eb_stdabweichung(self, *args):
        self._pruefe_args('stdabweichung', args, 1)
        if not isinstance(args[0], (list, set)):
            raise TypeError("'stdabweichung' erwartet eine Liste oder Menge")
        try:
            return statistics.pstdev(args[0])
        except statistics.StatisticsError:
            raise ValueError("'stdabweichung' erwartet eine nicht-leere Liste")

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
            raise TypeError("'umgebungsvariable' erwartet 1–2 Argumente")
        name = self._zu_text(args[0])
        if len(args) == 2:
            return os.environ.get(name, args[1])
        return os.environ.get(name)

    def _eb_pfad_existiert(self, *args):
        self._pruefe_args('pfad_existiert', args, 1)
        return os.path.exists(self._pfad_aufloesen(self._zu_text(args[0])))

    def _eb_dateien_auflisten(self, *args):
        self._pruefe_args('dateien_auflisten', args, 1)
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
        self._pruefe_args('ordner_erstellen', args, 1)
        pfad = self._zu_text(args[0])
        try:
            os.makedirs(self._pfad_aufloesen(pfad), exist_ok=True)
        except FileExistsError:
            raise FileExistsError(f"'{pfad}' existiert bereits als Datei, kann nicht als Ordner erstellt werden")
        except PermissionError:
            raise PermissionError(f"Keine Berechtigung zum Erstellen von '{pfad}'")
        return None

    def _eb_hash_sha256(self, *args):
        self._pruefe_args('hash_sha256', args, 1)
        return hashlib.sha256(self._zu_text(args[0]).encode('utf-8')).hexdigest()

    def _eb_base64_kodieren(self, *args):
        self._pruefe_args('base64_kodieren', args, 1)
        return base64.b64encode(self._zu_text(args[0]).encode('utf-8')).decode('ascii')

    def _eb_base64_dekodieren(self, *args):
        self._pruefe_args('base64_dekodieren', args, 1)
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

    def _typname(self, wert) -> str:
        if wert is None:              return 'Nichts'
        if isinstance(wert, bool):    return 'Wahrheitswert'
        if isinstance(wert, int):     return 'Ganzzahl'
        if isinstance(wert, float):   return 'Kommazahl'
        if isinstance(wert, str):     return 'Zeichenkette'
        if isinstance(wert, list):    return 'Liste'
        if isinstance(wert, dict):    return 'Woerterbuch'
        if isinstance(wert, set):     return 'Menge'
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
        if isinstance(wert, (str, list, dict, set)): return len(wert) > 0
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
        try:
            for anw in k.anweisungen:
                ergebnis = self._besuche_anweisung(anw, u)
        except _KONTROLLSIGNALE as signal:
            # Oberste Ebene (auch eine per 'lade' geladene Datei): kein Schleifen-/Funktionskontext
            raise self._signal_fehler_hier(signal) from None
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
            if zeile is not None and 'Zeile' not in str(e):
                self._letzter_aufruf_stack = list(self._aufruf_stack)
                nachricht = f'{self._ort(zeile)}: {e}'
                if isinstance(e, AusnahmeFehler):
                    neu = AusnahmeFehler(e.wert, nachricht=nachricht)
                else:
                    neu = self._fehler_neu_mit_meldung(e, nachricht)
                # Fundort als Attribute: Datei (absoluter Pfad, None = Hauptskript/REPL) und Zeile
                neu.datei = self._aktuelle_datei
                neu.zeile = zeile
                raise neu from e
            raise

    @staticmethod
    def _fehler_neu_mit_meldung(e: Exception, nachricht: str) -> Exception:
        """Baut e mit neuer Meldung neu. Typen mit mehreren Pflichtargumenten (z. B. UnicodeDecodeError)
        fallen auf den nächsten Basistyp zurück, der eine einzelne Meldung annimmt; so greift
        'fange (ValueError)' weiterhin. Notfalls RuntimeError."""
        for klasse in type(e).__mro__:
            if not issubclass(klasse, Exception):
                continue
            try:
                return klasse(nachricht)
            except TypeError:
                continue
        return RuntimeError(nachricht)

    def _ort(self, zeile: int) -> str:
        """'Zeile 3' im Hauptskript, 'hilfe.deu, Zeile 3' in einer per 'lade' geladenen Datei."""
        if self._aktuelle_datei is None:
            return f'Zeile {zeile}'
        return f'{self._datei_anzeigename(self._aktuelle_datei)}, Zeile {zeile}'

    def _datei_anzeigename(self, pfad: str) -> str:
        """Pfad relativ zum Ordner des Hauptskripts (mit '/'), außerhalb davon der volle Pfad."""
        try:
            relativ = os.path.relpath(pfad, self._ladepfad)
        except ValueError:  # z. B. anderes Laufwerk unter Windows
            return pfad
        if relativ == os.pardir or relativ.startswith(os.pardir + os.sep):
            return pfad
        return relativ.replace(os.sep, '/')

    def _signal_fehler_hier(self, signal) -> RuntimeError:
        """Wie _signal_fehler, nennt aber die Datei, in der gerade Code läuft."""
        if self._aktuelle_datei is None:
            return _signal_fehler(signal)
        return _signal_fehler(signal, self._aktuelle_datei, self._datei_anzeigename(self._aktuelle_datei))

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

    # Entpacken ('*x', '**x'): erlaubt sind Listen, Mengen, Zeichenketten und Wörterbücher (deren Schlüssel)
    _ENTPACKBAR = (list, tuple, set, frozenset, str, dict)

    def _entpackte_elemente(self, knoten, u):
        """Wert von '*ausdruck' (ast.Entpacken): eine Sammlung, deren Elemente eingesetzt werden."""
        wert = self._besuche(knoten.ausdruck, u)
        if not isinstance(wert, self._ENTPACKBAR):
            raise TypeError(f"Entpacken mit '*' erwartet eine Liste, Menge, Zeichenkette oder ein "
                            f"Wörterbuch, bekam {self._typname(wert)}")
        return wert

    def _entpacktes_woerterbuch(self, ausdruck, u):
        """Wert von '**ausdruck': ein Wörterbuch, dessen Einträge eingesetzt werden."""
        wert = self._besuche(ausdruck, u)
        if not isinstance(wert, dict):
            raise TypeError(f"Entpacken mit '**' erwartet ein Wörterbuch, bekam {self._typname(wert)}")
        return wert

    def _elemente_mit_entpacken(self, elemente, u):
        ergebnis = []
        for e in elemente:
            if isinstance(e, ast.Entpacken):
                ergebnis.extend(self._entpackte_elemente(e, u))
            else:
                ergebnis.append(self._besuche(e, u))
        return ergebnis

    def _besuche_Liste(self, k, u):
        if k.mit_entpacken:
            return self._elemente_mit_entpacken(k.elemente, u)
        return [self._besuche(e, u) for e in k.elemente]

    def _besuche_Woerterbuch(self, k, u):
        if not k.mit_entpacken:
            return {self._besuche(kk, u): self._besuche(ww, u) for kk, ww in k.paare}
        ergebnis = {}
        for kk, ww in k.paare:
            if kk is None:  # '**x': spätere Schlüssel überschreiben frühere
                ergebnis.update(self._entpacktes_woerterbuch(ww, u))
            else:
                schluessel = self._besuche(kk, u)
                ergebnis[schluessel] = self._besuche(ww, u)
        return ergebnis

    def _besuche_MengenLiteral(self, k, u):
        if k.mit_entpacken:
            elemente = self._elemente_mit_entpacken(k.elemente, u)
        else:
            elemente = [self._besuche(e, u) for e in k.elemente]
        try:
            return set(elemente)
        except TypeError:
            raise TypeError('Mengen-Elemente müssen hashbar sein (keine Listen/Wörterbücher)')

    def _besuche_ListenAusdruck(self, k, u):
        iterable = self._besuche(k.iterable, u)
        ergebnis = []
        for elem in self._iteriere(iterable):
            iter_u = Umgebung(u)
            self._schleifenvariable_binden(k.variable, elem, iter_u)
            if k.bedingung is None or self._ist_wahr(self._besuche(k.bedingung, iter_u)):
                ergebnis.append(self._besuche(k.ausdruck, iter_u))
        return ergebnis

    def _schleifenvariable_binden(self, variable, elem, u):
        """variable: str (einfache Bindung) | ast.Muster (Destrukturierung)."""
        if isinstance(variable, ast.Muster):
            paare = []
            self._muster_zerlegen(variable, elem, paare)
            for name, wert in paare:
                u.setze(name, wert)
        else:
            u.setze(variable, elem)

    @staticmethod
    def _werte_text(n):
        return '1 Wert' if n == 1 else f'{n} Werte'

    def _muster_zerlegen(self, muster, wert, paare):
        """Verteilt wert auf die Ziele des Musters und hängt (ziel, teilwert) für jedes Blatt an paare an.
        Prüft zuerst alles (Typ, Anzahl, verschachtelte Muster); erst danach darf jemand binden/zuweisen.
        Ein Rest-Ziel ('*r') bekommt eine Liste; Blätter sind Namen (str) oder Zuweisungsziele (Knoten)."""
        if not isinstance(wert, (list, tuple)):
            raise TypeError(f"Destrukturierung erwartet eine Liste, bekam {self._typname(wert)}")
        ziele = muster.ziele
        if muster.rest is None:
            if len(wert) != len(ziele):
                raise TypeError(f"Destrukturierung erwartet {self._werte_text(len(ziele))}, bekam {len(wert)}")
            teile = list(wert)
        else:
            mindestens = len(ziele) - 1
            if len(wert) < mindestens:
                raise TypeError(
                    f"Destrukturierung erwartet mindestens {self._werte_text(mindestens)}, bekam {len(wert)}")
            nach_rest = len(ziele) - muster.rest - 1
            ende = len(wert) - nach_rest
            teile = list(wert[:muster.rest]) + [list(wert[muster.rest:ende])] + list(wert[ende:])
        for ziel, teil in zip(ziele, teile):
            if isinstance(ziel, ast.Muster):
                self._muster_zerlegen(ziel, teil, paare)
            else:
                paare.append((ziel, teil))

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
            u.setze_konstante(k.name, wert, k.typhinweis)
        else:
            u.setze(k.name, wert, k.typhinweis)
        return wert

    def _besuche_DestrukturierendeDeklaration(self, k, u):
        wert = self._besuche(k.wert, u)
        paare = []
        self._muster_zerlegen(k.muster, wert, paare)
        for name, einzelwert in paare:
            u.setze(name, einzelwert)
        return wert

    def _besuche_Zuweisung(self, k, u):
        wert = self._besuche(k.wert, u)
        self._ziel_setzen(k.ziel, wert, u)
        return wert

    def _besuche_KettenZuweisung(self, k, u):
        # a = b = ausdruck: Wert einmal auswerten; alle Namen müssen vorher existieren,
        # damit bei einem unbekannten Namen keines der Ziele schon verändert ist
        wert = self._besuche(k.wert, u)
        for ziel in k.ziele:
            self._ziel_vorpruefen(ziel, u)
        for ziel in k.ziele:
            self._ziel_setzen(ziel, wert, u)
        return wert

    def _ziel_vorpruefen(self, ziel, u):
        """Wirft den NameError für noch nicht deklarierte Namen, bevor irgendetwas zugewiesen wird."""
        if isinstance(ziel, ast.Bezeichner):
            if not u.existiert(ziel.name):
                raise NameError(u.nicht_deklariert_meldung(ziel.name))
        elif isinstance(ziel, ast.Muster):
            for teilziel in ziel.ziele:
                self._ziel_vorpruefen(teilziel, u)

    def _besuche_VerbundZuweisung(self, k, u):
        if isinstance(k.ziel, ast.Bezeichner) and not u.existiert(k.ziel.name):
            raise NameError(u.nicht_deklariert_meldung(k.ziel.name))
        alter_wert = self._besuche(k.ziel, u)
        delta = self._besuche(k.wert, u)
        neuer_wert = self._binaerer_operator(k.operator, alter_wert, delta)
        self._ziel_setzen(k.ziel, neuer_wert, u)
        return neuer_wert

    def _ziel_setzen(self, ziel, wert, u):
        if isinstance(ziel, ast.Muster):
            # [a, b] = …: erst vollständig zerlegen und Namen prüfen, dann zuweisen
            paare = []
            self._muster_zerlegen(ziel, wert, paare)
            self._ziel_vorpruefen(ziel, u)
            for teilziel, teilwert in paare:
                self._ziel_setzen(teilziel, teilwert, u)
        elif isinstance(ziel, ast.Bezeichner):
            # Existiert der Name in keinem Scope, wirft weise_zu einen NameError (neue Variablen: 'sei')
            u.weise_zu(
                ziel.name, wert,
                lambda w, hinweis, scope: self._pruefe_typ(w, hinweis, f"Variable '{ziel.name}'", scope),
            )
        elif isinstance(ziel, ast.AttributZugriff):
            obj = self._besuche(ziel.objekt, u)
            if isinstance(obj, DeutschInstanz):
                obj.setze_attribut(ziel.attribut, wert)
            elif isinstance(obj, DeutschKlasse):
                if ziel.attribut in obj.konstante_attribute:
                    raise TypeError(
                        f"'{ziel.attribut}' ist eine Konstante der Klasse '{obj.name}' "
                        f"und kann nicht neu zugewiesen werden"
                    )
                obj.klassenattribute[ziel.attribut] = wert
            else:
                raise TypeError(f"Kann Attribut von '{self._typname(obj)}' nicht setzen")
        elif isinstance(ziel, ast.IndexZugriff):
            if isinstance(ziel.index, ast.SliceAusdruck):
                raise TypeError('Slice-Zuweisung wird nicht unterstützt')
            obj = self._besuche(ziel.objekt, u)
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
        if k.operator == '??':
            # Null-Koaleszenz: rechts wird nur ausgewertet, wenn links 'nichts' ist
            l = self._besuche(k.links, u)
            return l if l is not None else self._besuche(k.rechts, u)

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
            if op == '**':  return l ** r
            if op == '%':
                if r == 0: raise ZeroDivisionError('Division durch Null')
                return l % r
            if op in _BIT_OPERATOREN: return self._bit_operator(op, l, r)
            if op == '==':  return l == r
            if op == '!=':  return l != r
            if op == '<':   return l < r
            if op == '>':   return l > r
            if op == '<=':  return l <= r
            if op == '>=':  return l >= r
            if op == 'in':  return l in r
            if op == 'nicht in': return l not in r
        except TypeError:
            raise TypeError(
                f"Operator '{op}' nicht unterstützt für {self._typname(l)} und {self._typname(r)}"
            )
        raise RuntimeError(f'Unbekannter Operator: {op!r}')

    def _bit_operator(self, op, l, r):
        """& | ^ << >> für Ganzzahlen; & | ^ zusätzlich für Mengen (Schnitt, Vereinigung, symm. Differenz).
        Alles andere (auch Wörterbücher und Kommazahlen) ist ein Typfehler."""
        if isinstance(l, int) and isinstance(r, int):
            if op == '&': return l & r
            if op == '|': return l | r
            if op == '^': return l ^ r
            if r < 0:
                raise ValueError('Negative Schiebezahl')
            if op == '>>': return l >> r
            try:
                return l << r
            except (OverflowError, MemoryError):
                raise OverflowError('Ergebnis der Linksschiebung ist zu groß')
        if isinstance(l, set) and isinstance(r, set):
            if op == '&': return l & r
            if op == '|': return l | r
            if op == '^': return l ^ r
        raise TypeError(
            f"Operator '{op}' nicht unterstützt für {self._typname(l)} und {self._typname(r)}"
        )

    def _besuche_UnaereOperation(self, k, u):
        val = self._besuche(k.operand, u)
        if k.operator == '-':
            try:
                return -val
            except TypeError:
                raise TypeError(f"Operator '-' nicht unterstützt für {self._typname(val)}")
        if k.operator == '~':
            if isinstance(val, int):
                return ~val
            raise TypeError(f"Operator '~' nicht unterstützt für {self._typname(val)}")
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
        iterable = self._besuche(k.iterable, u)
        schleifen_u = Umgebung(u)
        for elem in self._iteriere(iterable):
            self._schleifenvariable_binden(k.variable, elem, schleifen_u)
            try:
                self._besuche(k.koerper, schleifen_u)
            except _AbbrechenSignal: break
            except _WeiterSignal:    continue
        return None

    def _besuche_ZurueckAnweisung(self, k, u):
        wert = self._besuche(k.wert, u)
        raise _ZurueckSignal(wert, getattr(k, 'zeile', None))

    def _besuche_WerfeAnweisung(self, k, u):
        raise AusnahmeFehler(self._besuche(k.wert, u))

    def _besuche_PruefeAnweisung(self, k, u):
        if not self._ist_wahr(self._besuche(k.bedingung, u)):
            if k.meldung is not None:
                raise AssertionError(self._zu_text(self._besuche(k.meldung, u)))
            raise AssertionError('Prüfung fehlgeschlagen')
        return None

    def _besuche_AbbrechenAnweisung(self, k, u): raise _AbbrechenSignal(getattr(k, 'zeile', None))
    def _besuche_WeiterAnweisung(self, k, u):    raise _WeiterSignal(getattr(k, 'zeile', None))

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

    def _pfad_vorpruefen(self, pfad: str, ordner_erlaubt: bool = False) -> str:
        """Voller Pfad für open(). Nullzeichen und Ordner meldet es vorab auf Deutsch,
        bevor open() es unverständlich meldet. ordner_erlaubt: Ordner sind hier kein Fehler (z. B. umbenennen)."""
        if '\x00' in pfad:
            sichtbar = pfad.replace('\x00', '\\0')
            raise ValueError(f"'{sichtbar}' ist kein gültiger Dateipfad")
        voller_pfad = self._pfad_aufloesen(pfad)
        if not ordner_erlaubt and os.path.isdir(voller_pfad):  # unter Windows meldet open() auf einen Ordner sonst 'Permission denied'
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
        return voller_pfad

    def _json_bereit(self, wert, aktiv: frozenset = frozenset()):
        """Prüft wert auf JSON-Tauglichkeit und liefert eine reine Python-Kopie (Mengen werden sortierte Listen).
        Die Fehler kommen dabei auf Deutsch; json.dump wirft danach nur noch Ein-/Ausgabefehler."""
        if wert is None or isinstance(wert, (str, int, float)):  # bool ist ein int
            return wert
        if isinstance(wert, set):
            wert = self._sortiert(list(wert))
        if isinstance(wert, list):
            if id(wert) in aktiv:
                raise ValueError(f"Zirkulärer Verweis: '{self._typname(wert)}' enthält sich selbst und kann nicht als JSON gespeichert werden")
            innen = aktiv | {id(wert)}
            return [self._json_bereit(e, innen) for e in wert]
        if isinstance(wert, dict):
            if id(wert) in aktiv:
                raise ValueError(f"Zirkulärer Verweis: '{self._typname(wert)}' enthält sich selbst und kann nicht als JSON gespeichert werden")
            innen = aktiv | {id(wert)}
            ergebnis = {}
            for schluessel, eintrag in wert.items():
                if schluessel is not None and not isinstance(schluessel, (str, int, float)):
                    raise TypeError(f"Schlüssel vom Typ '{self._typname(schluessel)}' kann nicht als JSON gespeichert werden")
                ergebnis[schluessel] = self._json_bereit(eintrag, innen)
            return ergebnis
        raise TypeError(f"'{self._typname(wert)}' kann nicht als JSON gespeichert werden")

    def _besuche_PasseAnweisung(self, k, u):
        subjekt = self._besuche(k.ausdruck, u)
        for werte, block in k.faelle:
            if any(subjekt == self._besuche(w, u) for w in werte):
                return self._besuche(block, u)
        if k.sonst is not None:
            return self._besuche(k.sonst, u)
        return None

    def _lade_pfad_aufloesen(self, pfad: str) -> str:
        """Relative 'lade'-Pfade gelten ab dem Ordner der ladenden Datei; im Hauptskript
        (bzw. in der REPL) ab dem Ladepfad des Interpreters. Ergebnis: absolut und normalisiert."""
        if not os.path.isabs(pfad):
            basis = os.path.dirname(self._aktuelle_datei) if self._aktuelle_datei else self._ladepfad
            pfad = os.path.join(basis, pfad)
        return os.path.abspath(pfad)

    @staticmethod
    def _pfad_schluessel(pfad: str) -> str:
        """Vergleichsschlüssel für die Zyklus-Erkennung (Symlinks aufgelöst, unter Windows ohne Groß-/Kleinschreibung)."""
        return os.path.normcase(os.path.realpath(pfad))

    @staticmethod
    def _lade_quelltext(pfad: str) -> str:
        if os.path.isdir(pfad):  # unter Windows meldet open() auf einen Ordner sonst 'Permission denied'
            raise IsADirectoryError(f"'lade': '{pfad}' ist ein Ordner, keine Datei")
        try:
            with open(pfad, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"'lade': Datei nicht gefunden: '{pfad}'") from None
        except PermissionError:
            raise PermissionError(f"'lade': Keine Berechtigung zum Lesen von '{pfad}'") from None
        except UnicodeDecodeError:
            raise ValueError(f"'lade': '{pfad}' ist keine gültige UTF-8-Textdatei") from None
        except OSError:
            raise OSError(f"'lade': '{pfad}' konnte nicht gelesen werden") from None

    def _syntax_fehler_in_datei(self, fehler: SyntaxError, pfad: str) -> SyntaxError:
        """Ergänzt einen Lexer-/Parser-Fehler der geladenen Datei um ihren Namen: 'hilfe.deu, Zeile 3: ...'."""
        treffer = re.match(r'Zeile (\d+): ?(.*)', str(fehler), re.DOTALL)
        name = self._datei_anzeigename(pfad)
        if treffer:
            zeile = int(treffer.group(1))
            neu = SyntaxError(f'{name}, Zeile {zeile}: {treffer.group(2)}')
        else:
            zeile = None
            neu = SyntaxError(f'{name}: {fehler}')
        neu.datei = pfad  # nicht .filename/.lineno setzen: SyntaxError.__str__ hängt sie sonst an die Meldung
        neu.zeile = zeile
        return neu

    def _besuche_LadeAnweisung(self, k, u):
        from .lexer import Lexer
        from .parser import Parser
        roh = self._besuche(k.pfad, u)
        if not isinstance(roh, str):
            raise TypeError(f"'lade' erwartet einen Pfad als Zeichenkette, bekam {self._typname(roh)}")
        pfad = self._lade_pfad_aufloesen(roh)
        schluessel = self._pfad_schluessel(pfad)
        if any(self._pfad_schluessel(p) == schluessel for p in self._lade_stack):
            kette = ' -> '.join(os.path.basename(p) for p in self._lade_stack + [pfad])
            raise ImportError(f"Zyklischer 'lade'-Import erkannt: {kette}")
        quelltext = self._lade_quelltext(pfad)
        self._lade_stack.append(pfad)
        vorherige_datei = self._aktuelle_datei
        self._aktuelle_datei = pfad  # Fehler der Datei nennen ab hier ihren Namen, 'lade' darin gilt ab ihrem Ordner
        try:
            try:
                tokens = Lexer(quelltext).tokenisieren()
                baum = Parser(tokens).parse()
            except SyntaxError as e:
                raise self._syntax_fehler_in_datei(e, pfad) from None
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
            self._aktuelle_datei = vorherige_datei
            self._lade_stack.pop()

    # Funktionen
    def _besuche_FunktionDefinition(self, k, u):
        fn = DeutschFunktion(k, u, self._aktuelle_datei)
        if k.name is not None:
            u.setze(k.name, fn)
        return fn

    def _besuche_FunktionAufruf(self, k, u):
        fn = self._besuche(k.funktion, u)
        args, kwargs = self._argumente_auswerten(k, u)
        return self._aufrufen(fn, args, kwargs)

    def _argumente_auswerten(self, k, u):
        """Wertet die Argumente eines Aufrufs (FunktionAufruf, NeuInstanz) aus: (args, kwargs).
        Mit Entpacken: '*x' fügt die Elemente an der Stelle ein, '**x' die Einträge (Schlüssel = Namen)."""
        if not k.mit_entpacken:
            return ([self._besuche(a, u) for a in k.argumente],
                    {name: self._besuche(w, u) for name, w in k.keyword_argumente})
        args = self._elemente_mit_entpacken(k.argumente, u)
        kwargs = {}
        for name, w in k.keyword_argumente:
            if name is None:
                for schluessel, wert in self._entpacktes_woerterbuch(w, u).items():
                    if not isinstance(schluessel, str):
                        raise TypeError("Entpacken mit '**' in einem Aufruf braucht Zeichenketten als "
                                        f"Schlüssel, bekam {self._typname(schluessel)}")
                    if schluessel in kwargs:
                        raise TypeError(f"Keyword-Argument '{schluessel}' mehrfach angegeben")
                    kwargs[schluessel] = wert
            else:
                wert = self._besuche(w, u)
                if name in kwargs:
                    raise TypeError(f"Keyword-Argument '{name}' mehrfach angegeben")
                kwargs[name] = wert
        return args, kwargs

    def _aufrufen(self, fn, args, kwargs=None):
        kwargs = kwargs or {}
        if isinstance(fn, DeutschFunktion):
            return self._funktion_aufrufen(fn, args, kwargs)
        if isinstance(fn, GebundeneMethode):
            return self._funktion_aufrufen(fn.funktion, [fn.instanz] + args, kwargs)
        if callable(fn):
            if kwargs:
                ziel = fn.func if isinstance(fn, functools.partial) else fn
                if not getattr(ziel, '_akzeptiert_keywords', False):
                    raise TypeError("Eingebaute Funktionen unterstützen keine Keyword-Argumente")
                return fn(*args, **kwargs)
            return fn(*args)
        raise TypeError(f"'{self._zu_text(fn)}' ist nicht aufrufbar")

    def _funktion_aufrufen(self, fn: DeutschFunktion, args: list, kwargs: dict = None):
        kwargs = kwargs or {}
        fname = fn.definition.name or '<anonym>'
        params = fn.definition.parameter  # [(name, default, variadic, typhinweis), ...]

        # Parameterstruktur analysieren
        variadic_idx = next((i for i, (_, _, v, _) in enumerate(params) if v), None)
        param_namen = [p[0] for p in params]
        n_gesamt = len(params) - (1 if variadic_idx is not None else 0)  # ohne variadic

        kwargs_parameter = fn.definition.kwargs_parameter  # (name, typhinweis|None) | None
        ueberzaehlige = None
        if kwargs_parameter is None:
            unbekannt = [n for n in kwargs if n not in param_namen]
            if unbekannt:
                raise TypeError(f"'{fname}' hat kein Parameter '{unbekannt[0]}'")
            if variadic_idx is not None and param_namen[variadic_idx] in kwargs:
                raise TypeError(
                    f"Variadischer Parameter '{param_namen[variadic_idx]}' kann nicht per Keyword gesetzt werden"
                )
        else:
            # Mit '**name': jedes Keyword, das kein benannter Parameter ist, landet im Wörterbuch
            # (der '*'-Parameter ist per Keyword nicht ansprechbar, auch das geht ins Wörterbuch)
            benannte = {n for i, n in enumerate(param_namen) if i != variadic_idx}
            ueberzaehlige = {n: w for n, w in kwargs.items() if n not in benannte}
            kwargs = {n: w for n, w in kwargs.items() if n in benannte}
        if variadic_idx is None and len(args) > n_gesamt:
            raise TypeError(
                f"'{fname}' erwartet höchstens {n_gesamt} Argument(e), "
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
                        f"'{fname}' erhielt mehrere Werte für Parameter '{p_name}'"
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

        if kwargs_parameter is not None:
            self._pruefe_typ(ueberzaehlige, kwargs_parameter[1], f"Parameter '{kwargs_parameter[0]}'", fn.umgebung)
            fn_u.setze(kwargs_parameter[0], ueberzaehlige)

        if fehlende:
            raise TypeError(f"'{fname}': Pflichtargument(e) fehlen: {', '.join(fehlende)}")

        self._aufruf_stack.append((fname, self._aktuelle_zeile))
        vorherige_datei = self._aktuelle_datei
        self._aktuelle_datei = fn.datei  # Fehler und 'lade' im Körper gehören zur Datei der Definition
        try:
            kontext = f"Rückgabewert von '{fname}'"
            try:
                self._besuche(fn.definition.koerper, fn_u)
            except _ZurueckSignal as r:
                self._pruefe_typ(r.wert, fn.definition.typhinweis, kontext, fn.umgebung)
                return r.wert
            except (_AbbrechenSignal, _WeiterSignal) as signal:
                # Schleifen-Signale enden an der Funktionsgrenze und erreichen nie die Schleife des Aufrufers
                self._letzter_aufruf_stack = list(self._aufruf_stack)
                raise self._signal_fehler_hier(signal) from None
            self._pruefe_typ(None, fn.definition.typhinweis, kontext, fn.umgebung)
            return None
        finally:
            self._aktuelle_datei = vorherige_datei
            self._aufruf_stack.pop()

    # Klassen
    def _besuche_KlassenDefinition(self, k, u):
        eltern = []
        for eltern_name in k.eltern:
            eltern_klasse = u.hole(eltern_name)
            if not isinstance(eltern_klasse, DeutschKlasse):
                raise TypeError(f"'{eltern_name}' ist keine Klasse")
            eltern.append(eltern_klasse)
        datei = self._aktuelle_datei
        methoden = {m.name: DeutschFunktion(m, u, datei) for m in k.methoden}
        statische_methoden = {m.name: DeutschFunktion(m, u, datei) for m in k.statische_methoden}
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
        klasse = self._besuche(k.klasse, u)  # Bezeichner oder Punktpfad (modul.Klasse)
        if not isinstance(klasse, DeutschKlasse):
            raise TypeError(f"'{k.name}' ist keine Klasse")
        instanz = DeutschInstanz(klasse)
        args, kwargs = self._argumente_auswerten(k, u)
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
            fn = self._listen_methoden.get(k.attribut)
            if fn is None:
                raise AttributeError(f"Liste hat kein Attribut '{k.attribut}'")
            return functools.partial(fn, obj)

        if isinstance(obj, str):
            fn = self._string_methoden.get(k.attribut)
            if fn is None:
                raise AttributeError(f"Zeichenkette hat kein Attribut '{k.attribut}'")
            return functools.partial(fn, obj)

        if isinstance(obj, dict):
            fn = self._woerterbuch_methoden.get(k.attribut)
            if fn is None:
                raise AttributeError(f"Wörterbuch hat kein Attribut '{k.attribut}'")
            return functools.partial(fn, obj)

        if isinstance(obj, set):
            fn = self._menge_methoden.get(k.attribut)
            if fn is None:
                raise AttributeError(f"Menge hat kein Attribut '{k.attribut}'")
            return functools.partial(fn, obj)

        raise AttributeError(f"Typ '{self._typname(obj)}' hat kein Attribut '{k.attribut}'")

    def _eb_zusammenfuehren(self, *args):
        if not args:
            raise TypeError("'zusammenführen' erwartet mindestens 1 Argument")
        return self._woerterbuecher_zusammenfuehren('zusammenführen', args)

    def _woerterbuecher_zusammenfuehren(self, name, woerterbuecher):
        """Neues Wörterbuch aus allen Eingaben; bei gleichen Schlüsseln gewinnt der spätere Wert."""
        ergebnis = {}
        for wb in woerterbuecher:
            if not isinstance(wb, dict):
                raise TypeError(f"'{name}' erwartet Wörterbücher, bekam {self._typname(wb)}")
            ergebnis.update(wb)
        return ergebnis

    @staticmethod
    def _woerterbuch_entferne(obj, schluessel):
        try:
            return obj.pop(schluessel)
        except KeyError:
            raise SchluesselFehler(f"Schlüssel '{schluessel}' nicht im Wörterbuch")

    def _slice_bauen(self, slice_knoten, u):
        start = self._besuche(slice_knoten.start, u) if slice_knoten.start is not None else None
        stop = self._besuche(slice_knoten.stop, u) if slice_knoten.stop is not None else None
        step = self._besuche(slice_knoten.step, u) if slice_knoten.step is not None else None
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
