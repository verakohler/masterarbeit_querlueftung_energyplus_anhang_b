from dataclasses import dataclass


@dataclass
class HallenConfig:
    laenge: float                 # Hallenlaenge in m
    breite: float                 # Hallenbreite in m
    prozent_umschlag: float       # Prozentualer Anteil Umschlagsflaeche (0-1)
    anzahl_tore: int              # Anzahl Be-/Entladetore
    be_entladezeit_min: float     # Be-/Entladezeit pro LKW in Minuten
    delta_s: int = 3              # Phasenverschiebung in Schichten
    spiegelung: bool = False      # Tagesvektor spiegeln statt Phasenverschiebung
    paletten_pro_lkw: int = 33    # Standardpaletten pro LKW
    paletten_stellplatz_m2: float = 0.96  # Flaeche einer Standardpalette (0.8m x 1.2m)
    tages_arbeitszeit_min: float = 1440.0  # Arbeitstag in Minuten (24h default)

    @property
    def flaeche(self) -> float:
        return self.laenge * self.breite

    @property
    def kapazitaet_m2(self) -> float:
        return self.flaeche * self.prozent_umschlag

    @property
    def kapazitaet_paletten(self) -> float:
        return self.kapazitaet_m2 / self.paletten_stellplatz_m2

    @property
    def schicht_dauer_min(self) -> float:
        return self.tages_arbeitszeit_min / 5.0
