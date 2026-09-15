import math
import numpy as np


def lkw_pro_zone(n_lkw: int, distanz_gewichte: np.ndarray) -> np.ndarray:
    """Verteilt n_lkw auf 5 Distanzzonen per Gewicht mit Carry-Over-Rundung."""
    W = distanz_gewichte.sum()
    if W == 0 or n_lkw == 0:
        return np.zeros(len(distanz_gewichte), dtype=int)

    zonen = np.zeros(len(distanz_gewichte), dtype=int)
    carry = 0.0

    for k in range(len(distanz_gewichte)):
        if distanz_gewichte[k] == 0:
            continue
        exakt = (n_lkw / W) * distanz_gewichte[k] + carry
        gerundet = math.floor(exakt)
        carry = exakt - gerundet
        zonen[k] = gerundet

    # Restlichen Carry auf die gewichtsstaerkste Zone verteilen
    rest = n_lkw - zonen.sum()
    if rest > 0:
        max_zone = int(np.argmax(distanz_gewichte))
        zonen[max_zone] += rest

    return zonen


def distanzen_in_zone(n_zone: int, zone_start: float, zone_ende: float) -> list[float]:
    """Erzeugt n_zone gleichmaessig verteilte Distanzen innerhalb [zone_start, zone_ende]."""
    if n_zone == 0:
        return []
    zone_breite = zone_ende - zone_start
    return [
        round(zone_start + (zone_breite / (n_zone + 1)) * (i + 1), 1)
        for i in range(n_zone)
    ]


def erzeuge_distanzen(n_lkw: int, einzugsbereich_km: float,
                      distanz_gewichte: np.ndarray) -> tuple[list[float], list[int]]:
    """Erzeugt deterministisch n_lkw Distanzen basierend auf Zonengewichten.

    Returns:
        (distanzen, zone_verteilung): Sortierte Distanzliste und Anzahl LKWs pro Zone.
    """
    n_zonen = len(distanz_gewichte)
    zone_breite = einzugsbereich_km / n_zonen

    zonen_counts = lkw_pro_zone(n_lkw, distanz_gewichte)

    distanzen = []
    for k in range(n_zonen):
        zone_start = k * zone_breite
        zone_ende = (k + 1) * zone_breite
        distanzen.extend(distanzen_in_zone(zonen_counts[k], zone_start, zone_ende))

    return distanzen, zonen_counts.tolist()


def erzeuge_distanz_ergebnisse(ergebnisse_daten: dict,
                               einzugsbereich_km: float,
                               distanz_gewichte: np.ndarray) -> dict:
    """Erzeugt distanzbasierte Ergebnisse aus bestehenden Simulationsergebnissen."""
    n_zonen = len(distanz_gewichte)
    zone_breite = einzugsbereich_km / n_zonen
    zonen_grenzen = [round(i * zone_breite, 1) for i in range(n_zonen + 1)]

    ausgabe = {
        "meta": {
            "einzugsbereich_km": einzugsbereich_km,
            "distanz_gewichte": distanz_gewichte.tolist(),
            "zonen_grenzen": zonen_grenzen,
        },
        "ergebnisse": [],
    }

    for monat_daten in ergebnisse_daten["ergebnisse"]:
        monat_ausgabe = {
            "monat": monat_daten["monat"],
            "monat_name": monat_daten["monat_name"],
            "wochen": [],
        }

        for wochen_daten in monat_daten["wochen"]:
            anlieferung = wochen_daten["anlieferung"]  # 7x5
            distanzen_matrix = []
            zonen_matrix = []

            for tag in anlieferung:
                tag_distanzen = []
                tag_zonen = []
                for n_lkw in tag:
                    d, z = erzeuge_distanzen(n_lkw, einzugsbereich_km, distanz_gewichte)
                    tag_distanzen.append(d)
                    tag_zonen.append(z)
                distanzen_matrix.append(tag_distanzen)
                zonen_matrix.append(tag_zonen)

            monat_ausgabe["wochen"].append({
                "woche": wochen_daten["woche"],
                "anlieferung_distanzen": distanzen_matrix,
                "zone_verteilung": zonen_matrix,
            })

        ausgabe["ergebnisse"].append(monat_ausgabe)

    return ausgabe
