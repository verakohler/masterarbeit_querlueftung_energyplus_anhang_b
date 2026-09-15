# -*- coding: utf-8 -*-
"""
Generator fuer die isothermen EnergyPlus-Eingabedateien der Varianten 1-6
(Masterarbeit M13, Kapitel 5.3 / 5.4).

Erzeugt:
  * 2 Wetterdateien (Anstroemrichtung 247,5 Grad und 157,5 Grad, u10 = 5,071965 m/s)
  * 6 x AFN_E+          AirflowNetwork, SurfaceAverageCalculation
  * 6 x WSOA            ZoneVentilation:WindandStackOpenArea, Autocalculate
  * 6 x DFR_DEFAULT     ZoneVentilation:DesignFlowRate, Programmvoreinstellung
  * 6 x DFR_BLAST       ZoneVentilation:DesignFlowRate, BLAST-Koeffizienten
  * 6 x DFR_DOE-2       ZoneVentilation:DesignFlowRate, DOE-2-Koeffizienten
  * Sollwerte_Isotherm.csv
  * README_Isotherm_Varianten.md

Alle Zahlenwerte stammen aus Handrechnungen_neu.xlsx und werden hier aus den
dort dokumentierten Eingangsgroessen neu berechnet, nicht abgeschrieben.
"""

import csv
import math
import os
import shutil

# ---------------------------------------------------------------- Grundwerte
EPLUS_VERSION = "25.2"

U10 = 6.5                     # Wetter!E3   Windgeschwindigkeit in 10 m, Heizperiodenmittel WSW
Z_MET = 10.0                  # Wetter!E4
Z_REF = 1.7                   # Wetter!E5   gewaehlte Bezugshoehe (Toroeffnungsmitte)
ALPHA = 0.14                  # Wetter!E6   Offenland
DELTA = 270.0                 # Wetter!E7   Offenland
U_REF = U10 * (Z_REF / Z_MET) ** ALPHA          # = 5.071965 m/s

CD = 0.62                     # Durchflussbeiwert, in allen Blaettern gesetzt
A_TOR = 9.0                   # Toroeffnungsflaeche, 3 x 3 m
A_SPALT = 30.0                # Barrierenspalt, 15 x 2 m
V_HALLE = 10800.0             # Hallenvolumen
T_ISO = 17.0                  # isotherme Temperatur innen = aussen
P_STAT = 95300.0              # Stationsdruck der Wetterdatei

# Halle
LX, LY, LZ = 15.0, 60.0, 12.0
Y_BARRIERE = 30.0

# Barrierenspalt: 0,01 m Randabstand links/rechts, damit die Unterflaeche
# vollstaendig innerhalb der Basisflaeche liegt. Hoehe so nachgefuehrt, dass
# die Flaeche exakt 30,000 m2 bleibt (nur A geht in die Gleichung ein).
SPALT_X0, SPALT_X1 = 0.01, LX - 0.01
SPALT_B = SPALT_X1 - SPALT_X0
SPALT_H = A_SPALT / SPALT_B

# Tore: Position in der Fassade
GATES = {
    1: dict(wall="AW_Sued", x0=1.0, x1=4.0, azimut=180.0),
    2: dict(wall="AW_Sued", x0=6.0, x1=9.0, azimut=180.0),
    3: dict(wall="AW_Sued", x0=11.0, x1=14.0, azimut=180.0),
    4: dict(wall="AW_Nord", x0=1.0, x1=4.0, azimut=0.0),
    5: dict(wall="AW_Nord", x0=6.0, x1=9.0, azimut=0.0),
    6: dict(wall="AW_Nord", x0=11.0, x1=14.0, azimut=0.0),
}
GATE_Z0, GATE_Z1 = 0.0, 3.0

EPW_WSW = "DEU_Munich.108660_Isotherm-WSW2475-u5072.epw"
EPW_SSE = "DEU_Munich.108660_Isotherm-SSE1575-u5072.epw"

# Varianten nach Blatt CFD, Spalten A bis F
VARIANTS = {
    1: dict(tore=(2, 5), barriere=False, winddir=247.5, epw=EPW_WSW,
            beschreibung="Tore 2 + 5 gegenueberliegend, keine Barriere, schraege Anstroemung"),
    2: dict(tore=(2, 5), barriere=True, winddir=247.5, epw=EPW_WSW,
            beschreibung="Tore 2 + 5 gegenueberliegend, innere Barriere mit Spalt, schraege Anstroemung"),
    3: dict(tore=(2, 4), barriere=False, winddir=247.5, epw=EPW_WSW,
            beschreibung="Tore 2 + 4 diagonal, keine Barriere, schraege Anstroemung"),
    4: dict(tore=(2, 5), barriere=False, winddir=157.5, epw=EPW_SSE,
            beschreibung="Tore 2 + 5 gegenueberliegend, keine Barriere, frontale Anstroemung"),
    5: dict(tore=(2, 5), barriere=True, winddir=157.5, epw=EPW_SSE,
            beschreibung="Tore 2 + 5 gegenueberliegend, innere Barriere mit Spalt, frontale Anstroemung"),
    6: dict(tore=(2, 4), barriere=False, winddir=157.5, epw=EPW_SSE,
            beschreibung="Tore 2 + 4 diagonal, keine Barriere, frontale Anstroemung"),
}

# Winddruckbeiwerte, die EnergyPlus mit SurfaceAverageCalculation selbst
# berechnet (aus .eio der Laeufe vom 09.07.2026, Blatt AFN_1Zone Spalten E/J).
# Nur zur Berechnung der Sollwerte, NICHT als IDF-Eingabe.
CP_EPLUS = {
    247.5: dict(sued=0.033, nord=-0.44),
    157.5: dict(sued=0.48, nord=-0.315),
}

# Koeffizientensaetze ZoneVentilation:DesignFlowRate
# A, B, C, D nach Blatt DesignFlowRate Zeilen 13 bis 16
DFR_SETS = {
    "DEFAULT": dict(A=1.0, B=0.0, C=0.0, D=0.0,
                    quelle="Programmvoreinstellung von EnergyPlus"),
    "BLAST": dict(A=0.606, B=0.03636, C=0.1177, D=0.0,
                  quelle="BLAST-Koeffizientensatz, Input Output Reference"),
    "DOE-2": dict(A=0.0, B=0.0, C=0.224, D=0.0,
                  quelle="DOE-2-Koeffizientensatz, Input Output Reference"),
}


def dfr_uref(s):
    """Normierungsgeschwindigkeit: die Geschwindigkeit, bei der das
    Koeffizientenpolynom bei Delta-T = 0 den Wert 1 annimmt."""
    A, B, C, D = s["A"], s["B"], s["C"], s["D"]
    if C == 0.0 and D == 0.0:
        return U_REF                      # DEFAULT: Polynom ist konstant 1
    if D == 0.0:
        return (1.0 - A) / C
    raise ValueError("D-Term nicht implementiert")


def dfr_poly(s, u):
    return s["A"] + s["B"] * 0.0 + s["C"] * u + s["D"] * u * u


def a_eff(barriere):
    """Effektive Flaeche der Reihenschaltung, Blatt cos Zeile 6."""
    inv = 2.0 / A_TOR ** 2
    if barriere:
        inv += 1.0 / A_SPALT ** 2
    return 1.0 / math.sqrt(inv)


def theta(winddir):
    """Anstroemwinkel gegen die Fassadennormale der Luvfassade (AW_Sued, 180 Grad)."""
    return abs(winddir - 180.0)


def k_faktor(v):
    """k = C_D * A_eff * cos(theta), Blatt DesignFlowRate Zeile 21."""
    return CD * a_eff(v["barriere"]) * math.cos(math.radians(theta(v["winddir"])))


def cw_ang(effective_angle, winddir):
    """Auf 0 bis 180 Grad gefalteter Anstroemwinkel, wie in der Implementierung."""
    return 180.0 - abs(abs(winddir - effective_angle) - 180.0)


def cw_eplus(effective_angle, winddir):
    """Implementiertes Opening-Effectiveness-Gesetz von EnergyPlus 25.2:
      ang = 180 - | |WindDirection - EffectiveAngle| - 180 |
      C_w = 0                              fuer ang > 90
      C_w = 0,55 + ang * (0,30 - 0,55)/45  sonst
    Nicht Gleichung 8.7 der Engineering Reference, vgl.
    Notiz_Cw_Fehler_EngineeringReference.md."""
    ang = cw_ang(effective_angle, winddir)
    if ang > 90.0:
        return 0.0
    return 0.55 + ang * (0.30 - 0.55) / 45.0


