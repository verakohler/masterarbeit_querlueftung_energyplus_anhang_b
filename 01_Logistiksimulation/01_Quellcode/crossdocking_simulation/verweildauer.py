"""Verweildauer-Berechnung: Kopplung von Wareneingang und Warenausgang.

Berechnet pro Woche die Verweildauer jeder Ladung in der Halle durch
chronologisches 1:1-Matching von Ankunfts- und Abfahrtszeiten.
"""

from .zeitachse import minuten_zu_uhrzeit


def _flatten_zeitachse(wochen_zeitachse: list, tages_arbeitszeit_min: float,
                       hat_distanz: bool = False) -> list[dict]:
    """Flacht eine Wochen-Zeitachse zu einer sortierten Liste mit absoluten Zeiten ab.

    Args:
        wochen_zeitachse: zeitachse[tag][schicht] -> LKW-Liste
        tages_arbeitszeit_min: Tagesarbeitszeit fuer absolute Zeitberechnung.
        hat_distanz: True wenn die LKW-Daten ein distanz_km-Feld haben.

    Returns:
        Sortierte Liste von dicts mit absoluter Zeit und Herkunfts-Info.
    """
    eintraege = []

    for tag_idx, tag_schichten in enumerate(wochen_zeitachse):
        for schicht_idx, schicht_lkws in enumerate(tag_schichten):
            for lkw in schicht_lkws:
                t_absolut = tag_idx * tages_arbeitszeit_min + lkw["zeit_min"]
                eintrag = {
                    "t_absolut": t_absolut,
                    "zeit_min": lkw["zeit_min"],
                    "tag": tag_idx,
                    "schicht": schicht_idx,
                }
                if hat_distanz and "distanz_km" in lkw:
                    eintrag["distanz_km"] = lkw["distanz_km"]
                eintraege.append(eintrag)

    eintraege.sort(key=lambda e: e["t_absolut"])
    return eintraege


def _matche_verweildauer(ankuenfte: list[dict], abfahrten: list[dict],
                         mindestverweildauer_min: float) -> tuple[list[dict], int]:
    """Chronologisches 1:1-Matching von Ankuenften und Abfahrten.

    Fuer jede Ankunft wird die naechste verfuegbare Abfahrt zugeordnet,
    die zeitlich nach der Ankunft liegt. Die Verweildauer wird mindestens
    auf mindestverweildauer_min gesetzt.

    Returns:
        (ladungen, unmatched): Liste der gematchten Ladungen und Anzahl ohne Abholer.
    """
    ladungen = []
    abfahrt_idx = 0
    n_abfahrten = len(abfahrten)
    unmatched = 0

    for ankunft in ankuenfte:
        t_a = ankunft["t_absolut"]

        # Naechste Abfahrt finden, die nach der Ankunft liegt
        while abfahrt_idx < n_abfahrten and abfahrten[abfahrt_idx]["t_absolut"] < t_a:
            abfahrt_idx += 1

        if abfahrt_idx < n_abfahrten:
            abfahrt = abfahrten[abfahrt_idx]
            zeitspanne = abfahrt["t_absolut"] - t_a
            verweildauer = max(zeitspanne, mindestverweildauer_min)

            ladungen.append({
                "ankunft_min": ankunft["zeit_min"],
                "ankunft_uhrzeit": minuten_zu_uhrzeit(ankunft["zeit_min"]),
                "ankunft_tag": ankunft["tag"],
                "ankunft_schicht": ankunft["schicht"],
                "abfahrt_min": abfahrt["zeit_min"],
                "abfahrt_uhrzeit": minuten_zu_uhrzeit(abfahrt["zeit_min"]),
                "abfahrt_tag": abfahrt["tag"],
                "abfahrt_schicht": abfahrt["schicht"],
                "verweildauer_min": round(verweildauer, 1),
            })

            abfahrt_idx += 1
        else:
            ladungen.append({
                "ankunft_min": ankunft["zeit_min"],
                "ankunft_uhrzeit": minuten_zu_uhrzeit(ankunft["zeit_min"]),
                "ankunft_tag": ankunft["tag"],
                "ankunft_schicht": ankunft["schicht"],
                "abfahrt_min": None,
                "abfahrt_uhrzeit": None,
                "abfahrt_tag": None,
                "abfahrt_schicht": None,
                "verweildauer_min": None,
            })
            unmatched += 1

    return ladungen, unmatched


def erzeuge_verweildauer(zeitachse_daten: dict,
                         warenausgang_daten: dict,
                         mindestverweildauer_min: float = 120.0,
                         tages_arbeitszeit_min: float = 1440.0) -> dict:
    """Berechnet die Verweildauer jeder Ladung pro Woche.

    Koppelt die Ankunftszeiten (Wareneingang) mit den Abfahrtszeiten
    (Warenausgang) durch chronologisches 1:1-Matching.

    Args:
        zeitachse_daten: Geladene ergebnis_zeitachse.json-Struktur.
        warenausgang_daten: Geladene ergebnis_warenausgang.json-Struktur.
        mindestverweildauer_min: Minimale Verweildauer (Handling-Puffer).
        tages_arbeitszeit_min: Tagesarbeitszeit fuer absolute Zeitberechnung.

    Returns:
        Dict mit Statistiken und Einzelwerten pro Woche.
    """
    ausgabe = {
        "meta": {
            "mindestverweildauer_min": mindestverweildauer_min,
            "tages_arbeitszeit_min": tages_arbeitszeit_min,
            "matching": "chronologisch 1:1 (pro Woche)",
        },
        "ergebnisse": [],
    }

    for monat_eingang, monat_ausgang in zip(
        zeitachse_daten["ergebnisse"],
        warenausgang_daten["ergebnisse"],
    ):
        monat_ausgabe = {
            "monat": monat_eingang["monat"],
            "monat_name": monat_eingang["monat_name"],
            "wochen": [],
        }

        for wochen_eingang, wochen_ausgang in zip(
            monat_eingang["wochen"],
            monat_ausgang["wochen"],
        ):
            # Zeitachsen zu flachen, absolut-sortierten Listen machen
            ankuenfte = _flatten_zeitachse(
                wochen_eingang["zeitachse"], tages_arbeitszeit_min, hat_distanz=True
            )
            abfahrten = _flatten_zeitachse(
                wochen_ausgang["zeitachse"], tages_arbeitszeit_min
            )

            # Matching durchfuehren
            ladungen, unmatched = _matche_verweildauer(
                ankuenfte, abfahrten, mindestverweildauer_min
            )

            # Statistiken berechnen
            gueltige = [l["verweildauer_min"] for l in ladungen if l["verweildauer_min"] is not None]

            if gueltige:
                durchschnitt = round(sum(gueltige) / len(gueltige), 1)
                maximum = round(max(gueltige), 1)
                minimum = round(min(gueltige), 1)
            else:
                durchschnitt = 0.0
                maximum = 0.0
                minimum = 0.0

            monat_ausgabe["wochen"].append({
                "woche": wochen_eingang["woche"],
                "statistik": {
                    "durchschnittliche_verweildauer_min": durchschnitt,
                    "max_verweildauer_min": maximum,
                    "min_verweildauer_min": minimum,
                    "anzahl_lkw_eingang": len(ankuenfte),
                    "anzahl_lkw_ausgang": len(abfahrten),
                    "ware_ohne_abholer": unmatched,
                },
                "ladungen": ladungen,
            })

        ausgabe["ergebnisse"].append(monat_ausgabe)

    return ausgabe
