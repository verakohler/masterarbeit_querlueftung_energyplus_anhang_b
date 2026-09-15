import numpy as np

from .config import HallenConfig
from .simulation import CrossdockingSimulation


def alle_constraints_erfuellt(ergebnisse: list[list[dict]]) -> tuple[bool, str]:
    """
    Prueft ob in allen Wochen/Monaten saemtliche Constraints erfuellt sind.
    Gibt (True, "") zurueck wenn alles ok, sonst (False, engpass_name).
    """
    for monats_ergebnisse in ergebnisse:
        for wochen_ergebnis in monats_ergebnisse:
            if not wochen_ergebnis["kapazitaet_ok"].all():
                return False, "Hallenkapazitaet"
            if not wochen_ergebnis["same_day_ok"].all():
                return False, "Same-Day-Clearing"
            if not wochen_ergebnis["tor_kapazitaet_ok"].all():
                return False, "Tor-Kapazitaet"
    return True, ""


def finde_max_lkw_jahr(config: HallenConfig,
                       M: np.ndarray,
                       schicht_gewichte: np.ndarray,
                       monatsgewichte: np.ndarray,
                       wochengewichte_pro_monat: list[np.ndarray],
                       I_0: float = 0.0,
                       obergrenze: int | None = None) -> dict:
    """
    Binaere Suche ueber n_jahr um die maximale LKW-Anzahl zu finden,
    bei der alle Constraints erfuellt sind.

    Returns:
        {"max_n_jahr": int, "engpass": str}
    """
    untere = 0
    obere = obergrenze if obergrenze else 100_000

    # Obere Grenze verdoppeln falls bereits alle Constraints erfuellt
    sim_test = CrossdockingSimulation(
        config=config, M=M, schicht_gewichte=schicht_gewichte,
        n_jahr=obere, monatsgewichte=monatsgewichte,
        wochengewichte_pro_monat=wochengewichte_pro_monat, I_0=I_0,
    )
    ok, _ = alle_constraints_erfuellt(sim_test.simuliere_jahr())
    while ok:
        obere *= 2
        sim_test = CrossdockingSimulation(
            config=config, M=M, schicht_gewichte=schicht_gewichte,
            n_jahr=obere, monatsgewichte=monatsgewichte,
            wochengewichte_pro_monat=wochengewichte_pro_monat, I_0=I_0,
        )
        ok, _ = alle_constraints_erfuellt(sim_test.simuliere_jahr())

    letzter_engpass = ""

    while obere - untere > 1:
        mitte = (untere + obere) // 2
        sim = CrossdockingSimulation(
            config=config, M=M, schicht_gewichte=schicht_gewichte,
            n_jahr=mitte, monatsgewichte=monatsgewichte,
            wochengewichte_pro_monat=wochengewichte_pro_monat, I_0=I_0,
        )
        ok, engpass = alle_constraints_erfuellt(sim.simuliere_jahr())
        if ok:
            untere = mitte
        else:
            obere = mitte
            letzter_engpass = engpass

    return {
        "max_n_jahr": untere,
        "engpass": letzter_engpass,
    }
