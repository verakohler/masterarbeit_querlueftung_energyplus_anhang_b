"""Tests fuer den Schedule:Compact-Export, insbesondere Mitternachts-
Ueberlauf (Andockung spaet am Tag, Zustandswechsel reicht in den Folgetag)
und die Ruecklese-Validierung aus der geschriebenen Datei."""
from datetime import date, datetime, timedelta

from gate_scheduling.config import GateScheduleConfig
from gate_scheduling.gates import Gate, TorSeite, TorStatus
from gate_scheduling.schedules import (
    _schedule_name,
    _status_am_tagesanfang,
    lese_schedule_aus_datei,
    schreibe_tor_datei,
)
from gate_scheduling.state_model import Zustandswechsel


def test_status_am_tagesanfang_erkennt_mitternachtsueberlauf():
    """Andockung um 23:59 -> abdock (t+15) faellt auf 00:14 des Folgetags.
    Der Folgetag muss mit Status LKW beginnen, nicht mit 'zu'."""
    gate = Gate(TorSeite.AN, 1)
    t = datetime(2026, 1, 5, 23, 59)
    wechsel = [
        Zustandswechsel(datetime(2026, 1, 1), TorStatus.ZU),
        Zustandswechsel(t - timedelta(minutes=2), TorStatus.OFFEN),
        Zustandswechsel(t, TorStatus.LKW),
        Zustandswechsel(t + timedelta(minutes=15), TorStatus.OFFEN),  # 2026-01-06 00:14
        Zustandswechsel(t + timedelta(minutes=20), TorStatus.ZU),      # 2026-01-06 00:19
    ]
    status_tag5 = _status_am_tagesanfang(wechsel, date(2026, 1, 5))
    status_tag6 = _status_am_tagesanfang(wechsel, date(2026, 1, 6))

    assert status_tag5 == TorStatus.ZU
    assert status_tag6 == TorStatus.LKW  # Uebertrag aus dem Vortag


def test_schreiben_und_ruecklesen_ergibt_identischen_verlauf(tmp_path):
    gate = Gate(TorSeite.AN, 1)
    t = datetime(2026, 1, 5, 8, 0)
    wechsel = [
        Zustandswechsel(datetime(2026, 1, 1), TorStatus.ZU),
        Zustandswechsel(t - timedelta(minutes=2), TorStatus.OFFEN),
        Zustandswechsel(t, TorStatus.LKW),
        Zustandswechsel(t + timedelta(minutes=15), TorStatus.OFFEN),
        Zustandswechsel(t + timedelta(minutes=20), TorStatus.ZU),
    ]
    tage = [date(2026, 1, 1) + timedelta(days=i) for i in range(6)]
    config = GateScheduleConfig(seed=1, gates_per_side=1)
    pfad = tmp_path / "AN_1.idf"

    schreibe_tor_datei(pfad, gate, wechsel, tage, config, datetime(2026, 1, 1, 12, 0))
    gelesen = lese_schedule_aus_datei(pfad, _schedule_name(gate), 2026)

    eintraege_tag5 = sorted(gelesen[date(2026, 1, 5)])
    werte = [w for _, w in eintraege_tag5]
    # Erwartete Fraction-Sequenz: 0.0 (zu) -> 1.0 (offen) -> 0.048 (LKW) -> 1.0 (offen) -> 0.0 (zu)
    assert werte == [0.0, 1.0, 0.048, 1.0, 0.0]


def test_tag_ohne_andockung_hat_einzelnen_eintrag():
    gate = Gate(TorSeite.AN, 1)
    wechsel = [Zustandswechsel(datetime(2026, 1, 1), TorStatus.ZU)]
    config = GateScheduleConfig(seed=1, gates_per_side=1)
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        pfad = os.path.join(d, "AN_1.idf")
        schreibe_tor_datei(pfad, gate, wechsel, [date(2026, 1, 2)], config, datetime(2026, 1, 1, 12, 0))
        gelesen = lese_schedule_aus_datei(pfad, _schedule_name(gate), 2026)
        assert gelesen[date(2026, 1, 2)] == [(gelesen[date(2026, 1, 2)][0][0], 0.0)]
        assert len(gelesen[date(2026, 1, 2)]) == 1