def rho(t_celsius):
    return P_STAT / (287.06 * (t_celsius + 273.15))


# ------------------------------------------------------- Sollwerte ausrechnen
def soll_dfr(nr, setname):
    v = VARIANTS[nr]
    s = DFR_SETS[setname]
    vdes = k_faktor(v) * dfr_uref(s)
    q = vdes * dfr_poly(s, U_REF)
    return vdes, q, q * 3600.0 / V_HALLE


def soll_wsoa(nr):
    v = VARIANTS[nr]
    q = 0.0
    einzeln = []
    for g in v["tore"]:
        cw = cw_eplus(GATES[g]["azimut"], v["winddir"])
        qi = cw * A_TOR * U_REF          # F_Schedule = 1, Hoehendifferenz 0 -> Q_s = 0
        einzeln.append((g, cw, qi))
        q += qi
    return einzeln, q, q * 3600.0 / V_HALLE


def soll_afn(nr):
    """Geschlossene isotherme Loesung des Zwei-Oeffnungs-Netzwerks:
    b = 0, also Q = C_D * A * sqrt(2*|dP|/rho) je Oeffnung, Massenbilanz
    liefert bei gleicher Flaeche und gleicher Dichte dP_2 = -dP_5 = dCp*q_dyn/2.
    Bei Barriere zusaetzlich der Spalt in Reihe -> A_eff.
    Entspricht Blatt AFN_1Zone Zeile 32 bzw. AFN_2Zonen Zeile 36."""
    v = VARIANTS[nr]
    cp = CP_EPLUS[v["winddir"]]
    dcp = cp["sued"] - cp["nord"]
    r = rho(T_ISO)
    dp = dcp * 0.5 * r * U_REF ** 2
    q = CD * a_eff(v["barriere"]) * math.sqrt(2.0 * abs(dp) / r)
    return dcp, dp, q, q * 3600.0 / V_HALLE


# --------------------------------------------------------------- IDF-Bausteine
def fields(objtype, rows):
    """rows: Liste von (Wert, Kommentar). Erzeugt einen IDF-Objektblock."""
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


def druckanteile(barriere):
    """Aufteilung der Gesamtdruckdifferenz auf die Widerstaende in Reihe,
    Anteil proportional zu 1/A^2."""
    it = 1.0 / A_TOR ** 2
    isp = 1.0 / A_SPALT ** 2 if barriere else 0.0
    summe = 2.0 * it + isp
    return it / summe, (isp / summe if barriere else 0.0)


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


def block(title):
    return "\n!- " + "=" * 76 + "\n!-   " + title + "\n!- " + "=" * 76 + "\n\n"


# ----------------------------------------------------------------- Kopf/Basis
def kopf(dateiname, modell, nr, extra_zeilen, barriere_text=None):
    v = VARIANTS[nr]
    if barriere_text is None:
        barriere_text = "nein"
    L = ["! " + "=" * 78,
         "! %s" % dateiname,
         "! " + "=" * 78,
         "! Modellansatz      : %s" % modell,
         "! Variante          : %d - %s" % (nr, v["beschreibung"]),
         "! Offene Tore       : %s" % ", ".join("Tor %d" % g for g in v["tore"]),
         "! Innere Barriere   : %s" % barriere_text,
         "! Wetterdatei       : %s" % v["epw"],
         "! Windrichtung      : %s Grad (meteorologisch)" % num(v["winddir"], 1),
         "! Windgeschwindigk. : %s m/s in jeder Hoehe (flaches Profil, Exponent 0)" % num(U_REF),
         "!                     = %s * (%s/%s)^%s, Blatt Wetter" % (num(U10, 1), num(Z_REF, 1), num(Z_MET, 0), num(ALPHA, 2)),
         "! Randbedingung     : isotherm, T_aussen = T_zone = %s Grad C" % num(T_ISO, 1),
         "! EnergyPlus        : %s" % EPLUS_VERSION,
         "!",
         "! Werte aus Handrechnungen_neu.xlsx. Erzeugt von make_isotherm_varianten.py.",
         "! Keine Undichtheiten (kein AFN_Crack, kein ZoneInfiltration) und keine",
         "! internen Lasten: die Datei prueft ausschliesslich den Toranteil gegen die",
         "! Handrechnung.",
         "!"]
    L += ["! " + z for z in extra_zeilen]
    L += ["! " + "=" * 78, ""]
    return "\n".join(L) + "\n"


def basis(nr, zonen):
    """Alles, was in jeder Datei gleich ist. zonen: Liste von Zonendicts."""
    v = VARIANTS[nr]
    s = []

    s.append(block("VERSION, SIMULATIONCONTROL, BUILDING, TIMESTEP"))
    s.append(fields("Version", [(EPLUS_VERSION, "Version Identifier")]))
    s.append(fields("SimulationControl", [
        ("No", "Do Zone Sizing Calculation"), ("No", "Do System Sizing Calculation"),
        ("No", "Do Plant Sizing Calculation"), ("No", "Run Simulation for Sizing Periods"),
        ("Yes", "Run Simulation for Weather File Run Periods"),
        (None, "Do HVAC Sizing Simulation for Sizing Periods"),
        (None, "Maximum Number of HVAC Sizing Simulation Passes")]))
    s.append("!- North Axis 0: Gebaeude fest orientiert. Die Anstroemrichtung wird ueber\n"
             "!- die Wetterdatei gedreht, nicht ueber das Gebaeude - so bleiben Effective\n"
             "!- Angle und AFN-Azimut unveraendert und die Handrechnung vergleichbar.\n")
    s.append(fields("Building", [
        ("Halle_15x60x12", "Name"), ("0", "North Axis {deg}"), ("Country", "Terrain"),
        (None, "Loads Convergence Tolerance Value {W}"),
        (None, "Temperature Convergence Tolerance Value {deltaC}"),
        (None, "Solar Distribution"), (None, "Maximum Number of Warmup Days"),
        ("6", "Minimum Number of Warmup Days")]))
    s.append(fields("Timestep", [("4", "Number of Timesteps per Hour")]))

    s.append(block("SITE"))
    s.append(fields("Site:Location", [
        ("Muenchen_Bayern_DEU", "Name"), ("48.13", "Latitude {deg}"),
        ("11.70", "Longitude {deg}"), ("1", "Time Zone {hr}"), ("529", "Elevation {m}")]))
    s.append("!- Flaches Windprofil in beiden Objekten und Temperaturgradient 0.\n"
             "!- Nachgewiesen in Notiz_Windprofil_Verifikation_Sollwerte.md, Lauf B2:\n"
             "!- alle Zonen und alle External Nodes sehen u = u_EPW, Delta-T exakt 0.\n"
             "!- Site:WeatherStation ist bei Exponent 0 nicht zwingend (Lauf B1), wird\n"
             "!- aber gesetzt, damit das flache Profil explizit im Eingabefile steht.\n")
    s.append(fields("Site:WeatherStation", [
        ("10.0", "Wind Sensor Height Above Ground {m}"),
        ("0.0", "Wind Speed Profile Exponent"),
        (num(DELTA, 1), "Wind Speed Profile Boundary Layer Thickness {m}"),
        ("1.5", "Air Temperature Sensor Height Above Ground {m}")]))
    s.append(fields("Site:HeightVariation", [
        ("0.0", "Wind Speed Profile Exponent"),
        (num(DELTA, 1), "Wind Speed Profile Boundary Layer Thickness {m}"),
        ("0.0", "Air Temperature Gradient Coefficient {K/m}")]))
    s.append("!- Erdreichtemperatur = Zonentemperatur, damit der Boden keinen\n"
             "!- Waermestrom erzeugt und die Zone ohne Anlagenleistung isotherm bleibt.\n")
    s.append(fields("Site:GroundTemperature:BuildingSurface",
                    [(num(T_ISO, 1), "%s Ground Temperature {C}" % m) for m in
                     ["January", "February", "March", "April", "May", "June", "July",
                      "August", "September", "October", "November", "December"]]))

    s.append(block("RUNPERIOD"))
    s.append("!- Die Wetterdatei enthaelt genau einen Tag (15.01.) mit 24 identischen\n"
             "!- Stundenwerten. Auswertung an einem beliebigen Zeitschritt nach Warmup.\n")
    s.append(fields("RunPeriod", [
        ("Isotherm_15Jan", "Name"), ("1", "Begin Month"), ("15", "Begin Day of Month"),
        (None, "Begin Year"), ("1", "End Month"), ("15", "End Day of Month"),
        (None, "End Year"), ("Wednesday", "Day of Week for Start Day"),
        ("No", "Use Weather File Holidays and Special Days"),
        ("No", "Use Weather File Daylight Saving Period"),
        ("No", "Apply Weekend Holiday Rule"),
        ("No", "Use Weather File Rain Indicators"),
        ("No", "Use Weather File Snow Indicators")]))

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
        ("Sch_Tor_auf", "Name"), ("Fractional", "Schedule Type Limits Name"),
        ("1.0", "Hourly Value")]))
    s.append(fields("Schedule:Constant", [
        ("Sch_Tor_zu", "Name"), ("Fractional", "Schedule Type Limits Name"),
        ("0.0", "Hourly Value")]))
    s.append("!- Ein einziger Sollwert von %s Grad C, Regelungsart 3\n"
             "!- (SingleHeatingOrCooling): die Zone wird sowohl geheizt als auch gekuehlt\n"
             "!- und haelt damit exakt die Aussentemperatur. Nur so ist Delta-T = 0 und der\n"
             "!- Auftriebsterm sicher inaktiv.\n" % num(T_ISO, 1))
    s.append(fields("Schedule:Constant", [
        ("Sch_T_iso", "Name"), ("Temperature", "Schedule Type Limits Name"),
        (num(T_ISO, 1), "Hourly Value")]))
    s.append(fields("Schedule:Constant", [
        ("Sch_Regelungsart", "Name"), ("Control Type", "Schedule Type Limits Name"),
        ("3", "Hourly Value")]))

    s.append(block("MATERIALS AND CONSTRUCTIONS"))
    s.append("!- Uebernommen aus AFN_paper_Vorlage.idf. Im isothermen Fall ohne Wirkung\n"
             "!- (Delta-T = 0, keine Solarstrahlung in der Wetterdatei), aber erhalten,\n"
             "!- damit dieselbe Huelle im Heizperiodenlauf verwendet werden kann.\n")
    for name, rough, d, lam, dens, cp in [
            ("AW_IW_Obj30_Porenbeton", "MediumRough", 0.2032, 0.5, 464, 880),
            ("D_Obj14_Gipskarton", "MediumSmooth", 0.0159, 0.16, 800, 1090),
            ("B_Obj43_Beton", "MediumRough", 0.2032, 1.95, 2240, 900),
            ("AW_Obj91_Waermedaemmung", "Rough", 0.025, 0.0245, 24, 1590),
            ("D_Obj80_Daemmung", "MediumRough", 0.05, 0.036, 140, 960),
            ("D_Obj84_XPS", "MediumSmooth", 0.025, 0.029, 29, 1210),
            ("D_Obj8_Built-up roofing", "Rough", 0.0095, 0.16, 1120, 1460)]:
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
            ("Tor", ["Glazing_Tor"])]:
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

    s.append(block("ZONES"))
    for z in zonen:
        s.append(fields("Zone", [
            (z["name"], "Name"), ("0", "Direction of Relative North {deg}"),
            ("0", "X Origin {m}"), ("0", "Y Origin {m}"), ("0", "Z Origin {m}"),
            (None, "Type"), ("1", "Multiplier"), (num(LZ, 1), "Ceiling Height {m}"),
            (num(z["vol"], 1), "Volume {m3}"), (num(z["area"], 1), "Floor Area {m2}"),
            (None, "Zone Inside Convection Algorithm"),
            (None, "Zone Outside Convection Algorithm"),
            ("Yes", "Part of Total Floor Area")]))
    return "".join(s)


