# -*- coding: utf-8 -*-
# ==========================================================================
# BATCH: recorre los 6 casos, calcula para cada uno:
#   - Q en gate entrada (Y=0.11) y salida (Y=59.89) por integracion de U_y
#   - Cp de fachada, OPCION A: promedio sobre toda la pared solida (ex-hueco)
#   - Cp de fachada, OPCION B: local, banda estrecha junto al gate
#   - dCp y Q_formula para A y B, y Cd efectivo
# Vuelca todo a un CSV identificando cada caso.
#
# USO (desde la carpeta que contiene ProfMaileModel_caseN/):
#   pvpython batch_all_cases.py
# o en la consola Python de ParaView:
#   exec(open("batch_all_cases.py").read())
#
# Solver: buoyantBoussinesqSimpleFoam -> presion = p_rgh (cinematica).
# ==========================================================================
from paraview.simple import *
import math, csv, os

# ----------------- PARAMETROS -----------------
BASE_DIR = "."     # carpeta que contiene ProfMaileModel_case1/ ... case45/
CASES = {          # etiqueta -> ruta relativa al .foam
    "1":    "ProfMaileModel_case1/sim/foam.foam",
    "3":    "ProfMaileModel_case3/sim/foam.foam",
    "4":    "ProfMaileModel_case4/sim/foam.foam",
    "5":    "ProfMaileModel_case5/sim/foam.foam",
    "3-90": "ProfMaileModel_case35/sim/foam.foam",
    "4-90": "ProfMaileModel_case45/sim/foam.foam",
}
OUT_CSV = "validation_all_cases.csv"

VEL   = "U"
PRESS = "p_rgh"          # cinematica (buoyantBoussinesqSimpleFoam)
U_REF = 5.1
RHO   = 1.2              # no usado (p cinematica) pero se reporta
CD    = 0.62
A_GATE= 9.0
ASTAR = A_GATE/math.sqrt(2.0)     # 6.364 m2 (2 gates en serie)
QDYN  = 0.5*U_REF**2              # presion dinamica cinematica = 13.0 m2/s2
HALLV = 15.0*60.0*12.0

# Planos de caudal (dentro del hueco, un poco dentro del hall)
Y_IN, Y_OUT = 0.11, 59.89

# Caras EXTERIORES de la pared para Cp de fachada
# Pegados a la cara exterior de la pared (sur en Y~0, norte en Y~60),
# en el fluido inmediatamente adyacente. Acercar mas puede caer dentro
# de la celda de pared donde p_rgh no esta bien definida.
Y_WIND_EXT = -0.05       # justo fuera de la pared sur (windward)
Y_LEE_EXT  = 60.05       # justo fuera de la pared norte (leeward)

# Fachada del hall
HX = (0.0, 15.0); HZ = (0.0, 12.0)
# Hueco del gate (a excluir en A / a aislar en B)
GX = (6.0, 9.0);  GZ = (0.0, 3.0)
# Opcion B: franja horizontal COMPLETA a la altura del gate:
# todo el ancho de fachada (15 m) x altura del gate (Z 0..3 m), menos el hueco.
BX = (HX[0], HX[1])          # 0..15 m, ancho completo de la fachada
BZ = (GZ[0], GZ[1])          # 0..3 m, altura del gate
# ----------------------------------------------


def _last_time(src):
    UpdatePipeline()
    tk=GetTimeKeeper(); ts=list(tk.TimestepValues) if tk.TimestepValues else []
    if ts: UpdatePipeline(time=ts[-1])
    return ts[-1] if ts else None


def _integrate(src, array):
    """Integra 'array' sobre el src dado; devuelve (integral, area)."""
    ig=IntegrateVariables(Input=src); UpdatePipeline()
    cd=servermanager.Fetch(ig).GetCellData()
    area=cd.GetArray("Area").GetValue(0) if cd.GetArray("Area") else float("nan")
    val =cd.GetArray(array).GetValue(0)  if cd.GetArray(array)  else float("nan")
    Delete(ig)
    return val, area


def _slice_y(src, y):
    sl=Slice(Input=src); sl.SliceType="Plane"
    sl.SliceType.Origin=[7.5, y, 6.0]; sl.SliceType.Normal=[0,1,0]
    return sl


def _clip_box(src, x0,x1, y0,y1, z0,z1, invert=1):
    cl=Clip(Input=src); cl.ClipType="Box"; cl.Invert=invert
    cl.ClipType.Position=[x0,y0,z0]; cl.ClipType.Length=[x1-x0,y1-y0,z1-z0]
    return cl


def flow_at_gate(src, y):
    """Q = integral(U_y) sobre el hueco del gate en el plano y."""
    sl=_slice_y(src,y)
    cl=_clip_box(sl, HX[0],HX[1], y-1,y+1, HZ[0],HZ[1])  # restringe a fachada
    calc=Calculator(Input=cl); calc.AttributeType="Cell Data"
    calc.ResultArrayName="Un"; calc.Function="U_Y"
    Q,area=_integrate(calc,"Un")
    Delete(calc);Delete(cl);Delete(sl)
    return Q, area


