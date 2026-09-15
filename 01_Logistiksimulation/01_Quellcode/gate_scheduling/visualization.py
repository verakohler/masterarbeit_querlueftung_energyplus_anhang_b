"""Grafiken je Pipeline-Schritt (PNG), zur inhaltlichen Pruefung.

Jede Funktion erzeugt genau eine Grafik mit Achsenbeschriftung, Einheit und
Legende. 'Gleichzeitig offen' bezieht sich auf den physischen Tuerzustand:
sowohl 'offen' als auch 'LKW' bedeuten, dass das Tor geoeffnet ist -- nur
'zu' bedeutet geschlossen.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from .assignment import Andockung, Konflikt
from .gates import Gate, TorSeite, TorStatus
from .schedules import _status_am_tagesanfang, _wechsel_innerhalb_tag
from .state_model import Zustandswechsel

FARBE_STATUS = {TorStatus.ZU: "#9e9e9e", TorStatus.OFFEN: "#2ca02c", TorStatus.LKW: "#d62728"}
FARBE_SEITE = {TorSeite.AN: "#1f77b4", TorSeite.AB: "#ff7f0e"}


def _speichern(fig, pfad: str | Path) -> None:
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pfad, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_hallenschema(tore: list[Gate], pfad: str | Path) -> None:
    """01: Hallenschema mit AN-Toren (unten) und AB-Toren (oben)."""
    an_tore = [t for t in tore if t.seite == TorSeite.AN]
    ab_tore = [t for t in tore if t.seite == TorSeite.AB]
    n = max(len(an_tore), len(ab_tore))

    fig, ax = plt.subplots(figsize=(2 * n + 2, 5))
    ax.add_patch(patches.Rectangle((0, 0), n + 1, 4, fill=False, edgecolor="black", linewidth=2))
    ax.text((n + 1) / 2, 2, "Halle", ha="center", va="center", fontsize=14)

    for i, tor in enumerate(an_tore):
        x = i + 1
        ax.add_patch(patches.Rectangle((x - 0.3, -0.4), 0.6, 0.4, color=FARBE_SEITE[TorSeite.AN]))
        ax.text(x, -0.6, tor.gate_id, ha="center", va="top", fontsize=11)
    for i, tor in enumerate(ab_tore):
        x = i + 1
        ax.add_patch(patches.Rectangle((x - 0.3, 4.0), 0.6, 0.4, color=FARBE_SEITE[TorSeite.AB]))
        ax.text(x, 4.6, tor.gate_id, ha="center", va="bottom", fontsize=11)

    ax.text((n + 1) / 2, -1.1, "AN-Seite (ankommende LKW)", ha="center", fontsize=10, color=FARBE_SEITE[TorSeite.AN])
    ax.text((n + 1) / 2, 5.3, "AB-Seite (abfahrende LKW)", ha="center", fontsize=10, color=FARBE_SEITE[TorSeite.AB])

    ax.set_xlim(-0.5, n + 1.5)
    ax.set_ylim(-1.6, 5.8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("01 - Hallenschema mit Tor-Benennung")
    _speichern(fig, pfad)


def plot_torzuordnung(andockungen: list[Andockung], tore: list[Gate], seed: int, pfad: str | Path) -> None:
    """02: Balkendiagramm Andockungen je Tor, getrennt AN/AB, Seed im Titel."""
    zaehler = Counter(a.gate for a in andockungen)
    fig, ax = plt.subplots(figsize=(max(6, len(tore) * 1.2), 5))
    labels = [t.gate_id for t in tore]
    werte = [zaehler.get(t, 0) for t in tore]
    farben = [FARBE_SEITE[t.seite] for t in tore]
    ax.bar(labels, werte, color=farben)
    for i, w in enumerate(werte):
        ax.text(i, w, str(w), ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("Tor")
    ax.set_ylabel("Anzahl Andockungen [LKW]")
    ax.set_title(f"02 - Torzuordnung (Seed={seed})")
    handles = [patches.Patch(color=FARBE_SEITE[s], label=s.value) for s in TorSeite]
    ax.legend(handles=handles, title="Seite")
    _speichern(fig, pfad)


def plot_ankunftsdaten(
    andockungen: list[Andockung], tore: list[Gate], beispieltag: date, pfad: str | Path
) -> None:
    """03: Zeitstempel je Tor an einem Beispieltag + Tagesganglinie ueber den Gesamtzeitraum."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))

    tag_start = datetime.combine(beispieltag, time(0, 0))
    tag_ende = tag_start + timedelta(days=1)
    tages_andockungen = [a for a in andockungen if tag_start <= a.effektiver_t < tag_ende]

    for i, tor in enumerate(tore):
        zeiten = [a.effektiver_t for a in tages_andockungen if a.gate == tor]
        stunden = [(t - tag_start).total_seconds() / 3600 for t in zeiten]
        ax1.scatter(stunden, [i] * len(stunden), color=FARBE_SEITE[tor.seite], s=40)
    ax1.set_yticks(range(len(tore)))
    ax1.set_yticklabels([t.gate_id for t in tore])
    ax1.set_xlabel("Uhrzeit [h]")
    ax1.set_xlim(0, 24)
    ax1.set_ylabel("Tor")
    ax1.set_title(f"03a - Ankunftszeitpunkte je Tor am {beispieltag.isoformat()}")
    handles = [patches.Patch(color=FARBE_SEITE[s], label=s.value) for s in TorSeite]
    ax1.legend(handles=handles, title="Seite")

    tage_zaehler: dict[date, int] = Counter(a.effektiver_t.date() for a in andockungen)
    tage_sortiert = sorted(tage_zaehler)
    ax2.plot(tage_sortiert, [tage_zaehler[t] for t in tage_sortiert], color="#1f77b4", linewidth=1)
    ax2.set_xlabel("Datum")
    ax2.set_ylabel("Andockungen/Tag [LKW]")
    ax2.set_title("03b - Tagesganglinie ueber den Gesamtzeitraum")
    fig.tight_layout()
    _speichern(fig, pfad)


