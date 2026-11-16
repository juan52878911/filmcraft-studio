#!/usr/bin/env python3
"""Convierte una imagen fija en un plano animado coherente con su composición, guiado por su ficha.

Uso:
    imagen_a_video.py IMG --modo {kenburns,parallax,capas,ciclo,revelado} --dur S --fps N --out plano.mp4
                      [--ficha ficha.json] [--lienzo 1920x1080] [--max 1920] [--amp 0.012] [--zoom 0.06]
                      [--orden saliencia|inverso] [--grano auto|0..1] [--profundidad proxy|auto|mapa.png|modelo.onnx]
                      [--motor auto|rigido|malla] [--fotogramas 0.5,2.0] [--semilla 7]
    imagen_a_video.py IMG --plan         # qué haría cada modo con esta imagen (JSON), sin renderizar
    imagen_a_video.py IMG --prompt-ia    # prompt de imagen a video (Kling, Veo, Runway…) hecho con la ficha

Modos (cuándo usar cada uno: skills/director-video/references/imagen-a-video.md):
- kenburns: la cámara recorre los puntos fuertes en orden de saliencia (spline suave, sin salirse). No para
            en adornos de esquina, no corta un titular y el último encuadre contiene el texto entero.
- parallax: 2.5D con empuje hacia el foco principal. Una pieza gráfica (texto, bordes duros) se mueve
            por capas rígidas, sin deformar nada; una foto o ilustración, por malla continua.
- capas:    capas discretas por profundidad con el fondo rellenado; entran escalonadas y derivan. Solo
            para piezas gráficas con fondo liso; en foto las capas solo derivan (y el plan lo avisa).
- ciclo:    bucle sin costura: órbita de paralaje, respiración y grano periódicos (el último fotograma
            enlaza con el primero).
- revelado: la imagen se construye por valores (notan → medios tonos → color) desde el foco principal.

La profundidad sin modelos es un proxy (posición, nitidez, saliencia y croma por segmentos de color):
vale para amplitudes pequeñas. `--profundidad mapa.png` usa un mapa propio (blanco = cerca);
`--profundidad auto` usa Depth Anything si `transformers` y `torch` están instalados y el modelo ya está
en la caché (no descarga nada); un `.onnx` se ejecuta con onnxruntime.

Sale un MP4 H.264 sin audio (`-an`), como el resto de motores. Con `--fotogramas` escribe PNG en esos
segundos en vez del video. Imprime un JSON con fotogramas, duración y tiempos.
"""
import argparse
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
import ref_metricas as rm  # noqa: E402

MODOS = ("kenburns", "parallax", "capas", "ciclo", "revelado")


def suave(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def _par(v):
    return int(v) // 2 * 2


def cargar(path, lienzo=None, maximo=1920, sobre=1.0):
    """Imagen uint8 RGB al tamaño de salida × `sobre` (margen de resolución para acercar), y (W, H) de salida."""
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        im = Image.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, 255)), im)
    im = im.convert("RGB")
    if lienzo:
        W, H = lienzo
        s = max(W / im.width, H / im.height)                           # cubre el lienzo y recorta al centro
        tw, th = math.ceil(im.width * s), math.ceil(im.height * s)
        x0, y0 = (tw - W) // 2, (th - H) // 2
        caja = (x0 / s, y0 / s, (x0 + W) / s, (y0 + H) / s)
    else:
        s = min(1.0, maximo / max(im.size))
        W, H = _par(im.width * s), _par(im.height * s)
        caja = (0, 0, im.width, im.height)
    k = min(sobre, max(1.0, (caja[2] - caja[0]) / W))
    src = im.resize((round(W * k), round(H * k)), Image.LANCZOS, box=caja, reducing_gap=3.0)
    return np.asarray(src), (W, H)


# ---------------------------------------------------------------- profundidad

def profundidad(src, ficha, modo="proxy"):
    """Mapa float32 0..1 (1 = cerca) al tamaño de `src`, y de dónde salió."""
    h, w = src.shape[:2]
    origen, d = "proxy", None
    if modo not in ("proxy", "auto") and Path(modo).suffix.lower() == ".onnx":
        d, origen = _profundidad_onnx(src, modo), f"onnx:{Path(modo).name}"
    elif modo not in ("proxy", "auto"):
        d = np.asarray(Image.open(modo).convert("L").resize((w, h), Image.BILINEAR), np.float32) / 255
        origen = f"mapa:{Path(modo).name}"
    elif modo == "auto":
        d = _profundidad_transformers(src)
        origen = "depth-anything" if d is not None else "proxy"
    if d is None:
        s = 384 / max(h, w)
        peq = cv2.resize(src, (max(8, round(w * s)), max(8, round(h * s))), interpolation=cv2.INTER_AREA)
        d = rm.profundidad_proxy(peq.astype(np.float32) / 255, texto=ficha["metricas"]["texto"])
        d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
    d = d - d.min()
    return (d / d.max() if d.max() > 1e-6 else d).astype(np.float32), origen


def _profundidad_transformers(src):
    try:
        import torch  # noqa: F401
        from transformers import pipeline
    except ImportError:
        return None
    for modelo in ("depth-anything/Depth-Anything-V2-Small-hf", "LiheYoung/depth-anything-small-hf"):
        try:
            p = pipeline("depth-estimation", model=modelo, model_kwargs={"local_files_only": True})
            d = np.asarray(p(Image.fromarray(src))["depth"], np.float32)
            return cv2.resize(d, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_CUBIC)
        except Exception:
            continue
    return None


