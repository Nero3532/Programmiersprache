# -*- coding: utf-8 -*-
import difflib


class Umgebung:
    """Geltungsbereich: speichert Variablen und zeigt auf Eltern-Scope."""

    def __init__(self, eltern=None):
        self.variablen: dict = {}
        self.konstanten: set = set()
        self.typhinweise: dict = {}  # name -> Typ-Hinweis (nur für Bindungen mit Hinweis)
        # Scope, in dem die Typ-Hinweise dieses Scopes aufgelöst werden (None = dieser Scope selbst).
        # Bei Funktionsaufrufen die Definitionsumgebung: Parameter-Hinweise wie 'k: modul.Klasse'
        # meinen Namen dort, nicht gleichnamige Parameter oder Variablen im Körper.
        self.typ_kontext: 'Umgebung | None' = None
        # (Name, Wert, Herkunft) der Fehlervariable eines 'fange'-Blocks; 'werfe name' wirft sie
        # mit der Herkunft (Meldung, Datei, Zeile) des ursprünglichen Fehlers erneut
        self.gefangen = None
        self.eltern: 'Umgebung | None' = eltern

    def setze(self, name: str, wert, typhinweis=None):
        """Legt eine Bindung in diesem Scope an; ein früherer Typ-Hinweis des Namens entfällt."""
        self.variablen[name] = wert
        if typhinweis is None:
            self.typhinweise.pop(name, None)
        else:
            self.typhinweise[name] = typhinweis

    def setze_konstante(self, name: str, wert, typhinweis=None):
        self.setze(name, wert, typhinweis)
        self.konstanten.add(name)

    def _aehnlichster_name(self, name: str):
        alle_namen = set()
        u = self
        while u is not None:
            alle_namen.update(u.variablen.keys())
            u = u.eltern
        treffer = difflib.get_close_matches(name, alle_namen, n=1, cutoff=0.6)
        return treffer[0] if treffer else None

    def hole(self, name: str):
        u = self
        while u is not None:
            if name in u.variablen:
                return u.variablen[name]
            u = u.eltern
        msg = f"Unbekannte Variable oder Funktion: '{name}'"
        vorschlag = self._aehnlichster_name(name)
        if vorschlag:
            msg += f" – meintest du '{vorschlag}'?"
        raise NameError(msg)

    def weise_zu(self, name: str, wert, typpruefer=None):
        """Weist einer bestehenden Variable zu (sucht in Eltern-Scopes).

        typpruefer(wert, typhinweis, scope) wird aufgerufen, wenn die Bindung einen
        Typ-Hinweis trägt, und soll bei Verstoß eine Ausnahme werfen."""
        u = self
        while u is not None:
            if name in u.variablen:
                if name in u.konstanten:
                    raise TypeError(f"'{name}' ist eine Konstante und kann nicht neu zugewiesen werden")
                hinweis = u.typhinweise.get(name)
                if hinweis is not None and typpruefer is not None:
                    typpruefer(wert, hinweis, u.typ_kontext if u.typ_kontext is not None else u)
                u.variablen[name] = wert
                return
            u = u.eltern
        raise NameError(self.nicht_deklariert_meldung(name))

    def nicht_deklariert_meldung(self, name: str) -> str:
        msg = f"Variable '{name}' ist nicht deklariert"
        vorschlag = self._aehnlichster_name(name)
        if vorschlag:
            msg += f" – meintest du '{vorschlag}'?"
        else:
            msg += "."
        return msg + " Neue Variablen mit 'sei' anlegen."

    def existiert(self, name: str) -> bool:
        u = self
        while u is not None:
            if name in u.variablen:
                return True
            u = u.eltern
        return False