def plot_zustandsmodell(
    zustandslisten: dict[Gate, list[Zustandswechsel]], tore: list[Gate], beispieltag: date, pfad: str | Path
) -> None:
    """04: Gantt-Darstellung des Torstatus ueber einen Beispieltag, alle Tore."""
    fig, ax = plt.subplots(figsize=(12, 0.8 * len(tore) + 2))
    tag_start = datetime.combine(beispieltag, time(0, 0))
    tag_ende = tag_start + timedelta(days=1)

    for i, tor in enumerate(tore):
        wechsel = sorted(zustandslisten[tor], key=lambda w: w.zeitpunkt)
        segmente = []
        aktueller_status = TorStatus.ZU
        aktueller_start = tag_start
        for w in wechsel:
            if w.zeitpunkt <= tag_start:
                aktueller_status = w.status
                continue
            if w.zeitpunkt >= tag_ende:
                break
            segmente.append((aktueller_start, w.zeitpunkt, aktueller_status))
            aktueller_start = w.zeitpunkt
            aktueller_status = w.status
        segmente.append((aktueller_start, tag_ende, aktueller_status))

        for start, ende, status in segmente:
            start_h = (start - tag_start).total_seconds() / 3600
            dauer_h = (ende - start).total_seconds() / 3600
            ax.barh(i, dauer_h, left=start_h, color=FARBE_STATUS[status], edgecolor="white", height=0.6)

    ax.set_yticks(range(len(tore)))
    ax.set_yticklabels([t.gate_id for t in tore])
    ax.set_xlabel("Uhrzeit [h]")
    ax.set_xlim(0, 24)
    ax.set_title(f"04 - Torstatus (Gantt) am {beispieltag.isoformat()}")
    handles = [patches.Patch(color=FARBE_STATUS[s], label=s.value) for s in TorStatus]
    ax.legend(handles=handles, title="Status")
    _speichern(fig, pfad)


def plot_schedule_ruecklese(
    gelesen: dict[date, list[tuple[time, float]]],
    zustandslisten: dict[Gate, list[Zustandswechsel]],
    tor: Gate,
    fractions,
    beispieltag: date,
    pfad: str | Path,
) -> None:
    """05: Aus der Ausgabedatei zurueckgelesener Fraction-Verlauf, ueberlagert
    mit dem Zustandsmodell desselben Tages. Wichtigste Grafik: bestaetigt,
    dass der Export nichts verandert hat."""
    fig, ax = plt.subplots(figsize=(11, 4))
    tag_start = datetime.combine(beispieltag, time(0, 0))

    # Referenz aus dem Zustandsmodell (Fraction ueber Status abgeleitet).
    # Nutzt dieselbe Tagesanfangs-/Innerhalb-Tag-Logik wie schedules.py, damit
    # Referenz und Export garantiert konsistent bewertet werden.
    wechsel = sorted(zustandslisten[tor], key=lambda w: w.zeitpunkt)
    status_start = _status_am_tagesanfang(wechsel, beispieltag)
    im_tag = _wechsel_innerhalb_tag(wechsel, beispieltag)

    zeiten_ref = [0.0]
    werte_ref = [fractions.fuer(status_start)]
    for w in im_tag:
        zeiten_ref.append((w.zeitpunkt - tag_start).total_seconds() / 3600)
        werte_ref.append(fractions.fuer(w.status))
    zeiten_ref.append(24.0)
    werte_ref.append(werte_ref[-1])
    ax.step(zeiten_ref, werte_ref, where="post", color="black", linewidth=2.5, label="Zustandsmodell (intern)")

    # Aus der geschriebenen Datei zurueckgelesen. 'Until'-Eintraege sind
    # Werte, die BIS zu diesem Zeitpunkt gelten -- fuer 'post'-Darstellung
    # beginnt die Zeitachse bei 0.0 und die Werte werden um einen Index
    # vorgezogen (letzter Wert am Ende dupliziert).
    eintraege = sorted(gelesen.get(beispieltag, []))
    zeiten_ep = [0.0]
    werte_ep = []
    for uhrzeit, wert in eintraege:
        stunden = 24.0 if (uhrzeit.hour, uhrzeit.minute) == (23, 59) else uhrzeit.hour + uhrzeit.minute / 60
        zeiten_ep.append(stunden)
        werte_ep.append(wert)
    werte_ep.append(werte_ep[-1] if werte_ep else fractions.fuer(status_start))
    ax.step(zeiten_ep, werte_ep, where="post", color="#d62728", linewidth=1.5, linestyle="--",
            label="Aus .idf zurueckgelesen")

    ax.set_xlabel("Uhrzeit [h]")
    ax.set_ylabel("Fraction [-]")
    ax.set_xlim(0, 24)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title(f"05 - Schedule-Ruecklesevalidierung {tor.gate_id} am {beispieltag.isoformat()}")
    ax.legend()
    _speichern(fig, pfad)