def _profundidad_onnx(src, modelo):
    """Depth Anything exportado a ONNX: entrada 1×3×518×518 normalizada; salida = disparidad (más = cerca)."""
    import onnxruntime as ort
    s = ort.InferenceSession(str(modelo), providers=ort.get_available_providers())
    x = cv2.resize(src, (518, 518), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
    d = np.squeeze(s.run(None, {s.get_inputs()[0].name: x})[0]).astype(np.float32)
    return cv2.resize(d, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_CUBIC)


# ---------------------------------------------------------------- escenas (cada una devuelve f(u) → RGB uint8)

def _foco(ficha):
    p = ficha["metricas"]["composicion"]["puntos_fuertes"]
    c = ficha["metricas"]["composicion"]["centro_masa"]
    return (p[0]["x"], p[0]["y"]) if p else (c["x"], c["y"])


PESO_MIN = 0.08                  # un foco con menos peso es un adorno: la cámara no para ahí
BORDE_MIN = 0.08                 # ni a menos del 8 % del borde (pegatinas de esquina, marcas de corte)
VEL_MAX = 0.30                   # velocidad punta de la cámara, en anchos de ventana por segundo
MARGEN_TEXTO = 0.025             # aire entre un texto y el borde del encuadre


def _union(cajas, margen=MARGEN_TEXTO):
    """Rectángulo (x0, y0, x1, y1) que contiene las cajas, con aire. None si no hay."""
    if not cajas:
        return None
    return (max(0.0, min(k["x"] for k in cajas) - margen), max(0.0, min(k["y"] for k in cajas) - margen),
            min(1.0, max(k["x"] + k["w"] for k in cajas) + margen), min(1.0, max(k["y"] + k["h"] for k in cajas) + margen))


def _textos(ficha):
    """(titulares, todo): rectángulos de los renglones grandes (≥ 60 % del más alto) y de todo el texto."""
    t = ficha["metricas"]["texto"]
    cajas = t.get("cajas") or []
    if not t.get("hay") or not cajas:
        return None, None
    alto = max(k["h"] for k in cajas)
    return _union([k for k in cajas if k["h"] >= 0.6 * alto]), _union(cajas)


def _contener(x, y, z, r):
    """Encuadre (centro y zoom) corregido para que el rectángulo `r` quede entero dentro: baja el zoom lo
    justo y desplaza el centro. Es continuo en (x, y, z): aplicado fotograma a fotograma no da saltos."""
    if r is not None:
        z = max(1.0, min(z, 1 / max(r[2] - r[0], r[3] - r[1], 1e-6)))
        m = 0.5 / z
        x, y = min(max(x, r[2] - m), r[0] + m), min(max(y, r[3] - m), r[1] + m)
    m = 0.5 / z
    return min(max(x, m), 1 - m), min(max(y, m), 1 - m), z                # y la ventana no se sale de la imagen


def _tramos(paradas):
    """Longitud de cada tramo en anchos de ventana: desplazamiento del centro a ese zoom más el cambio de zoom."""
    return [math.hypot(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) * math.sqrt(a["zoom"] * b["zoom"]),
                       math.log(b["zoom"] / a["zoom"])) for a, b in zip(paradas, paradas[1:])]


def velocidad_punta(paradas, dur):
    """Velocidad punta estimada (anchos de ventana por segundo). Cada tramo dura lo mismo, así que manda el
    más largo; la suavización global la sube hasta 1,5× en el centro del plano."""
    t = _tramos(paradas)
    return 1.5 * len(t) * max(t) / max(dur, 1e-6) if t else 0.0