def geometrie(nr, zonen):
    """Huellflaechen und Tore. zonen wie in basis()."""
    v = VARIANTS[nr]
    # Die Barriere wird nur dort geometrisch abgebildet, wo das Modell sie auch
    # aufloesen kann - also im zweizonigen AirflowNetwork. In den einzonigen
    # Dateien existiert keine Trennflaeche.
    barriere_bauen = v["barriere"] and len(zonen) == 2
    s = [block("BUILDINGSURFACE:DETAILED")]

    for z in zonen:
        y0, y1, suffix, zn = z["y0"], z["y1"], z["suffix"], z["name"]
        s.append(surface("Boden" + suffix, "Floor", "Boden", zn, "Ground", None,
                         "NoSun", "NoWind", 1.0,
                         [(0, y0, 0), (0, y1, 0), (LX, y1, 0), (LX, y0, 0)]))
        s.append(surface("Dach" + suffix, "Roof", "Dach", zn, "Outdoors", None,
                         "SunExposed", "WindExposed", 0.0,
                         [(LX, y0, LZ), (LX, y1, LZ), (0, y1, LZ), (0, y0, LZ)]))
        s.append(surface("IW_West" + suffix, "Wall", "Innenwand", zn, "Adiabatic", None,
                         "NoSun", "NoWind", 0.0,
                         [(0, y0, LZ), (0, y1, LZ), (0, y1, 0), (0, y0, 0)]))
        s.append(surface("IW_Ost" + suffix, "Wall", "Innenwand", zn, "Adiabatic", None,
                         "NoSun", "NoWind", 0.0,
                         [(LX, y1, LZ), (LX, y0, LZ), (LX, y0, 0), (LX, y1, 0)]))
        if y0 == 0.0:
            s.append(surface("AW_Sued", "Wall", "Aussenwand", zn, "Outdoors", None,
                             "SunExposed", "WindExposed", 0.5,
                             [(LX, 0, LZ), (0, 0, LZ), (0, 0, 0), (LX, 0, 0)]))
        if y1 == LY:
            s.append(surface("AW_Nord", "Wall", "Aussenwand", zn, "Outdoors", None,
                             "SunExposed", "WindExposed", 0.5,
                             [(0, LY, LZ), (LX, LY, LZ), (LX, LY, 0), (0, LY, 0)]))

    if barriere_bauen:
        s.append("!- Innere Barriere bei y = %s m. Trennflaeche und Spalt als Paar\n"
                 "!- gekoppelter Flaechen (Outside Boundary Condition Surface).\n" % num(Y_BARRIERE, 1))
        s.append(surface("IW_Barriere_Sued", "Wall", "Innenwand", "Zone_Sued",
                         "Surface", "IW_Barriere_Nord", "NoSun", "NoWind", 0.0,
                         [(0, Y_BARRIERE, LZ), (LX, Y_BARRIERE, LZ),
                          (LX, Y_BARRIERE, 0), (0, Y_BARRIERE, 0)]))
        s.append(surface("IW_Barriere_Nord", "Wall", "Innenwand", "Zone_Nord",
                         "Surface", "IW_Barriere_Sued", "NoSun", "NoWind", 0.0,
                         [(LX, Y_BARRIERE, LZ), (0, Y_BARRIERE, LZ),
                          (0, Y_BARRIERE, 0), (LX, Y_BARRIERE, 0)]))

    s.append(block("FENESTRATIONSURFACE:DETAILED  (TORE)"))
    s.append("!- Alle sechs Tore sind in jeder Variante geometrisch vorhanden, damit die\n"
             "!- Huelle ueber alle Varianten identisch ist. Geoeffnet ist nur, was ein\n"
             "!- Lueftungsobjekt bzw. eine AirflowNetwork:MultiZone:Surface erhaelt.\n")
    for g in sorted(GATES):
        info = GATES[g]
        if info["wall"] == "AW_Sued":
            verts = [(info["x1"], 0, GATE_Z1), (info["x0"], 0, GATE_Z1),
                     (info["x0"], 0, GATE_Z0), (info["x1"], 0, GATE_Z0)]
        else:
            verts = [(info["x0"], LY, GATE_Z1), (info["x1"], LY, GATE_Z1),
                     (info["x1"], LY, GATE_Z0), (info["x0"], LY, GATE_Z0)]
        offen = " (offen in dieser Variante)" if g in v["tore"] else " (geschlossen)"
        s.append("!- Tor %d, %s, x = %s bis %s m, z = %s bis %s m, A = %s m2%s\n" % (
            g, info["wall"], num(info["x0"], 2), num(info["x1"], 2),
            num(GATE_Z0, 2), num(GATE_Z1, 2), num(A_TOR, 2), offen))
        s.append(fenestration("gate %d" % g, "Window", "Tor", info["wall"], None, verts))

    if barriere_bauen:
        s.append("!- Barrierenspalt: b = %s m, h = %s m, A = %s m2 (Soll 15,00 x 2,00 m).\n"
                 "!- Der Randabstand von 0,01 m links und rechts haelt die Unterflaeche\n"
                 "!- vollstaendig innerhalb der Basisflaeche; die Hoehe ist so nachgefuehrt,\n"
                 "!- dass die Flaeche exakt %s m2 bleibt. In die isotherme Gleichung geht\n"
                 "!- ausschliesslich A ein (b = 0, kein Auftrieb).\n" % (
                     num(SPALT_B, 3), num(SPALT_H, 6), num(SPALT_B * SPALT_H, 4),
                     num(A_SPALT, 2)))
        s.append(fenestration("Spalt_Sued", "Door", "Innenwand", "IW_Barriere_Sued",
                              "Spalt_Nord",
                              [(SPALT_X0, Y_BARRIERE, SPALT_H), (SPALT_X1, Y_BARRIERE, SPALT_H),
                               (SPALT_X1, Y_BARRIERE, 0), (SPALT_X0, Y_BARRIERE, 0)]))
        s.append(fenestration("Spalt_Nord", "Door", "Innenwand", "IW_Barriere_Nord",
                              "Spalt_Sued",
                              [(SPALT_X1, Y_BARRIERE, SPALT_H), (SPALT_X0, Y_BARRIERE, SPALT_H),
                               (SPALT_X0, Y_BARRIERE, 0), (SPALT_X1, Y_BARRIERE, 0)]))
    return "".join(s)


