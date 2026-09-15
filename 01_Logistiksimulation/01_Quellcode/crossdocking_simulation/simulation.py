import numpy as np

from .config import HallenConfig
from .wochenarbeitsmatrix import gewichte_matrix
from .verteilung import lkw_pro_monat, lkw_pro_woche, lkw_pro_schicht
from .bestandsrechnung import berechne_bestand
from .constraints import (
    pruefe_same_day_clearing,
    erzeuge_phasenverschiebung,
    erzeuge_spiegelung,
    pruefe_kapazitaet,
    pruefe_tor_kapazitaet,
)


class CrossdockingSimulation:
    """Syntheseschritt: Zusammenfuehrung aller Teilmodelle."""

    def __init__(self, config: HallenConfig,
                 M: np.ndarray,
                 schicht_gewichte: np.ndarray,
                 n_jahr: int,
                 monatsgewichte: np.ndarray,
                 wochengewichte_pro_monat: list[np.ndarray],
                 I_0: float = 0.0):

        self.config = config
        self.n_jahr = n_jahr
        self.I_0 = I_0

        # Wochenarbeitsmatrix gewichten
        self.M_gewichtet = gewichte_matrix(M, schicht_gewichte)

        # Jahresverteilung berechnen
        self.monatliche_lkw = lkw_pro_monat(n_jahr, monatsgewichte)
        self.wochengewichte_pro_monat = wochengewichte_pro_monat

    def simuliere_woche(self, n_woche: float) -> dict:
        """Simuliert eine einzelne Woche."""
        # LKWs pro Schicht (7x5 Matrix)
        L = lkw_pro_schicht(n_woche, self.M_gewichtet)

        # Anlieferung = LKW-Verteilung
        A = L

        # Abholung: Spiegelung oder Phasenverschiebung
        if self.config.spiegelung:
            D = erzeuge_spiegelung(A)
        else:
            D = erzeuge_phasenverschiebung(A, self.config.delta_s)

        # Bestandsverlauf in Paletten
        I = berechne_bestand(self.I_0, A, D, self.config.paletten_pro_lkw)

        # Constraints pruefen
        kapazitaet_ok = pruefe_kapazitaet(I, self.config.kapazitaet_paletten)
        same_day_ok = pruefe_same_day_clearing(I, self.config.kapazitaet_paletten)
        tor_kapazitaet_ok = pruefe_tor_kapazitaet(
            L,
            self.config.anzahl_tore,
            self.config.be_entladezeit_min,
            self.config.schicht_dauer_min,
        )

        return {
            "anlieferung": A,
            "abholung": D,
            "bestand": I,
            "kapazitaet_ok": kapazitaet_ok,
            "same_day_ok": same_day_ok,
            "tor_kapazitaet_ok": tor_kapazitaet_ok,
        }

    def simuliere_jahr(self) -> list[list[dict]]:
        """Simuliert das gesamte Jahr (12 Monate x ~4 Wochen)."""
        ergebnisse = []
        for m in range(12):
            monats_ergebnisse = []
            wochen_lkw = lkw_pro_woche(
                self.monatliche_lkw[m],
                self.wochengewichte_pro_monat[m],
            )
            for w, n_w in enumerate(wochen_lkw):
                ergebnis = self.simuliere_woche(n_w)
                monats_ergebnisse.append(ergebnis)
            ergebnisse.append(monats_ergebnisse)
        return ergebnisse