def ruta_camara(ficha, dur, orden="saliencia", zoom_max=1.5):
    """Paradas de la cámara: plano general y los puntos fuertes en orden de saliencia (≥ 1,5 s por parada).

    No para en adornos (focos con peso < 8 % o a menos del 8 % del borde). Con texto, ninguna parada corta
    un titular y la última contiene el texto entero. Si el camino pide más de `VEL_MAX` anchos de ventana
    por segundo (`velocidad_punta`), se quitan paradas (las menos salientes) y, si aún corre, se acorta."""
    comp = ficha["metricas"]["composicion"]
    todos = comp["puntos_fuertes"]
    pts = [p for p in todos if p["peso"] >= PESO_MIN and BORDE_MIN <= p["x"] <= 1 - BORDE_MIN
           and BORDE_MIN <= p["y"] <= 1 - BORDE_MIN]
    if not pts and todos:                                              # el único foco está en el borde: se mira desde dentro
        p = todos[0]
        pts = [dict(p, x=min(max(p["x"], 2 * BORDE_MIN), 1 - 2 * BORDE_MIN),
                    y=min(max(p["y"], 2 * BORDE_MIN), 1 - 2 * BORDE_MIN))]
    n = max(1, min(len(pts), 4, int(dur / 1.5)))
    paradas = [{"x": p["x"], "y": p["y"], "zoom": round(min(zoom_max, 1.25 + 0.5 * min(p["peso"], 0.5)), 2)}
               for p in pts[:n]]
    if not paradas:
        paradas = [{"x": 0.5, "y": 0.5, "zoom": 1.2}]
    cm = comp["centro_masa"]
    general = {"x": round(0.5 + 0.3 * (cm["x"] - 0.5), 3), "y": round(0.5 + 0.3 * (cm["y"] - 0.5), 3), "zoom": 1.03}
    titulares, todo = _textos(ficha)

    def ajusta(lista):
        out = []
        for i, q in enumerate(lista):
            final = i == len(lista) - 1 and orden != "inverso"
            x, y, z = _contener(q["x"], q["y"], q["zoom"], todo if final else titulares)
            out.append({"x": round(x, 3), "y": round(y, 3), "zoom": round(z, 3)})
        return [general] + out
    ruta = ajusta(paradas)
    while velocidad_punta(ruta, dur) > VEL_MAX and len(paradas) > 1:
        paradas = paradas[:-1]
        ruta = ajusta(paradas)
    if velocidad_punta(ruta, dur) > VEL_MAX:                            # una sola parada y aún corre: se queda a medio camino
        k = VEL_MAX / velocidad_punta(ruta, dur)
        q = ruta[1]
        ruta[1] = {"x": round(general["x"] + k * (q["x"] - general["x"]), 3),
                   "y": round(general["y"] + k * (q["y"] - general["y"]), 3),
                   "zoom": round(math.exp(math.log(general["zoom"]) + k * math.log(q["zoom"] / general["zoom"])), 3)}
        x, y, z = _contener(ruta[1]["x"], ruta[1]["y"], ruta[1]["zoom"], todo if orden != "inverso" else titulares)
        ruta[1] = {"x": round(x, 3), "y": round(y, 3), "zoom": round(z, 3)}
    return ruta[::-1] if orden == "inverso" else ruta


def _spline(ks, u):
    """Catmull-Rom por (x, y, log zoom) con u en 0..1."""
    n = len(ks) - 1
    if n == 0:
        return ks[0]
    t = min(u * n, n - 1e-9)
    i = int(t)
    t -= i
    p = [ks[max(i - 1, 0)], ks[i], ks[i + 1], ks[min(i + 2, n)]]
    out = []
    for a, b, c, d in zip(*p):
        out.append(0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t ** 3))
    return out


def encuadres(ficha, dur, orden="saliencia"):
    """→ (paradas, f(u) → (x, y, zoom)): el encuadre de kenburns en cada instante, ya corregido para no
    cortar titulares. Separado del render para poder comprobarlo sin dibujar."""
    paradas = ruta_camara(ficha, dur, orden)
    ks = [(p["x"], p["y"], math.log(p["zoom"])) for p in paradas]
    titulares, _ = _textos(ficha)

    def f(u):
        x, y, lz = _spline(ks, suave(u))
        return _contener(x, y, max(1.0, math.exp(lz)), titulares)
    return paradas, f


def escena_kenburns(src, tam, ficha, a):
    W, H = tam
    sh, sw = src.shape[:2]
    k = sw / W
    paradas, enc = encuadres(ficha, a.dur, a.orden)
    titulares, todo = _textos(ficha)

    def f(u):
        x, y, z = enc(u)
        e = z / k
        M = np.float32([[e, 0, W / 2 - e * x * sw], [0, e, H / 2 - e * y * sh]])
        return cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_CUBIC if e > 0.75 else cv2.INTER_AREA,
                              borderMode=cv2.BORDER_REFLECT_101)
    plan = {"paradas": paradas, "velocidad_punta": round(velocidad_punta(paradas, a.dur), 3)}
    if todo:
        plan["texto"] = {"titulares": [round(v, 3) for v in titulares], "todo": [round(v, 3) for v in todo],
                         "regla": "ningún encuadre corta un titular; el último contiene el texto entero"}
    return f, plan


def _malla(W, H):
    return np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))


def _paralaje(src, d, tam, foco, ox, oy, empuje):
    """Desplaza cada píxel según su profundidad (d − 0,5) y lo acerca hacia el foco (más los cercanos)."""
    W, H = tam
    xx, yy = _paralaje.malla if getattr(_paralaje, "tam", None) == tam else _malla(W, H)
    _paralaje.malla, _paralaje.tam = (xx, yy), tam
    fx, fy = foco[0] * W, foco[1] * H
    s = 1.0 + empuje * (0.4 + 1.2 * d)
    mx = fx + (xx - fx) / s - (d - 0.5) * ox
    my = fy + (yy - fy) / s - (d - 0.5) * oy
    return cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def _base(src, tam):
    return cv2.resize(src, tam, interpolation=cv2.INTER_AREA) if src.shape[1] != tam[0] else src


def _es_grafica(ficha):
    """Texto o formas de borde duro: nada se puede deformar, así que se mueve por capas rígidas."""
    m = ficha["metricas"]
    return bool(ficha["video"]["sugerido"].get("pieza_grafica", m["texto"]["hay"]))


def _motor(a, ficha):
    return a.motor if a.motor != "auto" else "rigido" if _es_grafica(ficha) else "malla"


