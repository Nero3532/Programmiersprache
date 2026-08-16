# -*- coding: utf-8 -*-
import difflib


class Umgebung:
    """Geltungsbereich: speichert Variablen und zeigt auf Eltern-Scope."""

    def __init__(self, eltern=None):
        self.variablen: dict = {}
        self.eltern: 'Umgebung | None' = eltern

    def setze(self, name: str, wert):
        self.variablen[name] = wert

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

    def weise_zu(self, name: str, wert):
        """Weist einer bestehenden Variable zu (sucht in Eltern-Scopes)."""
        u = self
        while u is not None:
            if name in u.variablen:
                u.variablen[name] = wert
                return
            u = u.eltern
        msg = f"Variable '{name}' wurde nicht deklariert (benutze 'sei')"
        vorschlag = self._aehnlichster_name(name)
        if vorschlag:
            msg += f" – meintest du '{vorschlag}'?"
        raise NameError(msg)

    def existiert(self, name: str) -> bool:
        u = self
        while u is not None:
            if name in u.variablen:
                return True
            u = u.eltern
        return False
