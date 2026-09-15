"""Torbenennung und Geometriezuordnung.

Zentrale, eindeutige Torbezeichner als Enum/Dataclass -- kein Freitext an
mehreren Stellen im Code. Die Halle besteht aus einem Hallenstueck mit
Andocktoren an zwei gegenueberliegenden Seiten: AN (ankommende LKW) und
AB (abfahrende LKW).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TorSeite(str, Enum):
    """Seite der Halle: AN = ankommende LKW, AB = abfahrende LKW."""
    AN = "AN"
    AB = "AB"


class TorStatus(str, Enum):
    """Zustand eines Tors. Enum statt Freitext-Strings."""
    ZU = "zu"
    OFFEN = "offen"
    LKW = "LKW"


@dataclass(frozen=True)
class Gate:
    """Ein einzelnes Andocktor.

    Attributes:
        seite: AN oder AB.
        index: 1-basierter Index innerhalb der Seite (1, 2, 3, ...).
        gate_id: Eindeutiger Bezeichner, z. B. "AN 1".
    """
    seite: TorSeite
    index: int

    @property
    def gate_id(self) -> str:
        return f"{self.seite.value} {self.index}"

    def __str__(self) -> str:
        return self.gate_id


def erzeuge_tore(gates_per_side: int = 3) -> list[Gate]:
    """Erzeugt die vollstaendige, geordnete Torliste (zuerst AN, dann AB).

    Args:
        gates_per_side: Anzahl Tore je Seite (Default 3, konfigurierbar).

    Returns:
        Liste von Gate-Objekten, Laenge 2 * gates_per_side.
    """
    if gates_per_side < 1:
        raise ValueError("gates_per_side muss >= 1 sein")
    tore = [Gate(TorSeite.AN, i) for i in range(1, gates_per_side + 1)]
    tore += [Gate(TorSeite.AB, i) for i in range(1, gates_per_side + 1)]
    return tore


def tore_je_seite(tore: list[Gate], seite: TorSeite) -> list[Gate]:
    """Filtert die Torliste auf eine Seite, Reihenfolge bleibt erhalten."""
    return [t for t in tore if t.seite == seite]
