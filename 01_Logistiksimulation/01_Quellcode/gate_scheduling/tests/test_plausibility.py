"""Tests fuer den Plausibilitaets-Pipeline-Schritt."""
from datetime import datetime, timedelta

from gate_scheduling.assignment import AndockEreignis, Andockung
from gate_scheduling.gates import Gate, TorSeite, TorStatus
from gate_scheduling.plausibility import pruefe_plausibilitaet
from gate_scheduling.state_model import Zustandswechsel


def _andockung(gate: Gate, t: datetime, event_id: str) -> Andockung:
    ereignis = AndockEreignis(
        event_id=event_id, seite=gate.seite, geplanter_t=t,
        monat_idx=0, woche_idx=0, tag_idx=0, schicht_idx=0,
    )
    return Andockung(ereignis=ereignis, gate=gate, effektiver_t=t)


def test_korrektes_szenario_ist_plausibel():
    gate = Gate(TorSeite.AN, 1)
    t1 = datetime(2026, 1, 5, 8, 0)
    t2 = t1 + timedelta(minutes=23)
    andockungen = [_andockung(gate, t1, "A"), _andockung(gate, t2, "B")]
    zustandslisten = {
        gate: [
            Zustandswechsel(datetime(2026, 1, 1), TorStatus.ZU),
            Zustandswechsel(t1 - timedelta(minutes=2), TorStatus.OFFEN),
            Zustandswechsel(t1, TorStatus.LKW),
            Zustandswechsel(t1 + timedelta(minutes=15), TorStatus.OFFEN),
            Zustandswechsel(t1 + timedelta(minutes=20), TorStatus.ZU),
            Zustandswechsel(t2 - timedelta(minutes=2), TorStatus.OFFEN),
            Zustandswechsel(t2, TorStatus.LKW),
            Zustandswechsel(t2 + timedelta(minutes=15), TorStatus.OFFEN),
            Zustandswechsel(t2 + timedelta(minutes=20), TorStatus.ZU),
        ]
    }
    bericht = pruefe_plausibilitaet(andockungen, eingangs_ereigniszahl=2,
                                     zustandslisten=zustandslisten, min_abstand_min=23.0)
    assert bericht.alles_ok, bericht.verstoesse


def test_erkennt_ueberlappende_fenster():
    gate = Gate(TorSeite.AN, 1)
    t1 = datetime(2026, 1, 5, 8, 0)
    t2 = t1 + timedelta(minutes=5)  # zu nah, unterhalb Mindestabstand
    andockungen = [_andockung(gate, t1, "A"), _andockung(gate, t2, "B")]
    bericht = pruefe_plausibilitaet(andockungen, eingangs_ereigniszahl=2,
                                     zustandslisten={gate: []}, min_abstand_min=23.0)
    assert not bericht.keine_ueberlappungen
    assert not bericht.alles_ok


def test_erkennt_falsche_ereigniszahl():
    gate = Gate(TorSeite.AN, 1)
    andockungen = [_andockung(gate, datetime(2026, 1, 5, 8, 0), "A")]
    bericht = pruefe_plausibilitaet(andockungen, eingangs_ereigniszahl=2,
                                     zustandslisten={gate: []}, min_abstand_min=23.0)
    assert not bericht.ereigniszahl_ok


def test_erkennt_unzulaessigen_statuswechsel():
    gate = Gate(TorSeite.AN, 1)
    zustandslisten = {
        gate: [
            Zustandswechsel(datetime(2026, 1, 1), TorStatus.ZU),
            Zustandswechsel(datetime(2026, 1, 1, 1, 0), TorStatus.LKW),  # zu -> LKW ist unzulaessig
        ]
    }
    bericht = pruefe_plausibilitaet([], eingangs_ereigniszahl=0,
                                     zustandslisten=zustandslisten, min_abstand_min=23.0)
    assert not bericht.zustandsreihenfolge_ok