def anlage(zonen):
    """Thermostat und Ideal Loads je Zone, damit T_zone = T_aussen bleibt."""
    s = [block("THERMOSTAT UND IDEAL LOADS")]
    for z in zonen:
        zn, sfx = z["name"], z["suffix"]
        s.append(fields("ZoneControl:Thermostat", [
            ("Thermostat" + sfx, "Name"), (zn, "Zone or ZoneList Name"),
            ("Sch_Regelungsart", "Control Type Schedule Name"),
            ("ThermostatSetpoint:SingleHeatingOrCooling", "Control 1 Object Type"),
            ("Sollwert_iso" + sfx, "Control 1 Name")]))
        s.append(fields("ThermostatSetpoint:SingleHeatingOrCooling", [
            ("Sollwert_iso" + sfx, "Name"),
            ("Sch_T_iso", "Setpoint Temperature Schedule Name")]))
        s.append(fields("ZoneHVAC:IdealLoadsAirSystem", [
            ("IdealLoads" + sfx, "Name"), (None, "Availability Schedule Name"),
            ("Inlet_Node" + sfx, "Zone Supply Air Node Name"),
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
            ("EquipmentList" + sfx, "Name"), ("SequentialLoad", "Load Distribution Scheme"),
            ("ZoneHVAC:IdealLoadsAirSystem", "Zone Equipment 1 Object Type"),
            ("IdealLoads" + sfx, "Zone Equipment 1 Name"),
            ("1", "Zone Equipment 1 Cooling Sequence"),
            ("1", "Zone Equipment 1 Heating or No-Load Sequence"),
            (None, "Zone Equipment 1 Sequential Cooling Fraction Schedule Name"),
            (None, "Zone Equipment 1 Sequential Heating Fraction Schedule Name")]))
        s.append(fields("ZoneHVAC:EquipmentConnections", [
            (zn, "Zone Name"), ("EquipmentList" + sfx, "Zone Conditioning Equipment List Name"),
            ("Inlet_Node" + sfx, "Zone Air Inlet Node or NodeList Name"),
            (None, "Zone Air Exhaust Node or NodeList Name"),
            ("Zone_Node" + sfx, "Zone Air Node Name"),
            ("Return_Node" + sfx, "Zone Return Air Node or NodeList Name")]))
    return "".join(s)


def ausgabe(modelltyp, mixing=False):
    s = [block("OUTPUT")]
    s.append(fields("Output:VariableDictionary", [("IDF", "Key Field"), ("Unsorted", "Sort Option")]))
    s.append(fields("Output:Table:SummaryReports", [("AllSummary", "Report 1 Name")]))
    s.append(fields("OutputControl:Table:Style", [("HTML", "Column Separator")]))
    s.append(fields("Output:SQLite", [("SimpleAndTabular", "Option Type")]))
    s.append(fields("Output:Diagnostics", [
        ("DisplayAllWarnings", "Key 1"), ("DisplayAdvancedReportVariables", "Key 2")]))
    gemeinsam = [
        ("Site Wind Speed", "Timestep"),
        ("Site Wind Direction", "Timestep"),
        ("Site Outdoor Air Drybulb Temperature", "Timestep"),
        ("Zone Outdoor Air Wind Speed", "Timestep"),
        ("Zone Outdoor Air Drybulb Temperature", "Timestep"),
        ("Zone Mean Air Temperature", "Timestep"),
        ("Zone Ideal Loads Supply Air Total Heating Rate", "Timestep"),
        ("Zone Ideal Loads Supply Air Total Cooling Rate", "Timestep"),
    ]
    if modelltyp == "AFN":
        speziell = [
            ("AFN Zone Infiltration Air Change Rate", "Timestep"),
            ("AFN Zone Infiltration Volume", "Timestep"),
            ("AFN Zone Mixing Mass Flow Rate", "Timestep"),
            ("AFN Surface Venting Window or Door Opening Factor", "Timestep"),
            ("AFN Linkage Node 1 to Node 2 Volume Flow Rate", "Timestep"),
            ("AFN Linkage Node 2 to Node 1 Volume Flow Rate", "Timestep"),
            ("AFN Linkage Node 1 to Node 2 Pressure Difference", "Timestep"),
            ("AFN Node Total Pressure", "Timestep"),
        ]
    else:
        speziell = [
            ("Zone Ventilation Current Density Volume Flow Rate", "Timestep"),
            ("Zone Ventilation Standard Density Volume Flow Rate", "Timestep"),
            ("Zone Ventilation Current Density Air Change Rate", "Timestep"),
            ("Zone Ventilation Mass Flow Rate", "Timestep"),
            ("Zone Ventilation Sensible Heat Loss Energy", "Timestep"),
        ]
        if mixing:
            speziell += [
                ("Zone Mixing Current Density Volume Flow Rate", "Timestep"),
                ("Zone Mixing Standard Density Volume Flow Rate", "Timestep"),
                ("Zone Mixing Mass Flow Rate", "Timestep"),
                ("Zone Mixing Sensible Heat Loss Energy", "Timestep"),
                ("Zone Mixing Sensible Heat Gain Energy", "Timestep"),
            ]
    if modelltyp == "AFN":
        s.append("!- Massgebend fuer den Vergleich mit der Handrechnung:\n"
                 "!- AFN Linkage Node 1 to Node 2 Volume Flow Rate der Verknuepfung des\n"
                 "!- luvseitigen Tores (gate 2). AFN Zone Infiltration Air Change Rate\n"
                 "!- bezieht sich auf das Zonenvolumen, in den zweizonigen Dateien also\n"
                 "!- auf 5400 m3 und nicht auf die ganze Halle.\n")
    else:
        s.append("!- Massgebend fuer den Vergleich mit der Handrechnung:\n"
                 "!- Zone Ventilation CURRENT Density Volume Flow Rate. Das Feld\n"
                 "!- Density Basis bleibt leer, Default Outdoor, also ist der Massenstrom\n"
                 "!- Q_soll * rho_aussen. Bei T_zone = T_aussen ist rho_zone = rho_aussen\n"
                 "!- und die Current-Density-Variante trifft Q_soll. Die\n"
                 "!- Standard-Density-Variante rechnet auf die Normdichte der\n"
                 "!- Standardatmosphaere um und liegt rund 1 Prozent daneben - das ist\n"
                 "!- keine Modellabweichung, sondern eine Dichteumrechnung.\n")
    s.append("!- Falls eine Variable in eplusout.err als unbekannt gemeldet wird, den\n"
             "!- Namen aus eplusout.rdd uebernehmen - Output:VariableDictionary ist aktiv.\n")
    for name, freq in gemeinsam + speziell:
        s.append(fields("Output:Variable", [
            ("*", "Key Value"), (name, "Variable Name"), (freq, "Reporting Frequency")]))
    return "".join(s)


# ----------------------------------------------------------- Zonendefinitionen
def zonen_fuer(nr):
    if VARIANTS[nr]["barriere"] and VARIANTS[nr].get("_zweizonig", True):
        return [dict(name="Zone_Sued", suffix="_Sued", y0=0.0, y1=Y_BARRIERE,
                     vol=V_HALLE / 2, area=LX * Y_BARRIERE),
                dict(name="Zone_Nord", suffix="_Nord", y0=Y_BARRIERE, y1=LY,
                     vol=V_HALLE / 2, area=LX * (LY - Y_BARRIERE))]
    return [dict(name="Zone_Halle", suffix="", y0=0.0, y1=LY,
                 vol=V_HALLE, area=LX * LY)]


