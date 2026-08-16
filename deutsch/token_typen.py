# -*- coding: utf-8 -*-
from enum import Enum, auto


class TokenTyp(Enum):
    # Literale
    GANZZAHL = auto()
    KOMMAZAHL = auto()
    ZEICHENKETTE = auto()
    INTERP_ZEICHENKETTE = auto()   # "Hallo {name}!" – Teile als Liste im Wert
    BEZEICHNER = auto()

    # Schlüsselwörter
    SEI = auto()
    WENN = auto()
    SONST = auto()
    SOLANGE = auto()
    FUER = auto()
    IN = auto()
    FUNKTION = auto()
    ZURUECK = auto()
    WAHR = auto()
    FALSCH = auto()
    NICHTS = auto()
    UND = auto()
    ODER = auto()
    NICHT = auto()
    KLASSE = auto()
    NEU = auto()
    ABBRECHEN = auto()
    WEITER = auto()
    VERSUCHE = auto()     # try
    FANGE = auto()        # catch
    ENDLICH = auto()      # finally
    LADE = auto()         # import / load
    PASSE = auto()        # match
    FALL = auto()         # case
    WERFE = auto()        # throw

    # Operatoren (einfach)
    PLUS = auto()
    MINUS = auto()
    STERN = auto()
    SCHRAEGSTRICH = auto()
    PROZENT = auto()
    GLEICH = auto()
    DOPPELGLEICH = auto()
    UNGLEICH = auto()
    KLEINER = auto()
    GROESSER = auto()
    KLEINERGLEICH = auto()
    GROESSERGLEICH = auto()

    STERN_STERN = auto()               # **
    SCHRAEGSTRICH_SCHRAEGSTRICH = auto()  # //

    # Verbund-Zuweisungen
    PLUS_GLEICH = auto()          # +=
    MINUS_GLEICH = auto()         # -=
    STERN_GLEICH = auto()         # *=
    SCHRAEGSTRICH_GLEICH = auto() # /=
    PROZENT_GLEICH = auto()       # %=
    STERN_STERN_GLEICH = auto()             # **=
    SCHRAEGSTRICH_SCHRAEGSTRICH_GLEICH = auto()  # //=

    # Trennzeichen
    LPAREN = auto()
    RPAREN = auto()
    LGESCHWEIFTE = auto()
    RGESCHWEIFTE = auto()
    LECKIG = auto()
    RECKIG = auto()
    KOMMA = auto()
    PUNKT = auto()
    DOPPELPUNKT = auto()
    SEMIKOLON = auto()
    PFEIL = auto()         # -> für Rückgabetyp-Hinweis

    # Sonderfälle
    ZEILENENDE = auto()
    DATEIENDE = auto()