def plot_gleichzeitigkeit(
    zustandslisten: dict[Gate, list[Zustandswechsel]], tore: list[Gate], pfad_praefix: str | Path
) -> None:
    """06: Anzahl gleichzeitig geoeffneter Tore ueber die Zeit, Haeufigkeits-
    verteilung (0..N) und Haeufigkeit konkreter Torkombinationen (zeitgewichtet
    in Minuten). Erzeugt drei Dateien mit Praefix pfad_praefix."""
    alle_zeitpunkte = sorted({w.zeitpunkt for wechsel in zustandslisten.values() for w in wechsel})
    letzter_status: dict[Gate, TorStatus] = {t: TorStatus.ZU for t in tore}
    naechster_index: dict[Gate, int] = {t: 0 for t in tore}
    geordnete_wechsel = {t: sorted(zustandslisten[t], key=lambda w: w.zeitpunkt) for t in tore}

    zeitreihe: list[tuple[datetime, int, frozenset]] = []
    dauer_je_anzahl: Counter = Counter()
    dauer_je_kombination: Counter = Counter()

    for i, zp in enumerate(alle_zeitpunkte):
        for t in tore:
            liste = geordnete_wechsel[t]
            idx = naechster_index[t]
            while idx < len(liste) and liste[idx].zeitpunkt <= zp:
                letzter_status[t] = liste[idx].status
                idx += 1
            naechster_index[t] = idx
        offene = frozenset(t.gate_id for t in tore if letzter_status[t] != TorStatus.ZU)
        zeitreihe.append((zp, len(offene), offene))
        if i + 1 < len(alle_zeitpunkte):
            dauer_min = (alle_zeitpunkte[i + 1] - zp).total_seconds() / 60.0
            dauer_je_anzahl[len(offene)] += dauer_min
            dauer_je_kombination[offene] += dauer_min

    # 06a: Zeitreihe Anzahl offener Tore
    fig, ax = plt.subplots(figsize=(12, 4))
    zeiten = [z[0] for z in zeitreihe]
    anzahlen = [z[1] for z in zeitreihe]
    ax.step(zeiten, anzahlen, where="post", color="#1f77b4")
    ax.set_xlabel("Datum")
    ax.set_ylabel("Anzahl gleichzeitig offener Tore [-]")
    ax.set_title("06a - Gleichzeitig geoeffnete Tore ueber die Zeit")
    _speichern(fig, f"{pfad_praefix}_zeitreihe.png")

    # 06b: Haeufigkeitsverteilung 0..N (zeitgewichtet)
    fig, ax = plt.subplots(figsize=(7, 4))
    n_max = len(tore)
    werte = [dauer_je_anzahl.get(k, 0.0) / 60.0 for k in range(n_max + 1)]
    ax.bar(range(n_max + 1), werte, color="#1f77b4")
    ax.set_xlabel("Anzahl gleichzeitig offener Tore [-]")
    ax.set_ylabel("Zeitanteil [Stunden]")
    ax.set_title("06b - Haeufigkeitsverteilung der Gleichzeitigkeit (zeitgewichtet)")
    _speichern(fig, f"{pfad_praefix}_verteilung.png")

    # 06c: Haeufigkeit konkreter Torkombinationen (Top 10)
    top = dauer_je_kombination.most_common(10)
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = [", ".join(sorted(k)) if k else "(keine)" for k, _ in top]
    werte = [v / 60.0 for _, v in top]
    ax.barh(range(len(top)), werte, color="#ff7f0e")
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Zeitanteil [Stunden]")
    ax.set_title("06c - Haeufigste Torkombinationen (Top 10, zeitgewichtet)")
    fig.tight_layout()
    _speichern(fig, f"{pfad_praefix}_kombinationen.png")