def zonen_einzonig():
    return [dict(name="Zone_Halle", suffix="", y0=0.0, y1=LY,
                 vol=V_HALLE, area=LX * LY)]


def zonen_zweizonig():
    return [dict(name="Zone_Sued", suffix="_Sued", y0=0.0, y1=Y_BARRIERE,
                 vol=V_HALLE / 2, area=LX * Y_BARRIERE),
            dict(name="Zone_Nord", suffix="_Nord", y0=Y_BARRIERE, y1=LY,
                 vol=V_HALLE / 2, area=LX * (LY - Y_BARRIERE))]


def zone_des_tors(g, zweizonig):
    if not zweizonig:
        return "Zone_Halle"
    return "Zone_Sued" if GATES[g]["wall"] == "AW_Sued" else "Zone_Nord"


def crossmixing(q):
    """ZoneCrossMixing zwischen den beiden Hallenhaelften.

    Quelle: Input Output Reference 25.2, Abschn. 1.17.8, S. 656-658.
    - Das Objekt tauscht in beide Richtungen dieselbe Menge aus und haelt
      Massen- und Energiebilanz beider Zonen. Bei gleicher Zonentemperatur
      transportiert es deshalb weder Energie noch Feuchte: unter isothermen
      Randbedingungen aendert es das Ergebnis nicht. Es steht hier, damit die
      Zonentopologie mit den AFN-Dateien uebereinstimmt und die Datei ohne
      Aenderung in den Heizperiodenlauf uebernommen werden kann.
    - Delta Temperature = 0: "If this field is zero, mixing occurs regardless
      of the relative air temperatures." Negative Werte sind hier - anders als
      bei ZoneVentilation - nicht zulaessig.
    - Das Objekt kommt genau EINMAL vor. Zweimal (je Zone) waere nur bei
      Delta Temperature > 0 sinnvoll und wuerde den Austausch hier verdoppeln.
    """
    s = [block("ZONECROSSMIXING")]
    s.append("!- Design Flow Rate = %s m3/s, also derselbe Volumenstrom, den das\n"
             "!- Lueftungsobjekt dieser Datei erzeugt. Quellzone ist die luvseitige\n"
             "!- Haelfte (Tor 2), Empfaengerzone die leeseitige (Tor 5).\n" % num(q, 6))
    s.append(fields("ZoneCrossMixing", [
        ("Spalt_CrossMixing", "Name"),
        ("Zone_Nord", "Zone or Space Name"),
        ("Sch_Tor_auf", "Schedule Name"),
        ("Flow/Zone", "Design Flow Rate Calculation Method"),
        (num(q, 6), "Design Flow Rate {m3/s}"),
        (None, "Flow Rate per Floor Area {m3/s-m2}"),
        (None, "Flow Rate per Person {m3/s-person}"),
        (None, "Air Changes per Hour {1/hr}"),
        ("Zone_Sued", "Source Zone or Space Name"),
        ("0.0", "Delta Temperature {deltaC}")]))
    return "".join(s)


