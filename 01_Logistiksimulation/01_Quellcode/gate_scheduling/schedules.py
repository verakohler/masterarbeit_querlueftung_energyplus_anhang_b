"""Export der Zustandslisten als EnergyPlus Schedule:Compact (.idf).

WICHTIGER VORBEHALT 1 (Timestep): Die Minutenauflösung dieser Schedules wirkt
in EnergyPlus nur, wenn im IDF 'Timestep, 60;' gesetzt ist. Bei einer
geringeren Zeitschrittzahl (z. B. Timestep, 4) mittelt EnergyPlus die Werte
innerhalb eines Zeitschritts, wodurch der Unterschied zwischen den Fraction-
Werten 1.0 (offen) und 0.048 (LKW) verwischt. Diese Datei enthaelt deshalb
in jedem Kopfkommentar einen Hinweis darauf; eine Pruefung des projektweiten
IDF-Timestep-Werts ist separat vorzunehmen, sobald eine IDF vorliegt (im
Rahmen dieser Erweiterung wurde keine IDF im Projekt gefunden).

WICHTIGER VORBEHALT 2 (Modellabhaengigkeit von 0.048): Der Fraction-Wert
0.048 ist nicht modellneutral. Als AirflowNetwork-Opening-Factor bedeutet er
einen Teiloeffnungsgrad der Toroeffnung; als Multiplikator auf
ZoneVentilation:DesignFlowRate bedeutet er einen Anteil des Nominal-
Volumenstroms. Das Schedule ist technisch fuer beide Verwendungen nutzbar,
die physikalische Kalibrierung des Werts 0.048 ist es nicht.

Format: Ein Through:-Block pro Kalendertag (For: AllDays), damit jeder Tag
sein eigenes Profil hat. Tage ohne Andockung erhalten einen einzelnen
Eintrag 'Until: 24:00, 0.0'. Zustandswechsel, die ueber Mitternacht
hinausreichen (moeglich bei Andockungen spaet am Tag, da schliessen_min bis
zu +20 min nach t liegt), werden korrekt auf den Folgetag uebertragen: der
Starzustand jedes Tages wird aus dem letzten Wechsel vor Tagesbeginn
abgeleitet, nicht angenommen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .config import GateScheduleConfig, StatusFractions
from .gates import Gate, TorStatus
from .state_model import Zustandswechsel

SCHEDULE_TYPE_LIMITS_BLOCK = (
    "ScheduleTypeLimits,\n"
    "    Fraction,                !- Name\n"
    "    0.0,                     !- Lower Limit Value\n"
    "    1.0,                     !- Upper Limit Value\n"
    "    Continuous;              !- Numeric Type\n"
)


def _schedule_name(gate: Gate) -> str:
    return f"{gate.gate_id.replace(' ', '_')}_Tor_Schedule"


def _minute_zu_hhmm(minute_des_tages: int) -> str:
    if minute_des_tages >= 1440:
        return "24:00"
    h, m = divmod(minute_des_tages, 60)
    return f"{h:02d}:{m:02d}"


def _status_am_tagesanfang(wechsel: list[Zustandswechsel], tag: date) -> TorStatus:
    """Letzter Zustandswechsel vor oder exakt bei 00:00 dieses Tages."""
    tagesanfang = datetime.combine(tag, time(0, 0))
    kandidaten = [w for w in wechsel if w.zeitpunkt <= tagesanfang]
    if not kandidaten:
        return TorStatus.ZU
    return max(kandidaten, key=lambda w: w.zeitpunkt).status


def _wechsel_innerhalb_tag(wechsel: list[Zustandswechsel], tag: date) -> list[Zustandswechsel]:
    """Wechsel, die strikt nach 00:00 und vor dem naechsten Tagesbeginn liegen."""
    start = datetime.combine(tag, time(0, 0))
    ende = start + timedelta(days=1)
    im_tag = [w for w in wechsel if start < w.zeitpunkt < ende]
    return sorted(im_tag, key=lambda w: w.zeitpunkt)


def _tagesblock_zeilen(
    tag: date, wechsel: list[Zustandswechsel], fractions: StatusFractions
) -> list[str]:
    status_start = _status_am_tagesanfang(wechsel, tag)
    im_tag = _wechsel_innerhalb_tag(wechsel, tag)

    zeilen = [f"    Through: {tag.month}/{tag.day},", "    For: AllDays,"]

    if not im_tag:
        zeilen.append(f"    Until: 24:00,{fractions.fuer(status_start):.3f},")
        return zeilen

    eintraege: list[tuple[str, float]] = []
    haltender_status = status_start
    for w in im_tag:
        gesamtminuten = w.zeitpunkt.hour * 60 + w.zeitpunkt.minute
        hhmm = _minute_zu_hhmm(round(gesamtminuten))
        eintraege.append((hhmm, fractions.fuer(haltender_status)))
        haltender_status = w.status
    eintraege.append(("24:00", fractions.fuer(haltender_status)))

    # Duplikate durch Minutenrundung zusammenfassen (letzter Wert je Minute gewinnt),
    # damit keine nicht-monoton steigenden Until:-Zeiten entstehen.
    zusammengefasst: list[tuple[str, float]] = []
    for hhmm, wert in eintraege:
        if zusammengefasst and zusammengefasst[-1][0] == hhmm:
            zusammengefasst[-1] = (hhmm, wert)
        else:
            zusammengefasst.append((hhmm, wert))

    for hhmm, wert in zusammengefasst:
        zeilen.append(f"    Until: {hhmm},{wert:.3f},")

    return zeilen


def _kopfkommentar(
    gate_bezeichnung: str,
    config: GateScheduleConfig,
    ereigniszahl: int,
    erzeugungszeitpunkt: datetime,
) -> str:
    s = config.schema
    f = config.status_fractions
    return (
        f"! Tor-Schedule: {gate_bezeichnung}\n"
        f"! Erzeugt: {erzeugungszeitpunkt.isoformat()}\n"
        f"! Skriptversion (gate_scheduling): {config.__module__.split('.')[0]} 0.1.0\n"
        f"! Seed (numpy.random.Generator): {config.seed}\n"
        f"! Schema-Offsets [min]: oeffnen={s.oeffnen_min}, andock={s.andock_min}, "
        f"abdock={s.abdock_min}, schliessen={s.schliessen_min}\n"
        f"! Statuswerte (Fraction): zu={f.zu}, offen={f.offen}, LKW={f.lkw}\n"
        f"! Ereigniszahl (Andockungen) fuer dieses Tor: {ereigniszahl}\n"
        f"!\n"
        f"! VORBEHALT 1: Die Minutenauflösung wirkt nur bei 'Timestep, 60;' im IDF.\n"
        f"!   Bei geringerer Zeitschrittzahl mittelt EnergyPlus die Werte und die\n"
        f"!   Unterscheidung zwischen 1.0 (offen) und {f.lkw} (LKW) verwischt.\n"
        f"! VORBEHALT 2: Der Wert {f.lkw} ist nicht modellneutral (AFN-Opening-Factor\n"
        f"!   vs. Multiplikator auf ZoneVentilation:DesignFlowRate) -- die physikalische\n"
        f"!   Kalibrierung ist verwendungsabhaengig und hier nicht vorgenommen.\n"
    )


def schedule_compact_objekt(
    gate: Gate,
    wechsel: list[Zustandswechsel],
    fractions: StatusFractions,
    tage: list[date],
) -> str:
    """Baut den vollstaendigen Schedule:Compact-Objekttext fuer ein Tor."""
    zeilen = [
        "Schedule:Compact,",
        f"    {_schedule_name(gate)},       !- Name",
        "    Fraction,                !- Schedule Type Limits Name",
    ]
    block_zeilen: list[str] = []
    for tag in tage:
        block_zeilen.extend(_tagesblock_zeilen(tag, wechsel, fractions))
    zeilen.extend(block_zeilen)
    # letztes Feld: Komma durch Semikolon ersetzen
    zeilen[-1] = zeilen[-1].rstrip(",") + ";"
    return "\n".join(zeilen) + "\n"


def schreibe_tor_datei(
    pfad: str | Path,
    gate: Gate,
    wechsel: list[Zustandswechsel],
    tage: list[date],
    config: GateScheduleConfig,
    erzeugungszeitpunkt: datetime,
) -> None:
    """Schreibt die separate .idf-Include-Datei fuer EIN Tor (ohne
    ScheduleTypeLimits -- die wird zentral in der Sammeldatei definiert, um
    Mehrfachdefinitionen zu vermeiden, wenn mehrere Include-Dateien
    gemeinsam in eine IDF eingebunden werden)."""
    ereigniszahl = sum(1 for w in wechsel if w.status == TorStatus.LKW)
    inhalt = (
        _kopfkommentar(gate.gate_id, config, ereigniszahl, erzeugungszeitpunkt)
        + "\n"
        + schedule_compact_objekt(gate, wechsel, config.status_fractions, tage)
    )
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(inhalt)


def schreibe_sammeldatei(
    pfad: str | Path,
    zustandslisten: dict[Gate, list[Zustandswechsel]],
    tage: list[date],
    config: GateScheduleConfig,
    erzeugungszeitpunkt: datetime,
) -> None:
    """Schreibt die Sammeldatei mit ScheduleTypeLimits + allen Tor-Schedules."""
    gesamt_ereignisse = sum(
        sum(1 for w in wechsel if w.status == TorStatus.LKW)
        for wechsel in zustandslisten.values()
    )
    teile = [
        _kopfkommentar("Sammeldatei (alle Tore)", config, gesamt_ereignisse, erzeugungszeitpunkt),
        "\n",
        SCHEDULE_TYPE_LIMITS_BLOCK,
        "\n",
    ]
    for gate, wechsel in zustandslisten.items():
        teile.append(schedule_compact_objekt(gate, wechsel, config.status_fractions, tage))
        teile.append("\n")

    with open(pfad, "w", encoding="utf-8") as f:
        f.write("".join(teile))


# --- Ruecklese-Validierung: liest die GESCHRIEBENE Datei erneut ein ---

_THROUGH_RE = re.compile(r"Through:\s*(\d{1,2})/(\d{1,2})")
_UNTIL_RE = re.compile(r"Until:\s*(\d{2}):(\d{2})\s*,\s*([0-9.]+)")


def lese_schedule_aus_datei(pfad: str | Path, schedule_name: str, jahr: int) -> dict[date, list[tuple[time, float]]]:
    """Parst eine geschriebene Schedule:Compact-Datei zurueck zu
    {datum: [(uhrzeit_bis, fraction), ...]}. Nutzt NUR die Ausgabedatei als
    Quelle (keine internen Zwischendaten) -- dient der Exportvalidierung.
    """
    with open(pfad, "r", encoding="utf-8") as f:
        text = f.read()

    ziel_name = schedule_name.replace(" ", "_")
    # Block des gesuchten Schedules isolieren: von "Schedule:Compact," bis zum
    # naechsten Semikolon, dessen Name-Feld dem gesuchten Tor entspricht.
    bloecke = text.split("Schedule:Compact,")[1:]
    gesuchter_block = None
    for block in bloecke:
        ende = block.find(";")
        stueck = block[: ende + 1] if ende != -1 else block
        if ziel_name in stueck.split(",")[0] or f"{ziel_name}," in stueck.replace("\n", ""):
            gesuchter_block = stueck
            break
    if gesuchter_block is None:
        raise ValueError(f"Schedule '{schedule_name}' nicht in {pfad} gefunden")

    ergebnis: dict[date, list[tuple[time, float]]] = {}
    aktuelles_datum: date | None = None
    for zeile in gesuchter_block.splitlines():
        through_match = _THROUGH_RE.search(zeile)
        if through_match:
            monat, tag = int(through_match.group(1)), int(through_match.group(2))
            aktuelles_datum = date(jahr, monat, tag)
            ergebnis[aktuelles_datum] = []
            continue
        until_match = _UNTIL_RE.search(zeile)
        if until_match and aktuelles_datum is not None:
            h, m, wert = int(until_match.group(1)), int(until_match.group(2)), float(until_match.group(3))
            uhrzeit = time(23, 59) if (h, m) == (24, 0) else time(h, m)
            ergebnis[aktuelles_datum].append((uhrzeit, wert))

    return ergebnis
