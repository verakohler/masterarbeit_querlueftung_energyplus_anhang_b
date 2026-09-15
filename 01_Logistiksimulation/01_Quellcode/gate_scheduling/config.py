"""Zentrale Konfiguration der Tor-Schedule-Erweiterung.

Alle veraenderlichen Parameter (Seed, Schema-Offsets, Statuswerte, Torzahl,
Wahrscheinlichkeiten) sind hier als Dataclass gebuendelt -- keine verstreuten
Konstanten in den einzelnen Modulen.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .gates import TorStatus

SCRIPT_VERSION = "0.1.0"


@dataclass(frozen=True)
class SchemaOffsets:
    """Die vier Offsets des Oeffnungsschemas relativ zum Andockzeitpunkt t (Minuten).

    ANNAHME: Reihenfolge und Vorzeichen folgen der Vorgabe:
    Tor oeffnet (t+oeffnen_min) -> LKW dockt an (t+andock_min) ->
    LKW dockt ab (t+abdock_min) -> Tor schliesst (t+schliessen_min).
    """
    oeffnen_min: float = -2.0
    andock_min: float = 0.0
    abdock_min: float = 45.0
    schliessen_min: float = 50.0

    @property
    def fensterdauer_min(self) -> float:
        """Dauer, die eine Andockung das Tor belegt."""
        return self.schliessen_min - self.oeffnen_min

    @classmethod
    def aus_be_entladezeit(cls, be_entladezeit_min: float) -> "SchemaOffsets":
        """Leitet die Offsets aus der Be-/Entladezeit der Crossdocking-Config ab.

        abdock_min = be_entladezeit_min; die 5 min zwischen Abdocken und
        Schliessen sowie die 2 min Vorlauf bleiben unveraendert. Damit sind
        HallenConfig.be_entladezeit_min und das Oeffnungsschema gekoppelt --
        vorher standen beide Werte unabhaengig voneinander auf 15 min und
        konnten stillschweigend auseinanderlaufen.
        """
        return cls(oeffnen_min=-2.0, andock_min=0.0,
                   abdock_min=float(be_entladezeit_min),
                   schliessen_min=float(be_entladezeit_min) + 5.0)


@dataclass(frozen=True)
class StatusFractions:
    """Fraction-Werte je Torstatus fuer den EnergyPlus-Schedule (0..1)."""
    zu: float = 0.0
    offen: float = 1.0
    lkw: float = 0.048

    def fuer(self, status: TorStatus) -> float:
        return {
            TorStatus.ZU: self.zu,
            TorStatus.OFFEN: self.offen,
            TorStatus.LKW: self.lkw,
        }[status]


@dataclass(frozen=True)
class GateScheduleConfig:
    """Gesamtkonfiguration eines Pipeline-Laufs.

    Attributes:
        seed: Seed fuer numpy.random.Generator (Torzuordnung). Wird in jedem
            Ausgabeartefakt protokolliert.
        gates_per_side: Anzahl Tore je Seite (AN bzw. AB).
        choice_probabilities: Auswahlwahrscheinlichkeiten je Tor einer Seite,
            Reihenfolge = Torindex 0..gates_per_side-1. None = Gleichverteilung.
        schema: Die vier Zeit-Offsets des Oeffnungsschemas.
        status_fractions: Fraction-Werte je Status fuer den EnergyPlus-Export.
        min_abstand_min: Mindestabstand zwischen zwei Andockungen am SELBEN Tor (Minuten).
            None (Default) leitet ihn aus dem Schema ab: Belegungsfensterdauer
            (schliessen_min - oeffnen_min) plus 1 min Sicherheitsabstand, damit
            Zustandswechsel nicht auf derselben Minute kollidieren. Bei
            abdock_min = 45 sind das 52 + 1 = 53 min.
            Die Regel wirkt je Tor, nicht je Fassade -- zwei Tore derselben Seite
            duerfen gleichzeitig belegt sein.
        kalenderjahr: Kalenderjahr, auf das (monat, woche, tag) abgebildet werden.
        zeitachse_pfad: Pfad zu ergebnis_zeitachse.json (Wareneingang, AN-Seite).
        warenausgang_pfad: Pfad zu ergebnis_warenausgang.json (Warenausgang, AB-Seite).
        output_basis: Basisverzeichnis fuer versionierte Pipeline-Laeufe.
    """
    seed: int = 42
    gates_per_side: int = 3
    choice_probabilities: tuple[float, ...] | None = None
    schema: SchemaOffsets = field(default_factory=SchemaOffsets)
    status_fractions: StatusFractions = field(default_factory=StatusFractions)
    min_abstand_min: float | None = None
    kalenderjahr: int = 2026
    zeitachse_pfad: str = "ergebnis_zeitachse.json"
    warenausgang_pfad: str = "ergebnis_warenausgang.json"
    output_basis: str = "gate_scheduling/output"

    def __post_init__(self) -> None:
        if self.min_abstand_min is None:
            object.__setattr__(self, "min_abstand_min",
                               self.schema.fensterdauer_min + 1.0)
        if self.gates_per_side < 1:
            raise ValueError("gates_per_side muss >= 1 sein")
        if self.choice_probabilities is not None:
            if len(self.choice_probabilities) != self.gates_per_side:
                raise ValueError(
                    "choice_probabilities muss genau gates_per_side Eintraege haben"
                )
            summe = sum(self.choice_probabilities)
            if abs(summe - 1.0) > 1e-9:
                raise ValueError(f"choice_probabilities muss zu 1.0 summieren, ist {summe}")
        fenster_dauer = self.schema.schliessen_min - self.schema.oeffnen_min
        if self.min_abstand_min < fenster_dauer:
            raise ValueError(
                f"min_abstand_min ({self.min_abstand_min}) darf nicht kleiner sein als "
                f"die Belegungsfensterdauer ({fenster_dauer}) -- sonst ueberlappen sich "
                "Zustandswechsel am selben Tor."
            )

    @classmethod
    def aus_crossdocking_config(
        cls, pfad: str | Path, **overrides
    ) -> "GateScheduleConfig":
        """Leitet gates_per_side aus der bestehenden HallenConfig.anzahl_tore ab.

        Die bestehende Crossdocking-Config kennt nur eine undifferenzierte
        Torzahl (fuer die aggregierte Torkapazitaets-Pruefung). Dieses Modul
        interpretiert anzahl_tore als gates_per_side * 2 (symmetrisch AN/AB).
        """
        with open(pfad, "r", encoding="utf-8") as f:
            daten = json.load(f)
        hallen = daten["hallen_config"]
        anzahl_tore = hallen["anzahl_tore"]
        if anzahl_tore % 2 != 0:
            raise ValueError(
                f"anzahl_tore={anzahl_tore} ist ungerade -- eine symmetrische "
                "AN/AB-Aufteilung ist damit nicht moeglich. Bitte gates_per_side "
                "explizit angeben."
            )
        params = {"gates_per_side": anzahl_tore // 2}
        if "be_entladezeit_min" in hallen:
            params["schema"] = SchemaOffsets.aus_be_entladezeit(
                hallen["be_entladezeit_min"]
            )
        params.update(overrides)
        return cls(**params)
