# -*- coding: utf-8 -*-
# ==========================================================================
# EXTRAKTION C_p AN DER TORFLAECHE + C_D EFFEKTIV
#
# Erweitert batch_all_cases.py um drei neue C_p-Varianten und einen
# Abstandsschwenk. Schreibt alles in EINE CSV.
#
# Varianten:
#   A  ganze Fassade 15 x 12 m, Torloch abgezogen        (wie bisher, korrigiert)
#   B  horizontaler Streifen ueber die ganze Breite, z 0..3 m   (wie bisher)
#   C  genau die Toroeffnung 3 x 3 m, bei mehreren Abstaenden d
#   D  Ring um das Tor: Tor + Rand, minus Torloch        (lokaler Fassadendruck)
#   E  vertikaler Streifen in Torbreite, z 0..12 m
#
# WICHTIG zur Interpretation von Variante C:
#   An der Toroeffnung ist keine Wand. Der statische Druck dort ist bereits
#   durch die Beschleunigung in die Oeffnung hinein beeinflusst und damit NICHT
#   der Fassadendruck, den ein Knotenmodell braucht. Im AFN ist C_p der Druck
#   der GESCHLOSSENEN Fassade; die Kontraktion der Oeffnung steckt in C_D.
#   Deshalb wird C bei mehreren Abstaenden ausgewertet und zusaetzlich D
#   (Ring um das Tor) berechnet. Erst der Vergleich zeigt, welche Definition
#   belastbar ist.
#
# USO:  aus dem Ordner, der ProfMaileModel_caseN/ enthaelt:
#         pvpython POST_SCRIPTS/extract_cp_gate.py
#       oder in der Python-Shell von ParaView:
#         exec(open("POST_SCRIPTS/extract_cp_gate.py").read())
#
# Solver: buoyantBoussinesqSimpleFoam -> Druckfeld p_rgh, KINEMATISCH (m2/s2).
# ==========================================================================
from paraview.simple import *
import math, csv, os

# ----------------------------- PARAMETER -----------------------------
BASE_DIR = "."
OUT_CSV  = "cp_gate_extraction.csv"

VEL   = "U"
PRESS = "p_rgh"
U_REF = 5.1                 # m/s, Normierungsgeschwindigkeit der C_p (uniformer Inlet)
QDYN  = 0.5 * U_REF**2      # kinematischer Staudruck = 13.005 m2/s2
P_INF = 0.0                 # durch die Outlet-BC (p = 0) festgelegt

A_GATE = 9.0                # m2 pro Tor
HALL_V = 15.0 * 60.0 * 12.0 # 10 800 m3

# Hallengeometrie im Netz
HX = (0.0, 15.0)            # Fassadenbreite
HZ = (0.0, 12.0)            # Fassadenhoehe
GZ = (0.0, 3.0)             # Torhoehe
Y_WALL_S, Y_WALL_N = 0.0, 60.0    # Aussenflaechen der Waende
Y_IN,     Y_OUT    = 0.11, 59.89  # Messebenen fuer den Volumenstrom (innen)

# Abstaende ausserhalb der Wand fuer Variante C
DISTANCES   = [0.05, 0.25, 0.5, 1.0, 2.0, 4.0]
RING_MARGIN = 1.0           # m Rand je Seite fuer Variante D
D_REF       = 0.05          # Abstand fuer A, B, D, E (wie im bisherigen Skript)

# Torpositionen, aus den Modell-JSON rekonstruiert (Wandsegmente -> Luecke).
# ACHTUNG: bei den Diagonalfaellen 4 und 4-90 liegt das leeseitige Tor
# NICHT bei x 6..9. Das bisherige Skript hat dort das falsche Loch abgezogen.
CASES = {
    "1":    dict(foam="ProfMaileModel_case1/sim/foam.foam",  south=(6.0, 9.0), north=(6.0, 9.0), szen=1, cos_theta=0.382683, zonen=1),
    "3":    dict(foam="ProfMaileModel_case3/sim/foam.foam",  south=(6.0, 9.0), north=(6.0, 9.0), szen=2, cos_theta=0.382683, zonen=2),
    "4":    dict(foam="ProfMaileModel_case4/sim/foam.foam",  south=(6.0, 9.0), north=(1.1, 4.0), szen=3, cos_theta=0.382683, zonen=1),
    "5":    dict(foam="ProfMaileModel_case5/sim/foam.foam",  south=(6.0, 9.0), north=(6.0, 9.0), szen=4, cos_theta=0.923880, zonen=1),
    "3-90": dict(foam="ProfMaileModel_case35/sim/foam.foam", south=(6.0, 9.0), north=(6.0, 9.0), szen=5, cos_theta=0.923880, zonen=2),
    "4-90": dict(foam="ProfMaileModel_case45/sim/foam.foam", south=(6.0, 9.0), north=(1.1, 4.0), szen=6, cos_theta=0.923880, zonen=1),
}

