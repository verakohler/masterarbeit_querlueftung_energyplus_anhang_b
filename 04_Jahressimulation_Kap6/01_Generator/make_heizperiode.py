# -*- coding: utf-8 -*-
"""
Generator fuer die EnergyPlus-Eingabedateien der Jahressimulation
(Masterarbeit M13, Kapitel 6 - Uebertragung in die Heizperiode).

Geometrie und Huelle wie Variante 1 aus Kapitel 5 (Hallenstueck 15 x 60 x 12 m),
aber alle sechs Tore schedulegesteuert, Grundinfiltration, interne Gewinne und
Speichermasse ergaenzt, reale IWEC-Wetterdatei, Jahreslauf bei Timestep 60.

Drei Stufen, in dieser Reihenfolge auszufuehren:

  Stufe 1   python make_heizperiode.py --modus crack
            -> AFN_E+_Crackkalibrierung.idf
            AFN mit dauerhaft geschlossenen Toren, nur Huellenleckage.
            Liefert den Skalierungsfaktor fuer den Crack-Koeffizienten.

  Stufe 2   python make_heizperiode.py --modus afn --crack-c <C>
            -> AFN_E+_Jahr.idf   (mit --pilot zusaetzlich AFN_E+_Pilot.idf)
            Der Referenzlauf. Liefert Q_AFN je Zeitschritt fuer die
            Kalibrierung der DFR-Objekte.

  Stufe 3   python make_heizperiode.py --modus final --crack-c <C> --qdes <Q>
            -> WSOA_Jahr.idf, DFR_DEFAULT_Jahr.idf,
               DFR_BLAST_Jahr.idf, DFR_DOE-2_Jahr.idf

Erzeugt ausserdem README_Heizperiode.md mit allen Setzungen.

Vorgehen und Begruendungen: claude/Arbeitsplan_Kapitel6_Heizperiode.md
"""

import argparse
import os
import re

EPLUS_VERSION = "25.2"

# ------------------------------------------------------------------ Geometrie
LX, LY, LZ = 15.0, 60.0, 12.0
A_BODEN = LX * LY                      # 900 m2
V_HALLE = LX * LY * LZ                 # 10800 m3
A_TOR = 9.0                            # 3 x 3 m
GATE_Z0, GATE_Z1 = 0.0, 3.0

GATES = {
    1: dict(wall="AW_Sued", x0=1.0, x1=4.0, azimut=180.0, sched="AN_1_Tor_Schedule"),
    2: dict(wall="AW_Sued", x0=6.0, x1=9.0, azimut=180.0, sched="AN_2_Tor_Schedule"),
    3: dict(wall="AW_Sued", x0=11.0, x1=14.0, azimut=180.0, sched="AN_3_Tor_Schedule"),
    4: dict(wall="AW_Nord", x0=1.0, x1=4.0, azimut=0.0, sched="AB_1_Tor_Schedule"),
    5: dict(wall="AW_Nord", x0=6.0, x1=9.0, azimut=0.0, sched="AB_2_Tor_Schedule"),
    6: dict(wall="AW_Nord", x0=11.0, x1=14.0, azimut=0.0, sched="AB_3_Tor_Schedule"),
}

# --------------------------------------------------------------- Betriebsfall
EPW = "DEU_Munich.108660_IWEC.epw"
TIMESTEP = 60                          # Minutenaufloesung, VORBEHALT 1 der Schedules
TIMESTEP_PILOT = 60
TIMESTEP_CRACK = 60                    # ohne Torereignisse genuegt 15 min
T_SOLL = 17.0                          # konstant, keine Nachtabsenkung
T_ERDREICH = 15.0                      # = T_SOLL - 2 K, Empfehlung der Input Output Reference

# Heizperiode fuer die Auswertung (der Lauf selbst geht ueber das ganze Jahr)
HEIZPERIODE = "Oktober bis April, 5088 h"

# --------------------------------- Uebernommene Kennwerte aus dem Referenzmodell
# Referenzhalle: 67,20 m2 Grundflaeche, 4,80 m Hoehe, 322,56 m3
# (AFN_paper_Vorlage.idf, Zone 'EXT-Story 1 Core Zone')
A_REF = 67.2
SKALIERUNG = A_BODEN / A_REF           # = 13.3929, flaechenbezogen

INFILTRATION_ACH = 0.025               # bereits volumenbezogen, NICHT skalieren
P_INTERN_REF = 700.0                   # W
A_METALL_REF = 120.0                   # m2, Obj03_Metal surface 5 mm
A_HOLZ_REF = 60.0                      # m2, Obj20_G06 50mm wood

P_INTERN = P_INTERN_REF * SKALIERUNG           # 9375.0 W
A_METALL = A_METALL_REF * SKALIERUNG           # 1607.14 m2
A_HOLZ = A_HOLZ_REF * SKALIERUNG               # 803.57 m2

# ------------------------------------------------------------ Andockzustand
# Schedule-Wert des angedockten LKW aus gate_scheduling 0.1.0
OF_ANDOCK = 0.048
# Umlaufende Dichtungsleckage, abgebildet als flaechengleicher waagerechter
# Spalt in Toroeffnungsmitte: Width Factor 1, Height Factor 0,048,
# Start Height so, dass der Spalt symmetrisch zur Mitte liegt.
# -> Auftriebsterm neutral, wie bei einer umlaufenden Leckage.
WF_ANDOCK = 1.0
HF_ANDOCK = OF_ANDOCK
SH_ANDOCK = (1.0 - HF_ANDOCK) / 2.0            # = 0.476
CD_TOR = 0.62                                   # Setzung aus Kapitel 4.2.3

# ------------------------------------------------------------ Huellenleckage
# Startwert des Crack-Koeffizienten. Die Kalibrierung erfolgt iterativ
# (Sekantenverfahren, 2 bis 3 Laeufe zu je rund 6 s). Eine reine Skalierung
# genuegt NICHT: die geschlossenen Tore tragen ueber das Feld "Air Mass Flow
# Coefficient When Opening is Closed" des DetailedOpening eine feste
# Parallelleckage, die nicht mitskaliert. Nachgerechnet: der Ansatz
# C = C0 * 0,025/ACH_0 verfehlt das Ziel um 9,8 %.
CRACK_C_START = 0.036                  # kg/s bei 1 Pa, aus AFN_paper_Vorlage.idf
CRACK_N = 0.65
CRACK_FLAECHEN = ["AW_Sued", "AW_Nord", "Dach"]

# --------------------------------- Koeffizientensaetze ZoneVentilation:DesignFlowRate
DFR_SETS = {
    "DEFAULT": dict(A=1.0, B=0.0, C=0.0, D=0.0,
                    quelle="Programmvoreinstellung von EnergyPlus"),
    "BLAST": dict(A=0.606, B=0.03636, C=0.1177, D=0.0,
                  quelle="BLAST-Koeffizientensatz, Input Output Reference"),
    "DOE-2": dict(A=0.0, B=0.0, C=0.224, D=0.0,
                  quelle="DOE-2-Koeffizientensatz, Input Output Reference"),
}

SCHEDULE_QUELLE = os.path.join("..", "..", "schedules", "alle_tore.idf")

# Gebaeudedrehung. 0 = Tore in Sued- und Nordfassade (Basisfall),
# 90 = Tore in Ost- und Westfassade.
# ACHTUNG: "Building, North Axis" dreht die Flaechenazimute, aber NICHT
#   - "Effective Angle" in ZoneVentilation:WindandStackOpenArea und
#   - "Azimuth Angle of Long Axis of Building" in AirflowNetwork:SimulationControl.
# Beide werden hier explizit mitgedreht. Nachgewiesen wird die Drehung am
# eplusout.eio (Azimut je Aussenflaeche).
DREHUNG = 0.0


def drehen(az):
    return (az + DREHUNG) % 360.0


# =============================================================== IDF-Bausteine
def fields(objtype, rows):
    out = [objtype + ","]
    n = len(rows)
    for i, (val, cmt) in enumerate(rows):
        sep = ";" if i == n - 1 else ","
        val = "" if val is None else str(val)
        out.append("    %-24s %s" % (val + sep, "!- " + cmt))
    return "\n".join(out) + "\n\n"


