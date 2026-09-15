import json
from dataclasses import dataclass

import numpy as np

from .config import HallenConfig
from .zeitstruktur import MONATE


@dataclass
class SimulationsEingabe:
    hallen_config: HallenConfig
    wochenarbeitsmatrix: np.ndarray      # 7x5 binaere Matrix
    schicht_gewichte: np.ndarray         # Laenge 5
    n_jahr: int
    monatsgewichte: np.ndarray           # Laenge 12
    wochengewichte_pro_monat: list[np.ndarray]  # 12 Arrays
    I_0: float


def lade_konfiguration(pfad: str) -> SimulationsEingabe:
    """Liest die Simulationskonfiguration aus einer JSON-Datei."""
    with open(pfad, "r", encoding="utf-8") as f:
        daten = json.load(f)

    hc = daten["hallen_config"]
    hallen_config = HallenConfig(
        laenge=hc["laenge"],
        breite=hc["breite"],
        prozent_umschlag=hc["prozent_umschlag"],
        anzahl_tore=hc["anzahl_tore"],
        be_entladezeit_min=hc["be_entladezeit_min"],
        delta_s=daten.get("delta_s", 3),
        spiegelung=daten.get("spiegelung", False),
        paletten_pro_lkw=daten.get("paletten_pro_lkw", 33),
        paletten_stellplatz_m2=daten.get("paletten_stellplatz_m2", 0.96),
        tages_arbeitszeit_min=daten.get("tages_arbeitszeit_min", 1440.0),
    )

    wochenarbeitsmatrix = np.array(daten["wochenarbeitsmatrix"], dtype=int)
    schicht_gewichte = np.array(daten["schicht_gewichte"], dtype=float)
    monatsgewichte = np.array(daten["monatsgewichte"], dtype=float)
    wochengewichte_pro_monat = [
        np.array(w, dtype=float) for w in daten["wochengewichte_pro_monat"]
    ]

    return SimulationsEingabe(
        hallen_config=hallen_config,
        wochenarbeitsmatrix=wochenarbeitsmatrix,
        schicht_gewichte=schicht_gewichte,
        n_jahr=daten["n_jahr"],
        monatsgewichte=monatsgewichte,
        wochengewichte_pro_monat=wochengewichte_pro_monat,
        I_0=daten.get("I_0", 0.0),
    )


def _numpy_zu_liste(obj):
    """Rekursiver Konverter fuer JSON-Serialisierung von numpy-Typen."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _numpy_zu_liste(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_numpy_zu_liste(i) for i in obj]
    return obj


def speichere_ergebnisse(ergebnisse: list[list[dict]],
                         pfad: str,
                         meta: dict | None = None) -> None:
    """Serialisiert die Simulationsergebnisse in eine JSON-Datei."""
    ausgabe = {
        "meta": _numpy_zu_liste(meta) if meta else {},
        "ergebnisse": [],
    }

    for m, monats_ergebnisse in enumerate(ergebnisse):
        monat_daten = {
            "monat": m,
            "monat_name": MONATE[m],
            "wochen": [],
        }
        for w, wochen_ergebnis in enumerate(monats_ergebnisse):
            wochen_daten = {"woche": w}
            wochen_daten.update(_numpy_zu_liste(wochen_ergebnis))
            monat_daten["wochen"].append(wochen_daten)
        ausgabe["ergebnisse"].append(monat_daten)

    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(ausgabe, f, indent=2, ensure_ascii=False)