# wirksame Flaeche der Reihenschaltung
ASTAR_1Z = A_GATE / math.sqrt(2.0)                                  # 6.364 m2
ASTAR_2Z = 1.0 / math.sqrt(1/A_GATE**2 + 1/30.0**2 + 1/A_GATE**2)   # 6.225 m2, Spalt 30 m2
# ---------------------------------------------------------------------


def _last_time(src):
    UpdatePipeline()
    tk = GetTimeKeeper()
    ts = list(tk.TimestepValues) if tk.TimestepValues else []
    if ts:
        UpdatePipeline(time=ts[-1])
        return ts[-1]
    return None


def _integrate(src, array):
    ig = IntegrateVariables(Input=src)
    UpdatePipeline()
    cd = servermanager.Fetch(ig).GetCellData()
    area = cd.GetArray("Area").GetValue(0) if cd.GetArray("Area") else float("nan")
    val  = cd.GetArray(array).GetValue(0)  if cd.GetArray(array)  else float("nan")
    Delete(ig)
    return val, area


def _slice_y(src, y):
    sl = Slice(Input=src)
    sl.SliceType = "Plane"
    sl.SliceType.Origin = [7.5, y, 6.0]
    sl.SliceType.Normal = [0, 1, 0]
    return sl


def _clip(src, x0, x1, y, z0, z1, invert=1):
    cl = Clip(Input=src)
    cl.ClipType = "Box"
    cl.Invert = invert
    cl.ClipType.Position = [x0, y - 1.0, z0]
    cl.ClipType.Length   = [x1 - x0, 2.0, z1 - z0]
    return cl


def p_window(src, y, x0, x1, z0, z1):
    """Flaechengewichteter Mittelwert von p_rgh im Fenster (x0..x1, z0..z1)."""
    sl = _slice_y(src, y)
    cl = _clip(sl, x0, x1, y, z0, z1)
    p, a = _integrate(cl, PRESS)
    Delete(cl); Delete(sl)
    return p, a


def cp_window(src, y, x0, x1, z0, z1):
    p, a = p_window(src, y, x0, x1, z0, z1)
    return ((p / a - P_INF) / QDYN if a > 1e-6 else float("nan")), a


def cp_minus_hole(src, y, x0, x1, z0, z1, hx0, hx1, hz0, hz1):
    """Fenster minus Torloch: Integrale subtrahieren, dann durch Restflaeche."""
    p_full, a_full = p_window(src, y, x0, x1, z0, z1)
    p_hole, a_hole = p_window(src, y, hx0, hx1, hz0, hz1)
    a = a_full - a_hole
    p = p_full - p_hole
    return ((p / a - P_INF) / QDYN if a > 1e-6 else float("nan")), a


def flow_plane(src, y, x0=None, x1=None):
    """Q = Integral(U_y) ueber die Fassadenebene bzw. ueber ein x-Fenster."""
    sl = _slice_y(src, y)
    cl = _clip(sl, HX[0] if x0 is None else x0, HX[1] if x1 is None else x1,
               y, HZ[0], HZ[1])
    ca = Calculator(Input=cl)
    ca.AttributeType = "Cell Data"
    ca.ResultArrayName = "Un"
    ca.Function = "U_Y"
    q, a = _integrate(ca, "Un")
    Delete(ca); Delete(cl); Delete(sl)
    return q, a


