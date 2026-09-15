# Anhang B — Simulationsdaten

**Ergebnisspannen der Modellierung torbedingter Querlüftung in Logistikhallen**
*Modellähnlichkeit unter isothermen und betrieblichen Randbedingungen*

Masterarbeit (M.Eng.) von Vera Kohler
Technische Hochschule Augsburg, Fakultät für Architektur und Bauwesen, 2026

---

Dieses Repository enthält die Eingabedateien, Ergebnisse und Auswertungen der in der Arbeit
beschriebenen Simulationen. Es dient dem Nachvollzug der in den Kapiteln 4 bis 6 berichteten
Zahlen; es ist kein lauffähiges Softwarepaket.

---

## 1 Verzeichnisstruktur

### `01_Logistiksimulation` — 52 Dateien

Erzeugung der Toröffnungszeiten aus einer Crossdocking-Simulation. Grundlage der
Betriebsannahme in Kapitel 4.

| Ordner | Dateien | Inhalt |
|---|---|---|
| `01_Quellcode` | 34 | Python-Quellcode. `crossdocking_simulation/` (16 Module) erzeugt Ankunfts- und Abfahrtszeiten, Verweildauern und Bestandsfortschreibung; `gate_scheduling/` (11 Module, 6 Tests) weist die Ereignisse den sechs Toren zu und schreibt die EnergyPlus-Schedules; `main.py` steuert die Pipeline. |
| `02_Eingabedaten` | 6 | Konfiguration und Zwischenergebnisse der Pipeline im JSON-Format (`beispiel_config.json`, `ergebnisse.json`, `ergebnis_zeitachse.json`, `ergebnis_distanz.json`, `ergebnis_warenausgang.json`, `synthese_graph.json`). |
| `03_Plots` | 8 | Abbildungen zur Torzuordnung, zum Zustandsmodell, zur Rückvalidierung der Schedules und zur Gleichzeitigkeit geöffneter Tore. |
| `04_Dokumentation` | 4 | `Syntheseschritt.md` — mathematische Beschreibung des Simulationsmodells; `Dokumentation_Tor_Schedule_Erweiterung.docx` — Erzeugung der Schedules; `konfliktbericht_20260811.csv` — Protokoll der Konfliktauflösung des verwendeten Laufs; `Oeffnungsfaelle.csv` — die 64 möglichen Zustände aus sechs Toren. |

### `02_CFD-Simulation` — 35 Dateien

Auswertung und Setup-Dokumentation der CFD-Rechnungen. Die Strömungsfelder selbst
(rund 4 GB Rohdaten) sind nicht enthalten.

| Ordner | Dateien | Inhalt |
|---|---|---|
| `01_cp-Auswertung` | 5 | `cp_gate_extraction.csv` — extrahierte Druckbeiwerte und Volumenströme je Fall über fünf Auswertefenster (A–E) sowie sechs Wandabstände für Fenster C. `Skripte/` enthält die vier Python-Skripte, mit denen diese Tabelle aus den Strömungsfeldern erzeugt wurde. |
| `02_Modellkonfiguration` | 6 | Modellkonfiguration je Fall im JSON-Format (Geometrie, Randbedingungen, Öffnungen). |
| `03_Netz_Diskretisierung` | 23 | `01_Netzdefinition` — meshDict und Randflächendefinition; `02_Diskretisierung` — controlDict, fvSchemes, fvSolution, turbulenceProperties sowie das Berichtsblatt zum numerischen Modell; `03_Netzpruefung` — sechs `checkMesh`-Protokolle und die Kennwerttabelle mit Gegenüberstellung der Grenzwerte; `04_Kennzahlen` — Zellzahlen aus der Gebietszerlegung. |
| `Modellbenennung.txt` | 1 | Zuordnung der Varianten 1 bis 6 der Arbeit zu den Fallbezeichnungen der CFD (`case1`, `case3`, `case4`, `case5`, `case35`, `case45`). |

### `03_Isotherme_Simulation_Kap5` — 96 Dateien

Isotherme Verifikation der vier Lüftungsmodelle gegen die Handrechnung. Kapitel 5.