def num(x, nd=6):
    s = ("%." + str(nd) + "f") % x
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def block(title):
    return "\n!- " + "=" * 76 + "\n!-   " + title + "\n!- " + "=" * 76 + "\n\n"


def surface(name, stype, constr, zone, bc, bcobj, sun, wind, vfg, verts):
    rows = [(name, "Name"), (stype, "Surface Type"), (constr, "Construction Name"),
            (zone, "Zone Name"), (None, "Space Name"), (bc, "Outside Boundary Condition"),
            (bcobj, "Outside Boundary Condition Object"), (sun, "Sun Exposure"),
            (wind, "Wind Exposure"), (num(vfg, 2), "View Factor to Ground"),
            (len(verts), "Number of Vertices")]
    for i, (x, y, z) in enumerate(verts, 1):
        rows += [(num(x, 5), "Vertex %d X-coordinate {m}" % i),
                 (num(y, 5), "Vertex %d Y-coordinate {m}" % i),
                 (num(z, 5), "Vertex %d Z-coordinate {m}" % i)]
    return fields("BuildingSurface:Detailed", rows)


def fenestration(name, stype, constr, base, bcobj, verts):
    rows = [(name, "Name"), (stype, "Surface Type"), (constr, "Construction Name"),
            (base, "Building Surface Name"), (bcobj, "Outside Boundary Condition Object"),
            (None, "View Factor to Ground"), (None, "Frame and Divider Name"),
            (None, "Multiplier"), (len(verts), "Number of Vertices")]
    for i, (x, y, z) in enumerate(verts, 1):
        rows += [(num(x, 5), "Vertex %d X-coordinate {m}" % i),
                 (num(y, 5), "Vertex %d Y-coordinate {m}" % i),
                 (num(z, 5), "Vertex %d Z-coordinate {m}" % i)]
    return fields("FenestrationSurface:Detailed", rows)


# ==================================================================== Kopf
def kopf(dateiname, modell, extra, timestep, runperiod_text):
    L = ["! " + "=" * 78,
         "! %s" % dateiname,
         "! " + "=" * 78,
         "! Modellansatz      : %s" % modell,
         "! Geometrie         : Hallenstueck %s x %s x %s m, A = %s m2, V = %s m3"
         % (num(LX, 0), num(LY, 0), num(LZ, 0), num(A_BODEN, 0), num(V_HALLE, 0)),
         "! Tore              : alle sechs, schedulegesteuert",
         "! Gebaeudedrehung   : %s Grad (Tore in %s)" % (
             num(DREHUNG, 1),
             "Sued/Nord" if DREHUNG == 0 else "Ost/West" if DREHUNG == 90 else "gedreht"),
         "!                     Tor 1-3 (AW_Sued) <- AN_1..3, Tor 4-6 (AW_Nord) <- AB_1..3",
         "! Wetterdatei       : %s (Stundenwerte, unveraendert)" % EPW,
         "! Windprofil        : EnergyPlus-Standard (Terrain Country)",
         "! Zeitraum          : %s" % runperiod_text,
         "! Timestep          : %d pro Stunde" % timestep,
         "! Sollwert          : %s Grad C konstant, keine Nachtabsenkung" % num(T_SOLL, 1),
         "! Auswertung        : %s" % HEIZPERIODE,
         "! EnergyPlus        : %s" % EPLUS_VERSION,
         "!",
         "! Erzeugt von make_heizperiode.py. Setzungen siehe README_Heizperiode.md.",
         "!"]
    L += ["! " + z for z in extra]
    L += ["! " + "=" * 78, ""]
    return "\n".join(L) + "\n"


