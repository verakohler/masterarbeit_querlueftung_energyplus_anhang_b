"""Warenausgang-Zeitachse: Abfahrtszeiten der abholenden LKW aus der Halle.

Nutzt dieselbe Kumaraswamy(2,2)-Verteilung wie die Eingangs-Zeitachse,
angewandt auf die Abholungsmatrix D statt der Anlieferungsmatrix A.
"""

from .zeitachse import ankunftszeiten_in_schicht, minuten_zu_uhrzeit


def erzeuge_warenausgang_zeitachse(ergebnisse_daten: dict,
                                   schicht_dauer_min: float,
                                   rng=None) -> dict:
    """Erzeugt Abfahrtszeiten fuer alle abholenden LKW (Warenausgang).

    Liest die Abholungsmatrix (D) aus ergebnisse.json und weist jedem
    ausgehenden LKW eine Abfahrtszeit innerhalb seiner Schicht zu
    (Kumaraswamy(2,2)-Verteilung). Bei gesetztem rng wird gezogen statt auf
    Quantilen platziert -- siehe zeitachse.ankunftszeiten_in_schicht.

    Args:
        ergebnisse_daten: Geladene ergebnisse.json-Struktur.
        schicht_dauer_min: Dauer einer Schicht in Minuten.

    Returns:
        Dict mit hierarchischer Struktur: ergebnisse -> wochen -> zeitachse[tag][schicht] -> LKW-Liste.
    """
    ausgabe = {
        "meta": {
            "schicht_dauer_min": schicht_dauer_min,
            "verteilungsform": "Kumaraswamy(2,2)",
            "ankunftszeiten": "deterministische Quantile" if rng is None else "gezogen (Inversionsmethode)",
            "typ": "warenausgang",
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
            abholung = wochen_daten["abholung"]  # 7x5 Matrix (int-Werte)
            wochen_zeitachse = []

            for tag_idx, tag_abholung in enumerate(abholung):
                tag_zeitachse = []

                for schicht_idx, n_lkw in enumerate(tag_abholung):
                    schicht_start = schicht_idx * schicht_dauer_min

                    zeiten = ankunftszeiten_in_schicht(
                        n_lkw, schicht_start, schicht_dauer_min, rng
                    )

                    lkw_liste = [
                        {
                            "zeit_min": zeit,
                            "uhrzeit": minuten_zu_uhrzeit(zeit),
                        }
                        for zeit in zeiten
                    ]

                    tag_zeitachse.append(lkw_liste)

                wochen_zeitachse.append(tag_zeitachse)

            monat_ausgabe["wochen"].append({
                "woche": wochen_daten["woche"],
                "zeitachse": wochen_zeitachse,
            })

        ausgabe["ergebnisse"].append(monat_ausgabe)

    return ausgabe