# ------------------------------------------------------------------- AFN-Datei
def idf_afn(nr):
    v = VARIANTS[nr]
    zonen = zonen_fuer(nr)
    dcp, dp, q, ach = soll_afn(nr)
    cp = CP_EPLUS[v["winddir"]]

    extra = [
        "Sollwerte fuer die Verifikation (Blatt AFN_1Zone bzw. AFN_2Zonen):",
        "  C_p AW_Sued (Tor 2)      = %s   (von EnergyPlus selbst berechnet)" % num(cp["sued"], 3),
        "  C_p AW_Nord (Tor 4/5)    = %s" % num(cp["nord"], 3),
        "  Delta C_p                = %s" % num(dcp, 4),
        "  Staudruck 0,5*rho*u^2    = %s Pa (rho = %s kg/m3 bei %s Grad C, %s Pa)" % (
            num(0.5 * rho(T_ISO) * U_REF ** 2, 4), num(rho(T_ISO), 5),
            num(T_ISO, 1), num(P_STAT, 0)),
        "  Gesamtdruckdifferenz     = %s Pa" % num(abs(dp), 4),
        "  davon je Tor             = %s Pa" % num(abs(dp) * druckanteile(v["barriere"])[0], 4),
    ] + ([
        "  davon am Spalt           = %s Pa" % num(abs(dp) * druckanteile(True)[1], 4),
    ] if v["barriere"] else []) + [
        "  A_eff (Reihenschaltung)  = %s m2" % num(a_eff(v["barriere"]), 5),
        "  Q_vent                   = %s m3/s" % num(q, 4),
        "  Luftwechsel (V = %s m3) = %s 1/h" % (num(V_HALLE, 0), num(ach, 4)),
    ]
    if v["barriere"]:
        extra += ["  Der Luftwechsel bezieht sich auf das Gesamtvolumen. Die beiden Zonen",
                  "  fuehren je 5400 m3; EnergyPlus gibt AFN Zone Infiltration je Zone aus."]
    btxt = ("ja, zwei Zonen, Spalt als Oeffnung b = %s m, h = %s m, A = %s m2"
            % (num(SPALT_B, 3), num(SPALT_H, 5), num(SPALT_B * SPALT_H, 2))
            ) if v["barriere"] else "nein"
    s = [kopf("AFN_E+_%d.idf" % nr,
              "AirflowNetwork, MultiZone:Component:DetailedOpening, "
              "Winddruckbeiwerte SurfaceAverageCalculation", nr, extra, btxt)]
    s.append(basis(nr, zonen))
    s.append(geometrie(nr, zonen))
    s.append(anlage(zonen))

    s.append(block("AIRFLOWNETWORK"))
    s.append("!- Wind Pressure Coefficient Type = SurfaceAverageCalculation: EnergyPlus\n"
             "!- berechnet die Winddruckbeiwerte selbst nach Swami und Chandra (1988).\n"
             "!- Azimuth Angle of Long Axis = 0 Grad (Laengsachse Nord-Sued),\n"
             "!- Ratio Short/Long = %s (%s m / %s m).\n"
             "!- Allow Unsupported Zone Equipment = No: das Feld schaltet nur\n"
             "!- ZoneHVAC:Dehumidifier, ZoneHVAC:EnergyRecoveryVentilator und\n"
             "!- WaterHeater:HeatPump frei und wird ausserdem nur im Zweig mit\n"
             "!- Luftverteilung geprueft. ZoneHVAC:IdealLoadsAirSystem ist mit\n"
             "!- MultizoneWithoutDistribution ohne Sonderfreigabe zulaessig.\n"
             "!- Height Selection for Local Wind Pressure Calculation wird bei\n"
             "!- SurfaceAverageCalculation nicht ausgewertet; das Feld ist nur belegt,\n"
             "!- weil es beim Wechsel auf Wind Pressure Coefficient Type = Input\n"
             "!- (Varianten AFN_DIN und AFN_CFD_*) gebraucht wird.\n" % (
                 num(LX / LY, 2), num(LX, 0), num(LY, 0)))
    s.append(fields("AirflowNetwork:SimulationControl", [
        ("AFN_Isotherm", "Name"),
        ("MultizoneWithoutDistribution", "AirflowNetwork Control"),
        ("SurfaceAverageCalculation", "Wind Pressure Coefficient Type"),
        ("ExternalNode", "Height Selection for Local Wind Pressure Calculation"),
        ("LowRise", "Building Type"),
        ("500", "Maximum Number of Iterations {dimensionless}"),
        ("LinearInitializationMethod", "Initialization Type"),
        ("0.0001", "Relative Airflow Convergence Tolerance {dimensionless}"),
        ("0.000001", "Absolute Airflow Convergence Tolerance {kg/s}"),
        ("-0.5", "Convergence Acceleration Limit {dimensionless}"),
        ("0", "Azimuth Angle of Long Axis of Building {deg}"),
        (num(LX / LY, 4), "Ratio of Building Width Along Short Axis to Width Along Long Axis"),
        ("No", "Height Dependence of External Node Temperature"),
        ("SkylineLU", "Solver"),
        ("No", "Allow Unsupported Zone Equipment"),
        ("No", "Do Distribution Duct Sizing Calculation")]))
    for z in zonen:
        s.append(fields("AirflowNetwork:MultiZone:Zone", [
            (z["name"], "Zone Name"), ("Constant", "Ventilation Control Mode"),
            (None, "Ventilation Control Zone Temperature Setpoint Schedule Name"),
            (None, "Minimum Venting Open Factor {dimensionless}"),
            ("0", "Indoor and Outdoor Temperature Difference Lower Limit For Maximum Venting Open Factor {deltaC}"),
            ("100", "Indoor and Outdoor Temperature Difference Upper Limit for Minimum Venting Open Factor {deltaC}"),
            ("0", "Indoor and Outdoor Enthalpy Difference Lower Limit For Maximum Venting Open Factor {deltaJ/kg}"),
            ("300000", "Indoor and Outdoor Enthalpy Difference Upper Limit for Minimum Venting Open Factor {deltaJ/kg}")]))

    s.append("!- Nur die in dieser Variante geoeffneten Tore sind Bestandteil des\n"
             "!- Netzwerks. Die geschlossenen Tore und die Restwandflaechen erhalten kein\n"
             "!- Objekt, damit ausser den Toren kein einziger Stroemungspfad existiert.\n")
    for g in v["tore"]:
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
            ("Sch_Tor_auf", "Venting Availability Schedule Name"),
            (None, "Occupant Ventilation Control Name"),
            ("PolygonHeight", "Equivalent Rectangle Method"),
            ("1", "Equivalent Rectangle Aspect Ratio {dimensionless}")]))
    if v["barriere"]:
        s.append(fields("AirflowNetwork:MultiZone:Surface", [
            ("Spalt_Sued", "Surface Name"), ("AFN_Spalt", "Leakage Component Name"),
            (None, "External Node Name"),
            ("1", "Window/Door Opening Factor, or Crack Factor {dimensionless}"),
            ("Constant", "Ventilation Control Mode"),
            (None, "Ventilation Control Zone Temperature Setpoint Schedule Name"),
            (None, "Minimum Venting Open Factor {dimensionless}"),
            (None, "Indoor and Outdoor Temperature Difference Lower Limit For Maximum Venting Open Factor {deltaC}"),
            ("100", "Indoor and Outdoor Temperature Difference Upper Limit for Minimum Venting Open Factor {deltaC}"),
            (None, "Indoor and Outdoor Enthalpy Difference Lower Limit For Maximum Venting Open Factor {deltaJ/kg}"),
            ("300000", "Indoor and Outdoor Enthalpy Difference Upper Limit for Minimum Venting Open Factor {deltaJ/kg}"),
            ("Sch_Tor_auf", "Venting Availability Schedule Name"),
            (None, "Occupant Ventilation Control Name"),
            ("PolygonHeight", "Equivalent Rectangle Method"),
            ("1", "Equivalent Rectangle Aspect Ratio {dimensionless}")]))

    s.append("!- Durchflussbeiwert C_D = %s bei Opening Factor 2 (voll offen), Wert aus\n"
             "!- der Excel. Der geschlossene Zustand wird nie angefahren\n"
             "!- (Venting Availability = 1, Ventilation Control Mode = Constant); die\n"
             "!- Felder fuer Opening Factor 1 sind deshalb nur formal belegt.\n" % num(CD, 2))
    s.append(fields("AirflowNetwork:MultiZone:Component:DetailedOpening", [
        ("AFN_Tor", "Name"),
        ("0.001", "Air Mass Flow Coefficient When Opening is Closed {kg/s-m}"),
        ("0.65", "Air Mass Flow Exponent When Opening is Closed {dimensionless}"),
        ("NonPivoted", "Type of Rectangular Large Vertical Opening (LVO)"),
        ("0", "Extra Crack Length or Height of Pivoting Axis {m}"),
        ("2", "Number of Sets of Opening Factor Data"),
        ("0", "Opening Factor 1 {dimensionless}"),
        ("0.001", "Discharge Coefficient for Opening Factor 1 {dimensionless}"),
        ("0", "Width Factor for Opening Factor 1 {dimensionless}"),
        ("0", "Height Factor for Opening Factor 1 {dimensionless}"),
        ("0", "Start Height Factor for Opening Factor 1 {dimensionless}"),
        ("1", "Opening Factor 2 {dimensionless}"),
        (num(CD, 2), "Discharge Coefficient for Opening Factor 2 {dimensionless}"),
        ("1", "Width Factor for Opening Factor 2 {dimensionless}"),
        ("1", "Height Factor for Opening Factor 2 {dimensionless}"),
        ("0", "Start Height Factor for Opening Factor 2 {dimensionless}")]))
    if v["barriere"]:
        s.append("!- Barrierenspalt als Oeffnung mit demselben C_D = %s, nicht als\n"
                 "!- Surface:Crack. Nur so entspricht der innere Widerstand der\n"
                 "!- Handrechnung Q = C_D * A_Spalt * sqrt(2*dP/rho) (Blatt AFN_2Zonen\n"
                 "!- Zeile 66).\n" % num(CD, 2))
        s.append(fields("AirflowNetwork:MultiZone:Component:DetailedOpening", [
            ("AFN_Spalt", "Name"),
            ("0.001", "Air Mass Flow Coefficient When Opening is Closed {kg/s-m}"),
            ("0.65", "Air Mass Flow Exponent When Opening is Closed {dimensionless}"),
            ("NonPivoted", "Type of Rectangular Large Vertical Opening (LVO)"),
            ("0", "Extra Crack Length or Height of Pivoting Axis {m}"),
            ("2", "Number of Sets of Opening Factor Data"),
            ("0", "Opening Factor 1 {dimensionless}"),
            ("0.001", "Discharge Coefficient for Opening Factor 1 {dimensionless}"),
            ("0", "Width Factor for Opening Factor 1 {dimensionless}"),
            ("0", "Height Factor for Opening Factor 1 {dimensionless}"),
            ("0", "Start Height Factor for Opening Factor 1 {dimensionless}"),
            ("1", "Opening Factor 2 {dimensionless}"),
            (num(CD, 2), "Discharge Coefficient for Opening Factor 2 {dimensionless}"),
            ("1", "Width Factor for Opening Factor 2 {dimensionless}"),
            ("1", "Height Factor for Opening Factor 2 {dimensionless}"),
            ("0", "Start Height Factor for Opening Factor 2 {dimensionless}")]))
    s.append(ausgabe("AFN"))
    return "".join(s)


