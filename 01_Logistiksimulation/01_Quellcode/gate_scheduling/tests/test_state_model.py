"""Tests: Oeffnungsschema (exakte Offsets) und Anfangszustand 'zu'."""
from datetime import datetime, timedelta

from gate_scheduling.assignment import AndockEreignis, Andockung
from gate_scheduling.config import SchemaOffsets
from gate_scheduling.gates import Gate, TorSeite, TorStatus
from gate_scheduling.state_model import alle_zustandslisten, zustandsliste_fuer_tor


def _andockung(gate: Gate, t: datetime) -> Andockung:
    ereignis = AndockEreignis(
        event_id="TEST-1", seite=gate.seite, geplanter_t=t,
        monat_idx=0, woche_idx=0, tag_idx=0, schicht_idx=0,
    )
    return Andockung(ereignis=ereignis, gate=gate, effektiver_t=t)


def test_oeffnungsschema_exakte_offsets():
    gate = Gate(TorSeite.AN, 1)
    t = datetime(2026, 1, 5, 8, 0, 0)
    schema = SchemaOffsets(oeffnen_min=-2.0, andock_min=0.0, abdock_min=15.0, schliessen_min=20.0)
    simulation_start = datetime(2026, 1, 1, 0, 0)

    wechsel = zustandsliste_fuer_tor([_andockung(gate, t)], schema, simulation_start)

    zeiten_status = [(w.zeitpunkt, w.status) for w in wechsel]
    assert zeiten_status == [
        (simulation_start, TorStatus.ZU),
        (t - timedelta(minutes=2), TorStatus.OFFEN),
        (t, TorStatus.LKW),
        (t + timedelta(minutes=15), TorStatus.OFFEN),
        (t + timedelta(minutes=20), TorStatus.ZU),
    ]


def test_anfangszustand_ist_immer_zu_auch_ohne_andockung():
    gate = Gate(TorSeite.AN, 1)
    schema = SchemaOffsets()
    simulation_start = datetime(2026, 1, 1, 0, 0)

    wechsel = zustandsliste_fuer_tor([], schema, simulation_start)

    assert len(wechsel) == 1
    assert wechsel[0].status == TorStatus.ZU
    assert wechsel[0].zeitpunkt == simulation_start


def test_alle_zustandslisten_enthaelt_auch_tore_ohne_andockung():
    an1, an2 = Gate(TorSeite.AN, 1), Gate(TorSeite.AN, 2)
    schema = SchemaOffsets()
    simulation_start = datetime(2026, 1, 1, 0, 0)
    t = datetime(2026, 1, 5, 8, 0, 0)

    listen = alle_zustandslisten([_andockung(an1, t)], [an1, an2], schema, simulation_start)

    assert len(listen[an1]) == 5
    assert len(listen[an2]) == 1
    assert listen[an2][0].status == TorStatus.ZU


def test_custom_offsets_werden_uebernommen():
    gate = Gate(TorSeite.AN, 1)
    t = datetime(2026, 1, 5, 8, 0, 0)
    schema = SchemaOffsets(oeffnen_min=-5.0, andock_min=0.0, abdock_min=10.0, schliessen_min=12.0)
    simulation_start = datetime(2026, 1, 1, 0, 0)

    wechsel = zustandsliste_fuer_tor([_andockung(gate, t)], schema, simulation_start)

    zeiten = [w.zeitpunkt for w in wechsel[1:]]
    assert zeiten == [
        t - timedelta(minutes=5),
        t,
        t + timedelta(minutes=10),
        t + timedelta(minutes=12),
    ]
