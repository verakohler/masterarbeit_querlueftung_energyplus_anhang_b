"""Zustandsmodell je Tor: ereignisbasierte Zustandsliste aus dem Oeffnungsschema.

Oeffnungsschema pro Andockung (t = effektiver Andockzeitpunkt), Offsets aus
config.SchemaOffsets:

    t + oeffnen_min     Tor oeffnet     -> offen
    t + andock_min      LKW dockt an    -> LKW
    t + abdock_min      LKW dockt ab    -> offen
    t + schliessen_min  Tor schliesst   -> zu

Die Zustandsliste ist ereignisbasiert (nur bei Wechsel), kein Minutenraster.
Anfangszustand jedes Tors zu Simulationsbeginn: zu.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .assignment import Andockung
from .config import SchemaOffsets
from .gates import Gate, TorStatus


@dataclass(frozen=True)
class Zustandswechsel:
    """Ein einzelner Zustandswechsel eines Tors zu einem Zeitpunkt."""
    zeitpunkt: datetime
    status: TorStatus


def zustandsliste_fuer_tor(
    andockungen_am_tor: list[Andockung],
    schema: SchemaOffsets,
    simulation_start: datetime,
) -> list[Zustandswechsel]:
    """Baut die Zustandsliste eines einzelnen Tors aus seinen Andockungen.

    Voraussetzung (durch die Kollisionsregel in assignment.py garantiert):
    zwei aufeinanderfolgende Andockungen am selben Tor liegen mindestens
    min_abstand_min auseinander, sodass sich die Zustandsfenster nie
    ueberlappen und stets zu -> offen -> LKW -> offen -> zu durchlaufen wird.
    """
    wechsel = [Zustandswechsel(simulation_start, TorStatus.ZU)]

    for a in sorted(andockungen_am_tor, key=lambda a: a.effektiver_t):
        t = a.effektiver_t
        wechsel.append(Zustandswechsel(t + timedelta(minutes=schema.oeffnen_min), TorStatus.OFFEN))
        wechsel.append(Zustandswechsel(t + timedelta(minutes=schema.andock_min), TorStatus.LKW))
        wechsel.append(Zustandswechsel(t + timedelta(minutes=schema.abdock_min), TorStatus.OFFEN))
        wechsel.append(Zustandswechsel(t + timedelta(minutes=schema.schliessen_min), TorStatus.ZU))

    return wechsel


def alle_zustandslisten(
    andockungen: list[Andockung],
    tore: list[Gate],
    schema: SchemaOffsets,
    simulation_start: datetime,
) -> dict[Gate, list[Zustandswechsel]]:
    """Baut die Zustandslisten fuer alle Tore (auch Tore ohne Andockung:
    dann nur der Anfangszustand 'zu')."""
    ergebnis: dict[Gate, list[Zustandswechsel]] = {}
    for gate in tore:
        am_tor = [a for a in andockungen if a.gate == gate]
        ergebnis[gate] = zustandsliste_fuer_tor(am_tor, schema, simulation_start)
    return ergebnis
