import numpy as np

SCHICHTEN = ["Morgen", "Mittag", "Nachmittag", "Abends", "Nachts"]
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONATE = [
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

AUSLASTUNGSSTUFEN = {
    "Keine": 1,
    "niedrig": 2,
    "Mittel": 3,
    "Hoch": 4,
    "sehr Hoch": 5,
}


def standard_schicht_gewichte() -> np.ndarray:
    return np.array([1, 2, 3, 4, 5], dtype=float)