def process(label, cfg):
    print("=" * 70)
    print("Fall %s  (Szenario %d)  ->  %s" % (label, cfg["szen"], cfg["foam"]))
    src = OpenDataFile(os.path.join(BASE_DIR, cfg["foam"]))
    try:
        src.CellArrays = [VEL, PRESS]
    except Exception:
        pass
    t = _last_time(src)

    gs, gn = cfg["south"], cfg["north"]
    row = dict(case=label, szen=cfg["szen"], time=t,
               gate_south_x="%.2f-%.2f" % gs, gate_north_x="%.2f-%.2f" % gn)

    # ---------- Volumenstrom ----------
    q_in_full,  _ = flow_plane(src, Y_IN)
    q_out_full, _ = flow_plane(src, Y_OUT)
    q_in_gate,  _ = flow_plane(src, Y_IN,  gs[0], gs[1])
    q_out_gate, _ = flow_plane(src, Y_OUT, gn[0], gn[1])
    Qcfd = 0.5 * (abs(q_in_full) + abs(q_out_full))
    row.update(Q_in=q_in_full, Q_out=q_out_full,
               Q_in_gate=q_in_gate, Q_out_gate=q_out_gate,
               Q_cfd=Qcfd, ACH=Qcfd * 3600.0 / HALL_V)
    print("   Q_in=%.3f  Q_out=%.3f  ->  Q_cfd=%.3f m3/s  (%.3f 1/h)"
          % (q_in_full, q_out_full, Qcfd, Qcfd * 3600.0 / HALL_V))

    ys, yn = Y_WALL_S - D_REF, Y_WALL_N + D_REF

    # ---------- A: ganze Fassade minus Torloch ----------
    cpA_s, aA_s = cp_minus_hole(src, ys, HX[0], HX[1], HZ[0], HZ[1], gs[0], gs[1], GZ[0], GZ[1])
    cpA_n, aA_n = cp_minus_hole(src, yn, HX[0], HX[1], HZ[0], HZ[1], gn[0], gn[1], GZ[0], GZ[1])
    row.update(cpA_south=cpA_s, cpA_north=cpA_n, dCp_A=cpA_s - cpA_n, area_A=aA_s)

    # ---------- B: horizontaler Streifen, ganze Breite ----------
    cpB_s, aB_s = cp_window(src, ys, HX[0], HX[1], GZ[0], GZ[1])
    cpB_n, aB_n = cp_window(src, yn, HX[0], HX[1], GZ[0], GZ[1])
    row.update(cpB_south=cpB_s, cpB_north=cpB_n, dCp_B=cpB_s - cpB_n, area_B=aB_s)

    # ---------- C: genau die Torflaeche, mehrere Abstaende ----------
    for d in DISTANCES:
        cs, _ = cp_window(src, Y_WALL_S - d, gs[0], gs[1], GZ[0], GZ[1])
        cn, _ = cp_window(src, Y_WALL_N + d, gn[0], gn[1], GZ[0], GZ[1])
        k = ("%.2f" % d).replace(".", "")
        row["cpC_south_d" + k] = cs
        row["cpC_north_d" + k] = cn
        row["dCp_C_d" + k]     = cs - cn
        print("   C  d=%4.2f m:  Cp_Sued=%+.4f  Cp_Nord=%+.4f  dCp=%+.4f" % (d, cs, cn, cs - cn))

    # ---------- D: Ring um das Tor ----------
    m = RING_MARGIN
    rs = (max(HX[0], gs[0] - m), min(HX[1], gs[1] + m))
    rn = (max(HX[0], gn[0] - m), min(HX[1], gn[1] + m))
    cpD_s, aD_s = cp_minus_hole(src, ys, rs[0], rs[1], GZ[0], GZ[1] + m, gs[0], gs[1], GZ[0], GZ[1])
    cpD_n, aD_n = cp_minus_hole(src, yn, rn[0], rn[1], GZ[0], GZ[1] + m, gn[0], gn[1], GZ[0], GZ[1])
    row.update(cpD_south=cpD_s, cpD_north=cpD_n, dCp_D=cpD_s - cpD_n, area_D=aD_s)
    print("   D  Ring (Rand %.1f m): Cp_Sued=%+.4f  Cp_Nord=%+.4f  dCp=%+.4f"
          % (m, cpD_s, cpD_n, cpD_s - cpD_n))

    # ---------- E: vertikaler Streifen in Torbreite ----------
    cpE_s, aE_s = cp_window(src, ys, gs[0], gs[1], HZ[0], HZ[1])
    cpE_n, aE_n = cp_window(src, yn, gn[0], gn[1], HZ[0], HZ[1])
    row.update(cpE_south=cpE_s, cpE_north=cpE_n, dCp_E=cpE_s - cpE_n, area_E=aE_s)

    # ---------- C_D effektiv ----------
    astar = ASTAR_2Z if cfg["zonen"] == 2 else ASTAR_1Z
    row["CD_geom"] = Qcfd / (A_GATE * U_REF * cfg["cos_theta"])
    for tag in ["A", "B", "D", "E"] + ["C_d" + ("%.2f" % d).replace(".", "") for d in DISTANCES]:
        dcp = row.get("dCp_" + tag)
        row["CD_" + tag] = (Qcfd / (astar * U_REF * math.sqrt(dcp))
                            if dcp and dcp > 0 else float("nan"))
    row["astar"] = astar
    print("   C_D geometrisch (ohne C_p) = %.4f   |   C_D aus dCp_D = %s"
          % (row["CD_geom"], ("%.4f" % row["CD_D"]) if row["CD_D"] == row["CD_D"] else "n.d."))

    Delete(src)
    return row


def run():
    rows = []
    for label, cfg in CASES.items():
        p = os.path.join(BASE_DIR, cfg["foam"])
        if not os.path.exists(p):
            print("  UEBERSPRUNGEN (nicht gefunden):", p)
            continue
        try:
            rows.append(process(label, cfg))
        except Exception as e:
            print("  FEHLER bei Fall", label, ":", e)
    if not rows:
        print("Kein Fall verarbeitet.")
        return
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})
    print("=" * 70)
    print("CSV geschrieben:", os.path.abspath(OUT_CSV), "(", len(rows), "Faelle )")


run()