# ==================================================================== Basis
def basis(timestep, runperiod, schedules_txt):
    """runperiod: (name, bm, bd, em, ed, wochentag)"""
    s = []
    s.append(block("VERSION, SIMULATIONCONTROL, BUILDING, TIMESTEP"))
    s.append(fields("Version", [(EPLUS_VERSION, "Version Identifier")]))
    s.append(fields("SimulationControl", [
        ("No", "Do Zone Sizing Calculation"), ("No", "Do System Sizing Calculation"),
        ("No", "Do Plant Sizing Calculation"), ("No", "Run Simulation for Sizing Periods"),
        ("Yes", "Run Simulation for Weather File Run Periods"),
        (None, "Do HVAC Sizing Simulation for Sizing Periods"),
        (None, "Maximum Number of HVAC Sizing Simulation Passes")]))
    s.append("!- Die Anstroemrichtung kommt aus der unveraenderten Wetterdatei, nicht\n"
             "!- mehr aus einer konstruierten EPW wie in Kapitel 5. Die Gebaeudedrehung\n"
             "!- betraegt %s Grad: Toroeffnungen in %s.\n"
             "!- Mitgedreht sind zusaetzlich Effective Angle (WSOA) und Azimuth Angle of\n"
             "!- Long Axis (AFN) - beide folgen North Axis nicht selbsttaetig.\n"
             % (num(DREHUNG, 1),
                "Sued- und Nordfassade" if DREHUNG == 0 else
                "Ost- und Westfassade" if DREHUNG == 90 else "gedrehten Fassaden"))
    s.append(fields("Building", [
        ("Halle_15x60x12", "Name"), (num(DREHUNG, 1), "North Axis {deg}"),
        ("Country", "Terrain"),
        (None, "Loads Convergence Tolerance Value {W}"),
        (None, "Temperature Convergence Tolerance Value {deltaC}"),
        (None, "Solar Distribution"), (None, "Maximum Number of Warmup Days"),
        ("6", "Minimum Number of Warmup Days")]))
    s.append(fields("Timestep", [(str(timestep), "Number of Timesteps per Hour")]))

    s.append(block("SITE"))
    s.append(fields("Site:Location", [
        ("Muenchen_Bayern_DEU", "Name"), ("48.13", "Latitude {deg}"),
        ("11.70", "Longitude {deg}"), ("1", "Time Zone {hr}"), ("529", "Elevation {m}")]))
    s.append("!- Kein Site:WeatherStation und kein Site:HeightVariation. Das flache\n"
             "!- Windprofil aus Kapitel 5 war eine Verifikationsmassnahme, damit\n"
             "!- Handrechnung, ZoneVentilation, WSOA und die AFN-External-Nodes dieselbe\n"
             "!- Geschwindigkeit sehen. In Kapitel 6 gibt es keine Handrechnung mehr; ein\n"
             "!- flaches Profil wuerde die Bezugshoehen der drei Modellansaetze kuenstlich\n"
             "!- gleichsetzen und damit einen Teil der Zwischen-Spanne wegdefinieren.\n")
    s.append("!- Erdreichtemperatur = Sollwert minus 2 K = %s Grad C, konstant ueber alle\n"
             "!- zwoelf Monate. Quelle: EnergyPlus Input Output Reference, Abschnitt\n"
             "!- Site:GroundTemperature:BuildingSurface: 'When considering a typical\n"
             "!- commercial building in the USA, a reasonable default value is 2 C less\n"
             "!- than the average indoor space temperature if the user elects to not run\n"
             "!- either the Slab or Basement program.' Die dort ebenfalls genannten\n"
             "!- ungestoerten Bodentemperaturen aus der Wetterdatei sind laut derselben\n"
             "!- Quelle fuer Gebaeudeverluste ausdruecklich nicht geeignet.\n"
             "!- Der Bodenanteil ist in allen fuenf Modellen identisch und faellt in der\n"
             "!- Differenz zwischen den Modellen heraus, nicht aber im Absolutwert.\n"
             % num(T_ERDREICH, 1))
    s.append(fields("Site:GroundTemperature:BuildingSurface",
                    [(num(T_ERDREICH, 1), "%s Ground Temperature {C}" % m) for m in
                     ["January", "February", "March", "April", "May", "June", "July",
                      "August", "September", "October", "November", "December"]]))

    s.append(block("RUNPERIOD"))
    nm, bm, bd, em, ed, wd = runperiod
    s.append(fields("RunPeriod", [
        (nm, "Name"), (str(bm), "Begin Month"), (str(bd), "Begin Day of Month"),
        (None, "Begin Year"), (str(em), "End Month"), (str(ed), "End Day of Month"),
        (None, "End Year"), (wd, "Day of Week for Start Day"),
        ("No", "Use Weather File Holidays and Special Days"),
        ("No", "Use Weather File Daylight Saving Period"),
        ("No", "Apply Weekend Holiday Rule"),
        ("Yes", "Use Weather File Rain Indicators"),
        ("Yes", "Use Weather File Snow Indicators")]))

    s.append(block("SCHEDULES"))
    s.append(fields("ScheduleTypeLimits", [
        ("Fractional", "Name"), ("0", "Lower Limit Value"), ("1", "Upper Limit Value"),
        ("Continuous", "Numeric Type")]))
    s.append(fields("ScheduleTypeLimits", [
        ("Temperature", "Name"), ("-60", "Lower Limit Value"), ("200", "Upper Limit Value"),
        ("Continuous", "Numeric Type"), ("Temperature", "Unit Type")]))
    s.append(fields("ScheduleTypeLimits", [
        ("Control Type", "Name"), ("0", "Lower Limit Value"), ("4", "Upper Limit Value"),
        ("Discrete", "Numeric Type"), ("Control", "Unit Type")]))
    s.append(fields("Schedule:Constant", [
        ("Sch_Immer_an", "Name"), ("Fractional", "Schedule Type Limits Name"),
        ("1.0", "Hourly Value")]))
    s.append("!- Heizsollwert konstant, keine Nachtabsenkung. Begruendung: eine Absenkung\n"
             "!- legt die Aufheizspitze auf den Schichtbeginn und damit genau auf den\n"
             "!- Beginn des Torbetriebs. Spitzenlast (6.4.2) und Lastgradient (6.4.3)\n"
             "!- wuerden dann eine Ueberlagerung aus Anlagenfahrweise und Torlueftung\n"
             "!- messen statt der Torlueftung allein.\n")
    s.append(fields("Schedule:Constant", [
        ("Sch_T_soll", "Name"), ("Temperature", "Schedule Type Limits Name"),
        (num(T_SOLL, 1), "Hourly Value")]))
    s.append(fields("Schedule:Constant", [
        ("Sch_Regelungsart", "Name"), ("Control Type", "Schedule Type Limits Name"),
        ("1", "Hourly Value")]))
    s.append("!- Nutzungsprofil der internen Gewinne, uebernommen aus AFN_paper_Vorlage.idf\n"
             "!- (Schedule 'Geraete': Werktags 07:00 bis 16:00).\n")
    s.append("Schedule:Compact,\n"
             "    Sch_Geraete,             !- Name\n"
             "    Fractional,              !- Schedule Type Limits Name\n"
             "    Through: 12/31,\n"
             "    For: Weekdays,\n"
             "    Until: 07:00,0.0,\n"
             "    Until: 16:00,1.0,\n"
             "    Until: 24:00,0.0,\n"
             "    For: AllOtherDays,\n"
             "    Until: 24:00,0.0;\n\n")
    s.append(schedules_txt)

    s.append(block("MATERIALS AND CONSTRUCTIONS"))
    for name, rough, d, lam, dens, cp in [
            ("AW_IW_Obj30_Porenbeton", "MediumRough", 0.2032, 0.5, 464, 880),
            ("D_Obj14_Gipskarton", "MediumSmooth", 0.0159, 0.16, 800, 1090),
            ("B_Obj43_Beton", "MediumRough", 0.2032, 1.95, 2240, 900),
            ("AW_Obj91_Waermedaemmung", "Rough", 0.025, 0.0245, 24, 1590),
            ("D_Obj80_Daemmung", "MediumRough", 0.05, 0.036, 140, 960),
            ("D_Obj84_XPS", "MediumSmooth", 0.025, 0.029, 29, 1210),
            ("D_Obj8_Built-up roofing", "Rough", 0.0095, 0.16, 1120, 1460),
            # Speichermasse, Werte aus AFN_paper_Vorlage.idf
            ("Obj03_Metal surface", "Smooth", 0.005, 15.0, 7824, 500),
            ("Obj20_G06 50mm wood", "MediumSmooth", 0.0508, 0.15, 608, 1630)]:
        s.append(fields("Material", [
            (name, "Name"), (rough, "Roughness"), (num(d, 4), "Thickness {m}"),
            (num(lam, 4), "Conductivity {W/m-K}"), (num(dens, 1), "Density {kg/m3}"),
            (num(cp, 1), "Specific Heat {J/kg-K}")]))
    s.append(fields("WindowMaterial:SimpleGlazingSystem", [
        ("Glazing_Tor", "Name"), ("1.8", "U-Factor {W/m2-K}"),
        ("0.0001", "Solar Heat Gain Coefficient")]))
    for name, layers in [
            ("Aussenwand", ["AW_Obj91_Waermedaemmung", "AW_IW_Obj30_Porenbeton"]),
            ("Innenwand", ["AW_IW_Obj30_Porenbeton"]),
            ("Dach", ["D_Obj8_Built-up roofing", "D_Obj80_Daemmung", "D_Obj14_Gipskarton"]),
            ("Boden", ["D_Obj84_XPS", "B_Obj43_Beton"]),
            ("Tor", ["Glazing_Tor"]),
            ("Metall_IM", ["Obj03_Metal surface"]),
            ("Holz_IM", ["Obj20_G06 50mm wood"])]:
        rows = [(name, "Name"), (layers[0], "Outside Layer")]
        for i, l in enumerate(layers[1:], 2):
            rows.append((l, "Layer %d" % i))
        s.append(fields("Construction", rows))

    s.append(block("GLOBALGEOMETRYRULES"))
    s.append(fields("GlobalGeometryRules", [
        ("UpperLeftCorner", "Starting Vertex Position"),
        ("Counterclockwise", "Vertex Entry Direction"),
        ("Relative", "Coordinate System"),
        ("Relative", "Daylighting Reference Point Coordinate System"),
        ("Relative", "Rectangular Surface Coordinate System")]))

    s.append(block("ZONE"))
    s.append(fields("Zone", [
        ("Zone_Halle", "Name"), ("0", "Direction of Relative North {deg}"),
        ("0", "X Origin {m}"), ("0", "Y Origin {m}"), ("0", "Z Origin {m}"),
        (None, "Type"), ("1", "Multiplier"), (num(LZ, 1), "Ceiling Height {m}"),
        (num(V_HALLE, 1), "Volume {m3}"), (num(A_BODEN, 1), "Floor Area {m2}"),
        (None, "Zone Inside Convection Algorithm"),
        (None, "Zone Outside Convection Algorithm"),
        ("Yes", "Part of Total Floor Area")]))
    return "".join(s)


