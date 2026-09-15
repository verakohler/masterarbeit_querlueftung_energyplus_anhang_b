# -*- coding: utf-8 -*-
# ============================================================
# VALIDACION Cp: presion vs velocidad
# Extrae Cp en fachada barlovento/sotavento, calcula dCp, y
# valida el caudal CFD contra la formula de ventilacion cruzada
#   Q = Cd * A* * U * sqrt(dCp)
#
# USO: carga el result.foam, seleccionalo, pega y ejecuta.
# Deja en el pipeline los slices de presion para inspeccion.
# ============================================================
from paraview.simple import *
import math

# ---------------- PARAMETROS ----------------
PRESS_ARRAY = "p_rgh"    # buoyantBoussinesqSimpleFoam: usar p_rgh (presion motriz),
                         # NO "p" (que incluye la parte hidrostatica rho*g*h).
U_REF   = 5.1            # m/s, velocidad en la que se basa Cp
RHO     = 1.2            # kg/m3 (solo si p es presion DINAMICA en Pa)
CD      = 0.62           # coef. descarga (borde afilado 0.60-0.65)
A_GATE  = 9.0            # m2 por gate

# --- IMPORTANTE: naturaleza del campo p en OpenFOAM ---
# simpleFoam/pisoFoam INCOMPRESIBLE -> p es CINEMATICA (p/rho, m2/s2).
#   En ese caso Cp = (p - p_inf) / (0.5 * U^2)     [SIN rho]
# Solvers COMPRESIBLES -> p en Pa.
#   Cp = (p - p_inf) / (0.5 * rho * U^2)
P_IS_KINEMATIC = True    # buoyantBoussinesqSimpleFoam -> p_rgh es CINEMATICA (m2/s2).
                         # Dejar SIEMPRE True para este solver.

# Planos de las fachadas (mismos que en el script de caudal)
Y_WIND = 0.11            # fachada barlovento (sur, entrada)
Y_LEE  = 59.89           # fachada sotavento  (norte, salida)
HALL_X, HALL_Z = (0.0, 15.0), (0.0, 12.0)

# Presion de referencia p_inf:
# La BC de outlet del tunel es pressure = 0 (ver JSON, vent_0F_2 flowType=pressure,
# customValue=0). Ese plano esta en flujo libre lejos del hall, asi que fija el
# datum del dominio: p_rgh -> 0 en el freestream. Por tanto p_inf = 0 por
# construccion. No hace falta medir ningun plano ni conocer el nombre del patch.
P_INF = 0.0
# --------------------------------------------


def _mean_over_facade(src, y_plane, array, tag):
    sl = Slice(Input=src, registrationName="pSlice_" + tag)
    sl.SliceType = "Plane"
    sl.SliceType.Origin = [(HALL_X[0]+HALL_X[1])/2.0, y_plane, (HALL_Z[0]+HALL_Z[1])/2.0]
    sl.SliceType.Normal = [0.0, 1.0, 0.0]

    clip = Clip(Input=sl, registrationName="pFacade_" + tag)
    clip.ClipType = "Box"; clip.Invert = 1
    clip.ClipType.Position = [HALL_X[0], y_plane-1.0, HALL_Z[0]]
    clip.ClipType.Length   = [HALL_X[1]-HALL_X[0], 2.0, HALL_Z[1]-HALL_Z[0]]

    integ = IntegrateVariables(Input=clip, registrationName="pInteg_" + tag)
    UpdatePipeline()
    cd_ = servermanager.Fetch(integ).GetCellData()
    area = cd_.GetArray("Area").GetValue(0) if cd_.GetArray("Area") else float("nan")
    psum = cd_.GetArray(array).GetValue(0) if cd_.GetArray(array) else float("nan")
    Show(clip)
    # media ponderada por area = integral / area
    return (psum/area if area else float("nan")), area



def validar():
    src = GetActiveSource()
    if src is None:
        print("Carga y selecciona el result.foam primero."); return
    UpdatePipeline()
    tk = GetTimeKeeper()
    times = list(tk.TimestepValues) if tk.TimestepValues else []
    if times: UpdatePipeline(time=times[-1])

    # limpiar objetos de validacion previos
    for name, obj in list(GetSources().items()):
        if name[0].startswith(("pSlice_", "pFacade_", "pInteg_")):
            try: Delete(obj)
            except Exception: pass

    # comprobar campo de presion
    cdi = src.CellData
    names = [cdi.GetArray(i).Name for i in range(cdi.GetNumberOfArrays())]
    if PRESS_ARRAY not in names:
        print("AVISO: '%s' no esta en Cell Data. Disponibles: %s" % (PRESS_ARRAY, names))

    p_wind, a_w = _mean_over_facade(src, Y_WIND, PRESS_ARRAY, "wind")
    p_lee,  a_l = _mean_over_facade(src, Y_LEE,  PRESS_ARRAY, "lee")
    p_inf       = P_INF   # anclado a BC outlet (p=0)

    # dinamica de referencia
    qdyn = 0.5 * U_REF**2 if P_IS_KINEMATIC else 0.5 * RHO * U_REF**2

    Cp_wind = (p_wind - p_inf) / qdyn
    Cp_lee  = (p_lee  - p_inf) / qdyn
    dCp = Cp_wind - Cp_lee

    Astar = 1.0/math.sqrt(1.0/A_GATE**2 + 1.0/A_GATE**2)
    Q_formula = CD * Astar * U_REF * math.sqrt(abs(dCp)) if dCp > 0 else float("nan")

    print("="*60)
    print("VALIDACION Cp  (p %s)" % ("cinematica m2/s2" if P_IS_KINEMATIC else "dinamica Pa"))
    print("-"*60)
    print("  p_inf (BC outlet, p=0)         = %+.4f" % p_inf)
    print("  p_wind (barlovento, area %.1f) = %+.4f  -> Cp = %+.3f" % (a_w, p_wind, Cp_wind))
    print("  p_lee  (sotavento,  area %.1f) = %+.4f  -> Cp = %+.3f" % (a_l, p_lee, Cp_lee))
    print("  dCp = Cp_wind - Cp_lee          = %+.3f" % dCp)
    print("-"*60)
    print("  A* (2 gates en serie) = %.3f m2" % Astar)
    print("  Q_formula = Cd*A*U*sqrt(dCp) = %.3f m3/s   (Cd=%.2f)" % (Q_formula, CD))
    print("  --> compara este Q_formula con el Q que mediste")
    print("      por integracion de velocidad para este mismo caso.")
    print("="*60)
    Render()
    return dCp, Q_formula


validar()
