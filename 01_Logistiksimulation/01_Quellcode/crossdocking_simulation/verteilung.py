import math
import numpy as np


def lkw_pro_monat(n_jahr: int, monatsgewichte: np.ndarray) -> np.ndarray:
    """Ebene 1: Jahr -> Monat. Gibt Array mit 12 Monatswerten zurueck."""
    v_jahr = monatsgewichte.sum()
    return n_jahr * monatsgewichte / v_jahr


def lkw_pro_woche(n_monat: float, wochengewichte: np.ndarray) -> np.ndarray:
    """Ebene 2: Monat -> Woche. Gibt Array mit Wochenwerten zurueck."""
    u_monat = wochengewichte.sum()
    return n_monat * wochengewichte / u_monat


def lkw_pro_schicht(n_woche: float, M_w: np.ndarray) -> np.ndarray:
    """Ebene 3: Woche -> Schicht mit Carry-Over-Rundung (Fehleruebertrag).

    Rundet per math.floor auf ganze LKW-Zahlen und uebertraegt den Rest
    chronologisch (Tag 0..6, Schicht 0..4) auf die naechste aktive Schicht.
    """
    W_woche = M_w.sum()
    if W_woche == 0:
        return np.zeros_like(M_w, dtype=int)

    L = np.zeros((7, 5), dtype=int)
    carry = 0.0

    for j in range(7):
        for i in range(5):
            if M_w[j, i] == 0:
                continue
            exakt = (n_woche / W_woche) * M_w[j, i] + carry
            gerundet = math.floor(exakt)
            carry = exakt - gerundet
            L[j, i] = gerundet

    return L


def gesamtformel(n_jahr: int, v_m: float, V_jahr: float,
                 u_w: float, U_monat: float,
                 m_wji: float, W_woche: float) -> float:
    """Kombinierte Gesamtformel: l_{m,w,j,i}"""
    return n_jahr * (v_m / V_jahr) * (u_w / U_monat) * (m_wji / W_woche)