# =============================================================== Geometrie
def geometrie():
    s = [block("BUILDINGSURFACE:DETAILED")]
    s.append(surface("Boden", "Floor", "Boden", "Zone_Halle", "Ground", None,
                     "NoSun", "NoWind", 1.0,
                     [(0, 0, 0), (0, LY, 0), (LX, LY, 0), (LX, 0, 0)]))
    s.append(surface("Dach", "Roof", "Dach", "Zone_Halle", "Outdoors", None,
                     "SunExposed", "WindExposed", 0.0,
                     [(LX, 0, LZ), (LX, LY, LZ), (0, LY, LZ), (0, 0, LZ)]))
    s.append(surface("IW_West", "Wall", "Innenwand", "Zone_Halle", "Adiabatic", None,
                     "NoSun", "NoWind", 0.0,
                     [(0, 0, LZ), (0, LY, LZ), (0, LY, 0), (0, 0, 0)]))
    s.append(surface("IW_Ost", "Wall", "Innenwand", "Zone_Halle", "Adiabatic", None,
                     "NoSun", "NoWind", 0.0,
                     [(LX, LY, LZ), (LX, 0, LZ), (LX, 0, 0), (LX, LY, 0)]))
    s.append(surface("AW_Sued", "Wall", "Aussenwand", "Zone_Halle", "Outdoors", None,
                     "SunExposed", "WindExposed", 0.5,
                     [(LX, 0, LZ), (0, 0, LZ), (0, 0, 0), (LX, 0, 0)]))
    s.append(surface("AW_Nord", "Wall", "Aussenwand", "Zone_Halle", "Outdoors", None,
                     "SunExposed", "WindExposed", 0.5,
                     [(0, LY, LZ), (LX, LY, LZ), (LX, LY, 0), (0, LY, 0)]))

    s.append(block("FENESTRATIONSURFACE:DETAILED  (TORE)"))
    s.append("!- Alle sechs Tore sind offen im Sinne des Modells; wie weit, bestimmt\n"
             "!- der jeweilige Schedule. Die Warnung CHKSBS 'Base surface does not\n"
             "!- surround subsurface' entsteht dadurch, dass die Tore mit z = 0 exakt\n"
             "!- auf der Unterkante der Basisflaeche liegen. Nach dem Lauf ist im\n"
             "!- Tabellenbericht 'Envelope Summary' zu pruefen, ob die Nettoflaeche von\n"
             "!- AW_Sued und AW_Nord jeweils 153,00 m2 betraegt (180,00 - 3 x 9,00).\n"
             "!- Trifft das zu, ist die Warnung folgenlos.\n")
    for g in sorted(GATES):
        info = GATES[g]
        if info["wall"] == "AW_Sued":
            verts = [(info["x1"], 0, GATE_Z1), (info["x0"], 0, GATE_Z1),
                     (info["x0"], 0, GATE_Z0), (info["x1"], 0, GATE_Z0)]
        else:
            verts = [(info["x0"], LY, GATE_Z1), (info["x1"], LY, GATE_Z1),
                     (info["x1"], LY, GATE_Z0), (info["x0"], LY, GATE_Z0)]
        s.append("!- Tor %d, %s, x = %s bis %s m, z = %s bis %s m, A = %s m2, Schedule %s\n" % (
            g, info["wall"], num(info["x0"], 2), num(info["x1"], 2),
            num(GATE_Z0, 2), num(GATE_Z1, 2), num(A_TOR, 2), info["sched"]))
        s.append(fenestration("gate %d" % g, "Window", "Tor", info["wall"], None, verts))
    return "".join(s)


# ================================================================== Anlage
def anlage():
    s = [block("THERMOSTAT UND IDEAL LOADS")]
    s.append("!- Reiner Heizfall: SingleHeating, Regelungsart 1. Kuehlung ist nach 4.1.1\n"
             "!- ausdruecklich ausgeschlossen.\n")
    s.append(fields("ZoneControl:Thermostat", [
        ("Thermostat", "Name"), ("Zone_Halle", "Zone or ZoneList Name"),
        ("Sch_Regelungsart", "Control Type Schedule Name"),
        ("ThermostatSetpoint:SingleHeating", "Control 1 Object Type"),
        ("Sollwert_Heizen", "Control 1 Name")]))
    s.append(fields("ThermostatSetpoint:SingleHeating", [
        ("Sollwert_Heizen", "Name"), ("Sch_T_soll", "Setpoint Temperature Schedule Name")]))
    s.append("!- Heizleistung unbegrenzt (NoLimit). Eine leistungsbegrenzte Versorgung\n"
             "!- wuerde die Spanne von der Last in die Zonentemperatur verschieben; das\n"
             "!- ist als Ausblick in Kapitel 8 vermerkt, nicht Gegenstand dieser Arbeit.\n")
    s.append(fields("ZoneHVAC:IdealLoadsAirSystem", [
        ("IdealLoads", "Name"), (None, "Availability Schedule Name"),
        ("Inlet_Node", "Zone Supply Air Node Name"),
        (None, "Zone Exhaust Air Node Name"), (None, "System Inlet Air Node Name"),
        ("50", "Maximum Heating Supply Air Temperature {C}"),
        ("13", "Minimum Cooling Supply Air Temperature {C}"),
        ("0.0156", "Maximum Heating Supply Air Humidity Ratio {kgWater/kgDryAir}"),
        ("0.0077", "Minimum Cooling Supply Air Humidity Ratio {kgWater/kgDryAir}"),
        ("NoLimit", "Heating Limit"), (None, "Maximum Heating Air Flow Rate {m3/s}"),
        (None, "Maximum Sensible Heating Capacity {W}"),
        ("NoLimit", "Cooling Limit"), (None, "Maximum Cooling Air Flow Rate {m3/s}"),
        (None, "Maximum Total Cooling Capacity {W}"),
        (None, "Heating Availability Schedule Name"),
        (None, "Cooling Availability Schedule Name"),
        ("None", "Dehumidification Control Type"),
        (None, "Cooling Sensible Heat Ratio {dimensionless}"),
        ("None", "Humidification Control Type"),
        (None, "Design Specification Outdoor Air Object Name"),
        (None, "Outdoor Air Inlet Node Name"),
        ("None", "Demand Controlled Ventilation Type"),
        ("NoEconomizer", "Outdoor Air Economizer Type"),
        ("None", "Heat Recovery Type"),
        (None, "Sensible Heat Recovery Effectiveness {dimensionless}"),
        (None, "Latent Heat Recovery Effectiveness {dimensionless}")]))
    s.append(fields("ZoneHVAC:EquipmentList", [
        ("EquipmentList", "Name"), ("SequentialLoad", "Load Distribution Scheme"),
        ("ZoneHVAC:IdealLoadsAirSystem", "Zone Equipment 1 Object Type"),
        ("IdealLoads", "Zone Equipment 1 Name"),
        ("1", "Zone Equipment 1 Cooling Sequence"),
        ("1", "Zone Equipment 1 Heating or No-Load Sequence"),
        (None, "Zone Equipment 1 Sequential Cooling Fraction Schedule Name"),
        (None, "Zone Equipment 1 Sequential Heating Fraction Schedule Name")]))
    s.append(fields("ZoneHVAC:EquipmentConnections", [
        ("Zone_Halle", "Zone Name"), ("EquipmentList", "Zone Conditioning Equipment List Name"),
        ("Inlet_Node", "Zone Air Inlet Node or NodeList Name"),
        (None, "Zone Air Exhaust Node or NodeList Name"),
        ("Zone_Node", "Zone Air Node Name"),
        ("Return_Node", "Zone Return Air Node or NodeList Name")]))
    return "".join(s)


# ===================================================== Interne Lasten / Masse
def interne_lasten():
    s = [block("INTERNE GEWINNE UND SPEICHERMASSE")]
    s.append("!- Uebernommen aus dem Referenzmodell hinter Kohler et al. (2025)\n"
             "!- (Hausladen et al.), dort fuer eine Halle mit %s m2 Grundflaeche.\n"
             "!- Skaliert mit dem Verhaeltnis der Grundflaechen %s / %s = %s.\n"
             "!- ANNAHME: interne Gewinne und Speichermasse sind an die Nutzflaeche\n"
             "!- gebunden (Regal, Ware, Flurfoerderzeuge), nicht an das Luftvolumen.\n"
             "!- Die Referenzhalle ist 4,80 m hoch, diese Halle 12,00 m - eine\n"
             "!- volumenbezogene Skalierung ergaebe den Faktor 33,48 statt %s.\n" % (
                 num(A_REF, 2), num(A_BODEN, 0), num(A_REF, 2),
                 num(SKALIERUNG, 4), num(SKALIERUNG, 4)))
    s.append(fields("ElectricEquipment", [
        ("Interne_Gewinne_Geraete", "Name"),
        ("Zone_Halle", "Zone or ZoneList or Space or SpaceList Name"),
        ("Sch_Geraete", "Schedule Name"),
        ("EquipmentLevel", "Design Level Calculation Method"),
        (num(P_INTERN, 2), "Design Level {W}"),
        (None, "Watts per Floor Area {W/m2}"), (None, "Watts per Person {W/person}"),
        (None, "Fraction Latent"), (None, "Fraction Radiant"), (None, "Fraction Lost"),
        ("General", "End-Use Subcategory")]))
    s.append(fields("InternalMass", [
        ("Interne_Masse_Metall", "Name"), ("Metall_IM", "Construction Name"),
        ("Zone_Halle", "Zone or ZoneList Name"), (None, "Space or SpaceList Name"),
        (num(A_METALL, 2), "Surface Area {m2}")]))
    s.append(fields("InternalMass", [
        ("Interne_Masse_Holz", "Name"), ("Holz_IM", "Construction Name"),
        ("Zone_Halle", "Zone or ZoneList Name"), (None, "Space or SpaceList Name"),
        (num(A_HOLZ, 2), "Surface Area {m2}")]))
    return "".join(s)


