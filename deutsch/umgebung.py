# -*- coding: utf-8 -*-


class Umgebung:
    """Geltungsbereich: speichert Variablen und zeigt auf Eltern-Scope."""

    def __init__(self, eltern=None):
        self.variablen: dict = {}
        self.eltern: 'Umgebung | None' = eltern

    def setze(self, name: str, wert):
        self.variablen[name] = wert

    def hole(self, name: str):
        if name in self.variablen:
            return self.variablen[name]
        if self.eltern is not None:
            return self.eltern.hole(name)
        raise NameError(f"Unbekannte Variable oder Funktion: '{name}'")

    def weise_zu(self, name: str, wert):
        """Weist einer bestehenden Variable zu (sucht in Eltern-Scopes)."""
        if name in self.variablen:
            self.variablen[name] = wert
            return
        if self.eltern is not None:
            self.eltern.weise_zu(name, wert)
            return
        raise NameError(f"Variable '{name}' wurde nicht deklariert (benutze 'sei')")

    def existiert(self, name: str) -> bool:
        if name in self.variablen:
            return True
        if self.eltern is not None:
            return self.eltern.existiert(name)
        return False
