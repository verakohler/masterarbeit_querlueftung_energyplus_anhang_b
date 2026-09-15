import math

import numpy as np


def kumaraswamy_quantile(p: float, a: float = 2.0, b: float = 2.0) -> float:
    """Kumaraswamy(a,b) Quantilfunktion. Glockenfoermig fuer a=b=2.

    Geschlossene Formel: Q(p) = (1 - (1-p)^(1/b))^(1/a)
    Deterministisch, keine Zufallszahlen.
    """
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    return (1.0 - (1.0 - p) ** (1.0 / b)) ** (1.0 / a)


def ankunftszeiten_in_schicht(n_lkw: int, schicht_start_min: float,
                               schicht_dauer_min: float,
                               rng: "np.random.Generator | None" = None) -> list[float]:
    """Erzeugt n_lkw Ankunftszeiten innerhalb einer Schicht.

    Verteilungsform in beiden Faellen Kumaraswamy(2,2) -- glockenfoermig, viele
    Ankuenfte in der Schichtmitte, wenige an den Raendern.

    rng is None  -- deterministische Platzierung auf den aequidistanten
        Quantilen q_i = (i + 0.5) / n_lkw. Verhalten vor dem 10.08.2026.
    rng gesetzt  -- Ziehung nach der Inversionsmethode: q ~ U(0,1), danach
        dieselbe Quantilfunktion. Die Verteilung der Ankunftszeitpunkte ist
        damit identisch, aber die Realisierung ist nicht mehr allein durch
        n_lkw bestimmt.

    Warum die Aenderung (Befund 10.08.2026, siehe Dokumentation Abschnitt 10):
    Die deterministische Fassung erzwingt einen Mindestabstand von
    schicht_dauer_min / (n_lkw * f_max) mit f_max = 1,53960 als Dichtemaximum
    der Kumaraswamy(2,2). Bei 288 min Schichtdauer sind das 187,06 / n_lkw
    Minuten, also 23,58 min bei n_lkw = 8. Da das Belegungsfenster eines Tores
    nur 22 min betraegt, konnten zwei Tore derselben Fassade nie gleichzeitig
    belegt sein -- ein Artefakt der Platzierung, keine Betriebseigenschaft.
    Ausserdem hingen die Zeitpunkte allein von n_lkw ab, was ueber das Jahr nur
    14 verschiedene Tagesmuster ergab.
    """
    if n_lkw == 0:
        return []

    if rng is None:
        quantile = [(i + 0.5) / n_lkw for i in range(n_lkw)]
    else:
        quantile = sorted(float(q) for q in rng.random(n_lkw))

    zeiten = []
    for q in quantile:
        t_relativ = kumaraswamy_quantile(q)
        t_absolut = schicht_start_min + t_relativ * schicht_dauer_min
        zeiten.append(round(t_absolut, 1))

    return zeiten


def minuten_zu_uhrzeit(minuten: float) -> str:
    """Wandelt Tagesminuten in HH:MM-Format um."""
    m = int(minuten) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def erzeuge_zeitachse(ergebnis_distanz_daten: dict,
                      schicht_dauer_min: float,
                      rng: "np.random.Generator | None" = None) -> dict:
    """Erzeugt die Zeitachse: jeder LKW erhaelt Ankunftszeit + Distanz.

    Paarung: Ferne LKWs kommen frueher in der Schicht an (frueher losgefahren).

    rng wird durchgereicht und laeuft ueber alle Monate, Wochen, Tage und
    Schichten fort -- kein Neuseeding je Tag, sonst entstuenden erneut
    wiederkehrende Tagesmuster.
    """
    ausgabe = {
        "meta": {
            "schicht_dauer_min": schicht_dauer_min,
            "verteilungsform": "Kumaraswamy(2,2)",
            "ankunftszeiten": "deterministische Quantile" if rng is None else "gezogen (Inversionsmethode)",
            "paarung": "distanz-absteigend (ferne LKWs zuerst)",
            "einzugsbereich_km": ergebnis_distanz_daten["meta"]["einzugsbereich_km"],
            "distanz_gewichte": ergebnis_distanz_daten["meta"]["distanz_gewichte"],
        },
        "ergebnisse": [],
    }

    for monat_daten in ergebnis_distanz_daten["ergebnisse"]:
        monat_ausgabe = {
            "monat": monat_daten["monat"],
            "monat_name": monat_daten["monat_name"],
            "wochen": [],
        }

        for wochen_daten in monat_daten["wochen"]:
            distanzen_matrix = wochen_daten["anlieferung_distanzen"]  # 7x5
            wochen_zeitachse = []

            for tag_idx, tag_distanzen in enumerate(distanzen_matrix):
                tag_zeitachse = []

                for schicht_idx, schicht_distanzen in enumerate(tag_distanzen):
                    n_lkw = len(schicht_distanzen)
                    schicht_start = schicht_idx * schicht_dauer_min

                    # Ankunftszeiten erzeugen (glockenfoermig)
                    zeiten = ankunftszeiten_in_schicht(
                        n_lkw, schicht_start, schicht_dauer_min, rng
                    )

                    # Distanzen absteigend sortieren (fern -> nah)
                    distanzen_sortiert = sorted(schicht_distanzen, reverse=True)

                    # Paaren: fruehe Ankunft = ferner LKW
                    lkw_liste = []
                    for zeit, distanz in zip(zeiten, distanzen_sortiert):
                        lkw_liste.append({
                            "zeit_min": zeit,
                            "uhrzeit": minuten_zu_uhrzeit(zeit),
                            "distanz_km": distanz,
                        })

                    tag_zeitachse.append(lkw_liste)

                wochen_zeitachse.append(tag_zeitachse)

            monat_ausgabe["wochen"].append({
                "woche": wochen_daten["woche"],
                "zeitachse": wochen_zeitachse,
            })

        ausgabe["ergebnisse"].append(monat_ausgabe)

    return ausgabe
