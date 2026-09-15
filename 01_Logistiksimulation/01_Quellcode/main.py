"""
Crossdocking-Center Simulation - Hauptprogramm

Ausfuehrung:
    python main.py
    python main.py --config meine_config.json
    python main.py --config meine_config.json --output ergebnis.json
    python main.py --optimierung
"""
import argparse
import json

import numpy as np

from crossdocking_simulation.json_io import lade_konfiguration, speichere_ergebnisse
from crossdocking_simulation.simulation import CrossdockingSimulation
from crossdocking_simulation.optimierung import finde_max_lkw_jahr
from crossdocking_simulation.distanzverteilung import erzeuge_distanz_ergebnisse
from crossdocking_simulation.zeitachse import erzeuge_zeitachse
from crossdocking_simulation.abfahrtszeit import erzeuge_abfahrtszeiten
from crossdocking_simulation.warenausgang_zeitachse import erzeuge_warenausgang_zeitachse
from crossdocking_simulation.verweildauer import erzeuge_verweildauer
from crossdocking_simulation.ladungszeitachse import erzeuge_ladungszeitachse


def main():
    parser = argparse.ArgumentParser(description="Crossdocking-Center Simulation")
    parser.add_argument("--config", default="crossdocking_simulation/beispiel_config.json",
                        help="Pfad zur JSON-Konfigurationsdatei")
    parser.add_argument("--output", default="ergebnisse.json",
                        help="Pfad fuer die JSON-Ausgabedatei")
    parser.add_argument("--optimierung", action="store_true",
                        help="Maximale LKW-Menge pro Jahr berechnen")
    parser.add_argument("--distanz", action="store_true",
                        help="Distanzverteilung fuer LKWs erzeugen")
    parser.add_argument("--distanz-output", default="ergebnis_distanz.json",
                        help="Pfad fuer die Distanz-JSON-Ausgabedatei")
    parser.add_argument("--zeitachse", action="store_true",
                        help="Zeitachse mit Ankunftszeiten und Distanzen erzeugen")
    parser.add_argument("--zeitachse-output", default="ergebnis_zeitachse.json",
                        help="Pfad fuer die Zeitachse-JSON-Ausgabedatei")
    parser.add_argument("--abfahrt", action="store_true",
                        help="Abfahrtszeiten mit EU-Lenkzeitpausen berechnen")
    parser.add_argument("--abfahrt-output", default="ergebnis_abfahrt.json",
                        help="Pfad fuer die Abfahrt-JSON-Ausgabedatei")
    parser.add_argument("--warenausgang", action="store_true",
                        help="Warenausgang-Zeitachse (Abfahrtszeiten abholender LKW) erzeugen")
    parser.add_argument("--warenausgang-output", default="ergebnis_warenausgang.json",
                        help="Pfad fuer die Warenausgang-JSON-Ausgabedatei")
    parser.add_argument("--verweildauer", action="store_true",
                        help="Verweildauer pro Ladung berechnen (benoetigt --zeitachse und --warenausgang)")
    parser.add_argument("--verweildauer-output", default="ergebnis_verweildauer.json",
                        help="Pfad fuer die Verweildauer-JSON-Ausgabedatei")
    parser.add_argument("--ladungszeitachse", action="store_true",
                        help="Vollstaendige Ladungs-Zeitachse erzeugen (benoetigt --abfahrt und --verweildauer)")
    parser.add_argument("--ladungszeitachse-output", default="ergebnis_ladungszeitachse.json",
                        help="Pfad fuer die Ladungszeitachse-JSON-Ausgabedatei")
    args = parser.parse_args()

    # 1. Konfiguration laden
    eingabe = lade_konfiguration(args.config)
    config = eingabe.hallen_config

    print(f"Konfiguration geladen: {args.config}")
    print(f"  Halle: {config.laenge}m x {config.breite}m = {config.flaeche:.0f} m2")
    print(f"  Umschlagsflaeche: {config.kapazitaet_m2:.0f} m2")
    print(f"  Palettenstellplaetze: {config.kapazitaet_paletten:.0f}")
    print(f"  Tore: {config.anzahl_tore}")
    print(f"  LKWs/Jahr: {eingabe.n_jahr}")
    print(f"  Phasenverschiebung: {config.delta_s} Schichten")
    print(f"  Spiegelung: {config.spiegelung}")
    print()

    # 2. Simulation erstellen und ausfuehren
    sim = CrossdockingSimulation(
        config=config,
        M=eingabe.wochenarbeitsmatrix,
        schicht_gewichte=eingabe.schicht_gewichte,
        n_jahr=eingabe.n_jahr,
        monatsgewichte=eingabe.monatsgewichte,
        wochengewichte_pro_monat=eingabe.wochengewichte_pro_monat,
        I_0=eingabe.I_0,
    )

    ergebnisse = sim.simuliere_jahr()

    # 3. Ergebnisse serialisieren
    meta = {
        "n_jahr": eingabe.n_jahr,
        "hallenkapazitaet_paletten": config.kapazitaet_paletten,
        "delta_s": config.delta_s,
        "spiegelung": config.spiegelung,
        "paletten_pro_lkw": config.paletten_pro_lkw,
    }
    speichere_ergebnisse(ergebnisse, args.output, meta=meta)
    print(f"Ergebnisse gespeichert: {args.output}")

    # 4. Distanzverteilung (optional)
    if args.distanz:
        with open(args.config, "r", encoding="utf-8") as f:
            config_daten = json.load(f)

        einzugsbereich_km = config_daten.get("einzugsbereich_km", 500)
        distanz_gewichte = np.array(config_daten.get("distanz_gewichte", [5, 4, 3, 2, 1]), dtype=float)

        with open(args.output, "r", encoding="utf-8") as f:
            ergebnisse_daten = json.load(f)

        distanz_ergebnisse = erzeuge_distanz_ergebnisse(
            ergebnisse_daten, einzugsbereich_km, distanz_gewichte
        )

        with open(args.distanz_output, "w", encoding="utf-8") as f:
            json.dump(distanz_ergebnisse, f, indent=2, ensure_ascii=False)

        print(f"Distanzverteilung gespeichert: {args.distanz_output}")
        print(f"  Einzugsbereich: {einzugsbereich_km} km")
        print(f"  Distanzgewichte: {distanz_gewichte.tolist()}")

    # 5. Zeitachse (optional, benoetigt --distanz)
    if args.zeitachse:
        distanz_pfad = args.distanz_output
        with open(distanz_pfad, "r", encoding="utf-8") as f:
            distanz_daten = json.load(f)

        with open(args.config, "r", encoding="utf-8") as f:
            _cfg_zeit = json.load(f)
        _stoch = _cfg_zeit.get("ankunftszeiten_stochastisch", True)
        _seed = _cfg_zeit.get("ankunft_seed", 42)
        _rng = np.random.default_rng(_seed) if _stoch else None

        zeitachse_ergebnisse = erzeuge_zeitachse(
            distanz_daten, config.schicht_dauer_min, _rng
        )

        with open(args.zeitachse_output, "w", encoding="utf-8") as f:
            json.dump(zeitachse_ergebnisse, f, indent=2, ensure_ascii=False)

        print(f"Zeitachse gespeichert: {args.zeitachse_output}")
        print(f"  Schichtdauer: {config.schicht_dauer_min:.0f} min")
        print(f"  Verteilung: Kumaraswamy(2,2) - glockenfoermig")
        print(f"  Ankunftszeiten: {'gezogen (Seed %d)' % _seed if _stoch else 'deterministische Quantile'}")

    # 6. Abfahrtszeiten (optional, benoetigt --zeitachse)
    if args.abfahrt:
        zeitachse_pfad = args.zeitachse_output
        with open(zeitachse_pfad, "r", encoding="utf-8") as f:
            zeitachse_daten = json.load(f)

        abfahrt_ergebnisse = erzeuge_abfahrtszeiten(zeitachse_daten)

        with open(args.abfahrt_output, "w", encoding="utf-8") as f:
            json.dump(abfahrt_ergebnisse, f, indent=2, ensure_ascii=False)

        print(f"Abfahrtszeiten gespeichert: {args.abfahrt_output}")
        print(f"  Geschwindigkeit: 80 km/h")
        print(f"  Pausenregelung: EU VO (EG) 561/2006 (45 min nach 4,5h Lenkzeit)")

    # 7. Warenausgang-Zeitachse (optional)
    if args.warenausgang:
        with open(args.output, "r", encoding="utf-8") as f:
            ergebnisse_daten = json.load(f)

        with open(args.config, "r", encoding="utf-8") as f:
            _cfg_wa = json.load(f)
        _stoch_wa = _cfg_wa.get("ankunftszeiten_stochastisch", True)
        # Eigener Generator-Strom fuer die AB-Seite, damit die AN-Seite
        # unveraendert bleibt, wenn nur der Warenausgang neu erzeugt wird.
        _rng_wa = (np.random.default_rng(_cfg_wa.get("ankunft_seed", 42) + 1)
                   if _stoch_wa else None)

        warenausgang_ergebnisse = erzeuge_warenausgang_zeitachse(
            ergebnisse_daten, config.schicht_dauer_min, _rng_wa
        )

        with open(args.warenausgang_output, "w", encoding="utf-8") as f:
            json.dump(warenausgang_ergebnisse, f, indent=2, ensure_ascii=False)

        print(f"Warenausgang-Zeitachse gespeichert: {args.warenausgang_output}")
        print(f"  Schichtdauer: {config.schicht_dauer_min:.0f} min")
        print(f"  Verteilung: Kumaraswamy(2,2) - glockenfoermig")

    # 8. Verweildauer (optional, benoetigt --zeitachse und --warenausgang)
    if args.verweildauer:
        with open(args.config, "r", encoding="utf-8") as f:
            config_daten = json.load(f)

        mindestverweildauer = config_daten.get("mindestverweildauer_min", 120.0)

        zeitachse_pfad = args.zeitachse_output
        with open(zeitachse_pfad, "r", encoding="utf-8") as f:
            zeitachse_daten = json.load(f)

        warenausgang_pfad = args.warenausgang_output
        with open(warenausgang_pfad, "r", encoding="utf-8") as f:
            warenausgang_daten = json.load(f)

        verweildauer_ergebnisse = erzeuge_verweildauer(
            zeitachse_daten, warenausgang_daten,
            mindestverweildauer_min=mindestverweildauer,
            tages_arbeitszeit_min=config.tages_arbeitszeit_min,
        )

        with open(args.verweildauer_output, "w", encoding="utf-8") as f:
            json.dump(verweildauer_ergebnisse, f, indent=2, ensure_ascii=False)

        print(f"Verweildauer gespeichert: {args.verweildauer_output}")
        print(f"  Mindestverweildauer: {mindestverweildauer:.0f} min")
        print(f"  Matching: chronologisch 1:1 (pro Woche)")

    # 9. Ladungs-Zeitachse (optional, benoetigt --abfahrt und --verweildauer)
    if args.ladungszeitachse:
        abfahrt_pfad = args.abfahrt_output
        with open(abfahrt_pfad, "r", encoding="utf-8") as f:
            abfahrt_daten = json.load(f)

        verweildauer_pfad = args.verweildauer_output
        with open(verweildauer_pfad, "r", encoding="utf-8") as f:
            verweildauer_daten = json.load(f)

        ladungszeitachse_ergebnisse = erzeuge_ladungszeitachse(
            abfahrt_daten, verweildauer_daten
        )

        with open(args.ladungszeitachse_output, "w", encoding="utf-8") as f:
            json.dump(ladungszeitachse_ergebnisse, f, indent=2, ensure_ascii=False)

        print(f"Ladungs-Zeitachse gespeichert: {args.ladungszeitachse_output}")
        print(f"  Phasen: Abfahrt -> Transport -> Ankunft -> Verweildauer -> Abfahrt Halle")

    # 10. Optimierung (optional)
    if args.optimierung:
        print()
        print("Optimierung: Suche maximale LKW-Menge pro Jahr...")
        ergebnis = finde_max_lkw_jahr(
            config=config,
            M=eingabe.wochenarbeitsmatrix,
            schicht_gewichte=eingabe.schicht_gewichte,
            monatsgewichte=eingabe.monatsgewichte,
            wochengewichte_pro_monat=eingabe.wochengewichte_pro_monat,
            I_0=eingabe.I_0,
        )
        print(f"  Maximale LKWs/Jahr: {ergebnis['max_n_jahr']}")
        print(f"  Limitierender Constraint: {ergebnis['engpass']}")


if __name__ == "__main__":
    main()
