# -*- coding: utf-8 -*-
import os
import math
import functools
import random
import json
import re
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


class DeutschKlasse:
    def __init__(self, name: str, eltern: list, methoden: dict):
        self.name = name
        self.eltern: list['DeutschKlasse'] = eltern
        self.methoden = methoden  # {name: DeutschFunktion}

    def suche_methode(self, name: str):
        if name in self.methoden:
            return self.methoden[name]
        for e in self.eltern:  # links-nach-rechts, Tiefensuche, erster Treffer gewinnt
            m = e.suche_methode(name)
            if m is not None:
                return m
        return None

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
            'entferne':  lambda obj, *a: obj.pop(int(a[0])) if a else obj.pop(),
            'enthält':   lambda obj, x: x in obj,
            'umkehren':  lambda obj: (obj.reverse(), None)[1],
            'sortiere':  lambda obj: self._sortiert(obj, in_place=True),
            'erste':     lambda obj: obj[0] if obj else None,
            'letzte':    lambda obj: obj[-1] if obj else None,
            'kopiere':   lambda obj: list(obj),
            'flach':     lambda obj: [e for sub in obj for e in (sub if isinstance(sub, list) else [sub])],
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
            'ersetze':       lambda obj, alt, neu: obj.replace(alt, neu),
            'trimmen':       lambda obj: obj.strip(),
            'links_trimmen': lambda obj: obj.lstrip(),
            'rechts_trimmen':lambda obj: obj.rstrip(),
            'beginnt_mit':   lambda obj, x: obj.startswith(x),
            'endet_mit':     lambda obj, x: obj.endswith(x),
            'grossschreibe': lambda obj: obj.capitalize(),
            'großschreibe':  lambda obj: obj.capitalize(),
            'zeichen':       lambda obj: list(obj),
            'wiederhole':    lambda obj, n: obj * int(n),
            'zahl':          lambda obj: int(obj) if obj.lstrip('-').isdigit() else float(obj),
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

    def _eb_drucke(self, *args):
        print(' '.join(self._zu_text(a) for a in args))
        return None

    def _eb_eingabe(self, *args):
        return input(self._zu_text(args[0]) if args else '')

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

    def _eb_sortiere(self, *args):
        self._pruefe_args('sortiere', args, 1)
        if not isinstance(args[0], (list, set)):
            raise TypeError("'sortiere' erwartet eine Liste oder Menge")
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
        return liste.pop(int(args[1]) if len(args) == 2 else -1)

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
        if not args: raise TypeError("'max' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
        if not werte: raise ValueError("'max' erwartet eine nicht-leere Liste")
        return max(werte)

    def _eb_min(self, *args):
        if not args: raise TypeError("'min' erwartet mindestens 1 Argument")
        werte = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
        if not werte: raise ValueError("'min' erwartet eine nicht-leere Liste")
        return min(werte)

    def _eb_abs(self, *args):
        self._pruefe_args('abs', args, 1); return abs(args[0])

    def _eb_runde(self, *args):
        if len(args) not in (1, 2): raise TypeError("'runde' erwartet 1–2 Argumente")
        stellen = int(args[1]) if len(args) == 2 else 0
        return round(float(args[0]), stellen) if stellen > 0 else int(round(args[0]))

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

    def _eb_logarithmus(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("'logarithmus' erwartet 1–2 Argumente")
        try:
            return math.log(args[0]) if len(args) == 1 else math.log(args[0], args[1])
        except ValueError:
            raise ValueError(f"'logarithmus' nicht definiert für {args[0]}")
        except TypeError:
            raise TypeError(f"'logarithmus' erwartet eine Zahl, bekam {self._typname(args[0])}")

    def _eb_datei_lesen(self, *args):
        self._pruefe_args('datei_lesen', args, 1)
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
        self._pruefe_args('datei_schreiben', args, 2)
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
        self._pruefe_args('datei_anhängen', args, 2)
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
        try:
            with open(self._pfad_aufloesen(pfad), 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Datei nicht gefunden: '{pfad}'")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ungültiges JSON in '{pfad}': {e}")

    def _eb_json_schreiben(self, *args):
        self._pruefe_args('json_schreiben', args, 2)
        pfad, wert = self._zu_text(args[0]), args[1]

        def _konvertiere(o):
            if isinstance(o, set):
                return self._sortiert(list(o))
            raise TypeError(f"'{self._typname(o)}' kann nicht als JSON gespeichert werden")

        try:
            with open(self._pfad_aufloesen(pfad), 'w', encoding='utf-8') as f:
                json.dump(wert, f, default=_konvertiere, ensure_ascii=False, indent=2)
        except IsADirectoryError:
            raise IsADirectoryError(f"'{pfad}' ist ein Ordner, keine Datei")
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
        return {self._besuche(kk, u): self._besuche(ww, u) for kk, ww in k.paare}

    def _besuche_MengenLiteral(self, k, u):
        elemente = [self._besuche(e, u) for e in k.elemente]
        try:
            return set(elemente)
        except TypeError:
            raise TypeError('Mengen-Elemente müssen hashbar sein (keine Listen/Wörterbücher)')

    def _besuche_ListenAusdruck(self, k, u):
        iterable = self._besuche(k.iterable, u)
        ergebnis = []
        for elem in iterable:
            iter_u = Umgebung(u)
            iter_u.setze(k.variable, elem)
            if k.bedingung is None or self._ist_wahr(self._besuche(k.bedingung, iter_u)):
                ergebnis.append(self._besuche(k.ausdruck, iter_u))
        return ergebnis

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
            if u.existiert(ziel.name):
                u.weise_zu(ziel.name, wert)
            else:
                u.setze(ziel.name, wert)
        elif isinstance(ziel, ast.AttributZugriff):
            obj = self._besuche(ziel.objekt, u)
            if isinstance(obj, DeutschInstanz):
                obj.setze_attribut(ziel.attribut, wert)
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

        l = self._besuche(k.links, u)
        r = self._besuche(k.rechts, u)
        return self._binaerer_operator(k.operator, l, r)

    def _binaerer_operator(self, op, l, r):
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
            if op == '%':   return l % r
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

    def _besuche_UnaereOperation(self, k, u):
        val = self._besuche(k.operand, u)
        if k.operator == '-':    return -val
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
        for elem in iterable:
            schleifen_u.setze(k.variable, elem)
            try:
                self._besuche(k.koerper, schleifen_u)
            except _AbbrechenSignal: break
            except _WeiterSignal:    continue
        return None

    def _besuche_ZurueckAnweisung(self, k, u):
        raise _ZurueckSignal(self._besuche(k.wert, u))

    def _besuche_WerfeAnweisung(self, k, u):
        raise AusnahmeFehler(self._besuche(k.wert, u))

    def _besuche_AbbrechenAnweisung(self, k, u): raise _AbbrechenSignal()
    def _besuche_WeiterAnweisung(self, k, u):    raise _WeiterSignal()

    def _besuche_VersucheAnweisung(self, k, u):
        try:
            self._besuche(k.koerper, u)
        except _KONTROLLSIGNALE:
            raise  # Kontrollfluss-Signale niemals abfangen
        except Exception as e:
            if k.fange_koerper is not None:
                fange_u = Umgebung(u)
                if k.fange_name:
                    wert = e.wert if isinstance(e, AusnahmeFehler) else str(e)
                    fange_u.setze(k.fange_name, wert)
                self._besuche(k.fange_koerper, fange_u)
        finally:
            if k.endlich_koerper is not None:
                self._besuche(k.endlich_koerper, u)
        return None

    def _pfad_aufloesen(self, pfad: str) -> str:
        if not os.path.isabs(pfad):
            pfad = os.path.join(self._ladepfad, pfad)
        return os.path.normpath(pfad)

    def _besuche_PasseAnweisung(self, k, u):
        subjekt = self._besuche(k.ausdruck, u)
        for werte, block in k.faelle:
            if any(subjekt == self._besuche(w, u) for w in werte):
                return self._besuche(block, u)
        if k.sonst is not None:
            return self._besuche(k.sonst, u)
        return None

    def _besuche_LadeAnweisung(self, k, u):
        from .lexer import Lexer
        from .parser import Parser
        pfad = self._pfad_aufloesen(self._besuche(k.pfad, u))
        with open(pfad, 'r', encoding='utf-8') as f:
            quelltext = f.read()
        tokens = Lexer(quelltext).tokenisieren()
        baum = Parser(tokens).parse()
        # Im globalen Scope ausführen, damit geladene Definitionen sichtbar sind
        return self.ausfuehren(baum, self.global_umgebung)

    # Funktionen
    def _besuche_FunktionDefinition(self, k, u):
        fn = DeutschFunktion(k, u)
        if k.name is not None:
            u.setze(k.name, fn)
        return fn

    def _besuche_FunktionAufruf(self, k, u):
        fn = self._besuche(k.funktion, u)
        args = [self._besuche(a, u) for a in k.argumente]
        return self._aufrufen(fn, args)

    def _aufrufen(self, fn, args):
        if callable(fn):
            return fn(*args)
        if isinstance(fn, DeutschFunktion):
            return self._funktion_aufrufen(fn, args)
        if isinstance(fn, GebundeneMethode):
            return self._funktion_aufrufen(fn.funktion, [fn.instanz] + args)
        raise TypeError(f"'{self._zu_text(fn)}' ist nicht aufrufbar")

    def _funktion_aufrufen(self, fn: DeutschFunktion, args: list):
        params = fn.definition.parameter  # [(name, default, variadic, typhinweis), ...]

        # Parameterstruktur analysieren
        variadic_idx = next((i for i, (_, _, v, _) in enumerate(params) if v), None)
        n_pflicht = sum(1 for _, d, v, _ in params if d is None and not v)
        n_gesamt = len(params) - (1 if variadic_idx is not None else 0)  # ohne variadic

        if len(args) < n_pflicht:
            raise TypeError(
                f"'{fn.definition.name}' erwartet mindestens {n_pflicht} Argument(e), "
                f"bekam {len(args)}"
            )
        if variadic_idx is None and len(args) > n_gesamt:
            raise TypeError(
                f"'{fn.definition.name}' erwartet höchstens {n_gesamt} Argument(e), "
                f"bekam {len(args)}"
            )

        fn_u = Umgebung(fn.umgebung)
        for i, (p_name, p_default, p_variadic, p_typ) in enumerate(params):
            if p_variadic:
                fn_u.setze(p_name, list(args[i:]))
                break
            if i < len(args):
                wert = args[i]
                self._pruefe_typ(wert, p_typ, f"Parameter '{p_name}'", fn.umgebung)
                fn_u.setze(p_name, wert)
            elif p_default is not None:
                fn_u.setze(p_name, self._besuche(p_default, fn.umgebung))
            else:
                raise TypeError(f"Pflichtargument '{p_name}' fehlt")

        self._aufruf_stack.append((fn.definition.name or '<anonym>', self._aktuelle_zeile))
        try:
            kontext = f"Rückgabewert von '{fn.definition.name or '<anonym>'}'"
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
        klasse = DeutschKlasse(k.name, eltern, methoden)
        u.setze(k.name, klasse)
        return klasse

    def _besuche_NeuInstanz(self, k, u):
        klasse = u.hole(k.name)
        if not isinstance(klasse, DeutschKlasse):
            raise TypeError(f"'{k.name}' ist keine Klasse")
        instanz = DeutschInstanz(klasse)
        args = [self._besuche(a, u) for a in k.argumente]
        init = klasse.suche_methode('__init__')
        if init:
            self._funktion_aufrufen(init, [instanz] + args)
        return instanz

    # Attribut- und Index-Zugriff
    def _besuche_AttributZugriff(self, k, u):
        obj = self._besuche(k.objekt, u)

        if isinstance(obj, DeutschInstanz):
            return obj.hole_attribut(k.attribut)

        if isinstance(obj, DeutschKlasse):
            m = obj.suche_methode(k.attribut)
            if m: return m
            raise AttributeError(f"Klasse '{obj.name}' hat keine Methode '{k.attribut}'")

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
