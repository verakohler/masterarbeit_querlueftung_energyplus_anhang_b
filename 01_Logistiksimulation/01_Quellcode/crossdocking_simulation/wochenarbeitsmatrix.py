import numpy as np


def erstelle_binaere_matrix(arbeitstage: list[int], arbeitsschichten: list[int]) -> np.ndarray:
    """Erstellt die binaere 7x5 Wochenarbeitsmatrix M."""
    M = np.zeros((7, 5), dtype=int)
    for tag in arbeitstage:
        for schicht in arbeitsschichten:
            M[tag, schicht] = 1
    return M


def gewichte_matrix(M: np.ndarray, gewichte: np.ndarray) -> np.ndarray:
    """Elementweise Multiplikation: M' = M * w (Broadcasting)."""
    return M * gewichte  # Broadcasting: (7,5) * (5,) -> (7,5)
