#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erzeugt die Test-IDFs zur Verifikation der lokalen Windgeschwindigkeit in
EnergyPlus (Masterarbeit M13, Kapitel 5.3).

Zwei Fragen werden getrennt geprueft:

  Testfamilie A/B/C  ->  Welche Windgeschwindigkeit setzt E+ auf Zonenhoehe an?
                         Insbesondere: unterdrueckt "Wind Speed Profile
                         Exponent = 0" auch den Vorfaktor (d_met/z_met)^a_met
                         = 1,586?

  Testfamilie D      ->  Reproduziert E+ die Handrechnung Q_vent, wenn die
                         Windgeschwindigkeit gesichert bekannt ist?

Aufruf:  python3 make_idf.py
Ausgabe: IDF/*.idf

Die IDFs sind bewusst minimal: keine Anlagentechnik, adiabate Huelle, kein
Solareintrag, keine EPW noetig (SizingPeriod:DesignDay als Umgebung).
"""

import math
import os

# ----------------------------------------------------------------------------
# Konfiguration -- hier anpassen
# ----------------------------------------------------------------------------
EPLUS_VERSION = "25.2"      # Version der bisherigen Laeufe (25.2.0-cf7368216c)
U_MET = 6.5                 # Windgeschwindigkeit der Umgebung in 10 m [m/s]
T_ODB = 17.0                # Aussenlufttemperatur, konstant [degC]
P_BARO = 95500.0            # Luftdruck bei 494 m ue. NN [Pa]
OUTDIR = "IDF"

# Zonen der Testfamilie A/B/C: (Name, Hoehe [m], x-Offset [m])
# Schwerpunkthoehe eines Quaders = H/2
ZONES_ABC = [
    ("Z_TOR_ZSP_1P70",   3.4,   0.0),
    ("Z_HALLE_ZSP_6P00", 12.0,  20.0),
    ("Z_HOCH_ZSP_12P00", 24.0,  40.0),
]

# Testfamilie D: drei geometrisch identische Zonen (Schwerpunkt 1,70 m),
# je ein ZoneVentilation-Objekt mit einem der drei Koeffizientensaetze.
C_D, A_TOR, THETA_DEG = 0.62, 9.0, 67.5
K_TOR = C_D * A_TOR * math.cos(math.radians(THETA_DEG))
U_DESIGN = 5.072

COEFF_SETS = [
    # (Kuerzel, A, B, C, D, u_ref)
    ("BLAST",   0.606, 0.03636, 0.1177, 0.0, (1.0 - 0.606) / 0.1177),
    ("DOE2",    0.0,   0.0,     0.224,  0.0, 1.0 / 0.224),
    ("DEFAULT", 1.0,   0.0,     0.0,    0.0, U_DESIGN),
]

FOOTPRINT = 10.0            # quadratische Grundflaeche [m]


# ----------------------------------------------------------------------------
# Bausteine
# ----------------------------------------------------------------------------
def header(title, note, u_env=None, terrain="Country"):
    u_env = U_MET if u_env is None else u_env
    return f"""!-   ===========================================================================
!-   {title}
!-   {note}
!-   Erzeugt von make_idf.py -- Masterarbeit M13, Kapitel 5.3
!-   ===========================================================================

Version, {EPLUS_VERSION};

SimulationControl,
    No,                      !- Do Zone Sizing Calculation
    No,                      !- Do System Sizing Calculation
    No,                      !- Do Plant Sizing Calculation
    Yes,                     !- Run Simulation for Sizing Periods
    No;                      !- Run Simulation for Weather File Run Periods

Building,
    Windprofil_Test,         !- Name
    0.0,                     !- North Axis {{deg}}
    {terrain},{" " * max(1, 24 - len(terrain))}!- Terrain
    0.04,                    !- Loads Convergence Tolerance Value {{W}}
    0.4,                     !- Temperature Convergence Tolerance Value {{deltaC}}
    FullExterior,            !- Solar Distribution
    25,                      !- Maximum Number of Warmup Days
    6;                       !- Minimum Number of Warmup Days

Timestep, 4;

GlobalGeometryRules,
    UpperLeftCorner,         !- Starting Vertex Position
    CounterClockWise,        !- Vertex Entry Direction
    World;                   !- Coordinate System

Site:Location,
    Augsburg_Test,           !- Name
    48.35,                   !- Latitude {{deg}}
    10.90,                   !- Longitude {{deg}}
    1.0,                     !- Time Zone {{hr}}
    494.0;                   !- Elevation {{m}}

SizingPeriod:DesignDay,
    Isotherm_{u_env:.3f}mps,  !- Name
    7,                       !- Month
    21,                      !- Day of Month
    SummerDesignDay,         !- Day Type
    {T_ODB:.1f},                    !- Maximum Dry-Bulb Temperature {{C}}
    0.0,                     !- Daily Dry-Bulb Temperature Range {{deltaC}}
    DefaultMultipliers,      !- Dry-Bulb Temperature Range Modifier Type
    ,                        !- Dry-Bulb Temperature Range Modifier Day Schedule Name
    Wetbulb,                 !- Humidity Condition Type
    12.0,                    !- Wetbulb or DewPoint at Maximum Dry-Bulb {{C}}
    ,                        !- Humidity Condition Day Schedule Name
    ,                        !- Humidity Ratio at Maximum Dry-Bulb
    ,                        !- Enthalpy at Maximum Dry-Bulb
    ,                        !- Daily Wet-Bulb Temperature Range
    {P_BARO:.0f},                   !- Barometric Pressure {{Pa}}
    {u_env:.3f},                   !- Wind Speed {{m/s}}   <== Referenzgeschwindigkeit
    270,                     !- Wind Direction {{deg}}
    No,                      !- Rain Indicator
    No,                      !- Snow Indicator
    No,                      !- Daylight Saving Time Indicator
    ASHRAEClearSky,          !- Solar Model Indicator
    ,                        !- Beam Solar Day Schedule Name
    ,                        !- Diffuse Solar Day Schedule Name
    ,                        !- ASHRAE Clear Sky Optical Depth for Beam Irradiance
    ,                        !- ASHRAE Clear Sky Optical Depth for Diffuse Irradiance
    0.0;                     !- Sky Clearness   <== kein Solareintrag

Material,
    Beton_200mm,             !- Name
    MediumRough,             !- Roughness
    0.200,                   !- Thickness {{m}}
    2.100,                   !- Conductivity {{W/m-K}}
    2400.0,                  !- Density {{kg/m3}}
    880.0,                   !- Specific Heat {{J/kg-K}}
    0.90,                    !- Thermal Absorptance
    0.70,                    !- Solar Absorptance
    0.70;                    !- Visible Absorptance

Construction,
    Wand_Beton,              !- Name
    Beton_200mm;             !- Outside Layer

ScheduleTypeLimits,
    Fraction,                !- Name
    0.0,                     !- Lower Limit Value
    1.0,                     !- Upper Limit Value
    Continuous;              !- Numeric Type

Schedule:Constant,
    Sch_Immer_1,             !- Name
    Fraction,                !- Schedule Type Limits Name
    1.0;                     !- Hourly Value

"""


def site_weather_station(exponent, comment):
    """Site:WeatherStation -- steuert den Vorfaktor (d_met/z_met)^a_met."""
    if exponent is None:
        return ("!-   KEIN Site:WeatherStation-Objekt -> Defaults der Messstation:\n"
                "!-   z_met = 10 m, a_met = 0,14, d_met = 270 m, T-Sensor 1,5 m\n"
                "!-   -> Vorfaktor (270/10)^0,14 = 1,5863\n\n")
    return f"""!-   {comment}
Site:WeatherStation,
    10.0,                    !- Wind Sensor Height Above Ground {{m}}
    {exponent},{" " * max(1, 24 - len(str(exponent)))}!- Wind Speed Profile Exponent
    270.0,                   !- Wind Speed Profile Boundary Layer Thickness {{m}}
    1.5;                     !- Air Temperature Sensor Height Above Ground {{m}}

"""


def site_height_variation(exponent, blt, tgrad, comment):
    if exponent is None:
        return ("!-   KEIN Site:HeightVariation-Objekt -> E+ nutzt die Defaults\n"
                "!-   der Terrainklasse 'Suburbs': a = 0,22 / d = 370 m,\n"
                "!-   Air Temperature Gradient Coefficient = 0,0065 K/m\n\n")
    return f"""!-   {comment}
Site:HeightVariation,
    {exponent},{" " * max(1, 24 - len(str(exponent)))}!- Wind Speed Profile Exponent
    {blt},{" " * max(1, 24 - len(str(blt)))}!- Wind Speed Profile Boundary Layer Thickness {{m}}
    {tgrad};{" " * max(1, 24 - len(str(tgrad)))}!- Air Temperature Gradient Coefficient {{K/m}}

"""


def zone_block(name, height, x0, y0=0.0, footprint=FOOTPRINT):
    """Quaderzone mit adiabater Huelle; Sued-Wand und Dach nach Aussen."""
    x1, y1, h = x0 + footprint, y0 + footprint, height

    def verts(pts):
        out = []
        for i, (x, y, z) in enumerate(pts):
            sep = "," if i < len(pts) - 1 else ";"
            out.append(f"    {x:.3f}, {y:.3f}, {z:.3f}{sep}"
                       f"{' ' * 6}!- Vertex {i + 1}")
        return "\n".join(out)

    surfaces = [
        # (Suffix, Typ, aussen, Sonne, Wind, Vertices)
        ("Floor", "Floor", "Adiabatic", "NoSun", "NoWind",
         [(x0, y0, 0.0), (x0, y1, 0.0), (x1, y1, 0.0), (x1, y0, 0.0)]),
        ("Roof", "Roof", "Outdoors", "SunExposed", "WindExposed",
         [(x0, y1, h), (x0, y0, h), (x1, y0, h), (x1, y1, h)]),
        ("Wall_S", "Wall", "Outdoors", "SunExposed", "WindExposed",
         [(x0, y0, h), (x0, y0, 0.0), (x1, y0, 0.0), (x1, y0, h)]),
        ("Wall_E", "Wall", "Adiabatic", "NoSun", "NoWind",
         [(x1, y0, h), (x1, y0, 0.0), (x1, y1, 0.0), (x1, y1, h)]),
        ("Wall_N", "Wall", "Adiabatic", "NoSun", "NoWind",
         [(x1, y1, h), (x1, y1, 0.0), (x0, y1, 0.0), (x0, y1, h)]),
        ("Wall_W", "Wall", "Adiabatic", "NoSun", "NoWind",
         [(x0, y1, h), (x0, y1, 0.0), (x0, y0, 0.0), (x0, y0, h)]),
    ]

    txt = f"""Zone,
    {name},{" " * max(1, 24 - len(name))}!- Name
    0.0,                     !- Direction of Relative North {{deg}}
    0.0,                     !- X Origin {{m}}
    0.0,                     !- Y Origin {{m}}
    0.0,                     !- Z Origin {{m}}
    1,                       !- Type
    1,                       !- Multiplier
    ,                        !- Ceiling Height {{m}}
    ,                        !- Volume {{m3}}
    ,                        !- Floor Area {{m2}}
    ,                        !- Zone Inside Convection Algorithm
    ,                        !- Zone Outside Convection Algorithm
    Yes;                     !- Part of Total Floor Area

!-   Schwerpunkthoehe dieser Zone: {h / 2:.3f} m
"""
    for suffix, styp, outside, sun, wind, pts in surfaces:
        sname = f"{name}_{suffix}"
        obc_obj = "" if outside in ("Outdoors", "Adiabatic") else outside
        txt += f"""
BuildingSurface:Detailed,
    {sname},{" " * max(1, 24 - len(sname))}!- Name
    {styp},{" " * max(1, 24 - len(styp))}!- Surface Type
    Wand_Beton,              !- Construction Name
    {name},{" " * max(1, 24 - len(name))}!- Zone Name
    ,                        !- Space Name
    {outside},{" " * max(1, 24 - len(outside))}!- Outside Boundary Condition
    {obc_obj},{" " * max(1, 24 - len(obc_obj))}!- Outside Boundary Condition Object
    {sun},{" " * max(1, 24 - len(sun))}!- Sun Exposure
    {wind},{" " * max(1, 24 - len(wind))}!- Wind Exposure
    ,                        !- View Factor to Ground
    4,                       !- Number of Vertices
{verts(pts)}
"""
    return txt + "\n"


def zone_ventilation(name, zone, vdesign, a, b, c, d):
    return f"""ZoneVentilation:DesignFlowRate,
    {name},{" " * max(1, 24 - len(name))}!- Name
    {zone},{" " * max(1, 24 - len(zone))}!- Zone or ZoneList Name
    Sch_Immer_1,             !- Schedule Name
    Flow/Zone,               !- Design Flow Rate Calculation Method
    {vdesign:.4f},                 !- Design Flow Rate {{m3/s}}
    ,                        !- Flow Rate per Zone Floor Area {{m3/s-m2}}
    ,                        !- Flow Rate per Person {{m3/s-person}}
    ,                        !- Air Changes per Hour
    Natural,                 !- Ventilation Type
    0.0,                     !- Fan Pressure Rise {{Pa}}
    1.0,                     !- Fan Total Efficiency
    {a},                   !- Constant Term Coefficient
    {b},                 !- Temperature Term Coefficient
    {c},                  !- Velocity Term Coefficient
    {d},                     !- Velocity Squared Term Coefficient
    -100.0,                  !- Minimum Indoor Temperature {{C}}
    ,                        !- Minimum Indoor Temperature Schedule Name
    100.0,                   !- Maximum Indoor Temperature {{C}}
    ,                        !- Maximum Indoor Temperature Schedule Name
    -100.0,                  !- Delta Temperature {{deltaC}}   <== erzwingt Betrieb
    ,                        !- Delta Temperature Schedule Name
    -100.0,                  !- Minimum Outdoor Temperature {{C}}
    ,                        !- Minimum Outdoor Temperature Schedule Name
    100.0,                   !- Maximum Outdoor Temperature {{C}}
    ,                        !- Maximum Outdoor Temperature Schedule Name
    40.0;                    !- Maximum Wind Speed {{m/s}}

"""


OUTPUTS_ABC = """Output:VariableDictionary, IDF;

Output:Variable, *, Site Wind Speed, Hourly;
Output:Variable, *, Site Outdoor Air Drybulb Temperature, Hourly;
Output:Variable, *, Zone Outdoor Air Wind Speed, Hourly;
Output:Variable, *, Zone Outdoor Air Drybulb Temperature, Hourly;
Output:Variable, *, Surface Outside Face Outdoor Air Wind Speed, Hourly;
Output:Variable, *, Surface Outside Face Outdoor Air Drybulb Temperature, Hourly;
"""

OUTPUTS_D = """Output:VariableDictionary, IDF;

Output:Variable, *, Site Wind Speed, Hourly;
Output:Variable, *, Zone Outdoor Air Wind Speed, Hourly;
Output:Variable, *, Zone Outdoor Air Drybulb Temperature, Hourly;
Output:Variable, *, Zone Mean Air Temperature, Hourly;
Output:Variable, *, Zone Ventilation Standard Density Volume Flow Rate, Hourly;
Output:Variable, *, Zone Ventilation Current Density Volume Flow Rate, Hourly;
Output:Variable, *, Zone Ventilation Air Change Rate, Hourly;
"""


# ----------------------------------------------------------------------------
# Dateien schreiben
# ----------------------------------------------------------------------------
def build_abc():
    # (Tag, Titel, Notiz, Terrain, WS-Exponent, HV-Exponent, HV-Delta, HV-TGrad, Kommentar)
    cases = [
        ("A_Terrain_Suburbs_Default",
         "Variante A -- keine Site-Objekte, Terrain Suburbs (Ausgangszustand)",
         "Regressionstest: muss die Messung 4,1638 m/s bei z = 6,00 m reproduzieren.",
         "Suburbs", None, None, None, None, ""),
        ("B1_nur_HeightVariation_0",
         "Variante B1 -- nur Site:HeightVariation mit Exponent 0",
         "Direkter Test: bleibt der Vorfaktor 1,5863 stehen?",
         "Country", None, 0.0, 270.0, 0.0,
         "Exponent 0 -> (z/d)^0 = 1. Vorfaktor der Messstation unangetastet."),
        ("B2_beide_Exponenten_0",
         "Variante B2 -- Site:WeatherStation UND Site:HeightVariation mit Exponent 0",
         "Aufbau der Notiz vom 28.07.2026: flaches Profil, u = u_EPW.",
         "Country", 0.0, 0.0, 270.0, 0.0,
         "Beide Exponenten 0 -> u(z) = u_EPW, hoehenunabhaengig."),
        ("C_Exponent_014",
         "Variante C -- Exponent 0,14 / Grenzschicht 270 m (= Messstationsprofil)",
         "Reproduziert u(z) = u_10 * (z/10)^0,14, also die Handrechnung.",
         "Country", None, 0.14, 270.0, 0.0,
         "a = a_met und d = d_met -> Formel kollabiert zu u_10*(z/10)^0,14."),
    ]
    for tag, title, note, terrain, ws, hv, blt, tg, comment in cases:
        txt = header(title, note, terrain=terrain)
        txt += site_weather_station(ws, "Vorfaktor der Messstation auf 1 gesetzt.")
        txt += site_height_variation(hv, blt, tg, comment)
        for name, h, x0 in ZONES_ABC:
            txt += zone_block(name, h, x0)
        txt += OUTPUTS_ABC
        path = os.path.join(OUTDIR, f"Windprofil_{tag}.idf")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(txt)
        print(f"  geschrieben: {path}")


def build_d():
    title = "Variante D -- Verifikation Q_vent der drei Koeffizientensaetze"
    note = (f"Drei identische Zonen (Schwerpunkt 1,70 m), flaches Profil, "
            f"u = {U_DESIGN} m/s, DeltaT = 0.")
    txt = header(title, note, u_env=U_DESIGN, terrain="Country")
    txt += site_weather_station(0.0, "Vorfaktor der Messstation auf 1 gesetzt.")
    txt += site_height_variation(
        0.0, 270.0, 0.0,
        "Beide Exponenten 0 + Temperaturgradient 0 -> u = u_EPW, DeltaT sauber 0.")
    for i, (tag, a, b, c, d, u_ref) in enumerate(COEFF_SETS):
        zname = f"Z_{tag}"
        vdes = K_TOR * u_ref
        txt += f"!-   {tag}: u_ref = {u_ref:.6f} m/s, V_design = k*u_ref = {vdes:.4f} m3/s\n"
        txt += zone_block(zname, 3.4, i * 20.0)
        txt += zone_ventilation(f"Vent_{tag}", zname, vdes, a, b, c, d)
    txt += OUTPUTS_D
    path = os.path.join(OUTDIR, "Windprofil_D_ZoneVentilation.idf")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"  geschrieben: {path}")


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    print("Erzeuge IDFs ...")
    build_abc()
    build_d()
    print(f"\nk = C_D*A*cos(theta) = {K_TOR:.5f} m2")
    for tag, a, b, c, d, u_ref in COEFF_SETS:
        f_des = a + b * 0.0 + c * U_DESIGN + d * U_DESIGN ** 2
        q = K_TOR * u_ref * f_des
        print(f"  {tag:8s} u_ref={u_ref:8.4f}  V_design={K_TOR * u_ref:7.4f}  "
              f"f({U_DESIGN})={f_des:6.4f}  Q_vent={q:7.4f} m3/s  "
              f"Abw={q / (K_TOR * U_DESIGN) - 1:+7.2%}")