def grundinfiltration_zoneobjekt(f_infil=1.0):
    """Nur fuer WSOA und DFR. Unter AFN wird ZoneInfiltration ignoriert.
    f_infil: Dichtekorrektur. EnergyPlus interpretiert Design Flow Rate und
    Air Changes per Hour als Volumenstrom bei STANDARDDICHTE, rechnet daraus
    einen Massenstrom und gibt ihn als Volumenstrom bei aktueller Dichte
    wieder aus. Bei 529 m Standorthoehe liegt der ausgegebene Volumenstrom
    rund 5 % ueber dem eingegebenen. Der Eingabewert wird deshalb durch
    f_infil geteilt, damit der AUSGEGEBENE Wert die Vorgabe trifft."""
    ach_in = INFILTRATION_ACH / f_infil
    q = ach_in * V_HALLE / 3600.0
    s = [block("GRUNDINFILTRATION")]
    s.append("!- Grundinfiltration %s 1/h = %s m3/s, konstant.\n"
             "!- Koeffizienten 1/0/0/0: bewusst OHNE Wind- und Temperaturmodulation,\n"
             "!- damit sich die vier vereinfachten Modelle ausschliesslich in der\n"
             "!- Torabbildung unterscheiden. Wuerde die Grundinfiltration zusaetzlich\n"
             "!- je Modell anders moduliert, misst Kapitel 6 zwei Dinge gleichzeitig.\n"
             "!- Im AFN-Modell ist dieselbe Rate ueber Huellenrisse abgebildet, weil\n"
             "!- ZoneInfiltration dort ignoriert wird (siehe README).\n"
             "!- Eingabewert %s 1/h = Sollwert %s 1/h geteilt durch die\n"
             "!- Dichtekorrektur %s, damit die AUSGEGEBENE Rate %s 1/h betraegt.\n" % (
                 num(INFILTRATION_ACH, 4), num(q, 6),
                 num(ach_in, 6), num(INFILTRATION_ACH, 4), num(f_infil, 6),
                 num(INFILTRATION_ACH, 4)))
    s.append(fields("ZoneInfiltration:DesignFlowRate", [
        ("Grundinfiltration", "Name"),
        ("Zone_Halle", "Zone or ZoneList or Space or SpaceList Name"),
        ("Sch_Immer_an", "Schedule Name"),
        ("AirChanges/Hour", "Design Flow Rate Calculation Method"),
        (None, "Design Flow Rate {m3/s}"), (None, "Flow Rate per Floor Area {m3/s-m2}"),
        (None, "Flow Rate per Exterior Surface Area {m3/s-m2}"),
        (num(ach_in, 8), "Air Changes per Hour {1/hr}"),
        ("1.0", "Constant Term Coefficient"), ("0.0", "Temperature Term Coefficient"),
        ("0.0", "Velocity Term Coefficient"), ("0.0", "Velocity Squared Term Coefficient")]))
    return "".join(s)


