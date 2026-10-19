#!/usr/bin/env python3
"""Detecta paneos y barridos de cámara para usarlos como transiciones.

Uso:
    camera_motion.py scan VIDEO [--min 40]          # ventanas de 0,5 s con movimiento global fuerte
    camera_motion.py fine VIDEO INICIO FIN          # velocidad cada ~0,1 s dentro de una ventana

Convención: dx/dy = desplazamiento del CONTENIDO (no de la cámara), en px/s sobre un fotograma
reducido a 240x135. dx<0: el contenido va a la izquierda (la cámara gira a la derecha).
OpenCV aplica la rotación del móvil, así que x/y son los del video tal como se ve.
"""
import sys

import cv2
import numpy as np


def frames(path, start=0.0, end=None, every=1):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    if start:
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    i = 0
    while True:
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        ok = cap.grab()
        if not ok or (end is not None and t > end):
            break
        if i % every == 0:
            ok, fr = cap.retrieve()
            if ok:
                yield t, cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (240, 135)).astype(np.float32), fps
        i += 1


def scan_rows(path, thr=40.0):
    """Ventanas de 0,5 s con movimiento global fuerte: [{t, dx, dy, dif, dir}] (dx/dy en px/s a 240x135)."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(fps / 8))
    rows, prev = [], None
    for t, g, _ in frames(path, every=step):
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev, g)
            rows.append((t, dx * fps / step, dy * fps / step, float(np.mean(np.abs(g - prev)))))
        prev = g
    out = []
    if not rows:
        return out, 0.0
    a = np.array(rows)
    dur = float(a[-1, 0])
    t = 0.0
    while t < dur:
        m = (a[:, 0] >= t) & (a[:, 0] < t + 0.5)
        if m.any():
            vx, vy, d = float(np.median(a[m, 1])), float(np.median(a[m, 2])), float(a[m, 3].mean())
            if abs(vx) > thr or abs(vy) > thr:
                if abs(vx) >= abs(vy):
                    lado = "contenido_izq" if vx < 0 else "contenido_der"
                else:
                    lado = "contenido_arriba" if vy < 0 else "contenido_abajo"
                out.append({"t": round(t, 2), "dx": round(vx), "dy": round(vy), "dif": round(d), "dir": lado})
        t += 0.5
    return out, dur


def scan(path, thr=40.0):
    rows, dur = scan_rows(path, thr)
    print(f"{path}  duración≈{dur:.1f}s  (umbral {thr} px/s)")
    for r in rows:
        print(f"  {r['t']:6.1f}s  dx={r['dx']:+7.0f} dy={r['dy']:+7.0f} dif={r['dif']:4.0f}  {r['dir']}")
    print("Confirma cada candidato con: camera_motion.py fine VIDEO t-0.5 t+1.5")


def fine(path, a, b):
    out, prev = [], None
    for t, g, fps in frames(path, a, b):
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev, g)
            out.append((t, dx, dy))
        prev = g
    n = max(1, round(len(out) / max(1, (b - a) * 10)))
    for i in range(0, len(out), n):
        seg = out[i:i + n]
        t = seg[0][0]
        dx = float(np.mean([s[1] for s in seg]))
        dy = float(np.mean([s[2] for s in seg]))
        print(f"{t:7.2f}s dx{dx:+6.1f} dy{dy:+6.1f} {'#' * min(40, int(abs(dx) + abs(dy)))}")
    print("(px por fotograma de la fuente; el pico de la barra es el mejor punto de corte)")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("scan", "fine"):
        sys.exit(__doc__)
    if sys.argv[1] == "scan":
        thr = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 40.0
        scan(sys.argv[2], thr)
    else:
        fine(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