| Ordner | Dateien | Inhalt |
|---|---|---|
| `Berechnungen_isotherme_Simulation.xlsx` | 1 | Handrechnung und Gegenüberstellung Simulation/Handrechnung, blattweise nach den Abschnitten von Kapitel 5 gegliedert. |
| `01_Generator` | 2 | `make_isotherm_varianten.py` erzeugt die 30 IDF aus einer gemeinsamen Vorlage; `run_alle.bat` startet die Läufe. |
| `02_IDF` | 30 | EnergyPlus-Eingabedateien: je sechs Varianten für die vier Modellansätze `ZoneVentilation:DesignFlowRate` in den Koeffizientensätzen DEFAULT, BLAST und DOE-2, für `ZoneVentilation:WindandStackOpenArea` (WSOA) und für das `AirflowNetwork` (AFN). |
| `03_Wetterdaten` | 2 | Zwei konstruierte isotherme Wetterdateien für die Anströmrichtungen 157,5° und 247,5°. |
| `04_Ergebnisse_CSV` | 30 | Ergebnisreihen der 30 Läufe. |
| `05_Windprofil_Cw` | 31 | Vorstudien: `02_Windprofil` prüft das Windprofil in EnergyPlus und belegt die Bezugsgeschwindigkeit; `03_Cw_Tests` untersucht die Behandlung des Windbeiwerts bei schräger Anströmung; dazu Generator und zwei Wetterdateien für den CFD-Vergleich. |

### `04_Jahressimulation_Kap6` — 17 Dateien

Übertragung in die Heizperiode. Kapitel 6.

| Ordner | Dateien | Inhalt |
|---|---|---|
| `Auswertung_Jahressimulation.xlsx` | 1 | Auswertung nach den Abschnitten 6.1 bis 6.4: Torbetrieb, Luftwechsel, Heizwärmebedarf, Dauerlinie, Spitzenlasten und Formdistanz. |
| `01_Generator` | 1 | `make_heizperiode.py` erzeugt die Jahres-IDF aus den isothermen Vorlagen. |
| `02_IDF` | 12 | Fünf Modellansätze plus Crackkalibrierung, jeweils in Grundausrichtung und um 90° gedreht (`_rot90`). |
| `03_Schedules` | 1 | `alle_tore.idf` — die Toröffnungs-Schedules in Minutenauflösung für alle sechs Tore. |
| `04_Ergebnisse_CSV` | 2 | Stundenwerte der Heizperiode, getrennt nach Torachse Süd/Nord und Ost/West. |

---

## 2 Software

| | |
|---|---|
| Gebäudesimulation | EnergyPlus 25.2.0-cf7368216c |
| CFD, Rechnungen | OpenFOAM (ESI), Angabe im Berichtsblatt: v2412, Solver `buoyantBoussinesqSimpleFoam`, k–ω-SST |
| Auswertung | Python 3, Microsoft Excel |

---

## 3 Hinweise

**Wetterdatei der Jahressimulation.** Die Jahressimulationen verwenden
`DEU_Munich.108660_IWEC.epw`. Diese Datei ist hier nicht enthalten, weil die
ASHRAE-Lizenz die Weitergabe an Dritte untersagt. Sie ist über die Wetterdatenbank von
EnergyPlus frei beziehbar; die Quelle ist in der Arbeit angegeben. Die in den isothermen
Rechnungen verwendeten Wetterdateien sind eigene Konstruktionen und liegen bei.

**Stand der Schedules.** `alle_tore.idf` ist der Lauf vom 11.08.2026 mit den
Öffnungsversätzen −2 / 0 / +45 / +50 Minuten relativ zur Andockung. Alle Ergebnisse der
Jahressimulation beruhen auf diesem Stand.

**Rohdaten.** Die CFD-Strömungsfelder und die EnergyPlus-Ausgaben in Minutenauflösung sind
wegen ihres Umfangs nicht archiviert. Nachvollziehbar sind die daraus abgeleiteten
Kenngrößen: `cp_gate_extraction.csv` für die CFD, die Stundenwert-CSV und die
Auswertungs-Excel für die Jahressimulation.

**Herkunft der CFD-Rechnungen.** Die Strömungssimulationen wurden mit FlowDesk gerechnet.

---

## 4 Nutzungsrechte

Dieses Repository dient dem Nachweis und der Nachvollziehbarkeit der Masterarbeit. Es steht
keine Lizenz zur Nachnutzung; alle Rechte verbleiben bei der Autorin. Für eine
Weiterverwendung der Daten bitte Kontakt aufnehmen.