# ================================================================= AFN-Block
def afn_block(crack_c, tore_offen=True):
    s = [block("AIRFLOWNETWORK")]
    s.append("!- Wind Pressure Coefficient Type = SurfaceAverageCalculation wie in\n"
             "!- Kapitel 5 (Modellansatz AFN_E+). Azimuth Angle of Long Axis = %s Grad\n"
             "!- (Laengsachse 60 m, mit dem Gebaeude gedreht),\n"
             "!- Ratio Short/Long = %s.\n" % (num(drehen(0.0), 1), num(LX / LY, 4)))
    s.append(fields("AirflowNetwork:SimulationControl", [
        ("AFN_Heizperiode", "Name"),
        ("MultizoneWithoutDistribution", "AirflowNetwork Control"),
        ("SurfaceAverageCalculation", "Wind Pressure Coefficient Type"),
        ("ExternalNode", "Height Selection for Local Wind Pressure Calculation"),
        ("LowRise", "Building Type"),
        ("500", "Maximum Number of Iterations {dimensionless}"),
        ("LinearInitializationMethod", "Initialization Type"),
        ("0.0001", "Relative Airflow Convergence Tolerance {dimensionless}"),
        ("0.000001", "Absolute Airflow Convergence Tolerance {kg/s}"),
        ("-0.5", "Convergence Acceleration Limit {dimensionless}"),
        (num(drehen(0.0), 1), "Azimuth Angle of Long Axis of Building {deg}"),
        (num(LX / LY, 4), "Ratio of Building Width Along Short Axis to Width Along Long Axis"),
        ("No", "Height Dependence of External Node Temperature"),
        ("SkylineLU", "Solver"),
        ("No", "Allow Unsupported Zone Equipment"),
        ("No", "Do Distribution Duct Sizing Calculation")]))
    s.append(fields("AirflowNetwork:MultiZone:Zone", [
        ("Zone_Halle", "Zone Name"), ("Constant", "Ventilation Control Mode"),
        (None, "Ventilation Control Zone Temperature Setpoint Schedule Name"),
        (None, "Minimum Venting Open Factor {dimensionless}"),
        ("0", "Indoor and Outdoor Temperature Difference Lower Limit For Maximum Venting Open Factor {deltaC}"),
        ("100", "Indoor and Outdoor Temperature Difference Upper Limit for Minimum Venting Open Factor {deltaC}"),
        ("0", "Indoor and Outdoor Enthalpy Difference Lower Limit For Maximum Venting Open Factor {deltaJ/kg}"),
        ("300000", "Indoor and Outdoor Enthalpy Difference Upper Limit for Minimum Venting Open Factor {deltaJ/kg}")]))

    # ---- Huellenleckage
    flaeche = {"AW_Sued": LX * LZ - 3 * A_TOR, "AW_Nord": LX * LZ - 3 * A_TOR,
               "Dach": LX * LY}
    a_sum = sum(flaeche.values())
    s.append("!- Grundinfiltration als Huellenleckage. ZoneInfiltration:DesignFlowRate\n"
             "!- ist unter AirflowNetwork Control = MultizoneWithoutDistribution\n"
             "!- unwirksam - die Input Output Reference 25.2 sagt dazu woertlich: 'Any\n"
             "!- ZoneInfiltration:*, ZoneVentilation:*, ZoneMixing and ZoneCrossMixing\n"
             "!- objects specified in the input data file are not simulated.'\n"
             "!- Der Koeffizient ist auf die Netto-Aussenflaechen verteilt\n"
             "!- (AW_Sued %s m2, AW_Nord %s m2, Dach %s m2, Summe %s m2) und in\n"
             "!- Stufe 1 so kalibriert, dass das Heizperiodenmittel %s 1/h betraegt.\n" % (
                 num(flaeche["AW_Sued"], 2), num(flaeche["AW_Nord"], 2),
                 num(flaeche["Dach"], 2), num(a_sum, 2), num(INFILTRATION_ACH, 4)))
    for name in CRACK_FLAECHEN:
        c_i = crack_c * flaeche[name] / a_sum
        s.append(fields("AirflowNetwork:MultiZone:Surface:Crack", [
            ("Crack_%s" % name, "Name"),
            (num(c_i, 8), "Air Mass Flow Coefficient at Reference Conditions {kg/s}"),
            (num(CRACK_N, 2), "Air Mass Flow Exponent {dimensionless}")]))
        s.append(fields("AirflowNetwork:MultiZone:Surface", [
            (name, "Surface Name"), ("Crack_%s" % name, "Leakage Component Name"),
            (None, "External Node Name"),
            ("1", "Window/Door Opening Factor, or Crack Factor {dimensionless}"),
            ("Constant", "Ventilation Control Mode")]))

    # ---- Tore
    if tore_offen:
        s.append("!- Ein AirflowNetwork:MultiZone:Surface je Tor. Der Oeffnungsfaktor wird\n"
                 "!- NICHT ueber Venting Availability gesteuert: dieses Feld ist rein\n"
                 "!- binaer ('A value greater than zero means venting can occur',\n"
                 "!- Input Output Reference 25.2). Der Zwischenwert 0,048 des\n"
                 "!- Andockzustands wuerde dort als voll geoeffnetes Tor gelesen.\n"
                 "!- Die Steuerung erfolgt deshalb ueber den EMS-Aktor weiter unten.\n")
    else:
        s.append("!- Stufe 1 (Crack-Kalibrierung): alle Tore dauerhaft geschlossen,\n"
                 "!- der EMS-Aktor setzt den Oeffnungsfaktor konstant auf 0.\n")
    for g in sorted(GATES):
        s.append(fields("AirflowNetwork:MultiZone:Surface", [
            ("gate %d" % g, "Surface Name"), ("AFN_Tor", "Leakage Component Name"),
            (None, "External Node Name"),
            ("1", "Window/Door Opening Factor, or Crack Factor {dimensionless}"),
            ("Constant", "Ventilation Control Mode"),
            (None, "Ventilation Control Zone Temperature Setpoint Schedule Name"),
            (None, "Minimum Venting Open Factor {dimensionless}"),
            (None, "Indoor and Outdoor Temperature Difference Lower Limit For Maximum Venting Open Factor {deltaC}"),
            ("100", "Indoor and Outdoor Temperature Difference Upper Limit for Minimum Venting Open Factor {deltaC}"),
            (None, "Indoor and Outdoor Enthalpy Difference Lower Limit For Maximum Venting Open Factor {deltaJ/kg}"),
            ("300000", "Indoor and Outdoor Enthalpy Difference Upper Limit for Minimum Venting Open Factor {deltaJ/kg}"),
            ("Sch_Immer_an", "Venting Availability Schedule Name"),
            (None, "Occupant Ventilation Control Name"),
            ("PolygonHeight", "Equivalent Rectangle Method"),
            ("1", "Equivalent Rectangle Aspect Ratio {dimensionless}")]))

    s.append("!- Drei Saetze statt zwei. Der Oeffnungsfaktor ist bei DetailedOpening\n"
             "!- KEIN Flaechenanteil: die durchstroemte Flaeche folgt aus\n"
             "!- Width Factor x Height Factor x Fensterflaeche, beide Faktoren werden\n"
             "!- zwischen den Saetzen linear interpoliert. Mit nur zwei Saetzen ergaebe\n"
             "!- der Oeffnungsfaktor 0,048 eine Flaeche von 0,048 x 0,048 x %s = %s m2\n"
             "!- statt der beabsichtigten %s m2.\n"
             "!- Satz 2 bildet den angedockten LKW ab: umlaufende Dichtungsleckage,\n"
             "!- flaechengleich abgebildet als waagerechter Spalt in Toroeffnungsmitte\n"
             "!- (Width Factor %s, Height Factor %s, Start Height Factor %s).\n"
             "!- Die Lage in Mittenhoehe haelt den Auftriebsterm neutral - ein Bodenspalt\n"
             "!- wuerde einen gerichteten Auftriebsstrom erzeugen, den WSOA und DFR\n"
             "!- konstruktionsbedingt nicht abbilden koennen. SETZUNG, siehe README.\n" % (
                 num(A_TOR, 2), num(OF_ANDOCK * OF_ANDOCK * A_TOR, 4),
                 num(OF_ANDOCK * A_TOR, 4),
                 num(WF_ANDOCK, 3), num(HF_ANDOCK, 3), num(SH_ANDOCK, 3)))
    s.append(fields("AirflowNetwork:MultiZone:Component:DetailedOpening", [
        ("AFN_Tor", "Name"),
        ("0.001", "Air Mass Flow Coefficient When Opening is Closed {kg/s-m}"),
        ("0.65", "Air Mass Flow Exponent When Opening is Closed {dimensionless}"),
        ("NonPivoted", "Type of Rectangular Large Vertical Opening (LVO)"),
        ("0", "Extra Crack Length or Height of Pivoting Axis {m}"),
        ("3", "Number of Sets of Opening Factor Data"),
        ("0", "Opening Factor 1 {dimensionless}"),
        ("0.001", "Discharge Coefficient for Opening Factor 1 {dimensionless}"),
        ("0", "Width Factor for Opening Factor 1 {dimensionless}"),
        ("0", "Height Factor for Opening Factor 1 {dimensionless}"),
        ("0", "Start Height Factor for Opening Factor 1 {dimensionless}"),
        (num(OF_ANDOCK, 4), "Opening Factor 2 {dimensionless}"),
        (num(CD_TOR, 2), "Discharge Coefficient for Opening Factor 2 {dimensionless}"),
        (num(WF_ANDOCK, 4), "Width Factor for Opening Factor 2 {dimensionless}"),
        (num(HF_ANDOCK, 4), "Height Factor for Opening Factor 2 {dimensionless}"),
        (num(SH_ANDOCK, 4), "Start Height Factor for Opening Factor 2 {dimensionless}"),
        ("1", "Opening Factor 3 {dimensionless}"),
        (num(CD_TOR, 2), "Discharge Coefficient for Opening Factor 3 {dimensionless}"),
        ("1", "Width Factor for Opening Factor 3 {dimensionless}"),
        ("1", "Height Factor for Opening Factor 3 {dimensionless}"),
        ("0", "Start Height Factor for Opening Factor 3 {dimensionless}")]))
    return "".join(s)


def ems_block(tore_offen=True):
    s = [block("ENERGYMANAGEMENTSYSTEM  (OEFFNUNGSFAKTOR DER TORE)")]
    s.append("!- Der Aktor 'AirFlow Network Window/Door Opening' / 'Venting Opening\n"
             "!- Factor' setzt den Oeffnungsfaktor je Zeitschritt auf den Schedulewert\n"
             "!- (0 zu, %s angedockt, 1 offen). Application Guide for EMS, Air Movement.\n"
             "!- Kennung des Aktors ist der Name der Fensterflaeche, nicht des\n"
             "!- AirflowNetwork-Objekts.\n" % num(OF_ANDOCK, 3))
    for g in sorted(GATES):
        s.append(fields("EnergyManagementSystem:Sensor", [
            ("Sens_Tor%d" % g, "Name"),
            (GATES[g]["sched"], "Output:Variable or Output:Meter Index Key Name"),
            ("Schedule Value", "Output:Variable or Output:Meter Name")]))
    for g in sorted(GATES):
        s.append(fields("EnergyManagementSystem:Actuator", [
            ("Act_Tor%d" % g, "Name"),
            ("gate %d" % g, "Actuated Component Unique Name"),
            ("AirFlow Network Window/Door Opening", "Actuated Component Type"),
            ("Venting Opening Factor", "Actuated Component Control Type")]))
    prog = ["EnergyManagementSystem:Program,", "    Prog_Toroeffnung,        !- Name"]
    for g in sorted(GATES):
        rhs = ("Sens_Tor%d" % g) if tore_offen else "0.0"
        sep = ";" if g == max(GATES) else ","
        prog.append("    SET Act_Tor%d = %s%s" % (g, rhs, sep))
    s.append("\n".join(prog) + "\n\n")
    s.append(fields("EnergyManagementSystem:ProgramCallingManager", [
        ("Mgr_Toroeffnung", "Name"),
        ("BeginTimestepBeforePredictor", "EnergyPlus Model Calling Point"),
        ("Prog_Toroeffnung", "Program Name 1")]))
    return "".join(s)


