import numpy as np


def berechne_bestand(I_0: float,
                     A: np.ndarray,
                     D: np.ndarray,
                     paletten_pro_lkw: int = 33) -> np.ndarray:
    """
    Berechnet den Lagerbestand ueber alle Tage und Schichten in Paletten.

    Args:
        I_0: Anfangsbestand (in Paletten)
        A: Anlieferungsmatrix in LKWs (Tage x 5 Schichten)
        D: Abholungsmatrix in LKWs (Tage x 5 Schichten)
        paletten_pro_lkw: Anzahl Standardpaletten pro LKW (default 33)

    Returns:
        I: Bestandsmatrix in Paletten (Tage x 5 Schichten)

    Formel: I(t,s) = I(t,s-1) + A(t,s)*paletten - D(t,s)*paletten
    """
    tage, schichten = A.shape
    I = np.zeros((tage, schichten))

    A_pal = A * paletten_pro_lkw
    D_pal = D * paletten_pro_lkw

    for t in range(tage):
        for s in range(schichten):
            if t == 0 and s == 0:
                vorheriger_bestand = I_0
            elif s == 0:
                vorheriger_bestand = I[t - 1, schichten - 1]
            else:
                vorheriger_bestand = I[t, s - 1]

            I[t, s] = vorheriger_bestand + A_pal[t, s] - D_pal[t, s]

    return I
