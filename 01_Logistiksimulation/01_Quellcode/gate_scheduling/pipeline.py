"""Orchestrierung aller Module. Ein Aufruf durchlaeuft alle Schritte und
schreibt Zwischenergebnisse, Grafiken und Berichte in einen versionierten
Ausgabeordner. Jeder Schritt ist auch einzeln aufrufbar (siehe Funktionen
unten bzw. die jeweiligen Modul-Funktionen direkt).

Ohne globalen Zustand: alle Schritte sind reine Funktionen, die Konfiguration
und Zwischenergebnisse explizit als Parameter erhalten. Keine Seiteneffekte
auf Dateien ausserhalb des Ausgabeordners (Eingaben werden nur gelesen).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from . import assignment, plausibility, schedules, state_model, visualization
from .calendar_mapping import KalenderIndex
from .config import GateScheduleConfig
from .gates import Gate, TorSeite, erzeuge_tore


def _lade_json(pfad: str | Path) -> dict:
    with open(pfad, "r", encoding="utf-8") as f:
        return json.load(f)


def erzeuge_versionierten_output_ordner(basis: str | Path, erzeugungszeitpunkt: datetime) -> Path:
    ordner = Path(basis) / f"run_{erzeugungszeitpunkt.strftime('%Y%m%d_%H%M%S')}"
    for sub in ("schedules", "plots", "berichte"):
        (ordner / sub).mkdir(parents=True, exist_ok=True)
    return ordner


def schritt_laden(
    config: GateScheduleConfig, crossdocking_dir: str | Path
) -> tuple[list[assignment.AndockEreignis], list[assignment.AndockEreignis], KalenderIndex]:
    """Schritt 0: Ereignisse aus den bestehenden JSON-Artefakten laden."""
    ki = KalenderIndex(config.kalenderjahr)
    zeitachse = _lade_json(Path(crossdocking_dir) / config.zeitachse_pfad)
    warenausgang = _lade_json(Path(crossdocking_dir) / config.warenausgang_pfad)
    an_ereignisse = assignment.lade_ereignisse(zeitachse, TorSeite.AN, ki)
    ab_ereignisse = assignment.lade_ereignisse(warenausgang, TorSeite.AB, ki)
    return an_ereignisse, ab_ereignisse, ki


def schritt_zuordnung(
    an_ereignisse: list[assignment.AndockEreignis],
    ab_ereignisse: list[assignment.AndockEreignis],
    tore: list[Gate],
    config: GateScheduleConfig,
) -> tuple[list[assignment.Andockung], list[assignment.Konflikt]]:
    """Schritt 1: LKW -> Tor Zuordnung inkl. Kollisionspruefung."""
    return assignment.zuordnen_alle(an_ereignisse, ab_ereignisse, tore, config)


def schritt_zustandsmodell(
    andockungen: list[assignment.Andockung], tore: list[Gate], config: GateScheduleConfig
) -> dict[Gate, list[state_model.Zustandswechsel]]:
    """Schritt 2: Zustandslisten je Tor."""
    simulation_start = datetime(config.kalenderjahr, 1, 1, 0, 0)
    return state_model.alle_zustandslisten(andockungen, tore, config.schema, simulation_start)


def schritt_schedules(
    zustandslisten: dict[Gate, list[state_model.Zustandswechsel]],
    tore: list[Gate],
    config: GateScheduleConfig,
    output_ordner: Path,
    erzeugungszeitpunkt: datetime,
) -> None:
    """Schritt 3: EnergyPlus Schedule:Compact Export (je Tor + Sammeldatei)."""
    letzter_zeitpunkt = max(
        (w.zeitpunkt for wechsel in zustandslisten.values() for w in wechsel),
        default=datetime(config.kalenderjahr, 12, 31),
    )
    tage = [date(config.kalenderjahr, 1, 1) + timedelta(days=i)
            for i in range((date(config.kalenderjahr, 12, 31) - date(config.kalenderjahr, 1, 1)).days + 1)]
    if letzter_zeitpunkt.date() > tage[-1]:
        tage.append(letzter_zeitpunkt.date())

    for tor in tore:
        pfad = output_ordner / "schedules" / f"{tor.gate_id.replace(' ', '_')}.idf"
        schedules.schreibe_tor_datei(pfad, tor, zustandslisten[tor], tage, config, erzeugungszeitpunkt)

    schedules.schreibe_sammeldatei(
        output_ordner / "schedules" / "alle_tore.idf", zustandslisten, tage, config, erzeugungszeitpunkt
    )


def schritt_plausibilitaet(
    andockungen: list[assignment.Andockung],
    eingangs_ereigniszahl: int,
    zustandslisten: dict[Gate, list[state_model.Zustandswechsel]],
    config: GateScheduleConfig,
) -> plausibility.PlausibilitaetsBericht:
    """Schritt 4: Plausibilitaetspruefung."""
    return plausibility.pruefe_plausibilitaet(
        andockungen, eingangs_ereigniszahl, zustandslisten, config.min_abstand_min
    )


def schritt_visualisierung(
    andockungen: list[assignment.Andockung],
    zustandslisten: dict[Gate, list[state_model.Zustandswechsel]],
    tore: list[Gate],
    config: GateScheduleConfig,
    output_ordner: Path,
) -> date:
    """Schritt 5: alle Grafiken erzeugen. Gibt den gewaehlten Beispieltag zurueck."""
    plots = output_ordner / "plots"
    visualization.plot_hallenschema(tore, plots / "01_hallenschema.png")
    visualization.plot_torzuordnung(andockungen, tore, config.seed, plots / "02_torzuordnung.png")

    tage_mit_ereignissen = sorted({a.effektiver_t.date() for a in andockungen})
    beispieltag = tage_mit_ereignissen[0] if tage_mit_ereignissen else date(config.kalenderjahr, 1, 1)

    visualization.plot_ankunftsdaten(andockungen, tore, beispieltag, plots / "03_ankunftsdaten.png")
    visualization.plot_zustandsmodell(zustandslisten, tore, beispieltag, plots / "04_zustandsmodell.png")

    referenz_tor = tore[0]
    idf_pfad = output_ordner / "schedules" / f"{referenz_tor.gate_id.replace(' ', '_')}.idf"
    gelesen = schedules.lese_schedule_aus_datei(
        idf_pfad, schedules._schedule_name(referenz_tor), config.kalenderjahr
    )
    visualization.plot_schedule_ruecklese(
        gelesen, zustandslisten, referenz_tor, config.status_fractions, beispieltag,
        plots / "05_schedule_rueckvalidierung.png",
    )

    visualization.plot_gleichzeitigkeit(zustandslisten, tore, plots / "06_gleichzeitigkeit")
    return beispieltag


def fuehre_pipeline_aus(
    config: GateScheduleConfig, crossdocking_dir: str | Path, erzeugungszeitpunkt: datetime
) -> dict:
    """Fuehrt die vollstaendige Pipeline aus, schreibt alle Artefakte in einen
    versionierten Ausgabeordner und gibt eine Zusammenfassung zurueck."""
    output_ordner = erzeuge_versionierten_output_ordner(config.output_basis, erzeugungszeitpunkt)
    tore = erzeuge_tore(config.gates_per_side)

    an_ereignisse, ab_ereignisse, _ = schritt_laden(config, crossdocking_dir)
    eingangs_ereigniszahl = len(an_ereignisse) + len(ab_ereignisse)

    andockungen, konflikte = schritt_zuordnung(an_ereignisse, ab_ereignisse, tore, config)
    assignment.konflikte_zu_csv(konflikte, output_ordner / "berichte" / "konfliktbericht.csv")

    zustandslisten = schritt_zustandsmodell(andockungen, tore, config)
    schritt_schedules(zustandslisten, tore, config, output_ordner, erzeugungszeitpunkt)

    bericht = schritt_plausibilitaet(andockungen, eingangs_ereigniszahl, zustandslisten, config)
    beispieltag = schritt_visualisierung(andockungen, zustandslisten, tore, config, output_ordner)

    zusammenfassung = {
        "output_ordner": str(output_ordner),
        "erzeugungszeitpunkt": erzeugungszeitpunkt.isoformat(),
        "seed": config.seed,
        "eingangs_ereigniszahl": eingangs_ereigniszahl,
        "andockungen_gesamt": len(andockungen),
        "konflikte_gesamt": len(konflikte),
        "maximale_verschiebung_min": max((k.verschiebung_min for k in konflikte), default=0.0),
        "plausibilitaet_alles_ok": bericht.alles_ok,
        "plausibilitaet_verstoesse": bericht.verstoesse,
        "beispieltag": beispieltag.isoformat(),
    }
    with open(output_ordner / "berichte" / "zusammenfassung.json", "w", encoding="utf-8") as f:
        json.dump(zusammenfassung, f, indent=2, ensure_ascii=False)

    return zusammenfassung


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Tor-Schedule-Erweiterung (EnergyPlus)")
    parser.add_argument("--crossdocking-dir", default=".",
                        help="Verzeichnis mit ergebnis_zeitachse.json / ergebnis_warenausgang.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gates-per-side", type=int, default=3)
    parser.add_argument("--kalenderjahr", type=int, default=2026)
    parser.add_argument("--crossdocking-config", default=None,
                        help="beispiel_config.json - koppelt das Oeffnungsschema "
                             "an HallenConfig.be_entladezeit_min")
    args = parser.parse_args()

    if args.crossdocking_config:
        config = GateScheduleConfig.aus_crossdocking_config(
            args.crossdocking_config, seed=args.seed,
            gates_per_side=args.gates_per_side, kalenderjahr=args.kalenderjahr,
        )
    else:
        config = GateScheduleConfig(
            seed=args.seed, gates_per_side=args.gates_per_side,
            kalenderjahr=args.kalenderjahr,
        )
    print("Oeffnungsschema: oeffnen %+.0f, andock %+.0f, abdock %+.0f, schliessen %+.0f min; "
          "Mindestabstand je Tor %.0f min" % (
              config.schema.oeffnen_min, config.schema.andock_min,
              config.schema.abdock_min, config.schema.schliessen_min,
              config.min_abstand_min))
    zusammenfassung = fuehre_pipeline_aus(config, args.crossdocking_dir, datetime.now())
    print(json.dumps(zusammenfassung, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _cli()