# =============================================================== WSOA / DFR
def wsoa_block():
    s = [block("ZONEVENTILATION:WINDANDSTACKOPENAREA")]
    s.append("!- Ein Objekt je Tor, Opening Area Fraction Schedule = Tor-Schedule.\n"
             "!- Hier wirkt der Zwischenwert %s unmittelbar als Flaechenanteil - anders\n"
             "!- als bei AFN, wo er ueber den EMS-Aktor gesetzt werden muss.\n"
             "!- Height Difference = 0: alle Tore auf gleicher Hoehe, der Auftriebsterm\n"
             "!- ist strukturell null. Die sechs Objekte sind untereinander NICHT\n"
             "!- gekoppelt - jedes Tor wird als einseitige Oeffnung gerechnet und die\n"
             "!- Beitraege addieren sich. Befund fuer 6.4, kein Eingabefehler.\n" % num(OF_ANDOCK, 3))
    for g in sorted(GATES):
        s.append(fields("ZoneVentilation:WindandStackOpenArea", [
            ("WSOA_Tor%d" % g, "Name"), ("Zone_Halle", "Zone or Space Name"),
            (num(A_TOR, 2), "Opening Area {m2}"),
            (GATES[g]["sched"], "Opening Area Fraction Schedule Name"),
            ("Autocalculate", "Opening Effectiveness"),
            (num(drehen(GATES[g]["azimut"]), 1), "Effective Angle {deg}"),
            ("0.0", "Height Difference {m}"),
            ("Autocalculate", "Discharge Coefficient for Opening"),
            ("-100.0", "Minimum Indoor Temperature {C}"),
            (None, "Minimum Indoor Temperature Schedule Name"),
            ("100.0", "Maximum Indoor Temperature {C}"),
            (None, "Maximum Indoor Temperature Schedule Name"),
            ("-100.0", "Delta Temperature {deltaC}"),
            (None, "Delta Temperature Schedule Name"),
            ("-100.0", "Minimum Outdoor Temperature {C}"),
            (None, "Minimum Outdoor Temperature Schedule Name"),
            ("100.0", "Maximum Outdoor Temperature {C}"),
            (None, "Maximum Outdoor Temperature Schedule Name"),
            ("40.0", "Maximum Wind Speed {m/s}")]))
    return "".join(s)


def dfr_block(setname, qdes):
    st = DFR_SETS[setname]
    s = [block("ZONEVENTILATION:DESIGNFLOWRATE")]
    s.append("!- Koeffizientensatz %s: A = %s, B = %s 1/K, C = %s s/m, D = %s s2/m2\n"
             "!- Q = Design Flow Rate * F_Schedule * (A + B*|dT| + C*u + D*u^2)\n"
             "!- Ein Objekt je Tor mit dem gemeinsamen Design Flow Rate %s m3/s aus der\n"
             "!- Kalibrierung gegen den AFN-Lauf (Stufe 2). Der Wert ist fuer alle drei\n"
             "!- Koeffizientensaetze derselbe; die Saetze bilden die Innen-Spanne.\n"
             "!- Wie bei WSOA sind die sechs Objekte nicht gekoppelt.\n" % (
                 setname, num(st["A"], 5), num(st["B"], 5), num(st["C"], 5),
                 num(st["D"], 5), num(qdes, 6)))
    for g in sorted(GATES):
        s.append(fields("ZoneVentilation:DesignFlowRate", [
            ("DFR_%s_Tor%d" % (setname, g), "Name"),
            ("Zone_Halle", "Zone or ZoneList or Space or SpaceList Name"),
            (GATES[g]["sched"], "Schedule Name"),
            ("Flow/Zone", "Design Flow Rate Calculation Method"),
            (num(qdes, 6), "Design Flow Rate {m3/s}"),
            (None, "Flow Rate per Floor Area {m3/s-m2}"),
            (None, "Flow Rate per Person {m3/s-person}"),
            (None, "Air Changes per Hour {1/hr}"),
            ("Natural", "Ventilation Type"),
            ("0.0", "Fan Pressure Rise {Pa}"), ("1.0", "Fan Total Efficiency"),
            (num(st["A"], 5), "Constant Term Coefficient"),
            (num(st["B"], 5), "Temperature Term Coefficient"),
            (num(st["C"], 5), "Velocity Term Coefficient"),
            (num(st["D"], 5), "Velocity Squared Term Coefficient"),
            ("-100.0", "Minimum Indoor Temperature {C}"),
            (None, "Minimum Indoor Temperature Schedule Name"),
            ("100.0", "Maximum Indoor Temperature {C}"),
            (None, "Maximum Indoor Temperature Schedule Name"),
            ("-100.0", "Delta Temperature {deltaC}"),
            (None, "Delta Temperature Schedule Name"),
            ("-100.0", "Minimum Outdoor Temperature {C}"),
            (None, "Minimum Outdoor Temperature Schedule Name"),
            ("100.0", "Maximum Outdoor Temperature {C}"),
            (None, "Maximum Outdoor Temperature Schedule Name"),
            ("40.0", "Maximum Wind Speed {m/s}")]))
    return "".join(s)


# ================================================================== Ausgabe
def ausgabe(modelltyp, freq_fein="Timestep"):
    s = [block("OUTPUT")]
    s.append(fields("Output:VariableDictionary", [("IDF", "Key Field"), ("Unsorted", "Sort Option")]))
    s.append(fields("Output:Table:SummaryReports", [("AllSummary", "Report 1 Name")]))
    s.append(fields("OutputControl:Table:Style", [("HTML", "Column Separator")]))
    s.append(fields("Output:SQLite", [("SimpleAndTabular", "Option Type")]))
    s.append(fields("Output:Diagnostics", [
        ("DisplayAllWarnings", "Key 1"), ("DisplayAdvancedReportVariables", "Key 2")]))

    fein = []
    if modelltyp == "AFN":
        for g in sorted(GATES):
            fein += [("gate %d" % g, "AFN Linkage Node 1 to Node 2 Volume Flow Rate"),
                     ("gate %d" % g, "AFN Linkage Node 2 to Node 1 Volume Flow Rate"),
                     ("gate %d" % g, "AFN Surface Venting Window or Door Opening Factor")]
        for name in CRACK_FLAECHEN:
            fein += [(name, "AFN Linkage Node 1 to Node 2 Volume Flow Rate"),
                     (name, "AFN Linkage Node 2 to Node 1 Volume Flow Rate")]
    else:
        fein += [("*", "Zone Ventilation Current Density Volume Flow Rate"),
                 ("*", "Zone Infiltration Current Density Volume Flow Rate")]
    for g in sorted(GATES):
        fein.append((GATES[g]["sched"], "Schedule Value"))
    # Key der ZoneHVAC:IdealLoadsAirSystem-Variablen ist der OBJEKTNAME, nicht
    # der Zonenname - mit Key "Zone_Halle" werden sie stillschweigend nicht
    # erzeugt (nur eine Warnung "requested but not generated").
    fein += [("*", "Zone Ideal Loads Supply Air Total Heating Rate"),
             ("Zone_Halle", "Zone Mean Air Temperature"),
             ("Environment", "Site Outdoor Air Drybulb Temperature"),
             ("Environment", "Site Wind Speed"),
             ("Environment", "Site Wind Direction")]

    s.append("!- Feine Aufloesung nur fuer die Groessen, die 6.4 braucht.\n")
    for key, var in fein:
        s.append(fields("Output:Variable", [
            (key, "Key Value"), (var, "Variable Name"), (freq_fein, "Reporting Frequency")]))
    s.append("!- Zusaetzlich stuendlich fuer Dauerlinie und Bilanzen.\n")
    for var in ["Zone Ideal Loads Supply Air Total Heating Energy",
                "Zone Ideal Loads Supply Air Total Heating Rate"]:
        s.append(fields("Output:Variable", [
            ("*", "Key Value"), (var, "Variable Name"), ("Hourly", "Reporting Frequency")]))
    return "".join(s)


# =========================================================== Schedules laden
def lade_schedules(pfad):
    """Liest alle_tore.idf und gibt ScheduleTypeLimits + die sechs
    Schedule:Compact als Text zurueck (Kopfkommentare entfernt)."""
    with open(pfad, "r", encoding="utf-8", errors="replace") as f:
        txt = f.read()
    i = txt.find("ScheduleTypeLimits,")
    if i < 0:
        raise SystemExit("ScheduleTypeLimits nicht gefunden in %s" % pfad)
    txt = txt[i:]
    gefunden = re.findall(r"^\s*([A-Z]{2}_\d_Tor_Schedule)\s*,", txt, re.M)
    erwartet = sorted(g["sched"] for g in GATES.values())
    if sorted(gefunden) != erwartet:
        raise SystemExit("Schedule-Namen passen nicht.\n  gefunden : %s\n  erwartet : %s"
                         % (sorted(gefunden), erwartet))
    return ("!- Tor-Schedules, uebernommen aus %s (gate_scheduling 0.1.0, Seed 42).\n"
            "!- Minutenaufloesung; wirkt nur bei Timestep 60.\n\n" % os.path.basename(pfad)) + txt


