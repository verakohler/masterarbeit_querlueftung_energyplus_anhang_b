import math

from .zeitachse import minuten_zu_uhrzeit


def berechne_fahrtzeit(distanz_km: float, geschwindigkeit_kmh: float = 80.0) -> float:
    """Reine Fahrtzeit in Minuten (ohne Pausen)."""
    return distanz_km / geschwindigkeit_kmh * 60.0


def berechne_pausen_eu(fahrtzeit_min: float,
                       pause_nach_min: float = 270.0,
                       pausendauer_min: float = 45.0) -> tuple[int, float]:
    """EU-Lenkzeitpausen nach VO (EG) 561/2006.

    Nach 4,5h (270 min) ununterbrochener Lenkzeit: 45 min Pause.
    Gibt (anzahl_pausen, pausen_gesamt_min) zurueck.
    """
    n_pausen = int(math.floor(fahrtzeit_min / pause_nach_min))
    return n_pausen, n_pausen * pausendauer_min


def berechne_abfahrt(ankunft_min: float, distanz_km: float,
                     geschwindigkeit_kmh: float = 80.0) -> dict:
    """Berechnet Abfahrtszeit, Fahrtzeit, Pausen und Reisedauer fuer einen LKW."""
    fahrtzeit = berechne_fahrtzeit(distanz_km, geschwindigkeit_kmh)
    n_pausen, pausen_gesamt = berechne_pausen_eu(fahrtzeit)
    reisedauer = fahrtzeit + pausen_gesamt
    abfahrt = ankunft_min - reisedauer

    return {
        "fahrtzeit_min": round(fahrtzeit, 1),
        "anzahl_pausen": n_pausen,
        "pausen_gesamt_min": round(pausen_gesamt, 1),
        "reisedauer_min": round(reisedauer, 1),
        "abfahrt_min": round(abfahrt, 1),
        "abfahrt_uhrzeit": minuten_zu_uhrzeit(abfahrt),
    }


def erzeuge_abfahrtszeiten(zeitachse_daten: dict,
                           geschwindigkeit_kmh: float = 80.0) -> dict:
    """Reichert Zeitachse-Daten mit Abfahrtszeiten und EU-Pausen an.

    Liest ergebnis_zeitachse.json-Struktur, gibt erweiterte Struktur zurueck.
    """
    ausgabe = {
        "meta": {
            **zeitachse_daten["meta"],
            "geschwindigkeit_kmh": geschwindigkeit_kmh,
            "pausenregelung": "EU VO (EG) 561/2006",
            "pause_nach_min": 270.0,
            "pausendauer_min": 45.0,
        },
        "ergebnisse": [],
    }

    for monat_daten in zeitachse_daten["ergebnisse"]:
        monat_ausgabe = {
            "monat": monat_daten["monat"],
            "monat_name": monat_daten["monat_name"],
            "wochen": [],
        }

        for wochen_daten in monat_daten["wochen"]:
            wochen_zeitachse = []

            for tag_schichten in wochen_daten["zeitachse"]:
                tag_ausgabe = []

                for schicht_lkws in tag_schichten:
                    schicht_ausgabe = []

                    for lkw in schicht_lkws:
                        abfahrt_daten = berechne_abfahrt(
                            lkw["zeit_min"], lkw["distanz_km"],
                            geschwindigkeit_kmh
                        )
                        schicht_ausgabe.append({
                            "zeit_min": lkw["zeit_min"],
                            "uhrzeit": lkw["uhrzeit"],
                            "distanz_km": lkw["distanz_km"],
                            **abfahrt_daten,
                        })

                    tag_ausgabe.append(schicht_ausgabe)

                wochen_zeitachse.append(tag_ausgabe)

            monat_ausgabe["wochen"].append({
                "woche": wochen_daten["woche"],
                "zeitachse": wochen_zeitachse,
            })

        ausgabe["ergebnisse"].append(monat_ausgabe)

    return ausgabe
