"""Tests: Kalenderabbildung, insbesondere die Jahresgrenze (Regressionstest
fuer den anfangs gefundenen Fehler: Woche vom 29.12. wurde faelschlich als
Dezember des Zieljahres gezaehlt)."""
from datetime import date

from gate_scheduling.calendar_mapping import KalenderIndex, kalender_gewichte


def test_erste_januarwoche_liegt_nach_dem_1_1():
    ki = KalenderIndex(2026)
    montag = ki.datum(0, 0, 0)
    assert montag.year == 2026
    assert montag.month == 1


def test_keine_vorjahreswoche_in_dezember():
    ki = KalenderIndex(2026)
    n_wochen = ki.anzahl_wochen(11)
    for w in range(n_wochen):
        datum = ki.datum(11, w, 0)
        assert datum.year == 2026
        assert datum.month == 12


def test_monatsgewichte_summe_ergibt_reale_werktage_2026():
    monatsgewichte, wochengewichte = kalender_gewichte(2026)
    assert sum(monatsgewichte) == 261  # reale Werktage 2026 (Mo-Fr)
    assert len(monatsgewichte) == 12
    assert len(wochengewichte) == 12


def test_datum_tag_idx_ergibt_richtigen_wochentag():
    ki = KalenderIndex(2026)
    montag = ki.datum(0, 0, 0)
    sonntag = ki.datum(0, 0, 6)
    assert montag.weekday() == 0
    assert sonntag.weekday() == 6
    assert (sonntag - montag).days == 6
