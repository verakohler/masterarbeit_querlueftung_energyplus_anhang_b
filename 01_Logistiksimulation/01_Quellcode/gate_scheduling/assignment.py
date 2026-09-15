"""Zuordnung LKW -> Tor inkl. Kollisionspruefung.

Liest die bestehenden Ankunfts- (Wareneingang, AN-Seite) und Abfahrt-Ereignisse
(Warenausgang, AB-Seite) aus den JSON-Artefakten der Crossdocking-Simulation und
weist jeder Andockung ein Tor der jeweiligen Seite zu.

ANNAHME: 'zeit_min' in ergebnis_warenausgang.json wird als Andock-Zeitpunkt (t)
interpretiert, nicht als Zeitpunkt der tatsaechlichen Abfahrt nach Beladung
(Bestaetigung durch den Nutzer, siehe Projekt-Historie).

Kollisionsregel (Vorgabe): Jede Andockung belegt an ihrem Tor das Zeitfenster
[t - 2 min, t + 20 min]. Die Zufallsauswahl erfolgt nur unter den Toren der
Seite, deren Belegungsfenster zum Zeitpunkt t frei ist (Mindestabstand
zwischen zwei Andockungen am selben Tor: min_abstand_min, Default 23 min).
Da Ereignisse streng chronologisch verarbeitet werden, genuegt es, je Tor den
zuletzt zugewiesenen (effektiven) Andockzeitpunkt zu verfolgen -- fruehere
Andockungen liegen automatisch weiter zurueck.

Sind zu einem Zeitpunkt alle Tore einer Seite belegt, wird das Ereignis in den
Konfliktbericht aufgenommen und auf die fruehste zulaessige Minute verschoben
(Minimum ueber alle Tore aus letzter_Andockzeitpunkt + min_abstand_min).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .calendar_mapping import KalenderIndex
from .config import GateScheduleConfig
from .gates import Gate, TorSeite, tore_je_seite


@dataclass(frozen=True)
class AndockEreignis:
    """Ein LKW-Ereignis (Ankunft oder Abfahrt) mit geplantem Zeitpunkt.

    Der urspruengliche Zeitstempel aus der Crossdocking-Simulation wird nicht
    veraendert -- 'geplanter_t' ist genau dieser Wert, umgerechnet auf ein
    echtes Kalenderdatum.
    """
    event_id: str
    seite: TorSeite
    geplanter_t: datetime
    monat_idx: int
    woche_idx: int
    tag_idx: int
    schicht_idx: int
    attribute: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Andockung:
    """Ergebnis der Zuordnung: welches Tor, zu welchem effektiven Zeitpunkt."""
    ereignis: AndockEreignis
    gate: Gate
    effektiver_t: datetime

    @property
    def verschoben(self) -> bool:
        return self.effektiver_t != self.ereignis.geplanter_t


@dataclass(frozen=True)
class Konflikt:
    """Protokollierter Verschiebungsfall (fuer den Konfliktbericht)."""
    event_id: str
    gate: Gate
    original_t: datetime
    verschoben_t: datetime

    @property
    def verschiebung_min(self) -> float:
        return (self.verschoben_t - self.original_t).total_seconds() / 60.0


def lade_ereignisse(
    zeitachse_daten: dict, seite: TorSeite, ki: KalenderIndex
) -> list[AndockEreignis]:
    """Flacht eine ergebnis_zeitachse.json- oder ergebnis_warenausgang.json-
    Struktur zu einer Liste von AndockEreignis ab.

    Die event_id wird aus der Position in der (unveraenderten) Quellstruktur
    gebildet -- deterministisch, unabhaengig von Sortierung oder Zufallszahlen.
    """
    ereignisse = []
    for monat_daten in zeitachse_daten["ergebnisse"]:
        monat_idx = monat_daten["monat"]
        for woche_daten in monat_daten["wochen"]:
            woche_idx = woche_daten["woche"]
            for tag_idx, tag_schichten in enumerate(woche_daten["zeitachse"]):
                for schicht_idx, schicht_lkws in enumerate(tag_schichten):
                    datum = ki.datum(monat_idx, woche_idx, tag_idx)
                    for i, lkw in enumerate(schicht_lkws):
                        geplanter_t = datetime.combine(datum, datetime.min.time()) \
                            + timedelta(minutes=lkw["zeit_min"])
                        event_id = (
                            f"{seite.value}-{monat_idx:02d}-{woche_idx:02d}-"
                            f"{tag_idx}-{schicht_idx}-{i:03d}"
                        )
                        ereignisse.append(AndockEreignis(
                            event_id=event_id,
                            seite=seite,
                            geplanter_t=geplanter_t,
                            monat_idx=monat_idx,
                            woche_idx=woche_idx,
                            tag_idx=tag_idx,
                            schicht_idx=schicht_idx,
                            attribute=dict(lkw),
                        ))
    return ereignisse


def _normalisierte_wahrscheinlichkeiten(
    kandidaten_indizes: list[int], config_probs: tuple[float, ...] | None, gates_per_side: int
) -> list[float]:
    if config_probs is None:
        basis = [1.0 / gates_per_side] * gates_per_side
    else:
        basis = list(config_probs)
    ausgewaehlt = [basis[i] for i in kandidaten_indizes]
    summe = sum(ausgewaehlt)
    return [p / summe for p in ausgewaehlt]


def _zuordnen_seite(
    ereignisse: list[AndockEreignis],
    gates_seite: list[Gate],
    rng: np.random.Generator,
    config: GateScheduleConfig,
) -> tuple[list[Andockung], list[Konflikt]]:
    """Ordnet alle Ereignisse EINER Seite chronologisch den Toren dieser Seite zu."""
    min_abstand = timedelta(minutes=config.min_abstand_min)
    letzter_t: dict[Gate, datetime | None] = {g: None for g in gates_seite}

    geordnet = sorted(ereignisse, key=lambda e: (e.geplanter_t, e.event_id))

    andockungen: list[Andockung] = []
    konflikte: list[Konflikt] = []

    for ereignis in geordnet:
        t = ereignis.geplanter_t
        freie_indizes = [
            i for i, g in enumerate(gates_seite)
            if letzter_t[g] is None or (t - letzter_t[g]) >= min_abstand
        ]

        if freie_indizes:
            probs = _normalisierte_wahrscheinlichkeiten(
                freie_indizes, config.choice_probabilities, len(gates_seite)
            )
            gewaehlt_idx = freie_indizes[int(rng.choice(len(freie_indizes), p=probs))]
            effektiver_t = t
        else:
            fruehste_je_tor = {
                i: letzter_t[gates_seite[i]] + min_abstand for i in range(len(gates_seite))
            }
            fruehste_zeit = min(fruehste_je_tor.values())
            kandidaten_indizes = [i for i, tt in fruehste_je_tor.items() if tt == fruehste_zeit]
            probs = _normalisierte_wahrscheinlichkeiten(
                kandidaten_indizes, config.choice_probabilities, len(gates_seite)
            )
            gewaehlt_idx = kandidaten_indizes[int(rng.choice(len(kandidaten_indizes), p=probs))]
            effektiver_t = fruehste_zeit
            konflikte.append(Konflikt(
                event_id=ereignis.event_id,
                gate=gates_seite[gewaehlt_idx],
                original_t=t,
                verschoben_t=effektiver_t,
            ))

        gate = gates_seite[gewaehlt_idx]
        letzter_t[gate] = effektiver_t
        andockungen.append(Andockung(ereignis=ereignis, gate=gate, effektiver_t=effektiver_t))

    return andockungen, konflikte


def zuordnen_alle(
    an_ereignisse: list[AndockEreignis],
    ab_ereignisse: list[AndockEreignis],
    tore: list[Gate],
    config: GateScheduleConfig,
) -> tuple[list[Andockung], list[Konflikt]]:
    """Ordnet AN- und AB-Ereignisse den jeweiligen Toren zu.

    Nutzt EINEN numpy.random.Generator(seed), zuerst fuer die AN-Seite,
    danach fortlaufend fuer die AB-Seite. Bei gleichem Seed und gleichen
    Eingangsdaten ist die Ausgabe bitweise reproduzierbar.
    """
    rng = np.random.default_rng(config.seed)
    an_gates = tore_je_seite(tore, TorSeite.AN)
    ab_gates = tore_je_seite(tore, TorSeite.AB)

    an_andockungen, an_konflikte = _zuordnen_seite(an_ereignisse, an_gates, rng, config)
    ab_andockungen, ab_konflikte = _zuordnen_seite(ab_ereignisse, ab_gates, rng, config)

    return an_andockungen + ab_andockungen, an_konflikte + ab_konflikte


def konflikte_zu_csv(konflikte: list[Konflikt], pfad: str | Path) -> None:
    """Schreibt den Konfliktbericht: ursprünglicher Zeitstempel, verschobener
    Zeitstempel, Tor, Verschiebung in Minuten. Keine stille Korrektur --
    jede Verschiebung wird hier vollstaendig aufgefuehrt.
    """
    with open(pfad, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "tor", "original_zeitstempel", "verschobener_zeitstempel", "verschiebung_min"])
        for k in konflikte:
            writer.writerow([
                k.event_id, k.gate.gate_id,
                k.original_t.isoformat(), k.verschoben_t.isoformat(),
                round(k.verschiebung_min, 1),
            ])