# ====================================================================== Main
def schreibe(pfad, text):
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    n = len(re.findall(r"^[A-Za-z][A-Za-z0-9:]*\s*,\s*$|^[A-Za-z][A-Za-z0-9:]*,", text, re.M))
    print("  %-34s %8.1f kB" % (os.path.basename(pfad), len(text) / 1024.0))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modus", required=True, choices=["crack", "afn", "final"])
    p.add_argument("--crack-c", type=float, default=CRACK_C_START,
                   help="kalibrierter Crack-Koeffizient (Summe ueber alle Flaechen)")
    p.add_argument("--qdes", type=float, default=None,
                   help="Design Flow Rate je Tor in m3/s aus Stufe 2")
    p.add_argument("--schedules", default=SCHEDULE_QUELLE)
    p.add_argument("--ziel", default=".")
    p.add_argument("--f-vent", type=float, default=1.0,
                   help="Dichtekorrektur Lueftungsobjekte (gemessen/eingegeben)")
    p.add_argument("--f-infil", type=float, default=1.0,
                   help="Dichtekorrektur Infiltrationsobjekt")
    p.add_argument("--drehung", type=float, default=0.0,
                   help="Gebaeudedrehung in Grad (0 = Tore Sued/Nord, 90 = Ost/West)")
    p.add_argument("--pilot", action="store_true",
                   help="zusaetzlich eine Januarwoche als Pilotlauf erzeugen")
    a = p.parse_args()

    global DREHUNG
    DREHUNG = a.drehung
    SFX = "" if a.drehung == 0 else "_rot%d" % int(round(a.drehung))
    if not os.path.isdir(a.ziel):
        os.makedirs(a.ziel)
    sched = lade_schedules(a.schedules)

    JAHR = ("Jahr", 1, 1, 12, 31, "Thursday")
    WOCHE = ("Pilot_Januarwoche", 1, 12, 1, 18, "Monday")

    print("Skalierungsfaktor  %s / %s = %s" % (num(A_BODEN, 0), num(A_REF, 2), num(SKALIERUNG, 5)))
    print("Interne Gewinne    %s W" % num(P_INTERN, 2))
    print("Speichermasse      Metall %s m2, Holz %s m2" % (num(A_METALL, 2), num(A_HOLZ, 2)))
    print("Grundinfiltration  %s 1/h = %s m3/s" % (
        num(INFILTRATION_ACH, 4), num(INFILTRATION_ACH * V_HALLE / 3600.0, 6)))
    print("Andockspalt        A = %s m2 (WF %s, HF %s, Start %s)" % (
        num(OF_ANDOCK * A_TOR, 4), num(WF_ANDOCK, 3), num(HF_ANDOCK, 3), num(SH_ANDOCK, 3)))
    print()

    if a.modus == "crack":
        extra = ["STUFE 1 - Kalibrierung der Huellenleckage.",
                 "Alle Tore dauerhaft geschlossen (EMS setzt den Oeffnungsfaktor auf 0).",
                 "Crack-Koeffizient Startwert C0 = %s kg/s bei 1 Pa." % num(a.crack_c, 6),
                 "",
                 "Auswertung: Mittelwert der Summe aller AFN-Linkage-Volumenstroeme",
                 "ueber die Heizperiode, umgerechnet in 1/h -> ACH_0.",
                 "Kalibrierter Wert: C = C0 * %s / ACH_0." % num(INFILTRATION_ACH, 4),
                 "Das ist exakt, weil das Netzwerk homogen vom Grad 1 in allen",
                 "Crack-Koeffizienten ist: skaliert man alle gemeinsam, bleibt die",
                 "Druckloesung unveraendert und alle Volumenstroeme skalieren mit."]
        t = kopf("AFN_E+_Crackkalibrierung%s.idf" % SFX, "AirflowNetwork, nur Huellenleckage",
                 extra, TIMESTEP_CRACK, "1.1. bis 31.12.")
        t += basis(TIMESTEP_CRACK, JAHR, sched) + geometrie() + anlage() + interne_lasten()
        t += afn_block(a.crack_c, tore_offen=False) + ems_block(tore_offen=False)
        t += ausgabe("AFN", freq_fein="Hourly")
        schreibe(os.path.join(a.ziel, "AFN_E+_Crackkalibrierung%s.idf" % SFX), t)

    elif a.modus == "afn":
        extra = ["STUFE 2 - Referenzlauf AFN_E+.",
                 "Crack-Koeffizient C = %s kg/s bei 1 Pa (aus Stufe 1)." % num(a.crack_c, 6),
                 "",
                 "Liefert Q_AFN je Zeitschritt fuer die Kalibrierung der DFR-Objekte:",
                 "  Q_design = Summe(Q_AFN * dt) / Summe(Summe_i(s_i) * dt)",
                 "mit s_i dem Schedulewert von Tor i. Damit trifft DFR_DEFAULT den",
                 "kumulierten Aussenluftaustausch exakt; BLAST und DOE-2 weichen allein",
                 "durch ihre Koeffizientensaetze ab (Innen-Spanne fuer 6.3.2)."]
        for nm, rp, ts in ([("AFN_E+_Pilot%s.idf" % SFX, WOCHE, TIMESTEP_PILOT)] if a.pilot else []) + \
                          [("AFN_E+_Jahr%s.idf" % SFX, JAHR, TIMESTEP)]:
            rp_txt = "12.1. bis 18.1. (Pilotlauf)" if rp is WOCHE else "1.1. bis 31.12."
            t = kopf(nm, "AirflowNetwork, MultiZone:Component:DetailedOpening, "
                         "SurfaceAverageCalculation", extra, ts, rp_txt)
            t += basis(ts, rp, sched) + geometrie() + anlage() + interne_lasten()
            t += afn_block(a.crack_c, tore_offen=True) + ems_block(tore_offen=True)
            t += ausgabe("AFN")
            schreibe(os.path.join(a.ziel, nm), t)

    else:
        if a.qdes is None:
            raise SystemExit("--qdes fehlt (Design Flow Rate je Tor aus Stufe 2)")
        extra_gem = [
            "STUFE 3 - vereinfachte Modellansaetze.",
            "Grundinfiltration als ZoneInfiltration:DesignFlowRate, %s 1/h, konstant."
            % num(INFILTRATION_ACH, 4),
            "Die sechs Lueftungsobjekte sind untereinander nicht druckgekoppelt."]
        t = kopf("WSOA_Jahr%s.idf" % SFX,
                 "ZoneVentilation:WindandStackOpenArea, Opening Effectiveness Autocalculate",
                 extra_gem, TIMESTEP, "1.1. bis 31.12.")
        t += basis(TIMESTEP, JAHR, sched) + geometrie() + anlage() + interne_lasten()
        t += grundinfiltration_zoneobjekt(a.f_infil) + wsoa_block() + ausgabe("VENT")
        schreibe(os.path.join(a.ziel, "WSOA_Jahr%s.idf" % SFX), t)

        for setname in ["DEFAULT", "BLAST", "DOE-2"]:
            nm = "DFR_%s_Jahr%s.idf" % (setname, SFX)
            extra = extra_gem + [
                "", "Design Flow Rate je Tor = %s m3/s, kalibriert gegen AFN," % num(a.qdes, 6),
                "eingegeben als %s m3/s (Dichtekorrektur %s)." % (
                    num(a.qdes / a.f_vent, 6), num(a.f_vent, 6))]
            t = kopf(nm, "ZoneVentilation:DesignFlowRate, %s" % DFR_SETS[setname]["quelle"],
                     extra, TIMESTEP, "1.1. bis 31.12.")
            t += basis(TIMESTEP, JAHR, sched) + geometrie() + anlage() + interne_lasten()
            t += grundinfiltration_zoneobjekt(a.f_infil) + dfr_block(setname, a.qdes / a.f_vent) + ausgabe("VENT")
            schreibe(os.path.join(a.ziel, nm), t)


if __name__ == "__main__":
    main()
