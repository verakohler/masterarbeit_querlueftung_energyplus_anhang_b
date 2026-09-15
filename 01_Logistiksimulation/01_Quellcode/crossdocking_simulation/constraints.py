import numpy as np


def erzeuge_phasenverschiebung(A: np.ndarray, delta_s: int) -> np.ndarray:
    """
    Erzeugt die Abholmatrix D als zeitversetzte Funktion der Ankunftsmatrix A.
    delta_s: Anzahl Schichten Verschiebung (z.B. 3 = Morgen->Abends).
    """
    D = np.zeros_like(A)
    tage, schichten = A.shape
    for t in range(tage):
        for s in range(schichten):
            ziel_s = s + delta_s
            ziel_t = t + ziel_s // schichten
            ziel_s = ziel_s % schichten
            if ziel_t < tage:
                D[ziel_t, ziel_s] += A[t, s]
    return D


def erzeuge_spiegelung(A: np.ndarray) -> np.ndarray:
    """
    Spiegelt den Ankunftsvektor jedes Tages, um die Abholmatrix zu erzeugen.
    A[t, :] = [a1, a2, a3, a4, a5] -> D[t, :] = [a5, a4, a3, a2, a1]

    Dadurch wird Same-Day-Clearing automatisch erfuellt,
    da sum(A[t,:]) == sum(D[t,:]).
    """
    return A[:, ::-1].copy()


def pruefe_kapazitaet(I: np.ndarray, C_paletten: float) -> np.ndarray:
    """
    Constraint C: I(t,s) <= C_paletten fuer alle t, s.
    Bestand ist in Paletten, Kapazitaet in Palettenstellplaetzen.
    Gibt Boolean-Matrix zurueck (True = innerhalb Kapazitaet).
    """
    return I <= C_paletten


def pruefe_same_day_clearing(I: np.ndarray, C_paletten: float) -> np.ndarray:
    """
    Constraint A (verknuepft mit Kapazitaet):
    Ein Tagesrest ist erlaubt, SOLANGE die Hallenkapazitaet nicht ueberschritten wird.
    Prueft: I(t, letzte_schicht) <= C_paletten.
    Gibt Boolean-Array (pro Tag) zurueck.
    """
    return I[:, -1] <= C_paletten


def pruefe_tor_kapazitaet(L: np.ndarray, anzahl_tore: int,
                          be_entladezeit_min: float,
                          schicht_dauer_min: float) -> np.ndarray:
    """
    Constraint D: Genuegend Tore fuer die LKWs einer Schicht.
    Max LKWs pro Schicht = anzahl_tore * (schicht_dauer_min / be_entladezeit_min).
    Gibt Boolean-Matrix (7x5) zurueck (True = genuegend Tore).
    """
    max_lkw_pro_schicht = anzahl_tore * (schicht_dauer_min / be_entladezeit_min)
    return L <= max_lkw_pro_schicht
