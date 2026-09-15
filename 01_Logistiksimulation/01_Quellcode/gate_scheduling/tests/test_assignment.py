"""Tests: Kollisionsregel, Reproduzierbarkeit bei gleichem Seed, Ereigniszahl
vor/nach Zuordnung identisch (bis auf protokollierte Verschiebungen)."""
from datetime import datetime, timedelta

from gate_scheduling.assignment import AndockEreignis, zuordnen_alle
from gate_scheduling.config import GateScheduleConfig
from gate_scheduling.gates import TorSeite, erzeuge_tore


def _ereignis(event_id: str, seite: TorSeite, t: datetime) -> AndockEreignis:
    return AndockEreignis(
        event_id=event_id, seite=seite, geplanter_t=t,
        monat_idx=0, woche_idx=0, tag_idx=0, schicht_idx=0,
    )


def test_kollisionsregel_verschiebt_auf_frueheste_zulaessige_minute():
    """Ein einziges AN-Tor, zwei Ereignisse 10 min auseinander (< 23 min
    Mindestabstand). Das zweite muss auf t1 + 23 min verschoben und als
    Konflikt protokolliert werden."""
    config = GateScheduleConfig(seed=1, gates_per_side=1)
    tore = erzeuge_tore(1)
    t1 = datetime(2026, 1, 5, 8, 0)
    t2 = t1 + timedelta(minutes=10)

    ereignisse = [_ereignis("A", TorSeite.AN, t1), _ereignis("B", TorSeite.AN, t2)]
    andockungen, konflikte = zuordnen_alle(ereignisse, [], tore, config)

    andockungen_nach_id = {a.ereignis.event_id: a for a in andockungen}
    assert andockungen_nach_id["A"].effektiver_t == t1
    assert andockungen_nach_id["B"].effektiver_t == t1 + timedelta(minutes=23)

    assert len(konflikte) == 1
    assert konflikte[0].event_id == "B"
    assert konflikte[0].verschiebung_min == 13.0  # (t1+23) - t2 = 13 min


def test_keine_kollision_bei_ausreichendem_abstand():
    config = GateScheduleConfig(seed=1, gates_per_side=1)
    tore = erzeuge_tore(1)
    t1 = datetime(2026, 1, 5, 8, 0)
    t2 = t1 + timedelta(minutes=23)  # genau am Mindestabstand

    ereignisse = [_ereignis("A", TorSeite.AN, t1), _ereignis("B", TorSeite.AN, t2)]
    andockungen, konflikte = zuordnen_alle(ereignisse, [], tore, config)

    assert konflikte == []
    nach_id = {a.ereignis.event_id: a for a in andockungen}
    assert nach_id["A"].effektiver_t == t1
    assert nach_id["B"].effektiver_t == t2


def test_kollision_nutzt_mehrere_tore_bevor_verschoben_wird():
    """Mit 2 Toren duerfen 2 gleichzeitige Ereignisse ohne Konflikt auf
    verschiedene Tore verteilt werden."""
    config = GateScheduleConfig(seed=1, gates_per_side=2)
    tore = erzeuge_tore(2)
    t = datetime(2026, 1, 5, 8, 0)

    ereignisse = [_ereignis("A", TorSeite.AN, t), _ereignis("B", TorSeite.AN, t)]
    andockungen, konflikte = zuordnen_alle(ereignisse, [], tore, config)

    assert konflikte == []
    gates_verwendet = {a.gate for a in andockungen}
    assert len(gates_verwendet) == 2  # beide auf unterschiedlichen Toren


def _synthetische_ereignisse(seite: TorSeite, anzahl: int, start: datetime) -> list[AndockEreignis]:
    ereignisse = []
    for i in range(anzahl):
        t = start + timedelta(minutes=7 * i)  # dicht genug, um Konflikte zu erzwingen
        ereignisse.append(_ereignis(f"{seite.value}-{i:03d}", seite, t))
    return ereignisse


def test_reproduzierbarkeit_bei_gleichem_seed():
    """Gleicher Seed + gleiche Eingangsdaten -> bitweise identische Ausgabe."""
    config = GateScheduleConfig(seed=42, gates_per_side=3)
    tore = erzeuge_tore(3)
    start = datetime(2026, 1, 5, 6, 0)
    an = _synthetische_ereignisse(TorSeite.AN, 30, start)
    ab = _synthetische_ereignisse(TorSeite.AB, 30, start)

    lauf1 = zuordnen_alle(an, ab, tore, config)
    lauf2 = zuordnen_alle(an, ab, tore, config)

    profil1 = [(a.ereignis.event_id, a.gate.gate_id, a.effektiver_t) for a in lauf1[0]]
    profil2 = [(a.ereignis.event_id, a.gate.gate_id, a.effektiver_t) for a in lauf2[0]]
    assert profil1 == profil2

    konflikte1 = [(k.event_id, k.gate.gate_id, k.original_t, k.verschoben_t) for k in lauf1[1]]
    konflikte2 = [(k.event_id, k.gate.gate_id, k.original_t, k.verschoben_t) for k in lauf2[1]]
    assert konflikte1 == konflikte2
    assert len(konflikte1) > 0  # Testszenario muss tatsaechlich Konflikte erzeugen


def test_verschiedene_seeds_koennen_unterschiedliche_zuordnung_ergeben():
    tore = erzeuge_tore(3)
    start = datetime(2026, 1, 5, 6, 0)
    an = _synthetische_ereignisse(TorSeite.AN, 30, start)

    config_a = GateScheduleConfig(seed=1, gates_per_side=3)
    config_b = GateScheduleConfig(seed=2, gates_per_side=3)

    gates_a = [a.gate.gate_id for a in zuordnen_alle(an, [], tore, config_a)[0]]
    gates_b = [a.gate.gate_id for a in zuordnen_alle(an, [], tore, config_b)[0]]

    assert gates_a != gates_b


def test_ereigniszahl_bleibt_erhalten_trotz_verschiebungen():
    """Anzahl Andockungen == Anzahl Eingangsereignisse, unabhaengig davon,
    wie viele Verschiebungen protokolliert wurden."""
    config = GateScheduleConfig(seed=7, gates_per_side=1)
    tore = erzeuge_tore(1)
    start = datetime(2026, 1, 5, 6, 0)
    an = _synthetische_ereignisse(TorSeite.AN, 50, start)
    ab = _synthetische_ereignisse(TorSeite.AB, 50, start)

    andockungen, konflikte = zuordnen_alle(an, ab, tore, config)

    assert len(andockungen) == len(an) + len(ab)
    assert len(konflikte) > 0  # dieses Szenario (1 Tor, 7-min-Abstand) muss Konflikte erzeugen
    eingehende_ids = {e.event_id for e in an + ab}
    ausgehende_ids = {a.ereignis.event_id for a in andockungen}
    assert eingehende_ids == ausgehende_ids
