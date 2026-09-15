# -*- coding: utf-8 -*-
# ============================================================
# CAUDAL EN G2 (entrada) y G5 (salida)
# Estudio ventilacion cruzada FlowDesk / LUKIE - OpenFOAM
#
# USO: carga tu result.foam en ParaView, seleccionalo en el
#      Pipeline Browser, pega este script en la Python Shell
#      (View -> Python Shell) y ejecuta.
#
# Crea y DEJA en el pipeline, por cada gate:
#   Slice_G2 / Slice_G5          -> plano en la fachada
#   Facade_G2 / Facade_G5        -> Clip a la fachada del hall (15 x 12)
#   Un_G2 / Un_G5                -> componente normal U_Y
#   Integrate_G2 / Integrate_G5  -> resultado del caudal
# El Clip (Facade_*) queda visible: es el plano de post restringido
# a la fachada 15x12, no a todo el dominio.
# ============================================================
from paraview.simple import *

VEL_ARRAY  = "U"          # velocidad (Cell Data en OpenFOAM)
VEL_Y_COMP = 1            # 0=x, 1=y, 2=z  (fachadas normales a Y)

# Planos de medida: ligeramente EMBEBIDOS en el dominio para no caer
# en el borde exacto de la malla (que daba areas incoherentes).
Y_INLET  = 0.11           # fachada sur  (G2, entrada) -> dentro del dominio
Y_OUTLET = 59.89          # fachada norte (G5, salida) -> dentro del dominio

# Extension de la fachada del hall (para restringir el plano)
HALL_X, HALL_Z = (0.0, 15.0), (0.0, 12.0)
HALL_VOLUME = 15.0 * 60.0 * 12.0   # 10800 m3


def _facade(src, y_plane, tag):
    # 1) Slice en el plano de la fachada, normal Y
    sl = Slice(Input=src, registrationName="Slice_" + tag)
    sl.SliceType = "Plane"
    sl.SliceType.Origin = [(HALL_X[0]+HALL_X[1])/2.0, y_plane, (HALL_Z[0]+HALL_Z[1])/2.0]
    sl.SliceType.Normal = [0.0, 1.0, 0.0]

    # 2) Clip Box -> restringe el plano a la fachada 15 x 12 (no todo el dominio)
    #    Caja identica en ambas fachadas (solo cambia la Y del plano) para
    #    que las areas sean consistentes: 15 x 12 = 180 m2.
    clip = Clip(Input=sl, registrationName="Facade_" + tag)
    clip.ClipType = "Box"
    clip.Invert = 1   # conservar el interior de la caja
    clip.ClipType.Position = [HALL_X[0], y_plane - 1.0, HALL_Z[0]]
    clip.ClipType.Length   = [HALL_X[1]-HALL_X[0], 2.0, HALL_Z[1]-HALL_Z[0]]

    # 3) Calculator: componente normal U_Y (Cell Data)
    calc = Calculator(Input=clip, registrationName="Un_" + tag)
    calc.AttributeType = "Cell Data"
    calc.ResultArrayName = "Un"
    calc.Function = "{0}_{1}".format(VEL_ARRAY, "XYZ"[VEL_Y_COMP])   # U_Y
    # si "U_Y" fallara:  calc.Function = "U.jHat"

    # 4) Integrate Variables -> caudal
    integ = IntegrateVariables(Input=calc, registrationName="Integrate_" + tag)
    UpdatePipeline()

    cd = servermanager.Fetch(integ).GetCellData()
    area = cd.GetArray("Area").GetValue(0) if cd.GetArray("Area") else float("nan")
    Q    = cd.GetArray("Un").GetValue(0)   if cd.GetArray("Un")   else float("nan")

    Show(clip)   # dejar visible el plano restringido a la fachada
    return Q, area


def caudal():
    src = GetActiveSource()
    if src is None:
        print("No hay source activo. Carga el result.foam y seleccionalo en el Pipeline Browser.")
        return
    UpdatePipeline()

    tk = GetTimeKeeper()
    times = list(tk.TimestepValues) if tk.TimestepValues else []
    if times:
        UpdatePipeline(time=times[-1])

    print("=" * 60)
    print("Source activo:", src.__class__.__name__)
    if times:
        print("Tiempo:", times[-1])

    cdi = src.CellData
    names = [cdi.GetArray(i).Name for i in range(cdi.GetNumberOfArrays())]
    if VEL_ARRAY not in names:
        print("AVISO: '{}' no esta en Cell Data. Disponibles: {}".format(VEL_ARRAY, names))

    q_in,  a_in  = _facade(src, Y_INLET,  "G2")
    q_out, a_out = _facade(src, Y_OUTLET, "G5")

    print("-" * 60)
    print("  G2 (entrada, y={:.2f}): Q = {:+.4f} m3/s  [area = {:.2f} m2]".format(Y_INLET,  q_in,  a_in))
    print("  G5 (salida,  y={:.2f}): Q = {:+.4f} m3/s  [area = {:.2f} m2]".format(Y_OUTLET, q_out, a_out))
    print("-" * 60)
    if q_in == q_in and q_out == q_out:
        imb = abs(abs(q_in)-abs(q_out))/max(abs(q_in), abs(q_out))*100.0
        print("  |Q_G2| = {:.4f} m3/s   |Q_G5| = {:.4f} m3/s".format(abs(q_in), abs(q_out)))
        print("  Desbalance de masa: {:.2f} %".format(imb))
        print("  ACH: {:.2f} renov/h".format(abs(q_in)*3600.0/HALL_VOLUME))
    print("=" * 60)
    Render()
    return q_in, q_out


caudal()
