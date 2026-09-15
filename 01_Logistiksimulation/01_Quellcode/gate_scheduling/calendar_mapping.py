"""Abbildung des Modell-Zeitindex (Monat, Woche, Tag) auf echte Kalenderdaten.

Die bestehende Crossdocking-Simulation kennt kein echtes Kalenderdatum --
Ereignisse sind nur ueber ihre Position (monat 0-11, woche_index, tag_idx 0-6)
in der verschachtelten JSON-Struktur verortet. Fuer EnergyPlus-Schedules
(Through: MM/DD-Bloecke) wird jedoch ein echtes Kalenderjahr benoetigt.

ANNAHME: Jede "Woche" ist ein Montag-Sonntag-Block. Eine Woche gehoert zu dem
Kalendermonat, in dem ihr Montag liegt (auch wenn die Woche ueber die
Monatsgrenze hinausreicht). Diese Zuordnung ist konsistent mit der Reihenfolge,
in der monatsgewichte/wochengewichte_pro_monat in der Crossdocking-Config
erzeugt werden (siehe kalender_gewichte()).
"""
from __future__ import annotations

from datetime import date, timedelta


def _montage_je_monat(jahr: int) -> list[list[date]]:
    """Gruppiert alle Montage des Jahres nach dem Monat, in dem sie liegen.

    Rueckgabe: Liste mit 12 Eintraegen (Index 0 = Januar), jeweils die
    Montage (als date), deren Woche zu diesem Monat gehoert.
    """
    jahresanfang = date(jahr, 1, 1)
    jahresende = date(jahr, 12, 31)

    montage: list[list[date]] = [[] for _ in range(12)]
    montag = jahresanfang - timedelta(days=jahresanfang.weekday())
    while montag <= jahresende:
        # Der erste berechnete Montag kann ins Vorjahr fallen (z. B. 29.12.2025
        # fuer jahr=2026). Ohne Jahresfilter wuerde diese Woche faelschlich dem
        # gleichnamigen Monat des Zieljahres zugeschlagen (Dezember statt Vorjahr).
        if montag.year == jahr:
            montage[montag.month - 1].append(montag)
        montag += timedelta(days=7)
    return montage


class KalenderIndex:
    """Vorberechneter Index (monat, woche) -> Montagsdatum fuer ein Kalenderjahr."""

    def __init__(self, jahr: int):
        self.jahr = jahr
        self._montage = _montage_je_monat(jahr)

    def anzahl_wochen(self, monat_idx: int) -> int:
        return len(self._montage[monat_idx])

    def datum(self, monat_idx: int, woche_idx: int, tag_idx: int) -> date:
        """Liefert das Kalenderdatum fuer (monat_idx 0-11, woche_idx, tag_idx 0-6=Mo-So)."""
        montag = self._montage[monat_idx][woche_idx]
        return montag + timedelta(days=tag_idx)


def kalender_gewichte(jahr: int) -> tuple[list[int], list[list[int]]]:
    """Erzeugt monatsgewichte (=Werktage/Monat) und wochengewichte_pro_monat
    (uniform je real vorhandener Woche) fuer ein echtes Kalenderjahr.

    Konsistent mit der in beispiel_config.json hinterlegten Ableitung fuer 2026.
    Nutzt dieselbe Montags-Zuordnung wie KalenderIndex, damit Config-Erzeugung
    und Datums-Ruecklookup nicht auseinanderlaufen koennen.
    """
    montage = _montage_je_monat(jahr)
    monatsgewichte = [0] * 12
    tag = date(jahr, 1, 1)
    jahresende = date(jahr, 12, 31)
    while tag <= jahresende:
        if tag.weekday() < 5:
            monatsgewichte[tag.month - 1] += 1
        tag += timedelta(days=1)

    wochengewichte_pro_monat = [[1] * len(monate) for monate in montage]
    return monatsgewichte, wochengewichte_pro_monat
