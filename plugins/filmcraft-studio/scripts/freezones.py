#!/usr/bin/env python3
"""Zonas libres para pop-ups: dónde poner un bloque de texto sin tapar caras ni personas.

Uso como módulo (lo usa plan_compile):
    occ = occupancy(vision_rows, t0, t1, transform)   # cajas ocupadas en el lienzo (0-1) durante [t0, t1]
    pos, score = best_spot(occ, (w, h), ds, lado_previo="izq")

Uso como CLI (inspeccionar una toma):
    freezones.py VISION.json T0 T1 --size 0.6 0.13 [--ds sbg-brutalista-s5] [--punch 112]

Las cajas de cara se amplían a cabeza y hombros; las de persona se usan tal cual. Se toma la UNIÓN
de todos los muestreos del intervalo (la cámara se mueve), más uno antes y uno después.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def grow_face(b):
    x, y, w, h = b
    return [x - w * 0.9, y - h * 0.6, w * 2.8, h * 3.2]          # cabeza + hombros


def transform_box(b, scale=100.0, anchor=(0.5, 0.5)):
    """Caja de la fuente (0-1) -> lienzo cuando el plano está escalado `scale` % anclado en `anchor`."""
    s = scale / 100
    x, y, w, h = b
    ax, ay = anchor
    return [ax + (x - ax) * s, ay + (y - ay) * s, w * s, h * s]


def occupancy(rows, t0, t1, scale=100.0, anchor=(0.5, 0.5)):
    """rows = [{"t", "faces", "people"}] en tiempo de la fuente."""
    if not rows:
        return None                                                # sin datos de visión
    sel = [r for r in rows if t0 - 1.0 <= r["t"] <= t1 + 1.0]
    if not sel:
        sel = [min(rows, key=lambda r: abs(r["t"] - (t0 + t1) / 2))]
    boxes = []
    for r in sel:
        boxes += [transform_box(grow_face(f), scale, anchor) + ["cara"] for f in r.get("faces", [])]
        boxes += [transform_box(list(p), scale, anchor) + ["persona"] for p in r.get("people", [])]
    return boxes


def inter(a, b):
    """Área de intersección entre [x0,y0,x1,y1] y [x,y,w,h]."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[0] + b[2]), min(a[3], b[1] + b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)


def best_spot(occ, size, ds=None, lado_previo=None, preferir=None, evitar=None):
    """Mejor centro (cx, cy) para un bloque de tamaño (w, h) normalizado.

    Puntúa: solape con personas (prohibitivo), zonas reservadas del DS (marca y subtítulos),
    salirse del lienzo, preferencia por la mitad superior y alternancia de lado con el pop-up anterior.
    Devuelve ((cx, cy), {"solape": área, "lado": "izq|der|centro"}).
    """
    w, h = size
    z = (ds or {}).get("zonas", {})
    reservas = [(0, y0, 1, y1) for y0, y1 in z.get("evitar_y", [[0, 0.12], [0.72, 0.84]])] + list(evitar or [])
    m = z.get("margen", 0.03)
    ymin = z.get("y_min_bloque", 0.14)
    occ = occ or []
    best = None
    cxs = [i / 40 for i in range(41)]
    cys = [i / 80 for i in range(81)]
    for cy in cys:
        if cy - h / 2 < ymin - 1e-6 or cy + h / 2 > 0.97:
            continue
        for cx in cxs:
            if cx - w / 2 < m - 1e-6 or cx + w / 2 > 1 - m + 1e-6:
                continue
            box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
            ovc = sum(inter(box, b) for b in occ if b[4:5] == ["cara"])
            ovp = sum(inter(box, b) for b in occ if b[4:5] != ["cara"])
            ov = ovc + ovp
            rs = sum(inter(box, [r[0], r[1], r[2] - r[0], r[3] - r[1]]) for r in reservas)
            lado = "izq" if cx < 0.45 else ("der" if cx > 0.55 else "centro")
            score = ovc * 1500 + rs * 600 + ovp * 250             # cara > zona de marca/subtítulos > cuerpo
            score += abs(cy - (preferir[1] if preferir else 0.30)) * 0.6         # arriba, cerca de y≈0.30
            if preferir:
                score += abs(cx - preferir[0]) * 0.6
            if lado_previo and lado == lado_previo:
                score += 0.15                                                   # alterna lados
            score += abs(cx - 0.5) * 0.05
            if best is None or score < best[0]:
                best = (score, (round(cx, 4), round(cy, 4)), {"solape": round(ov, 4), "solape_cara": round(ovc, 4),
                                                              "reserva": round(rs, 4), "lado": lado})
    if best is None:
        return (0.5, max(ymin + h / 2, 0.3)), {"solape": None, "lado": "centro", "aviso": "no cabe"}
    return best[1], best[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vision")
    ap.add_argument("t0", type=float)
    ap.add_argument("t1", type=float)
    ap.add_argument("--size", nargs=2, type=float, default=[0.6, 0.13])
    ap.add_argument("--ds")
    ap.add_argument("--punch", type=float, default=100)
    a = ap.parse_args()
    rows = json.load(open(a.vision))
    rows = rows.get("data", rows)
    ds = None
    if a.ds:
        from common import load_ds
        ds = load_ds(a.ds)
    occ = occupancy(rows, a.t0, a.t1, a.punch)
    pos, info = best_spot(occ, tuple(a.size), ds)
    print(json.dumps({"ocupado": [[round(v, 3) for v in b[:4]] + b[4:] for b in occ or []], "pos": pos, **info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
