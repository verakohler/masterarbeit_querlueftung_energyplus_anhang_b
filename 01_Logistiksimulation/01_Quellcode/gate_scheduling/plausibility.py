"""Plausibilitaetspruefung als eigener Pipeline-Schritt.

Prueft, unabhaengig von den Einzelmodulen, vier Invarianten, die nach
Zuordnung und Zustandsmodellierung immer erfuellt sein muessen. Keine stille
Korrektur -- jede verletzte Invariante wird explizit aufgefuehrt.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .assignment import Andockung
from .gates import Gate, TorStatus
from .state_model import Zustandswechsel


@dataclass
class PlausibilitaetsBericht:
    ereigniszahl_ok: bool
    keine_doppelten_zeitstempel: bool
    keine_ueberlappungen: bool
    zustandsreihenfolge_ok: bool
    verstoesse: list[str] = field(default_factory=list)

    @property
    def alles_ok(self) -> bool:
        return (
            self.ereigniszahl_ok
            and self.keine_doppelten_zeitstempel
            and self.keine_ueberlappungen
            and self.zustandsreihenfolge_ok
        )


def _pruefe_ereigniszahl(andockungen: list[Andockung], eingangs_ereigniszahl: int, verstoesse: list[str]) -> bool:
    if len(andockungen) != eingangs_ereigniszahl:
        verstoesse.append(
            f"Ereigniszahl-Mismatch: {len(andockungen)} Andockungen vs. "
            f"{eingangs_ereigniszahl} Eingangsereignisse"
        )
        return False
    return True


def _pruefe_pro_tor(
    andockungen: list[Andockung], min_abstand_min: float, verstoesse: list[str]
) -> tuple[bool, bool]:
    """Prueft je Tor: keine doppelten Zeitstempel, keine ueberlappenden Fenster
    (Fenster = [t-2, t+20] entspricht min_abstand_min als Mindestabstand)."""
    keine_duplikate = True
    keine_ueberlappung = True

    nach_tor: dict[Gate, list[Andockung]] = {}
    for a in andockungen:
        nach_tor.setdefault(a.gate, []).append(a)

    for gate, liste in nach_tor.items():
        geordnet = sorted(liste, key=lambda a: a.effektiver_t)
        for i in range(1, len(geordnet)):
            delta = (geordnet[i].effektiver_t - geordnet[i - 1].effektiver_t).total_seconds() / 60.0
            if delta == 0:
                keine_duplikate = False
                verstoesse.append(
                    f"Doppelter Zeitstempel an {gate.gate_id}: {geordnet[i].effektiver_t.isoformat()}"
                )
            elif delta < min_abstand_min:
                keine_ueberlappung = False
                verstoesse.append(
                    f"Ueberlappendes Fenster an {gate.gate_id}: "
                    f"{geordnet[i-1].effektiver_t.isoformat()} -> {geordnet[i].effektiver_t.isoformat()} "
                    f"(Abstand {delta:.1f} min < {min_abstand_min} min)"
                )

    return keine_duplikate, keine_ueberlappung


_ERLAUBTE_UEBERGAENGE = {
    TorStatus.ZU: {TorStatus.OFFEN},
    TorStatus.OFFEN: {TorStatus.LKW, TorStatus.ZU},
    TorStatus.LKW: {TorStatus.OFFEN},
}


def _pruefe_zustandsreihenfolge(
    zustandslisten: dict[Gate, list[Zustandswechsel]], verstoesse: list[str]
) -> bool:
    """Statuswechsel muessen immer zu -> offen -> LKW -> offen -> zu folgen."""
    ok = True
    for gate, wechsel in zustandslisten.items():
        geordnet = sorted(wechsel, key=lambda w: w.zeitpunkt)
        if not geordnet or geordnet[0].status != TorStatus.ZU:
            ok = False
            verstoesse.append(f"{gate.gate_id}: Anfangszustand ist nicht 'zu'")
            continue
        for i in range(1, len(geordnet)):
            vorher, nachher = geordnet[i - 1].status, geordnet[i].status
            if nachher not in _ERLAUBTE_UEBERGAENGE[vorher]:
                ok = False
                verstoesse.append(
                    f"{gate.gate_id}: unzulaessiger Uebergang {vorher.value} -> {nachher.value} "
                    f"bei {geordnet[i].zeitpunkt.isoformat()}"
                )
    return ok


def pruefe_plausibilitaet(
    andockungen: list[Andockung],
    eingangs_ereigniszahl: int,
    zustandslisten: dict[Gate, list[Zustandswechsel]],
    min_abstand_min: float,
) -> PlausibilitaetsBericht:
    verstoesse: list[str] = []
    ereigniszahl_ok = _pruefe_ereigniszahl(andockungen, eingangs_ereigniszahl, verstoesse)
    keine_duplikate, keine_ueberlappung = _pruefe_pro_tor(andockungen, min_abstand_min, verstoesse)
    zustandsreihenfolge_ok = _pruefe_zustandsreihenfolge(zustandslisten, verstoesse)

    return PlausibilitaetsBericht(
        ereigniszahl_ok=ereigniszahl_ok,
        keine_doppelten_zeitstempel=keine_duplikate,
        keine_ueberlappungen=keine_ueberlappung,
        zustandsreihenfolge_ok=zustandsreihenfolge_ok,
        verstoesse=verstoesse,
    )
