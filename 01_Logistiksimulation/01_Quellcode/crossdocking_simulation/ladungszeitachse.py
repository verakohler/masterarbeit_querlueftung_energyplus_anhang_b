"""Vollstaendige Ladungs-Zeitachse: Zusammenfuehrung aller Phasen einer Sendung.

Verknuepft Abfahrt-Daten (Wareneingang) mit Verweildauer-Daten zu einer
durchgehenden Zeitleiste pro Ladung:

    Abfahrt (Ursprung) -> Transportdauer -> Ankunft (Halle) -> Verweildauer -> Abfahrt (Halle)
"""

from collections import defaultdict


def erzeuge_ladungszeitachse(abfahrt_daten: dict,
                             verweildauer_daten: dict) -> dict:
    """Fuehrt Abfahrt- und Verweildauer-Daten zu einer vollstaendigen Zeitachse zusammen.

    Args:
        abfahrt_daten: Geladene ergebnis_abfahrt.json-Struktur.
        verweildauer_daten: Geladene ergebnis_verweildauer.json-Struktur.

    Returns:
        Dict mit vollstaendiger Ladungs-Zeitachse pro Woche.
    """
    ausgabe = {
        "meta": {
            "beschreibung": "Vollstaendige Ladungs-Zeitachse pro Sendung",
            "phasen": "Abfahrt (Ursprung) -> Transport -> Ankunft (Halle) -> Verweildauer -> Abfahrt (Halle)",
            "geschwindigkeit_kmh": abfahrt_daten["meta"].get("geschwindigkeit_kmh"),
            "pausenregelung": abfahrt_daten["meta"].get("pausenregelung"),
            "mindestverweildauer_min": verweildauer_daten["meta"].get("mindestverweildauer_min"),
        },
        "ergebnisse": [],
    }

    for monat_abfahrt, monat_verweildauer in zip(
        abfahrt_daten["ergebnisse"],
        verweildauer_daten["ergebnisse"],
    ):
        monat_ausgabe = {
            "monat": monat_abfahrt["monat"],
            "monat_name": monat_abfahrt["monat_name"],
            "wochen": [],
        }

        for wochen_abfahrt, wochen_verweildauer in zip(
            monat_abfahrt["wochen"],
            monat_verweildauer["wochen"],
        ):
            # Lookup aufbauen: (tag, schicht) -> Liste von Abfahrt-LKW-Dicts
            # Innerhalb jeder Schicht sind die LKW bereits nach zeit_min sortiert.
            lookup = defaultdict(list)
            for tag_idx, tag_schichten in enumerate(wochen_abfahrt["zeitachse"]):
                for schicht_idx, schicht_lkws in enumerate(tag_schichten):
                    for lkw in schicht_lkws:
                        lookup[(tag_idx, schicht_idx)].append(lkw)

            # Verbrauchszeiger pro (tag, schicht)
            zeiger = defaultdict(int)

            ladungen = []
            for vd_ladung in wochen_verweildauer["ladungen"]:
                key = (vd_ladung["ankunft_tag"], vd_ladung["ankunft_schicht"])
                idx = zeiger[key]
                ab_lkw = lookup[key][idx]
                zeiger[key] = idx + 1

                # Gesamtdauer berechnen (Transport + Verweildauer)
                if vd_ladung["verweildauer_min"] is not None:
                    gesamtdauer = round(ab_lkw["reisedauer_min"] + vd_ladung["verweildauer_min"], 1)
                else:
                    gesamtdauer = None

                ladungen.append({
                    # Phase 1: Abfahrt am Ursprung
                    "ursprung_abfahrt_min": ab_lkw["abfahrt_min"],
                    "ursprung_abfahrt_uhrzeit": ab_lkw["abfahrt_uhrzeit"],
                    "distanz_km": ab_lkw["distanz_km"],
                    # Phase 2: Transport
                    "fahrtzeit_min": ab_lkw["fahrtzeit_min"],
                    "anzahl_pausen": ab_lkw["anzahl_pausen"],
                    "pausen_gesamt_min": ab_lkw["pausen_gesamt_min"],
                    "reisedauer_min": ab_lkw["reisedauer_min"],
                    # Phase 3: Ankunft an der Halle
                    "ankunft_min": vd_ladung["ankunft_min"],
                    "ankunft_uhrzeit": vd_ladung["ankunft_uhrzeit"],
                    "ankunft_tag": vd_ladung["ankunft_tag"],
                    "ankunft_schicht": vd_ladung["ankunft_schicht"],
                    # Phase 4: Verweildauer
                    "verweildauer_min": vd_ladung["verweildauer_min"],
                    # Phase 5: Abfahrt aus der Halle
                    "abfahrt_halle_min": vd_ladung["abfahrt_min"],
                    "abfahrt_halle_uhrzeit": vd_ladung["abfahrt_uhrzeit"],
                    "abfahrt_halle_tag": vd_ladung["abfahrt_tag"],
                    "abfahrt_halle_schicht": vd_ladung["abfahrt_schicht"],
                    # Gesamt
                    "gesamtdauer_min": gesamtdauer,
                })

            # Statistiken
            gueltige = [l["gesamtdauer_min"] for l in ladungen if l["gesamtdauer_min"] is not None]
            if gueltige:
                stat = {
                    "anzahl_ladungen": len(ladungen),
                    "durchschnittliche_gesamtdauer_min": round(sum(gueltige) / len(gueltige), 1),
                    "max_gesamtdauer_min": round(max(gueltige), 1),
                    "min_gesamtdauer_min": round(min(gueltige), 1),
                }
            else:
                stat = {
                    "anzahl_ladungen": len(ladungen),
                    "durchschnittliche_gesamtdauer_min": 0.0,
                    "max_gesamtdauer_min": 0.0,
                    "min_gesamtdauer_min": 0.0,
                }

            monat_ausgabe["wochen"].append({
                "woche": wochen_abfahrt["woche"],
                "statistik": stat,
                "ladungen": ladungen,
            })

        ausgabe["ergebnisse"].append(monat_ausgabe)

    return ausgabe