def _capas_por_forma(img, d, n=3):
    """Reparte la imagen en n capas (0 = fondo … n−1 = primer plano) sin partir formas.

    Segmenta por color (k-means en OKLab). Si un color ocupa casi la mitad del cuadro es el fondo, y lo
    demás se agrupa en objetos (formas vecinas y lo que encierran: una tarjeta con su texto es un objeto).
    Si no hay fondo (foto), los objetos son los componentes de cada color. Cada objeto va entero a la capa
    que le toca por su profundidad media."""
    H, W = d.shape
    s = 256 / max(H, W)
    peq = cv2.resize(img, (max(8, round(W * s)), max(8, round(H * s))), interpolation=cv2.INTER_AREA)
    cv2.setRNGSeed(11)
    _, _, cen = cv2.kmeans(rm.oklab(peq.astype(np.float32) / 255).reshape(-1, 3), 6, None,
                           (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1e-3), 1, cv2.KMEANS_PP_CENTERS)
    lab = rm.oklab(img.astype(np.float32) / 255)
    lbl = np.stack([((lab - c) ** 2).sum(-1) for c in cen]).argmin(0).astype(np.uint8)
    area = np.bincount(lbl.ravel(), minlength=6) / lbl.size
    fondo = int(area.argmax()) if area.max() >= 0.45 else -1
    if fondo >= 0:
        k = max(3, int(0.012 * W)) | 1                                  # más ancho que alto: une las palabras de un renglón
        junto = cv2.morphologyEx((lbl != fondo).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, 3 * k), np.uint8))
        cont, _ = cv2.findContours(junto, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        lleno = np.zeros((H, W), np.uint8)
        cv2.drawContours(lleno, cont, -1, 1, cv2.FILLED)
        k0, comp = cv2.connectedComponents(lleno, connectivity=8)
    else:
        comp, k0 = np.zeros((H, W), np.int32), 1
        for k in range(6):
            if (lbl == k).any():
                nc, c = cv2.connectedComponents((lbl == k).astype(np.uint8), connectivity=8)
                comp[c > 0] = c[c > 0] + k0 - 1
                k0 += nc - 1
    ar = np.bincount(comp.ravel(), minlength=k0).astype(np.float64)
    pr = np.bincount(comp.ravel(), d.ravel(), minlength=k0) / np.maximum(ar, 1)
    orden = np.argsort(pr[1:]) + 1
    acum = np.cumsum(ar[orden]) / max(ar[1:].sum(), 1)
    grupos = n - 1 if fondo >= 0 else n
    capa = np.zeros(k0, np.int32)
    for i in range(1, grupos):                                          # cortes por profundidad: empates, juntos
        if (acum >= i / grupos).any():
            corte = pr[orden][np.argmax(acum >= i / grupos)]
            capa[1:][pr[1:] > corte] += 1
    if fondo >= 0:
        capa[1:] += 1
    return capa[comp], fondo >= 0


def _separar(img, d, n, foco):
    """Plato de fondo (con lo que tapan las capas rellenado) y las capas de delante con su máscara."""
    H, W = d.shape
    idx, con_fondo = _capas_por_forma(img, d, n)
    pluma = max(1.0, W / 600)
    q = 4
    hueco = cv2.resize((idx >= 1).astype(np.float32), (W // q, H // q), interpolation=cv2.INTER_AREA)
    hueco = cv2.dilate((hueco > 0).astype(np.uint8), np.ones((5, 5), np.uint8))
    peq = cv2.resize(img, (W // q, H // q), interpolation=cv2.INTER_AREA)
    if 0 < hueco.mean() < 0.97:
        relleno = cv2.inpaint(peq, hueco, 4, cv2.INPAINT_TELEA)
    else:
        relleno = peq
    relleno = cv2.resize(relleno, (W, H), interpolation=cv2.INTER_CUBIC)
    hm = cv2.resize(cv2.GaussianBlur(hueco.astype(np.float32), (0, 0), 1.0), (W, H), interpolation=cv2.INTER_LINEAR)
    hm = np.clip(hm * 1.5, 0, 1)[..., None]
    fondo = img * (1 - hm) + relleno * hm
    capas = []
    for i in range(1, n):
        # Con fondo (pieza gráfica) cada capa son sus objetos, separados por el fondo. Sin fondo (foto) las
        # capas se tocan: cada una lleva también todo lo que tiene delante, así al separarse no se abre una
        # costura por la que asome el relleno (los trazos oscuros que quedaban en las crestas).
        m = cv2.GaussianBlur(((idx == i) if con_fondo else (idx >= i)).astype(np.float32), (0, 0), pluma)
        ys, xs = np.nonzero(idx == i)
        if not len(xs):
            continue
        v = np.array([xs.mean() / W - foco[0], ys.mean() / H - foco[1]])
        v = v / np.linalg.norm(v) if np.linalg.norm(v) > 1e-3 else np.array([0.0, 1.0])
        capas.append({"i": i, "m": m, "prof": i / (n - 1), "entra": v * 0.05 * W, "area": float((idx == i).mean())})
    return fondo.astype(np.float32), capas, con_fondo


def _componer(fondo, imgf, capas, tam, foco, ox, oy, empuje, entrada=None):
    """Capas rígidas: cada una se desplaza y se acerca según su profundidad; el fondo va al revés."""
    W, H = tam
    fx, fy = foco[0] * W, foco[1] * H

    def M(prof, dx=0.0, dy=0.0):
        s = 1 + empuje * (0.4 + 1.2 * prof)
        return np.float32([[s, 0, fx * (1 - s) + (prof - 0.5) * ox + dx], [0, s, fy * (1 - s) + (prof - 0.5) * oy + dy]])
    out = cv2.warpAffine(fondo, M(0.0), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    for c in capas:
        en = 1.0 if entrada is None else entrada(c)
        if en <= 0:
            continue
        m = M(c["prof"], (1 - en) * c["entra"][0], (1 - en) * c["entra"][1])
        ci = cv2.warpAffine(imgf, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        cm = cv2.warpAffine(c["m"], m, (W, H), flags=cv2.INTER_LINEAR)[..., None]
        if en < 1:
            cm = cm * en
        out = out * (1 - cm) + ci * cm
    return np.clip(out, 0, 255).astype(np.uint8)


def _movil(src, tam, ficha, a, n=4):
    """Prepara el paralaje: devuelve mover(ox, oy, empuje) → fotograma, y el plan."""
    img = _base(src, tam)
    d, origen = profundidad(img, ficha, a.profundidad)
    foco = _foco(ficha)
    motor = _motor(a, ficha)
    if motor == "rigido":
        fondo, capas, _ = _separar(img, d, n, foco)
        imgf = img.astype(np.float32)
        return (lambda ox, oy, e: _componer(fondo, imgf, capas, tam, foco, ox, oy, e)), \
            {"profundidad": origen, "motor": motor, "capas": len(capas) + 1, "foco": list(foco)}
    return (lambda ox, oy, e: _paralaje(img, d, tam, foco, ox, oy, e)), \
        {"profundidad": origen, "motor": motor, "foco": list(foco)}


def escena_parallax(src, tam, ficha, a):
    mover, plan = _movil(src, tam, ficha, a)
    ex, ey = ficha["video"]["sugerido"].get("paralaje_eje", [1.0, 0.0])
    A = a.amp * tam[0] * 2                                              # recorrido total de la cámara, en px

    def f(u):
        e = suave(u)
        return mover((e - 0.5) * A * ex, (e - 0.5) * A * ey, a.zoom * e)
    return f, dict(plan, eje=[ex, ey], recorrido_px=round(A, 1))


def escena_ciclo(src, tam, ficha, a):
    mover, plan = _movil(src, tam, ficha, a)
    A = a.amp * tam[0]

    def f(u):                                                           # todo es función de la fase: u=1 ≡ u=0
        fase = 2 * math.pi * u
        return mover(A * math.sin(fase), 0.5 * A * math.sin(2 * fase), a.zoom * 0.5 * (0.5 - 0.5 * math.cos(fase)))
    return f, dict(plan, amplitud_px=round(A, 1), bucle=True)


def escena_capas(src, tam, ficha, a, n=3):
    img = _base(src, tam)
    d, origen = profundidad(img, ficha, a.profundidad)
    foco = _foco(ficha)
    fondo, capas, con_fondo = _separar(img, d, n, foco)
    imgf = img.astype(np.float32)
    ex, ey = ficha["video"]["sugerido"].get("paralaje_eje", [1.0, 0.0])
    A = a.amp * tam[0] * 2
    # entrada escalonada, de atrás hacia delante; después, deriva de paralaje. Sin un fondo liso detrás
    # (foto) no hay nada limpio que enseñar mientras entra una capa: solo deriva.
    entrada = (lambda u: (lambda c: suave((u - 0.08 - 0.14 * (c["i"] - 1)) / 0.3))) if con_fondo else (lambda u: None)

    def f(u):
        e = suave(u)
        return _componer(fondo, imgf, capas, tam, foco, (e - 0.5) * A * ex, (e - 0.5) * A * ey, a.zoom * e,
                         entrada=entrada(u))
    plan = {"profundidad": origen, "capas": [{"capa": c["i"], "area": round(c["area"], 3)} for c in capas],
            "recorrido_px": round(A, 1),
            "entradas_s": [round((0.08 + 0.14 * (c["i"] - 1)) * a.dur, 2) for c in capas] if con_fondo else []}
    if not con_fondo:
        plan["aviso"] = ("la imagen no tiene un fondo liso (foto o ilustración continua): las capas no entran "
                         "escalonadas, solo derivan. Para esta imagen conviene parallax o kenburns.")
    return f, plan


def escena_revelado(src, tam, ficha, a):
    W, H = tam
    img = _base(src, tam)
    imgf = img.astype(np.float32)
    L = np.clip(rm.oklab(imgf / 255)[..., 0], 0, 1)
    t1, t2 = ficha["metricas"]["valores"]["notan3"]["umbrales"]
    cls = (L >= t1).astype(np.uint8) + (L >= t2).astype(np.uint8)
    medios = [imgf[cls == i].mean(0) if (cls == i).any() else imgf.mean(0) for i in range(3)]
    dom = int(np.argmax([(cls == i).mean() for i in range(3)]))
    notan = np.zeros_like(imgf)
    for i in range(3):
        notan[cls == i] = medios[i]
    notan = cv2.GaussianBlur(notan, (0, 0), max(0.6, W / 1500))          # filo de recorte, sin dientes
    fondo = np.float32(medios[dom])
    foco = _foco(ficha)
    xx, yy = _malla(W, H)
    r = np.hypot(xx - foco[0] * W, yy - foco[1] * H)
    campo = r / r.max()                                                  # 0 en el foco, 1 en lo más lejano
    rng = np.random.default_rng(a.semilla)
    ruido = cv2.resize(rng.random((max(2, H // 48), max(2, W // 48)), dtype=np.float32), (W, H),
                       interpolation=cv2.INTER_CUBIC)
    campo = np.clip(0.85 * campo + 0.15 * ruido, 0, 1)

    def frente(p, ancho=0.18):
        """Máscara 0..1 de un frente que sale del foco: p=0 nada, p=1 todo."""
        x = np.clip((p * (1 + ancho) - campo) / ancho, 0, 1)
        return (x * x * (3 - 2 * x))[..., None]

    def f(u):
        ma = frente(suave((u - 0.04) / 0.42))                           # A: la masa (notan) sobre el valor dominante
        mb = frente(suave((u - 0.38) / 0.47))                           # B: del notan a la imagen
        out = fondo * (1 - ma) + notan * ma
        out = out * (1 - mb) + imgf * mb
        z = 1 + a.zoom * 0.5 * suave(u)
        if z > 1.0005:
            fx, fy = foco[0] * W, foco[1] * H
            M = np.float32([[z, 0, fx * (1 - z)], [0, z, fy * (1 - z)]])
            out = cv2.warpAffine(out, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        return np.clip(out, 0, 255).astype(np.uint8)
    return f, {"foco": list(foco), "umbrales": [t1, t2], "valor_dominante": ["oscuro", "medio", "claro"][dom],
               "fases": {"masa_s": [round(0.04 * a.dur, 2), round(0.46 * a.dur, 2)],
                         "color_s": [round(0.38 * a.dur, 2), round(0.85 * a.dur, 2)]}}


ESCENAS = {"kenburns": escena_kenburns, "parallax": escena_parallax, "capas": escena_capas, "ciclo": escena_ciclo,
           "revelado": escena_revelado}


# ---------------------------------------------------------------- grano, render, prompt

def grano(tam, fuerza, semilla, n=8):
    """n texturas de grano int16 (σ = fuerza × 16 niveles); se rotan por fotograma."""
    if fuerza <= 0:
        return None
    rng = np.random.default_rng(semilla)
    W, H = tam
    g = rng.standard_normal((n, H // 2 + 1, W // 2 + 1), dtype=np.float32) * fuerza * 16
    return [cv2.resize(x, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.int16)[..., None] for x in g]


def con_grano(fr, g, i):
    if g is None:
        return fr
    return np.clip(fr.astype(np.int16) + g[i % len(g)], 0, 255).astype(np.uint8)


def preparar(a):
    t0 = time.perf_counter()
    if a.ficha and Path(a.ficha).is_file():
        ficha = json.loads(Path(a.ficha).read_text())
    else:
        ficha = rm.ficha(a.imagen)
    t_ficha = time.perf_counter() - t0
    modo = a.modo or ficha["video"]["sugerido"]["modo"]
    src, tam = cargar(a.imagen, a.lienzo, a.max, 1.5 if modo == "kenburns" else 1.0)
    if a.lienzo:                                                         # el recorte cambia la composición: se mide lo que se ve
        with tempfile.TemporaryDirectory() as tmp:
            rec = Path(tmp) / "lienzo.png"
            Image.fromarray(cv2.resize(src, tam, interpolation=cv2.INTER_AREA)).save(rec)
            ficha = rm.ficha(rec)
    fuerza = ficha["video"]["sugerido"].get("grano", 0.0) if a.grano == "auto" else float(a.grano)
    f, plan = ESCENAS[modo](src, tam, ficha, a)
    return ficha, modo, tam, f, plan, fuerza, t_ficha, time.perf_counter() - t0


def renderizar(a):
    ficha, modo, tam, f, plan, fuerza, t_ficha, t_prep = preparar(a)
    W, H = tam
    n = max(1, round(a.dur * a.fps))
    g = grano(tam, fuerza, a.semilla)
    den = n if modo == "ciclo" else max(1, n - 1)                       # el ciclo no repite el primer fotograma
    info = {"modo": modo, "lienzo": f"{W}x{H}", "fps": a.fps, "fotogramas": n, "dur_s": round(n / a.fps, 3),
            "grano": round(fuerza, 3), "plan": plan, "ficha_s": round(t_ficha, 3), "preparacion_s": round(t_prep, 3)}
    if a.fotogramas:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        info["png"] = []
        for t in a.fotogramas:
            i = min(n - 1, max(0, round(t * a.fps)))
            p = out.with_name(f"{out.stem}_{t:05.2f}s.png")
            Image.fromarray(con_grano(f(i / den), g, i)).save(p)
            info["png"].append(str(p))
        return info
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(a.out)]
    t0 = time.perf_counter()
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            ff.stdin.write(np.ascontiguousarray(con_grano(f(i / den), g, i)).tobytes())
        ff.stdin.close()
    except BrokenPipeError:
        pass
    err = ff.stderr.read().decode(errors="replace")
    if ff.wait() != 0:
        sys.exit(f"ffmpeg falló: {err.strip()[-400:]}")
    t = time.perf_counter() - t0
    info.update(out=str(a.out), render_s=round(t, 2), ms_por_fotograma=round(1000 * t / n, 1),
                mb=round(Path(a.out).stat().st_size / 1e6, 2))
    return info


def prompt_ia(ficha, modo=None, dur=4):
    """Prompt de imagen a video para un modelo generativo, escrito con lo medido. No llama a ninguna API."""
    m, v = ficha["metricas"], ficha["video"]
    c, fi = m["composicion"], ficha.get("filosofia") or {}
    pts = c["puntos_fuertes"]
    foco = f"{round(pts[0]['x'] * 100)}% from the left, {round(pts[0]['y'] * 100)}% from the top" if pts else "the center"
    grafica = _es_grafica(ficha)
    hz = c["lineas"]["horizonte"]
    if hz and (grafica or hz.get("confianza", 0) < 0.6):               # en una pieza gráfica no hay horizonte que seguir
        hz = None
    if hz and hz.get("inclinado"):                                     # un horizonte inclinado ya rompe la simetría
        cam = (f"slow tracking shot parallel to the horizon line, which crosses the frame at {round(hz['y'] * 100)}% height "
               f"tilted {abs(hz['angulo']):.0f} degrees; keep that tilt, do not level it")
    elif c["simetria"]["horizontal"] > 0.75:
        cam = "slow, perfectly centered push-in; no lateral drift (the frame is symmetric)"
    elif hz:
        cam = f"slow lateral tracking shot parallel to the horizon line at {round(hz['y'] * 100)}% height; horizon stays level"
    elif c["lineas"]["diagonal"] > 0.5 and c["lineas"]["n"] >= 3:
        cam = "slow move along the dominant diagonal of the composition"
    else:
        cam = "slow push-in toward the main subject"
    luz = {"alta": "high-key, bright, low contrast", "baja": "low-key, deep shadows",
           "media": "mid-key, balanced exposure"}[m["valores"]["clave"]]
    prof = {"plana": "flat, graphic depth: keep parallax minimal", "atmosferica": "atmospheric depth",
            "foco_selectivo": "shallow depth of field"}[m["profundidad"]["pista"]]
    arm = {"acromatica": "achromatic", "monocromatica": "monochromatic", "analoga": "analogous", "diada": "two-hue",
           "complementaria": "complementary", "complementaria_dividida": "split-complementary", "triada": "triadic",
           "tetrada": "tetradic", "policromatica": "multi-hue"}[m["color"]["armonia"]["tipo"]]
    pal = ", ".join(k["hex"] for k in m["color"]["paleta"][:4])
    du = m["bordes"]["duros"]
    filo = "crisp hard edges, graphic shapes" if du >= 0.9 else "soft edges, gentle falloff" if du < 0.5 else \
        "defined edges with soft shading between them"
    gr = "visible animated film grain" if m["textura"]["grano"] > 0.006 else "clean, no added grain"
    quieto = ["any text or lettering stays perfectly rigid and legible, never morphs or gets cropped"] if m["texto"]["hay"] else []
    quieto.append("composition, palette and value structure of the first frame are preserved")
    pa, ti, trat = m.get("patron") or {}, m.get("tipografia") or {}, m.get("tratamiento") or {}
    if pa.get("hay"):
        quieto.append(f"the {'halftone dot' if pa['tipo'] == 'puntos' else 'line'} pattern keeps its scale and angle "
                      f"({pa['angulo']:.0f} degrees), no moire, no blur")
    if (trat.get("desregistro") or {}).get("hay"):
        quieto.append("the ink misregistration (offset color layers) stays exactly as printed")
    if (trat.get("duotono") or {}).get("hay"):
        quieto.append(f"strict duotone from {trat['duotono']['sombra']} to {trat['duotono']['luz']}")
    if ti.get("hay") and ti.get("peso_clase"):
        peso = {"fina": "light", "regular": "regular", "negrita": "bold", "extra": "extra-bold"}[ti["peso_clase"]]
        quieto.append(f"{peso} {'uppercase ' if ti.get('caja') == 'alta' else ''}lettering keeps its weight and size hierarchy")
    lineas = [
        f"IMAGE-TO-VIDEO · first frame = the supplied image · {dur} s · {ficha['imagen']['ancho']}x{ficha['imagen']['alto']}",
        f"Camera: {cam}. Main subject at {foco}; it is where the move ends.",
        f"Motion: only what the image implies; background elements drift slower than foreground ({prof}). "
        f"Subtle, continuous, no new objects, no cuts.",
        f"Light and color: {luz}; {arm} palette ({pal}); color temperature "
        f"{'warm' if m['color']['temperatura'] > 0.15 else 'cool' if m['color']['temperatura'] < -0.15 else 'neutral'}; "
        f"do not shift hues or add colors.",
        f"Texture: {filo}; {gr}.",
        "Keep: " + "; ".join(quieto) + ".",
        "Avoid: morphing, warping, extra limbs or objects, invented text, logos, lens flares, zoom faster than 5% per second, "
        "style drift toward generic stock footage.",
    ]
    def frase(v):
        return ("; ".join(str(x) for x in v) if isinstance(v, list) else str(v)).strip().rstrip(".")
    # capa 2 (filosofía): lo que la ficha dice que hace el estilo entra en el prompt tal cual
    if fi.get("emocion"):
        lineas.insert(2, f"Mood: {frase(fi['emocion'])}.")
    if fi.get("movimiento"):
        lineas.insert(2, f"Visual movement: {frase(fi['movimiento'])}.")
    if fi.get("regla_generadora"):
        lineas.insert(2, f"Rule of the style (must hold in every frame): {frase(fi['regla_generadora'])}.")
    if fi.get("que_la_distingue"):
        lineas.insert(-1, f"What makes it distinctive (do not lose it): {frase(fi['que_la_distingue'])}.")
    if fi.get("donde_no"):
        lineas[-1] = lineas[-1].rstrip(".") + f"; and never: {frase(fi['donde_no'])}."
    pend = rm.filosofia_pendiente(ficha)
    return {"prompt": "\n".join(lineas),
            "filosofia": {"usada": [k for k in ("regla_generadora", "movimiento", "emocion", "que_la_distingue", "donde_no")
                                    if fi.get(k)], "pendiente": pend},
            "notas": (["La capa 2 (filosofía) de la ficha está sin rellenar: el prompt solo lleva medidas. Rellénala "
                       "(references/referencias.md) y pasa --ficha para que entren la regla, la emoción y el «dónde no»."]
                      if pend else []) +
                     ["Siempre desde imagen propia; 2–4 s por plano y 2–3 tomas.",
                      "Verifica el resultado con referencias.py --comparar IMG fotograma.png: el grupo «estilo» debe "
                      "seguir dentro de tolerancia en el último fotograma.",
                      "Pasa después por el grade y el grano del DS; anota modelo, prompt y licencia en el informe."],
            "traduccion": v["traduccion"], "modo_local_equivalente": modo or v["sugerido"]["modo"]}


def plan_de(ficha, dur=5.0, orden="saliencia"):
    """Lo que haría cada modo con esta imagen, sin renderizar: medidas (capas 1 y 3) y, si la ficha la
    trae, la capa 2: la regla del estilo y el «dónde no» mandan sobre el modo sugerido."""
    fi = ficha.get("filosofia") or {}
    v = ficha["video"]
    titulares, todo = _textos(ficha)
    paradas = ruta_camara(ficha, dur, orden)
    out = {"sugerido": v["sugerido"], "traduccion": v["traduccion"], "kenburns": paradas,
           "kenburns_velocidad_punta": round(velocidad_punta(paradas, dur), 3),
           "texto_protegido": {"titulares": titulares, "todo": todo} if todo else None,
           "filosofia": {k: fi[k] for k in ("regla_generadora", "movimiento", "emocion", "donde_actua", "donde_no",
                                            "que_la_distingue") if fi.get(k)},
           "plan_del_modelo": {k: v[k] for k in ("que_se_anima", "camara", "ritmo", "transiciones", "plan") if v.get(k)}}
    pend = rm.filosofia_pendiente(ficha)
    if pend:
        out["aviso"] = ("capa 2 (filosofía) sin rellenar: este plan solo traduce medidas. Antes de animar, rellena "
                        "la ficha (regla generadora, dónde no actúa) y vuelve a pedir el plan con --ficha.")
    else:
        out["criterio"] = [f"todo movimiento cumple la regla: {fi['regla_generadora']}",
                           f"no se anima: {'; '.join(fi['donde_no']) if isinstance(fi['donde_no'], list) else fi['donde_no']}"]
    return out


def _lienzo(s):
    w, h = s.lower().split("x")
    return _par(w), _par(h)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("imagen")
    ap.add_argument("--modo", choices=MODOS, help="por defecto, el sugerido por la ficha")
    ap.add_argument("--dur", type=float, default=5.0)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--out")
    ap.add_argument("--ficha", help="ficha ya medida (ref_metricas.py --ficha); si no, se mide")
    ap.add_argument("--lienzo", type=_lienzo, help="ANCHOxALTO; la imagen cubre el lienzo y se recorta al centro")
    ap.add_argument("--max", type=int, default=1920, help="lado mayor de salida si no hay --lienzo")
    ap.add_argument("--amp", type=float, default=0.012, help="amplitud del paralaje, fracción del ancho")
    ap.add_argument("--zoom", type=float, default=0.06, help="empuje total de la cámara (parallax, capas, ciclo, revelado)")
    ap.add_argument("--orden", choices=("saliencia", "inverso"), default="saliencia",
                    help="kenburns: del general a los focos, o de los focos al general")
    ap.add_argument("--grano", default="auto", help="auto (según el grano medido) o 0..1")
    ap.add_argument("--profundidad", default="proxy", help="proxy | auto | mapa.png | modelo.onnx")
    ap.add_argument("--motor", choices=("auto", "rigido", "malla"), default="auto",
                    help="parallax y ciclo: capas rígidas (gráfica, texto) o malla continua (foto, ilustración)")
    ap.add_argument("--fotogramas", type=lambda s: [float(x) for x in s.split(",")], help="segundos: PNG en vez de video")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--prompt-ia", action="store_true")
    a = ap.parse_args()
    if not Path(a.imagen).is_file():
        sys.exit(f"{a.imagen}: no existe")
    if a.plan or a.prompt_ia:
        ficha = json.loads(Path(a.ficha).read_text()) if a.ficha else rm.ficha(a.imagen)
        if a.prompt_ia:
            print(json.dumps(prompt_ia(ficha, a.modo, a.dur), ensure_ascii=False, indent=1))
        else:
            print(json.dumps(plan_de(ficha, a.dur, a.orden), ensure_ascii=False, indent=1))
        return
    if not a.out:
        sys.exit("falta --out")
    if a.dur <= 0 or a.fps <= 0:
        sys.exit("--dur y --fps tienen que ser positivos")
    print(json.dumps(renderizar(a), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