def cp_facade_A(src, y_ext, y_plane_ref):
    """Cp promedio sobre TODA la pared solida (fachada 15x12 menos el hueco).
       Se integra p_rgh sobre el plano exterior recortado a la fachada,
       y se RESTA la contribucion del hueco del gate."""
    sl=_slice_y(src,y_ext)
    # toda la fachada
    full=_clip_box(sl, HX[0],HX[1], y_ext-1,y_ext+1, HZ[0],HZ[1])
    p_full,a_full=_integrate(full,PRESS)
    # hueco del gate (para restar)
    hole=_clip_box(sl, GX[0],GX[1], y_ext-1,y_ext+1, GZ[0],GZ[1])
    p_hole,a_hole=_integrate(hole,PRESS)
    Delete(hole);Delete(full);Delete(sl)
    a_solid=a_full-a_hole
    p_solid=p_full-p_hole
    p_mean = p_solid/a_solid if a_solid>1e-6 else float("nan")
    return p_mean/QDYN, a_solid


def cp_facade_B(src, y_ext):
    """Cp de la franja rectangular a la altura del gate: ancho completo de la
       fachada (15 m) x altura del gate (Z 0..3 m), franja COMPLETA sin excluir
       el hueco. Integra p_rgh sobre BX x BZ tal cual."""
    sl=_slice_y(src,y_ext)
    band=_clip_box(sl, BX[0],BX[1], y_ext-1,y_ext+1, BZ[0],BZ[1])
    p_band,a_band=_integrate(band,PRESS)
    Delete(band);Delete(sl)
    p_mean=p_band/a_band if a_band>1e-6 else float("nan")
    return p_mean/QDYN, a_band


def process(label, foam):
    print("="*60); print("Caso", label, "->", foam)
    src=OpenDataFile(foam)
    try: src.CellArrays=[VEL,PRESS]
    except Exception: pass
    t=_last_time(src)

    q_in, a_in  = flow_at_gate(src, Y_IN)
    q_out,a_out = flow_at_gate(src, Y_OUT)
    Qcfd = 0.5*(abs(q_in)+abs(q_out))     # media de entrada/salida

    cpA_w, aAw = cp_facade_A(src, Y_WIND_EXT, Y_IN)
    cpA_l, aAl = cp_facade_A(src, Y_LEE_EXT,  Y_OUT)
    cpB_w, aBw = cp_facade_B(src, Y_WIND_EXT)
    cpB_l, aBl = cp_facade_B(src, Y_LEE_EXT)

    dCpA=cpA_w-cpA_l; dCpB=cpB_w-cpB_l
    QA = CD*ASTAR*U_REF*math.sqrt(dCpA) if dCpA>0 else float("nan")
    QB = CD*ASTAR*U_REF*math.sqrt(dCpB) if dCpB>0 else float("nan")

    row = dict(case=label, time=t,
        Q_in=q_in, Q_out=q_out, Q_cfd=Qcfd,
        area_in=a_in, area_out=a_out,
        CpA_wind=cpA_w, CpA_lee=cpA_l, dCp_A=dCpA, Q_formula_A=QA,
        area_A_wind=aAw, area_A_lee=aAl,
        CpB_wind=cpB_w, CpB_lee=cpB_l, dCp_B=dCpB, Q_formula_B=QB,
        ratio_A=(QA/Qcfd if Qcfd else float('nan')),
        ratio_B=(QB/Qcfd if Qcfd else float('nan')))

    # limpiar el reader para el siguiente caso
    Delete(src)
    print("  Q_cfd=%.3f | A: dCp=%.3f Qf=%.2f (r=%.2f) | B: dCp=%.3f Qf=%.2f (r=%.2f)"%(
        Qcfd,dCpA,QA,row['ratio_A'],dCpB,QB,row['ratio_B']))
    return row


def run():
    rows=[]
    for label,rel in CASES.items():
        foam=os.path.join(BASE_DIR,rel)
        if not os.path.exists(foam):
            print("  SALTADO (no existe):", foam); continue
        try:
            rows.append(process(label,foam))
        except Exception as e:
            print("  ERROR en caso",label,":",e)
    if not rows: print("No se proceso ningun caso."); return
    cols=["case","time","Q_in","Q_out","Q_cfd","area_in","area_out",
          "CpA_wind","CpA_lee","dCp_A","Q_formula_A","area_A_wind","area_A_lee","ratio_A",
          "CpB_wind","CpB_lee","dCp_B","Q_formula_B","ratio_B"]
    with open(OUT_CSV,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow({k:r.get(k) for k in cols})
    print("="*60); print("CSV escrito:", os.path.abspath(OUT_CSV), "(",len(rows),"casos )")


run()