# ------------------------------------------------------------------ WSOA-Datei
def idf_wsoa(nr, zweizonig=False):
    v = VARIANTS[nr]
    zonen = zonen_zweizonig() if zweizonig else zonen_einzonig()
    einzeln, q, ach = soll_wsoa(nr)
    extra = ["Sollwerte fuer die Verifikation (Blatt WindandStackOpenArea):"]
    for g, cw, qi in einzeln:
        extra.append("  Tor %d: Effective Angle %s Grad, ang = %s Grad, C_w = %s, "
                     "Q = %s m3/s" % (g, num(GATES[g]["azimut"], 1),
                                      num(cw_ang(GATES[g]["azimut"], v["winddir"]), 1),
                                      num(cw, 5), num(qi, 4)))
    extra += [
        "  Q_vent gesamt            = %s m3/s" % num(q, 4),
        "  Luftwechsel (V = %s m3) = %s 1/h" % (num(V_HALLE, 0), num(ach, 4)),
        "",
        "C_w folgt dem tatsaechlich implementierten Gesetz. In der Quelle steht der",
        "Anstroemwinkel erst auf 0 bis 180 Grad gefaltet:",
        "  ang = 180 - | |WindDirection - EffectiveAngle| - 180 |",
        "  C_w = 0                              fuer ang > 90 Grad",
        "  C_w = 0,55 + ang * (0,30 - 0,55)/45  sonst",
        "Nicht Gleichung 8.7 der Engineering Reference (Nachweis in",
        "Notiz_Cw_Fehler_EngineeringReference.md). Fuer die hier auftretenden Winkel",
        "ist das gleichbedeutend mit MAX(0 ; 0,55 - (delta/45)*0,25); allgemein gilt",
        "diese Kurzform wegen der Faltung nicht. Das leeseitige Tor liefert null,",
        "weil das Objekt kein Druckgefaelle zwischen den Oeffnungen kennt.",
    ]
    if v["barriere"] and zweizonig:
        extra += ["",
                  "Zweizonige Fassung: Trennflaeche bei y = 30 m, Tor 2 in Zone_Sued,",
                  "Tor 5 in Zone_Nord, beide Zonen ueber ZoneCrossMixing mit",
                  "%s m3/s verbunden. WindandStackOpenArea selbst kennt keine" % num(q, 4),
                  "Zonenkopplung; der Spalt ist geometrisch vorhanden, traegt aber keinen",
                  "Volumenstrom, sondern wird durch das CrossMixing vertreten.",
                  "ZoneCrossMixing ist massen- und energiebilanziert und tauscht in beide",
                  "Richtungen dieselbe Menge. Bei gleicher Zonentemperatur transportiert es",
                  "null Energie - das Ergebnis ist deshalb identisch mit der einzonigen",
                  "Fassung WSOA_%d_1Zone.idf. Der Nutzen liegt in der Vergleichbarkeit mit" % nr,
                  "AFN_E+_%d.idf und in der Uebertragbarkeit in den Heizperiodenlauf." % nr]
    elif v["barriere"]:
        extra += ["",
                  "Einzonige Fassung zum Vergleich mit der zweizonigen WSOA_%d.idf." % nr,
                  "Die innere Barriere ist in diesem Objekttyp nicht abbildbar: es gibt",
                  "keine Zonenkopplung. Ergebnis identisch mit den Varianten ohne",
                  "Barriere. Das ist ein Befund, kein Modellierungsfehler."]
    if v["barriere"] and zweizonig:
        btxt = "ja, zwei Zonen, Kopplung ueber ZoneCrossMixing mit %s m3/s" % num(q, 4)
    elif v["barriere"]:
        btxt = "vorhanden, in dieser Fassung nicht abgebildet - einzonig, keine Trennflaeche"
    else:
        btxt = "nein"
    s = [kopf("WSOA_%d%s.idf" % (nr, "" if zweizonig or not v["barriere"] else "_1Zone"),
              "ZoneVentilation:WindandStackOpenArea, Opening Effectiveness Autocalculate",
              nr, extra, btxt)]
    s.append(basis(nr, zonen))
    s.append(geometrie(nr, zonen))
    s.append(anlage(zonen))

    s.append(block("ZONEVENTILATION:WINDANDSTACKOPENAREA"))
    s.append("!- Ein Objekt je geoeffnetem Tor. Height Difference = 0, weil beide Tore auf\n"
             "!- gleicher Hoehe sitzen und die neutrale Ebene damit in Toroeffnungsmitte\n"
             "!- liegt - der Auftriebsterm ist strukturell null.\n"
             "!- Discharge Coefficient = Autocalculate ergibt 0,40 + 0,0045*|dT| = 0,40;\n"
             "!- ohne Wirkung, da Height Difference = 0.\n"
             "!- Delta Temperature = -100 K und die Temperaturgrenzen +/-100 Grad C\n"
             "!- verhindern, dass das Objekt bei dT = 0 auf der Abschaltschwelle liegt.\n")
    for g, cw, qi in einzeln:
        s.append("!- Tor %d in %s: C_w = %s, Q_soll = %s m3/s\n" % (
            g, GATES[g]["wall"], num(cw, 5), num(qi, 4)))
        s.append(fields("ZoneVentilation:WindandStackOpenArea", [
            ("WSOA_Tor%d" % g, "Name"), (zone_des_tors(g, zweizonig), "Zone or Space Name"),
            (num(A_TOR, 2), "Opening Area {m2}"),
            ("Sch_Tor_auf", "Opening Area Fraction Schedule Name"),
            ("Autocalculate", "Opening Effectiveness"),
            (num(GATES[g]["azimut"], 1), "Effective Angle {deg}"),
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
    if zweizonig:
        s.append(crossmixing(q))
    s.append(ausgabe("VENT", mixing=zweizonig))
    return "".join(s)


# ------------------------------------------------------------------- DFR-Datei
def idf_dfr(nr, setname, zweizonig=False):
    v = VARIANTS[nr]
    st = DFR_SETS[setname]
    zonen = zonen_zweizonig() if zweizonig else zonen_einzonig()
    vdes, q, ach = soll_dfr(nr, setname)
    k = k_faktor(v)
    q_soll = k * U_REF
    extra = [
        "Sollwerte fuer die Verifikation (Blatt DesignFlowRate):",
        "  A_eff (Reihenschaltung)  = %s m2" % num(a_eff(v["barriere"]), 5),
        "  Anstroemwinkel theta     = %s Grad, cos theta = %s" % (
            num(theta(v["winddir"]), 1), num(math.cos(math.radians(theta(v["winddir"]))), 5)),
        "  k = C_D * A_eff * cos    = %s m2" % num(k, 5),
        "  Normierungsgeschw. u_ref = %s m/s" % num(dfr_uref(st), 5),
        "  Design Flow Rate         = k * u_ref = %s m3/s" % num(vdes, 5),
        "  Koeffizientenpolynom     = %s bei u = %s m/s und dT = 0" % (
            num(dfr_poly(st, U_REF), 5), num(U_REF, 5)),
        "  Q_vent                   = %s m3/s" % num(q, 4),
        "  Luftwechsel (V = %s m3) = %s 1/h" % (num(V_HALLE, 0), num(ach, 4)),
        "  Referenz Q_soll = k * u   = %s m3/s  ->  Abweichung %s Prozent" % (
            num(q_soll, 4), num(100.0 * (q / q_soll - 1.0), 2)),
        "",
        "ZoneVentilation:DesignFlowRate enthaelt keinen Windrichtungsterm. Der",
        "Unterschied zwischen den Varianten 1-3 und 4-6 steckt ausschliesslich im",
        "handgerechneten Design Flow Rate ueber cos theta, nicht in einer Rechnung",
        "von EnergyPlus. Die Wetterdatei liefert hier nur die Windgeschwindigkeit.",
    ]
    if v["barriere"] and zweizonig:
        extra += ["",
                  "Die innere Barriere steckt im Volumenstrom allein in",
                  "A_eff = %s m2 statt %s m2 (Spalt 30 m2 in Reihe)."
                  % (num(a_eff(True), 5), num(a_eff(False), 5)),
                  "Zweizonige Fassung: Trennflaeche bei y = 30 m; das einzige",
                  "ZoneVentilation:DesignFlowRate-Objekt sitzt mit dem vollen",
                  "Design Flow Rate in der luvseitigen Zone_Sued (Tor 2), Zone_Nord",
                  "erhaelt keinen direkten Aussenluftaustausch. Beide Zonen sind ueber",
                  "ZoneCrossMixing mit %s m3/s verbunden. Damit bleibt der" % num(q, 4),
                  "Aussenluftaustausch der Halle exakt Q_vent und trifft die Handrechnung.",
                  "ZoneCrossMixing tauscht in beide Richtungen dieselbe Menge und ist",
                  "energiebilanziert; bei gleicher Zonentemperatur transportiert es null",
                  "Energie. Das Ergebnis ist deshalb identisch mit der einzonigen Fassung",
                  "DFR_%s_%d_1Zone.idf." % (setname, nr)]
    elif v["barriere"]:
        extra += ["",
                  "Einzonige Fassung zum Vergleich mit der zweizonigen",
                  "DFR_%s_%d.idf. Die innere Barriere steckt allein in" % (setname, nr),
                  "A_eff = %s m2 statt %s m2 (Spalt 30 m2 in Reihe)."
                  % (num(a_eff(True), 5), num(a_eff(False), 5))]
    if v["barriere"] and zweizonig:
        btxt = ("ja, zwei Zonen, Kopplung ueber ZoneCrossMixing mit %s m3/s; im "
                "Volumenstrom ueber A_eff = %s m2" % (num(q, 4), num(a_eff(True), 5)))
    elif v["barriere"]:
        btxt = ("nur ueber A_eff = %s m2 im Design Flow Rate - einzonig, "
                "keine Trennflaeche" % num(a_eff(True), 5))
    else:
        btxt = "nein"
    s = [kopf("DFR_%s_%d%s.idf" % (setname, nr,
                                   "" if zweizonig or not v["barriere"] else "_1Zone"),
              "ZoneVentilation:DesignFlowRate, %s" % st["quelle"], nr, extra, btxt)]
    s.append(basis(nr, zonen))
    s.append(geometrie(nr, zonen))
    s.append(anlage(zonen))

    s.append(block("ZONEVENTILATION:DESIGNFLOWRATE"))
    s.append(("!- Koeffizientensatz %s: A = %s, B = %s 1/K, C = %s s/m, D = %s s2/m2\n"
              "!- Q_vent = Design Flow Rate * F_Schedule * (A + B*|dT| + C*u + D*u^2)\n"
              "!- Ein einziges Objekt fuer beide Tore: das Modell bilanziert den\n"
              "!- Durchsatz der Halle, nicht die Einzeloeffnung.\n" % (
                  setname, num(st["A"], 5), num(st["B"], 5), num(st["C"], 5), num(st["D"], 5)))
             + ("!- Es sitzt in der luvseitigen Zone_Sued; Zone_Nord erhaelt den Zustrom\n"
                "!- ausschliesslich ueber ZoneCrossMixing.\n" if zweizonig else ""))
    s.append(fields("ZoneVentilation:DesignFlowRate", [
        ("DFR_%s" % setname, "Name"),
        ("Zone_Sued" if zweizonig else "Zone_Halle", "Zone or ZoneList or Space or SpaceList Name"),
        ("Sch_Tor_auf", "Schedule Name"),
        ("Flow/Zone", "Design Flow Rate Calculation Method"),
        (num(vdes, 6), "Design Flow Rate {m3/s}"),
        (None, "Flow Rate per Floor Area {m3/s-m2}"),
        (None, "Flow Rate per Person {m3/s-person}"),
        (None, "Air Changes per Hour {1/hr}"),
        ("Natural", "Ventilation Type"),
        ("0.0", "Fan Pressure Rise {Pa}"),
        ("1.0", "Fan Total Efficiency"),
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
    if zweizonig:
        s.append(crossmixing(q))
    s.append(ausgabe("VENT", mixing=zweizonig))
    return "".join(s)


# ------------------------------------------------------------------ Wetterdatei
def wetterdatei(quelle, ziel, winddir, ordner):
    with open(quelle, "r", encoding="latin-1") as f:
        zeilen = f.read().splitlines()
    out = []
    for i, z in enumerate(zeilen):
        if i == 0:
            teile = z.split(",")
            teile[4] = "Custom-Isotherm-u5072-%s" % ("WSW2475" if winddir == 247.5 else "SSE1575")
            out.append(",".join(teile))
        elif z.startswith("COMMENTS 2"):
            out.append(
                'COMMENTS 2,"Erstellt am 2026-08-06 aus %s. EINZIGE Aenderung gegenueber '
                'der Quelldatei: Windgeschwindigkeit von 6.5 m/s auf %.6f m/s gesetzt. '
                'Begruendung: %.6f m/s ist die aus der Heizperiodenauswertung abgeleitete '
                'Anstroemgeschwindigkeit auf Bezugshoehe 1.7 m, 6.5*(1.7/10)^0.14. In den '
                'zugehoerigen IDF-Dateien stehen Site:WeatherStation und '
                'Site:HeightVariation auf Windprofilexponent 0 und Temperaturgradient 0; '
                'damit gilt diese Geschwindigkeit in jeder Hoehe und die Objekte '
                'ZoneVentilation (Auswertung am Zonenschwerpunkt 6.0 m), '
                'WindandStackOpenArea und die AirflowNetwork-External-Nodes sehen '
                'denselben Wert wie die Handrechnung. Windrichtung %.1f Grad unveraendert. '
                'Solar- und Beleuchtungsfelder 0, Aussentemperatur 17 Grad C fuer '
                'Delta-T = 0 - beides aus der Quelldatei uebernommen. Datum 15.1.1986 '
                'symbolisch, RunPeriod in der IDF entsprechend gesetzt."' % (
                    os.path.basename(quelle), U_REF, U_REF, winddir))
        elif i >= 8 and z.strip():
            f_ = z.split(",")
            f_[20] = "%.1f" % winddir
            f_[21] = "%.6f" % U_REF
            out.append(",".join(f_))
        else:
            out.append(z)
    with open(os.path.join(ordner, ziel), "w", encoding="latin-1", newline="\r\n") as f:
        f.write("\n".join(out) + "\n")


# ------------------------------------------------------------------------- main
def main():
    quelle = "/mnt/user-data/uploads/work/M13/CLAUDE/Masterarbeit/EnergyPlus"
    ziel = "/home/claude/isotherm/Isotherm_Varianten_1-6"
    if os.path.isdir(ziel):
        shutil.rmtree(ziel)
    os.makedirs(ziel)

    wetterdatei(os.path.join(quelle, "DEU_Munich.108660_Isotherm-CFDvergleich-WSW_0.epw"),
                EPW_WSW, 247.5, ziel)
    wetterdatei(os.path.join(quelle, "DEU_Munich.108660_Isotherm-CFDvergleich-SSE_90.epw"),
                EPW_SSE, 157.5, ziel)

    tabelle = []
    for nr in sorted(VARIANTS):
        v = VARIANTS[nr]
        with open(os.path.join(ziel, "AFN_E+_%d.idf" % nr), "w", encoding="latin-1") as f:
            f.write(idf_afn(nr))
        dcp, dp, q, ach = soll_afn(nr)
        tabelle.append(dict(Datei="AFN_E+_%d.idf" % nr, Modell="AFN_E+", Variante=nr,
                            Wetterdatei=v["epw"], Zonen=len(zonen_fuer(nr)),
                            Tore="+".join(str(g) for g in v["tore"]),
                            Barriere="ja" if v["barriere"] else "nein",
                            Kennwert="Delta C_p = %.4f" % dcp,
                            Q_soll=round(q, 5), ACH_soll=round(ach, 5),
                            Ausgabevariable="AFN Linkage Node 1 to Node 2 Volume Flow Rate (gate 2)"))

        # Bei Barriere zwei Fassungen: zweizonig mit ZoneCrossMixing (Hauptdatei)
        # und einzonig als Vergleich (_1Zone).
        fassungen = [True, False] if v["barriere"] else [False]
        einzeln, q, ach = soll_wsoa(nr)
        for zz in fassungen:
            suffix = "" if (zz or not v["barriere"]) else "_1Zone"
            name = "WSOA_%d%s.idf" % (nr, suffix)
            with open(os.path.join(ziel, name), "w", encoding="latin-1") as f:
                f.write(idf_wsoa(nr, zweizonig=zz))
            tabelle.append(dict(Datei=name, Modell="WSOA", Variante=nr,
                                Wetterdatei=v["epw"], Zonen=2 if zz else 1,
                                Tore="+".join(str(g) for g in v["tore"]),
                                Barriere=("ZoneCrossMixing %.5f m3/s" % q) if zz else (
                                    "nicht abgebildet" if v["barriere"] else "nein"),
                                Kennwert="C_w = " + " / ".join("%.5f" % c for _, c, _ in einzeln),
                                Q_soll=round(q, 5), ACH_soll=round(ach, 5),
                                Ausgabevariable="Zone Ventilation Current Density Volume Flow Rate"))

        for setname in ["DEFAULT", "BLAST", "DOE-2"]:
            vdes, q, ach = soll_dfr(nr, setname)
            for zz in fassungen:
                suffix = "" if (zz or not v["barriere"]) else "_1Zone"
                name = "DFR_%s_%d%s.idf" % (setname, nr, suffix)
                with open(os.path.join(ziel, name), "w", encoding="latin-1") as f:
                    f.write(idf_dfr(nr, setname, zweizonig=zz))
                tabelle.append(dict(Datei=name, Modell="DFR_" + setname, Variante=nr,
                                    Wetterdatei=v["epw"], Zonen=2 if zz else 1,
                                    Tore="+".join(str(g) for g in v["tore"]),
                                    Barriere=("A_eff + ZoneCrossMixing %.5f m3/s" % q) if zz else (
                                        "nur ueber A_eff" if v["barriere"] else "nein"),
                                    Kennwert="V_design = %.5f m3/s" % vdes,
                                    Q_soll=round(q, 5), ACH_soll=round(ach, 5),
                                    Ausgabevariable="Zone Ventilation Current Density Volume Flow Rate"))

    felder = ["Datei", "Modell", "Variante", "Wetterdatei", "Zonen", "Tore", "Barriere",
              "Kennwert", "Q_soll", "ACH_soll", "Ausgabevariable"]
    with open(os.path.join(ziel, "Sollwerte_Isotherm.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=felder, delimiter=";")
        w.writeheader()
        for r in tabelle:
            r = dict(r)
            for k in ("Q_soll", "ACH_soll"):
                r[k] = ("%.5f" % r[k]).replace(".", ",")
            w.writerow(r)

    print("u_ref            = %.6f m/s" % U_REF)
    print("A_eff ohne/mit   = %.5f / %.5f m2" % (a_eff(False), a_eff(True)))
    print("Spalt            = %.3f x %.6f m = %.4f m2" % (SPALT_B, SPALT_H, SPALT_B * SPALT_H))
    print()
    print("%-22s %10s %10s" % ("Datei", "Q_soll", "ACH_soll"))
    for r in tabelle:
        print("%-22s %10.5f %10.5f" % (r["Datei"], r["Q_soll"], r["ACH_soll"]))
    return tabelle, ziel


if __name__ == "__main__":
    main()
