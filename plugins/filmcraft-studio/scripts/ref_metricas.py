#!/usr/bin/env python3
"""Ficha medida de una referencia de arte: lo que hace falta para reproducirla (o mejorarla) en números.

Uso:
    ref_metricas.py IMG [--json] [--hoja hoja.png] [--ficha ficha.json]
    ref_metricas.py ficha.json --validar [--completa]     # --completa exige la capa 2 (filosofía) rellena

Capa 1 (este script): color (paleta en OKLCH con proporciones, armonía, temperatura, croma), valores
(histograma, clave, contraste global y local, notan de 2 y 3 valores), composición (puntos fuertes por
saliencia, tercios, proporción áurea, diagonales, simetría, pesos, espacio negativo, líneas por Hough,
horizonte por regiones (±10°), orientación de bordes, margen, ritmo y retícula), textura (entropía,
frecuencia, grano), bordes (reparto continuo entre filo y difuminado), profundidad aparente, texto
(renglones y titulares grandes), tipografía (niveles, escala, peso del trazo, tracking, caja), patrón
(semitono o rayado: periodo y ángulo) y tratamiento (duotono, desregistro, viñeta). Cada escalar sale con
objetivo y tolerancia en `reproducir`. La `firma` (miniatura de luminancia sin bandas negras) deja que
`referencias.py --comparar` reconozca la misma imagen espejada, girada o recortada. Las capas 2
(`filosofia`) y 3 (`video.plan`) salen vacías: las rellena el modelo mirando la imagen y la hoja, y
`--validar --completa` las exige. `video.sugerido` y `video.traduccion` sí se derivan de las medidas.

Posiciones normalizadas (x, y en 0..1, origen arriba a la izquierda); distancias en fracción de la
diagonal. Todo se mide a 512 px de lado mayor (grano, nitidez, patrón y desregistro, sobre recortes a
resolución nativa; texto y tipografía, hasta 1024 y 2048 px), así que las cifras no dependen del tamaño
del archivo. La salida se valida con
schemas/referencia.schema.json.
"""
import argparse
import base64
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ESQUEMA = Path(__file__).resolve().parent.parent / "schemas" / "referencia.schema.json"
LADO = 512
VERSION = 2
FIRMA = 48                                                           # lado de la miniatura de luminancia

# (ruta, grupo, tolerancia, cómo se mueve ese número). Grupo «estilo»: lo que se reproduce.
# Grupo «composicion»: lo que distingue una pieza de otra; parecerse ahí es copiar.
METRICAS = [
    ("color.temperatura", "estilo", 0.15, "proporción de área cálida frente a fría; virar la paleta"),
    ("color.croma_media", "estilo", 0.03, "saturación global del grade"),
    ("color.croma_p90", "estilo", 0.05, "croma del acento más vivo"),
    ("color.colorido", "estilo", 0.12, "saturación y separación entre tonos"),
    ("color.colores_efectivos", "estilo", 1.0, "número de colores con área apreciable"),
    ("color.armonia.dispersion", "estilo", 0.15, "abrir o cerrar el abanico de tonos"),
    ("color.armonia.cromatico", "estilo", 0.15, "área con color frente a área neutra"),
    ("valores.media", "estilo", 0.08, "exposición"),
    ("valores.mediana", "estilo", 0.10, "clave: área de claros frente a oscuros"),
    ("valores.rango", "estilo", 0.12, "negros y blancos del grade (p05 y p95)"),
    ("valores.contraste_global", "estilo", 0.05, "curva de contraste"),
    ("valores.contraste_local", "estilo", 0.03, "microcontraste, textura y detalle"),
    ("valores.notan2.oscuro", "estilo", 0.12, "área de la masa oscura"),
    ("textura.entropia", "estilo", 0.10, "cantidad de valores distintos: degradados y textura"),
    ("textura.densidad_bordes", "estilo", 0.04, "cantidad de trazo y detalle"),
    ("textura.alta_frecuencia", "estilo", 0.08, "detalle fino frente a masas"),
    ("textura.grano", "estilo", 0.01, "grano o ruido añadido"),
    ("bordes.duros", "estilo", 0.20, "filo de las formas: vector o desenfoque"),
    ("composicion.espacio_negativo", "estilo", 0.15, "aire: área plana sin foco"),
    ("composicion.orientacion_bordes.anisotropia", "estilo", 0.15, "dirección dominante del trazo"),
    ("composicion.centro_masa.x", "composicion", 0.08, "dónde cae el peso en horizontal"),
    ("composicion.centro_masa.y", "composicion", 0.08, "dónde cae el peso en vertical"),
    ("composicion.balance_x", "composicion", 0.20, "peso a la derecha frente a la izquierda"),
    ("composicion.balance_y", "composicion", 0.20, "peso abajo frente a arriba"),
    ("composicion.simetria.horizontal", "composicion", 0.20, "espejo izquierda-derecha"),
    ("composicion.simetria.vertical", "composicion", 0.20, "espejo arriba-abajo"),
    ("composicion.tercios.distancia", "composicion", 0.06, "foco sobre un punto fuerte de tercios"),
    ("composicion.centro.distancia", "composicion", 0.08, "foco centrado o descentrado"),
    ("composicion.lineas.horizontal", "composicion", 0.20, "líneas horizontales"),
    ("composicion.lineas.vertical", "composicion", 0.20, "líneas verticales"),
    ("composicion.lineas.diagonal", "composicion", 0.20, "líneas diagonales"),
    ("texto.area", "composicion", 0.08, "área ocupada por texto"),
    ("tipografia.peso", "estilo", 0.06, "peso de la letra: grosor del trazo frente a su alto"),
    ("tipografia.escala", "estilo", 0.20, "tamaño del segundo nivel de texto frente al titular"),
]
# Especiales (no escalares): tolerancia en su propia unidad.
ESPECIALES = [
    ("color.paleta", "estilo", 0.06, "ΔE OKLab medio entre paletas, ponderado por área"),
    ("color.tono_principal", "estilo", 25.0, "grados entre los tonos dominantes"),
    ("valores.histograma", "estilo", 0.06, "distancia entre histogramas de luminancia (EMD)"),
    ("color.paleta_tonos", "estilo", 30.0, "grados entre los tonos de las paletas, color a color y sin ponderar por "
     "área: un acento de otro tono cuenta aunque ocupe poco"),
    ("valores.notan3.rejilla", "composicion", 0.20, "fracción de la figura del notan (las masas) que no coincide"),
    ("composicion.puntos_fuertes", "composicion", 0.08, "distancia media entre focos emparejados"),
]
# Sin estas tres dentro de tolerancia no hay «reproduce el estilo»: una paleta girada 120° es otro estilo
# aunque todo lo demás coincida (antes eran 2 votos de 23).
COLOR_NECESARIO = ("color.paleta", "color.tono_principal", "color.paleta_tonos")


def _r(v, n=3):
    return round(float(v), n)


# ---------------------------------------------------------------- carga y color

def cargar(path, lado=LADO, gris=False):
    """Devuelve (rgb float32 0..1 a `lado` px, recorte nativo float32 para grano/nitidez, ancho, alto).
    Con `gris`, además la luma uint8 a resolución nativa (2048 px de tope): texto y tipografía."""
    im = Image.open(path)
    if getattr(im, "is_animated", False):
        im.seek(0)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        im = Image.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, 255)), im)
    im = im.convert("RGB")
    w0, h0 = im.size
    s = lado / max(im.size)
    tam = (max(8, round(im.width * s)), max(8, round(im.height * s))) if s < 1 else im.size
    peq = im.resize(tam, Image.LANCZOS, reducing_gap=2.0) if tam != im.size else im
    c = min(512, im.width, im.height)
    x0, y0 = (im.width - c) // 2, (im.height - c) // 2
    nativo = np.asarray(im.crop((x0, y0, x0 + c, y0 + c)), np.float32) / 255
    if gris:
        sg = 2048 / max(im.size)
        g = im.convert("L")
        if sg < 1:
            g = g.resize((round(im.width * sg), round(im.height * sg)), Image.BILINEAR, reducing_gap=2.0)
        return np.asarray(peq, np.float32) / 255, nativo, w0, h0, np.asarray(g)
    return np.asarray(peq, np.float32) / 255, nativo, w0, h0


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]], np.float32)
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]], np.float32)


def oklab(rgb):
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4).astype(np.float32)
    return np.cbrt(lin @ _M1.T) @ _M2.T


def _hex(c):
    return "#%02X%02X%02X" % tuple(int(round(float(v) * 255)) for v in np.clip(c, 0, 1))


def _lch(lab):
    return float(lab[0]), float(math.hypot(lab[1], lab[2])), float(math.degrees(math.atan2(lab[2], lab[1])) % 360)


def medir_color(rgb, lab):
    h, w = rgb.shape[:2]
    paso = max(1, int(math.sqrt(h * w / 16000)))
    px, pl = rgb[::paso, ::paso].reshape(-1, 3), lab[::paso, ::paso].reshape(-1, 3)
    k = 8
    cv2.setRNGSeed(7)
    _, etq, cen = cv2.kmeans(pl.astype(np.float32), k, None,
                             (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1e-4), 2, cv2.KMEANS_PP_CENTERS)
    etq = etq.ravel()
    grupos = [[j] for j in sorted(range(k), key=lambda j: -(etq == j).sum()) if (etq == j).any()]
    fus = []
    for g in grupos:                                                   # fusiona centros casi iguales
        for f in fus:
            if np.linalg.norm(cen[f[0]] - cen[g[0]]) < 0.04:
                f += g
                break
        else:
            fus.append(g)
    pal = []
    for g in fus:
        m = np.isin(etq, g)
        L, C, H = _lch(pl[m].mean(0))
        pal.append({"hex": _hex(px[m].mean(0)), "proporcion": _r(m.mean(), 4),
                    "oklch": [_r(L), _r(C), _r(H, 1)]})
    pal.sort(key=lambda c: -c["proporcion"])
    for i, c in enumerate(pal):
        c["papel"] = "dominante" if i == 0 else "secundario" if i == 1 else "apoyo"
    vivos = [c for c in pal[1:] if c["proporcion"] < 0.2 and c["oklch"][1] > 0.08]
    if vivos:
        max(vivos, key=lambda c: c["oklch"][1])["papel"] = "acento"
    p = np.array([c["proporcion"] for c in pal])
    p = p / p.sum()
    efectivos = float(np.exp(-(p * np.log(p + 1e-12)).sum()))

    C = np.hypot(lab[..., 1], lab[..., 2])
    H = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    crom = C > 0.03
    peso = np.where(crom, C, 0)
    hist = np.bincount((H // 10).astype(int).ravel() % 36, peso.ravel(), 36)
    area_tono = np.bincount((H // 10).astype(int).ravel() % 36, crom.ravel().astype(np.float64), 36)
    cromatico = float(crom.mean())
    tonos, tipo, disp = [], "acromatica", 0.0
    if cromatico > 0.02 and hist.sum() > 0:
        hs = hist / hist.sum()
        suave = (np.roll(hs, 1) + 2 * hs + np.roll(hs, -1)) / 4
        picos = [i for i in range(36) if suave[i] >= suave[i - 1] and suave[i] > suave[(i + 1) % 36]
                 and suave[i] >= 0.12 * suave.max()]
        picos.sort(key=lambda i: -suave[i])
        sel = []
        for i in picos:
            if all(min(abs(i - j), 36 - abs(i - j)) >= 4 for j in sel):
                sel.append(i)
        for i in sel[:5]:
            vec = [(j % 36, hs[j % 36]) for j in range(i - 2, i + 3)]
            ang = math.degrees(math.atan2(sum(v * math.sin(math.radians(j * 10 + 5)) for j, v in vec),
                                          sum(v * math.cos(math.radians(j * 10 + 5)) for j, v in vec))) % 360
            # croma media del tono: un fondo casi neutro (croma < 0,06) es un tono «débil», que aparece o
            # desaparece con un ajuste de saturación; `--comparar` no lo toma por tono principal
            tonos.append({"tono": _r(ang, 1), "peso": _r(sum(v for _, v in vec)),
                          "croma": _r(sum(hist[j] for j, _ in vec) / max(sum(area_tono[j] for j, _ in vec), 1e-6))})
        rad = np.radians(np.arange(36) * 10 + 5)
        disp = 1 - float(np.hypot((hs * np.cos(rad)).sum(), (hs * np.sin(rad)).sum()))
        tipo = _armonia([t["tono"] for t in tonos], disp)
    caliente = np.cos(np.radians(H - 60))
    temp = float((peso * caliente).sum() / max(peso.sum(), 1e-6)) * min(1.0, cromatico / 0.1)
    rg, yb = (rgb[..., 0] - rgb[..., 1]) * 255, (0.5 * (rgb[..., 0] + rgb[..., 1]) - rgb[..., 2]) * 255
    colorido = (math.hypot(rg.std(), yb.std()) + 0.3 * math.hypot(rg.mean(), yb.mean())) / 109
    return {"paleta": pal, "colores_efectivos": _r(efectivos, 2),
            "armonia": {"tipo": tipo, "tonos": tonos, "dispersion": _r(disp), "cromatico": _r(cromatico)},
            "temperatura": _r(temp), "calido": _r((crom & (caliente > 0.3)).mean()),
            "frio": _r((crom & (caliente < -0.3)).mean()),
            "croma_media": _r(C.mean()), "croma_p90": _r(np.percentile(C, 90)), "colorido": _r(colorido)}


def _dang(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _armonia(t, disp):
    if not t:
        return "acromatica"
    if len(t) == 1:
        return "monocromatica" if disp < 0.03 else "analoga"
    if len(t) == 2:
        d = _dang(t[0], t[1])
        return "analoga" if d < 60 else "complementaria" if d >= 150 else "diada"
    d = sorted(_dang(a, b) for i, a in enumerate(t) for b in t[i + 1:])
    if len(t) == 3:
        if d[-1] < 90:
            return "analoga"
        if d[0] >= 90:
            return "triada"
        return "complementaria_dividida" if d[0] < 90 and d[1] >= 120 else "policromatica"
    if len(t) == 4 and sum(1 for x in d if x >= 150) >= 2:
        return "tetrada"
    return "analoga" if d[-1] < 90 else "policromatica"


# ---------------------------------------------------------------- valores

def _multi_otsu(L):
    """Dos umbrales que maximizan la varianza entre tres clases (histograma de 64 tramos)."""
    h = np.bincount(np.clip((L * 64).astype(int), 0, 63).ravel(), minlength=64).astype(np.float64)
    h /= h.sum()
    x = (np.arange(64) + 0.5) / 64
    w, m = np.cumsum(h), np.cumsum(h * x)
    mejor, t = -1, (21, 42)
    for a in range(1, 62):
        for b in range(a + 1, 63):
            w0, w1, w2 = w[a], w[b] - w[a], 1 - w[b]
            if min(w0, w1, w2) < 1e-4:
                continue
            m0, m1, m2 = m[a] / w0, (m[b] - m[a]) / w1, (m[-1] - m[b]) / w2
            v = w0 * m0 * m0 + w1 * m1 * m1 + w2 * m2 * m2
            if v > mejor:
                mejor, t = v, (a, b)
    return (t[0] + 1) / 64, (t[1] + 1) / 64


def _local_std(L, frac=1 / 16):
    k = max(3, int(max(L.shape) * frac) | 1)
    m = cv2.blur(L, (k, k))
    return np.sqrt(np.maximum(cv2.blur(L * L, (k, k)) - m * m, 0))


def medir_valores(L):
    hist = np.bincount(np.clip((L * 16).astype(int), 0, 15).ravel(), minlength=16) / L.size
    p05, med, p95 = (float(v) for v in np.percentile(L, [5, 50, 95]))
    u8 = np.clip(L * 255, 0, 255).astype(np.uint8)
    t2 = cv2.threshold(u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0] / 255
    if L.std() < 1e-3:
        t2, (a, b) = float(L.mean()) + 0.5, (float(L.mean()) - 0.5, float(L.mean()) + 0.5)
    else:
        a, b = _multi_otsu(L)
    n3 = (L >= a).astype(np.uint8) + (L >= b).astype(np.uint8)
    cols = 24
    filas = max(2, round(cols * L.shape[0] / L.shape[1]))
    rej = np.rint(cv2.resize(n3.astype(np.float32), (cols, filas), interpolation=cv2.INTER_AREA)).astype(int)
    return {"histograma": [_r(v, 4) for v in hist], "media": _r(L.mean()), "mediana": _r(med),
            "p05": _r(p05), "p95": _r(p95), "rango": _r(p95 - p05),
            "clave": "alta" if med >= 0.62 else "baja" if med <= 0.38 else "media",
            "contraste_global": _r(L.std()), "contraste_local": _r(_local_std(L).mean()),
            "notan2": {"umbral": _r(t2), "oscuro": _r((L < t2).mean()), "claro": _r((L >= t2).mean())},
            "notan3": {"umbrales": [_r(a), _r(b)],
                       "proporciones": [_r((n3 == i).mean()) for i in range(3)],
                       "rejilla": ["".join(str(v) for v in f) for f in rej]}}


# ---------------------------------------------------------------- composición

_t = np.ones(96, np.float32)
_t[:16] = 0.5 - 0.5 * np.cos(np.pi * (np.arange(16) + 0.5) / 16)
_t[-16:] = _t[:16][::-1]
_VENTANA_SR = np.outer(_t, _t)


def saliencia(lab):
    """Residuo espectral (Hou y Zhang) sobre L, a y b, más contraste global de color (Achanta). 0..1."""
    h, w = lab.shape[:2]
    sr = np.zeros((96, 96), np.float32)
    for c, g in ((0, 1.0), (1, 2.5), (2, 2.5)):
        x = cv2.resize(lab[..., c], (64, 64), interpolation=cv2.INTER_AREA) * g
        # la FFT es periódica: sin margen, el borde «salta». El margen repite el borde y se funde hacia la
        # mediana; reflejarlo duplicaba un sujeto pegado al borde y el foco se iba a un lóbulo fantasma.
        med = float(np.median(x))
        x = med + (cv2.copyMakeBorder(x, 16, 16, 16, 16, cv2.BORDER_REPLICATE) - med) * _VENTANA_SR
        f = np.fft.fft2(x)
        la = np.log(np.abs(f) + 1e-8)
        res = la - cv2.blur(la.astype(np.float32), (3, 3))
        sr += np.abs(np.fft.ifft2(np.exp(res + 1j * np.angle(f)))).astype(np.float32) ** 2
    sr = cv2.GaussianBlur(sr, (0, 0), 2.5)[16:80, 16:80]
    sr = cv2.resize(sr, (w, h), interpolation=cv2.INTER_CUBIC)
    sig = max(1.0, max(h, w) / 100)
    suave = cv2.GaussianBlur(lab, (0, 0), sig) * np.array([1, 2.5, 2.5], np.float32)
    ft = np.linalg.norm(suave - np.median(suave.reshape(-1, 3), 0), axis=2)

    def n(a):
        a = a - a.min()
        return a / a.max() if a.max() > 1e-6 else a * 0
    s = n(0.35 * n(sr) + 0.65 * n(ft))                                # el contraste de color manda sobre el residuo
    return s.astype(np.float32)


def puntos_fuertes(sal, n=5):
    h, w = sal.shape
    total = float(sal.sum()) or 1.0
    r = int(0.22 * min(h, w))
    yy, xx = np.mgrid[:h, :w]
    # la masa cuenta más que el pico, y un adorno pegado al borde pesa menos que lo mismo dentro
    s = cv2.GaussianBlur(sal, (0, 0), max(h, w) / 25)
    s = s * (1 - 0.65 * (((xx + 0.5) / w - 0.5) ** 2 + ((yy + 0.5) / h - 0.5) ** 2) / 0.5)
    b = max(1, int(0.05 * min(h, w)))                                 # un foco no vive en el filo del cuadro
    s[:b], s[-b:], s[:, :b], s[:, -b:] = 0, 0, 0, 0
    pts, tope = [], float(s.max())
    for _ in range(n):
        y, x = np.unravel_index(int(s.argmax()), s.shape)
        if tope <= 1e-6 or s[y, x] < 0.35 * tope:
            break
        m = (yy - y) ** 2 + (xx - x) ** 2 <= r * r
        _, comp = cv2.connectedComponents((s >= 0.35 * s[y, x]).astype(np.uint8))
        m |= comp == comp[y, x]                                      # una forma alargada es un foco, no cinco
        pts.append({"x": _r((x + 0.5) / w), "y": _r((y + 0.5) / h), "peso": _r(sal[m].sum() / total)})
        s[m] = 0
    return pts


def _dist(p, q, asp):
    """Distancia entre dos puntos normalizados, en fracción de la diagonal."""
    return math.hypot((p[0] - q[0]) * asp, p[1] - q[1]) / math.hypot(asp, 1)


def _cerca(foco, a, b, asp):
    nombres = {(0, 0): "sup-izq", (1, 0): "sup-der", (0, 1): "inf-izq", (1, 1): "inf-der"}
    d, k = min((_dist(foco, (x, y), asp), (i, j)) for i, x in enumerate((a, b)) for j, y in enumerate((a, b)))
    return {"distancia": _r(d), "punto": nombres[k]}


def _autocorr(perfil):
    """Periodo (fracción del lado) y fuerza (0..1) de la repetición de un perfil 1D."""
    p = perfil - perfil.mean()
    n = len(p)
    if p.std() < 1e-6:
        return {"periodo": None, "fuerza": 0.0}
    ac = np.correlate(p, p, "full")[n - 1:] / (np.arange(n, 0, -1) * p.var())
    a, b = max(3, int(0.03 * n)), n // 2
    seg = ac[a:b]
    if len(seg) < 3:
        return {"periodo": None, "fuerza": 0.0}
    baja = np.nonzero(seg < 0.25)[0]                                 # antes de repetirse tiene que dejar de parecerse
    if not len(baja):
        return {"periodo": None, "fuerza": 0.0}
    picos = [i for i in range(max(1, baja[0]), len(seg) - 1) if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1]]
    picos = [i for i in picos if seg[i] - seg[baja[0]:i].min() > 0.3]
    if not picos:
        return {"periodo": None, "fuerza": 0.0}
    tope = max(seg[i] for i in picos)
    if tope <= 0:
        return {"periodo": None, "fuerza": 0.0}
    i = next(i for i in picos if seg[i] >= 0.8 * tope)               # el fundamental, no un armónico
    f = float(max(0.0, min(1.0, seg[i])))
    return {"periodo": _r((i + a) / n, 4) if f > 0.15 else None, "fuerza": _r(f)}


def horizonte(lab, nb=16, amax=12):
    """Horizonte = recta casi horizontal (±10°) que separa dos regiones distintas a todo lo ancho.

    Se prueba cada inclinación enderezando la imagen; en cada fila se compara la franja de encima con la de
    debajo en `nb` tramos del ancho. Hay horizonte si el salto es del mismo signo en ≥ 85 % de los tramos,
    destaca sobre el degradado de fondo, no hay otra línea igual de fuerte (eso es una retícula) y lo de
    arriba y lo de abajo difieren en conjunto. Un subrayado o la base de unas tarjetas no cumplen."""
    H0, W0 = lab.shape[:2]
    w = 192
    h = max(24, round(w * H0 / W0))
    peq = cv2.resize(lab, (w, h), interpolation=cv2.INTER_AREA) * np.array([1, 2, 2], np.float32)
    b = max(2, round(0.06 * h))
    uno = np.ones((h, w), np.float32)
    ys = np.arange(b, h - b + 1)
    if len(ys) < 3:
        return None
    mejor = None
    for ang in range(-amax, amax + 1):
        if ang:
            M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
            r = cv2.warpAffine(peq, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            v = cv2.warpAffine(uno, M, (w, h), flags=cv2.INTER_LINEAR)
        else:
            r, v = peq, uno
        B = r[:, :w // nb * nb].reshape(h, nb, -1, 3).mean(2)
        V = v[:, :w // nb * nb].reshape(h, nb, -1).mean(2)
        cs = np.concatenate([np.zeros((1, nb, 3), np.float32), np.cumsum(B, 0)])
        cv = np.concatenate([np.zeros((1, nb), np.float32), np.cumsum(V, 0)])
        dif = (cs[ys] - cs[ys - b]) / b - (cs[ys + b] - cs[ys]) / b      # encima − debajo, por fila y tramo
        ok = ((cv[ys + b] - cv[ys - b]) / (2 * b)) > 0.97
        ref = np.median(np.linalg.norm(dif, axis=2), 0)[None]            # un degradado continuo no es un horizonte
        media = dif.mean(1)
        nm = np.linalg.norm(media, axis=1)
        proj = (dif * (media / np.maximum(nm, 1e-6)[:, None])[:, None]).sum(2)
        cob = ((proj > np.maximum(0.05, 2.5 * ref)) & ok).sum(1) / nb
        i = int(np.argmax(cob + 0.2 * np.minimum(nm, 0.5)))
        lejos = np.abs(ys - ys[i]) > 2 * b
        rival = float((nm[lejos] * (cob[lejos] >= 0.85)).max()) if lejos.any() else 0.0
        entre = float(np.linalg.norm(r[:ys[i]].reshape(-1, 3).mean(0) - r[ys[i]:].reshape(-1, 3).mean(0)))
        cand = (round(float(cob[i]), 3), float(nm[i]), ang, float(ys[i] / h), rival, entre)
        if mejor is None or cand[:2] > mejor[:2]:
            mejor = cand
    cob, con, ang, y, rival, entre = mejor
    if cob < 0.85 or not 0.08 < y < 0.92 or abs(ang) > 10 or rival > 0.6 * con or entre < 0.04:
        return None
    # ángulo en la convención de `lineas`: y hacia abajo, positivo = la línea baja hacia la derecha
    return {"y": _r(y), "angulo": float(ang), "confianza": _r(cob * min(1.0, 0.5 + con / 0.2)),
            "inclinado": bool(abs(ang) >= 2)}


def medir_composicion(rgb, lab, L, sal, bordes_canny):
    h, w = L.shape
    asp = w / h
    tot = float(sal.sum()) or 1.0
    yy, xx = np.mgrid[:h, :w]
    cm = ((sal * (xx + 0.5)).sum() / tot / w, (sal * (yy + 0.5)).sum() / tot / h)
    pts = puntos_fuertes(sal)
    foco = (pts[0]["x"], pts[0]["y"]) if pts else cm
    q = [sal[:h // 2, :w // 2].sum(), sal[:h // 2, w // 2:].sum(), sal[h // 2:, :w // 2].sum(),
         sal[h // 2:, w // 2:].sum()]
    q = [float(v) / tot for v in q]

    def espejo(a, eje):
        b = np.flip(a, eje)
        if a.std() < 1e-4:
            return 1.0
        return max(0.0, float(np.corrcoef(a.ravel(), b.ravel())[0, 1]))
    peq = cv2.resize(L, (64, max(8, round(64 / asp))), interpolation=cv2.INTER_AREA)

    plano = (_local_std(L, 1 / 24) < 0.02) & (sal < 0.25)

    # líneas
    lado = min(h, w)
    ls = cv2.HoughLinesP(bordes_canny, 1, np.pi / 180, threshold=max(25, lado // 10),
                         minLineLength=int(0.18 * lado), maxLineGap=max(4, lado // 80))
    lineas, lh, lv, ld = [], 0.0, 0.0, 0.0
    if ls is not None:
        for x1, y1, x2, y2 in ls.reshape(-1, 4).tolist():
            lon = math.hypot(x2 - x1, y2 - y1)
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
            dh = min(ang, 180 - ang)
            if dh <= 10:
                lh += lon
            elif abs(ang - 90) <= 10:
                lv += lon
            else:
                ld += lon
            lineas.append((lon, {"x1": _r(x1 / w), "y1": _r(y1 / h), "x2": _r(x2 / w), "y2": _r(y2 / h),
                                 "angulo": _r(ang, 1), "largo": _r(lon / math.hypot(w, h))}))
        lineas.sort(key=lambda t: -t[0])
    # con dos o tres líneas el reparto saltaba de 0 a 1 al reescalar: una longitud «a priori» de 0,3
    # diagonales repartida a tercios lo amortigua (sin líneas, 1/3 cada una)
    pri = 0.3 * math.hypot(w, h)
    st = lh + lv + ld + pri
    lh, lv, ld = lh + pri / 3, lv + pri / 3, ld + pri / 3
    hz = horizonte(lab)

    # orientación de bordes (dirección del borde, 0° = horizontal)
    gx, gy = cv2.Sobel(L, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(L, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    ang = (np.degrees(np.arctan2(gy, gx)) + 90) % 180
    oh = np.bincount((((ang + 11.25) % 180) // 22.5).astype(int).ravel(), mag.ravel(), 8)
    oh = oh / oh.sum() if oh.sum() > 1e-6 else oh
    ms = float(mag.sum())
    anis = float(np.hypot((mag * np.cos(np.radians(2 * ang))).sum(), (mag * np.sin(np.radians(2 * ang))).sum()) / ms) \
        if ms > 1e-6 else 0.0

    # margen: el contenido es lo que se aparta del color del borde
    b = max(2, int(0.02 * lado))
    anillo = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3), lab[:, :b].reshape(-1, 3),
                             lab[:, -b:].reshape(-1, 3)])
    fondo = np.median(anillo, 0)
    uniforme = float(np.linalg.norm(anillo - fondo, axis=1).mean()) < 0.03
    margen = {"izq": 0.0, "arriba": 0.0, "der": 0.0, "abajo": 0.0, "a_sangre": True}
    if uniforme:
        cont = np.linalg.norm(lab - fondo, axis=2) > 0.06
        cols, fils = np.where(cont.mean(0) > 0.01)[0], np.where(cont.mean(1) > 0.01)[0]
        if len(cols) and len(fils):
            margen = {"izq": _r(cols[0] / w), "arriba": _r(fils[0] / h), "der": _r(1 - (cols[-1] + 1) / w),
                      "abajo": _r(1 - (fils[-1] + 1) / h)}
            margen["a_sangre"] = min(margen.values()) < 0.01

    # ritmo y retícula: repetición del perfil de luminancia por columnas (x) y por filas (y)
    rx, ry = _autocorr(L.mean(0)), _autocorr(L.mean(1))
    def modulos(r):                                                    # más de 16 módulos no es maqueta: es un patrón
        n = round(1 / r["periodo"]) if r["periodo"] and r["fuerza"] >= 0.3 else None
        return n if n and n <= 16 else None
    ret = {"columnas": modulos(rx), "filas": modulos(ry), "confianza": _r(max(rx["fuerza"], ry["fuerza"]))}

    d1 = abs(foco[0] - foco[1]) / math.sqrt(2)                       # a la diagonal que baja (↘), en el cuadrado unidad
    d2 = abs(foco[0] + foco[1] - 1) / math.sqrt(2)                   # a la que sube (↗)
    return {"puntos_fuertes": pts, "centro_masa": {"x": _r(cm[0]), "y": _r(cm[1])},
            "tercios": _cerca(foco, 1 / 3, 2 / 3, asp), "aurea": _cerca(foco, 0.382, 0.618, asp),
            "centro": {"distancia": _r(_dist(foco, (0.5, 0.5), asp))},
            "diagonales": {"descendente": _r(d1), "ascendente": _r(d2)},
            "simetria": {"horizontal": _r(espejo(peq, 1)), "vertical": _r(espejo(peq, 0))},
            "peso_cuadrantes": {"sup_izq": _r(q[0]), "sup_der": _r(q[1]), "inf_izq": _r(q[2]), "inf_der": _r(q[3])},
            "balance_x": _r(q[1] + q[3] - q[0] - q[2]), "balance_y": _r(q[2] + q[3] - q[0] - q[1]),
            "espacio_negativo": _r(plano.mean()),
            "lineas": {"horizontal": _r(lh / st), "vertical": _r(lv / st), "diagonal": _r(ld / st), "n": len(lineas),
                       "principales": [d for _, d in lineas[:6]], "horizonte": hz},
            "orientacion_bordes": {"histograma": [_r(v) for v in oh], "dominante": _r(float(np.argmax(oh)) * 22.5, 1),
                                   "anisotropia": _r(anis)},
            "margen": margen, "ritmo": {"x": rx, "y": ry}, "reticula": ret}


# ---------------------------------------------------------------- textura, bordes, profundidad, texto

def medir_textura(L, nativo_L, canny):
    u8 = np.clip(L * 255, 0, 255).astype(np.uint8)
    p = np.bincount(u8.ravel(), minlength=256) / u8.size
    ent = float(-(p[p > 0] * np.log2(p[p > 0])).sum() / 8)
    x = cv2.resize(L, (256, 256), interpolation=cv2.INTER_AREA)
    f = np.abs(np.fft.fftshift(np.fft.fft2(x - x.mean()))) ** 2
    yy, xx = np.mgrid[-128:128, -128:128]
    r = np.hypot(yy, xx)
    tot = float(f[r <= 128].sum())
    alta = float(f[(r > 32) & (r <= 128)].sum() / tot) if tot > 1e-9 else 0.0
    pend = None
    if tot > 1e-9:
        rad = np.bincount(r.astype(int).ravel(), f.ravel())[2:128] / np.maximum(np.bincount(r.astype(int).ravel())[2:128], 1)
        ok = rad > 0
        if ok.sum() > 10:
            pend = _r(np.polyfit(np.log(np.arange(2, 128)[ok]), np.log(rad[ok]), 1)[0], 2)
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    grano = float(np.median(np.abs(cv2.filter2D(nativo_L, cv2.CV_32F, k))) / 0.6745 / 6)
    return {"entropia": _r(ent), "densidad_bordes": _r((canny > 0).mean()), "alta_frecuencia": _r(alta),
            "pendiente_espectral": pend, "grano": _r(grano, 4)}


ANCHO_DURO, ANCHO_SUAVE = 1.0, 3.4      # σ del borde (px a 512) que cuenta como filo de vector / como difuminado


def medir_bordes(L, nativo_L):
    """Filo de las formas, repartido por masa: cada píxel con transición tonal pesa lo que cambia ahí (el
    gradiente grueso) y vota con el ancho de su borde. Un vector da 1; una foto reparte entre aristas
    y sombreado suave; un desenfoque da 0. `ancho_px` = σ mediano del borde, en px a 512."""
    g1 = np.hypot(cv2.Sobel(L, cv2.CV_32F, 1, 0), cv2.Sobel(L, cv2.CV_32F, 0, 1)) / 8
    s = cv2.GaussianBlur(L, (0, 0), 2)
    g2 = np.hypot(cv2.Sobel(s, cv2.CV_32F, 1, 0), cv2.Sobel(s, cv2.CV_32F, 0, 1)) / 8
    if g2.max() < 0.004:
        return {"duros": 0.0, "suaves": 0.0, "nitidez": 0.0, "hay": False, "ancho_px": None}
    m = g2 >= 0.003                                                    # por debajo es ruido o un degradado de fondo
    k = np.ones((11, 11), np.uint8)                                    # cada píxel mira la cresta más cercana:
    razon = cv2.dilate(g2, k)[m] / np.maximum(cv2.dilate(g1, k)[m], 1e-6)   # en la falda la razón local no dice nada
    razon = np.clip(razon, 0.05, 0.995)                                # escalón nítido ≈ 0,4; borde difuso → 1
    # un escalón de ancho σ visto con y sin un desenfoque de 2 px: razón² = σ²/(σ²+4) → σ en px a 512
    ancho = 2 * razon / np.sqrt(1 - razon * razon)
    peso = g2[m]
    dureza = np.clip((ANCHO_SUAVE - ancho) / (ANCHO_SUAVE - ANCHO_DURO), 0, 1)
    duros = float((dureza * peso).sum() / peso.sum())
    orden = np.argsort(ancho)
    med = float(ancho[orden][np.searchsorted(np.cumsum(peso[orden]), 0.5 * peso.sum())])
    return {"duros": _r(duros), "suaves": _r(1 - duros), "hay": True, "ancho_px": _r(med, 2),
            "nitidez": _r(min(1.0, float(cv2.Laplacian(nativo_L, cv2.CV_32F).var()) * 40))}


def medir_profundidad(L, lab, canny, duros=0.0):
    h, w = L.shape
    lap = np.abs(cv2.Laplacian(L, cv2.CV_32F))
    cel = []
    for j in range(6):
        for i in range(6):
            sl = (slice(j * h // 6, (j + 1) * h // 6), slice(i * w // 6, (i + 1) * w // 6))
            if (canny[sl] > 0).mean() > 0.01:
                cel.append(float(np.percentile(lap[sl], 95)))
    rango = 0.0
    if len(cel) >= 6:
        a, b = np.percentile(cel, [10, 90])
        rango = float((b - a) / (b + a + 1e-6))
    ls = _local_std(L, 1 / 16)
    C = np.hypot(lab[..., 1], lab[..., 2])
    t = h // 3

    def grad(a):
        ar, ab = float(a[:t].mean()), float(a[-t:].mean())
        return (ab - ar) / (ab + ar) if ab + ar > 1e-4 else 0.0
    gc, gs = grad(ls), grad(C)
    pista = "foco_selectivo" if rango > 0.6 and duros < 0.5 else "atmosferica" if gc > 0.25 and gs > -0.05 else "plana"
    return {"rango_enfoque": _r(rango), "gradiente_contraste": _r(gc), "gradiente_croma": _r(gs), "pista": pista}


def _texto_grande(u8):
    """Titulares de cartel (letras de 20–80 % del alto): el filtro de renglones los descarta por altos.
    Glifo = forma de trazo (ni maciza ni hueca, trazo fino frente a su alto); texto = dos o más glifos
    contiguos sobre la misma línea base. Un círculo o un rectángulo sueltos no pasan."""
    h, w = u8.shape
    if u8.std() < 10:
        return []
    bw = cv2.threshold(u8, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    fg = bw if bw.mean() <= 0.5 else 1 - bw                              # el texto es la clase minoritaria
    n, comp, st, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8), 8)
    if n > 400:
        return []
    dt = cv2.distanceTransform(fg.astype(np.uint8), cv2.DIST_L2, 3)
    gl = []
    for i in range(1, n):
        x, y, cw, ch, a = (int(v) for v in st[i])
        if not 0.2 * h <= ch <= 0.8 * h or not 0.25 * ch <= cw <= 1.6 * ch or a < 0.004 * h * w:
            continue
        if x <= 1 or y <= 1 or x + cw >= w - 1 or y + ch >= h - 1:
            continue
        trazo = 4 * float(dt[y:y + ch, x:x + cw][comp[y:y + ch, x:x + cw] == i].mean()) - 2
        if not 0.15 <= a / (cw * ch) <= 0.72 or trazo > 0.34 * ch:
            continue
        gl.append((x, y, cw, ch))
    gl.sort()
    cajas, fila = [], []

    def cierra():
        if len(fila) >= 2:
            x0, y0 = min(g[0] for g in fila), min(g[1] for g in fila)
            x1, y1 = max(g[0] + g[2] for g in fila), max(g[1] + g[3] for g in fila)
            cajas.append({"x": _r(x0 / w), "y": _r(y0 / h), "w": _r((x1 - x0) / w), "h": _r((y1 - y0) / h)})
    for g in gl:
        if fila and abs((g[1] + g[3]) - (fila[-1][1] + fila[-1][3])) < 0.05 * h and \
                g[0] - (fila[-1][0] + fila[-1][2]) < 0.6 * max(g[3], fila[-1][3]):
            fila.append(g)
        else:
            cierra()
            fila = [g]
    cierra()
    return cajas


def medir_texto(L):
    """Heurístico: renglones = componentes anchos y bajos del gradiente cerrado en horizontal, más los
    titulares grandes (`_texto_grande`). `L` puede venir a más de 512 px: los umbrales son relativos."""
    h, w = L.shape
    u8 = np.clip(L * 255, 0, 255).astype(np.uint8) if L.dtype != np.uint8 else L
    g = cv2.morphologyEx(u8, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    if g.max() < 24:
        return {"hay": False, "area": 0.0, "bloques": 0, "alineacion": None, "cajas": [], "confianza": "baja"}
    b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    c = cv2.morphologyEx(b, cv2.MORPH_CLOSE, np.ones((1, max(3, int(0.03 * w))), np.uint8))
    c = cv2.morphologyEx(c, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(c, 8)
    cajas = []
    for x, y, bw, bh, a in st[1:n]:
        if bw < 2.2 * bh or not 0.012 * h <= bh <= 0.22 * h or bw < 0.05 * w or a < 0.45 * bw * bh:
            continue
        trozo = b[y:y + bh, x:x + bw]
        cambios = (np.diff(trozo[bh // 2].astype(int)) != 0).sum() / max(bw / bh, 1)   # trazos por «letra»
        if cambios < 1.5 or trozo.mean() / 255 > 0.85:
            continue
        lo, hi = np.percentile(u8[y:y + bh, x:x + bw], [5, 95])
        if hi - lo < 40:                                                # el grano de una foto no contrasta como la tinta
            continue
        if _autocorr(trozo.mean(0).astype(np.float64))["fuerza"] >= 0.8:   # una fila de puntos de semitono se repite
            continue                                                    # exacta; las letras, no
        cajas.append({"x": _r(x / w), "y": _r(y / h), "w": _r(bw / w), "h": _r(bh / h)})
    s = 512 / max(h, w)
    peq = cv2.resize(u8, (max(8, round(w * s)), max(8, round(h * s))), interpolation=cv2.INTER_AREA) if s < 1 else u8
    for k in _texto_grande(peq):                                       # los que no pise ya un renglón
        if not any(k["x"] < c["x"] + c["w"] and c["x"] < k["x"] + k["w"] and k["y"] < c["y"] + c["h"]
                   and c["y"] < k["y"] + k["h"] for c in cajas):
            cajas.append(k)
    area = float(sum(k["w"] * k["h"] for k in cajas))
    alin = None
    if cajas:
        izq = np.array([k["x"] for k in cajas])
        der = np.array([k["x"] + k["w"] for k in cajas])
        cen = (izq + der) / 2
        if len(cajas) >= 2:
            d = {"izquierda": izq.std(), "centro": cen.std(), "derecha": der.std()}
            alin = min(d, key=d.get) if min(d.values()) < 0.04 else "libre"
            if alin != "libre" and izq.std() < 0.04 and der.std() < 0.04:
                alin = "justificado"
        else:
            alin = "centro" if abs(cen[0] - 0.5) < 0.08 else "izquierda" if cen[0] < 0.5 else "derecha"
    cajas.sort(key=lambda k: -k["w"] * k["h"])
    # un titular (≥ 1 % del cuadro) o varios renglones pequeños (una hoja de contacto, una interfaz)
    return {"hay": bool(area >= 0.01 or (len(cajas) >= 3 and area >= 0.004)), "area": _r(area), "bloques": len(cajas), "alineacion": alin, "cajas": cajas[:12],
            "confianza": "baja"}


def _periodicidad(x):
    """Repetición 2D de un recorte cuadrado por autocorrelación: (fuerza, periodo_px, ángulo, tipo) o None.

    Un patrón (semitono, rayado, cuadrícula) deja picos secundarios en la autocorrelación; un borde o una
    foto, no: caen desde el centro sin volver a subir. `rayas` = el lóbulo central es una cresta que cruza
    la ventana; `puntos` = dos vectores de red independientes."""
    n = x.shape[0]
    x = x - x.mean()
    if n < 48 or x.std() < 0.01:
        return None
    N = 2 * n
    f = np.fft.rfft2(x, (N, N))
    ac = np.fft.fftshift(np.fft.irfft2(f.real ** 2 + f.imag ** 2, (N, N)))
    R = n // 3
    c = N // 2
    ac = ac[c - R:c + R + 1, c - R:c + R + 1]
    d = np.arange(-R, R + 1)
    ac = ac / ((n - np.abs(d))[:, None] * (n - np.abs(d))[None, :])   # sin sesgo por solape
    if ac[R, R] <= 0:
        return None
    ac = (ac / ac[R, R]).astype(np.float32)
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
    rad = np.hypot(yy, xx)
    _, comp = cv2.connectedComponents((ac > 0.5).astype(np.uint8))
    lobulo = comp == comp[R, R]
    cruza = bool(rad[lobulo].max() >= 0.9 * R)
    cerca = cv2.dilate(lobulo.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    pico = (ac >= cv2.dilate(ac, np.ones((5, 5), np.uint8)) - 1e-6) & ~cerca & (rad >= 3) & (rad <= R) & (ac >= 0.45)
    if not pico.any():
        return None
    ys, xs = np.nonzero(pico)
    orden = np.argsort(rad[ys, xs])
    tope = float(ac[ys, xs].max())
    for i in orden:                                                    # el más cercano de los fuertes: el fundamental
        py, px = int(ys[i]), int(xs[i])
        if ac[py, px] < 0.85 * tope:
            continue
        t = np.linspace(0, 1, max(4, int(rad[py, px])))[:, None]
        camino = ac[np.rint(R + t * (py - R)).astype(int), np.rint(R + t * (px - R)).astype(int)]
        if ac[py, px] - float(camino.min()) >= 0.25:                   # tiene que dejar de parecerse y volver
            break
    else:
        return None
    vy, vx = py - R, px - R
    ang = math.degrees(math.atan2(vy, vx)) % 180
    per = math.hypot(vy, vx)
    if cruza:                                                          # la raya va a lo largo del lóbulo central
        ly, lx = np.nonzero(lobulo)
        cov = np.cov(np.stack([lx - R, ly - R]).astype(np.float64))
        val, vec = np.linalg.eigh(cov)
        ex, ey = vec[:, int(np.argmax(val))]
        tipo, ang = "rayas", math.degrees(math.atan2(ey, ex)) % 180
        fuertes = ac[ys, xs] >= 0.85 * tope
        salto = np.abs((xs[fuertes] - R) * -ey + (ys[fuertes] - R) * ex)  # distancia perpendicular entre crestas
        salto = salto[salto >= 3]
        if not len(salto):
            return None
        per = float(salto.min())
    else:
        otros = [(abs(((math.degrees(math.atan2(y - R, x - R)) - ang + 90) % 180) - 90), float(ac[y, x]))
                 for y, x in zip(ys, xs) if rad[y, x] <= 1.6 * rad[py, px]]
        tipo = "puntos" if any(da >= 30 and v >= 0.6 * ac[py, px] for da, v in otros) else "repeticion"
        if tipo == "puntos":
            ang = ang % 90
    if tipo == "repeticion" or ac[py, px] < 0.6:                       # una sola dirección sin cresta continua es el
        return None                                                    # interlineado de un texto: eso ya es `ritmo`
    return float(ac[py, px]), float(per), float(ang), tipo


def medir_patron(L, nativo_L, w0, h0):
    """Patrón fino repetido: semitono o cuadrícula (`puntos`) y rayado (`rayas`). Se busca a resolución nativa (recorte
    central) y en la imagen entera; manda el más fuerte. Periodo en fracción del lado mayor y en px."""
    vacio = {"hay": False, "tipo": None, "periodo": None, "periodo_px": None, "angulo": None, "fuerza": 0.0}
    cand = []
    c = min(256, *nativo_L.shape)
    for fy, fx in ((0.5, 0.5), (0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)):   # un semitono puede estar en una esquina
        y0, x0 = int((nativo_L.shape[0] - c) * fy), int((nativo_L.shape[1] - c) * fx)
        r = _periodicidad(nativo_L[y0:y0 + c, x0:x0 + c])
        if r and r[1] / max(w0, h0) <= 1 / 12:
            cand.append((r[0], r[1] / max(w0, h0), r[1], r[2], r[3], "nativa"))
        if c >= min(nativo_L.shape):
            break
    if not cand:                                                       # a 512 px un patrón fino se solapa: solo si no se vio en nativo
        c = min(320, *L.shape)
        y0, x0 = (L.shape[0] - c) // 2, (L.shape[1] - c) // 2
        r = _periodicidad(L[y0:y0 + c, x0:x0 + c])
        if r and r[1] / max(L.shape) <= 1 / 12:                        # más grande ya es maqueta (ritmo, retícula)
            cand.append((r[0], r[1] / max(L.shape), r[1] * max(w0, h0) / max(L.shape), r[2], r[3], "global"))
    if not cand:
        return vacio
    f, per, px, ang, tipo, esc = max(cand)
    return {"hay": True, "tipo": tipo, "periodo": _r(per, 4), "periodo_px": _r(px, 1), "angulo": _r(ang, 1),
            "fuerza": _r(f), "escala": esc}


def medir_tipografia(gris, texto):
    """Lo que se puede medir de la letra sin reconocerla: niveles de tamaño y su escala, número de líneas,
    peso aparente (grosor del trazo / alto de la letra), tracking (hueco entre letras / alto) y caja.
    La familia (serif, palo seco, mono) no se mide: `clase` lo rellena el modelo mirando la imagen."""
    vacio = {"hay": False, "lineas": 0, "area": 0.0, "alineacion": None, "niveles": [], "escala": None,
             "peso": None, "peso_clase": None, "tracking": None, "caja": None, "clase": None, "confianza": "baja"}
    if not texto["hay"]:
        return vacio
    H, W = gris.shape
    med = []
    for k in texto["cajas"]:
        x0, y0 = max(0, int(k["x"] * W) - 1), max(0, int(k["y"] * H) - 1)
        x1, y1 = min(W, math.ceil((k["x"] + k["w"]) * W) + 1), min(H, math.ceil((k["y"] + k["h"]) * H) + 1)
        c = gris[y0:y1, x0:x1]
        if c.shape[0] < 8 or c.shape[1] < 16 or c.std() < 8:
            continue
        b = cv2.threshold(c, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        # la tinta es lo que no es el borde de la caja (una etiqueta con fondo propio tiene texto claro u oscuro)
        marco = np.concatenate([b[0], b[-1], b[:, 0], b[:, -1]]).mean()
        if marco > 0.5:
            b = 1 - b
        filas = np.nonzero(b.mean(1) > 0.02)[0]
        if not len(filas) or not 0.03 <= b.mean() <= 0.7:
            continue
        alto = int(filas[-1] - filas[0] + 1)
        if alto < 6:
            continue
        trazo = max(1.0, 4 * float(cv2.distanceTransform(b, cv2.DIST_L2, 3)[b > 0].mean()) - 2)
        if trazo > 0.35 * alto:                                        # eso no es un trazo: mancha, foto o caja mal cortada
            continue
        cols = b[filas[0]:filas[-1] + 1].max(0)
        cambios = np.flatnonzero(np.diff(np.concatenate([[1], cols, [1]])))
        huecos = (cambios[1::2] - cambios[::2])[1:-1] if len(cambios) >= 6 else np.array([])
        n, _, st, _ = cv2.connectedComponentsWithStats(b, 8)
        altos = st[1:n, 3][st[1:n, 4] >= 0.02 * alto * alto]
        letra = float(np.percentile(altos, 75)) if len(altos) else float(alto)   # alto de mayúscula, sin descendentes
        med.append({"alto": alto / H, "peso": trazo / max(letra, 1.0), "area": k["w"] * k["h"],
                    "tracking": float(np.median(huecos)) / alto if len(huecos) else None,
                    "alta": bool(len(altos) >= 2 and (altos >= 0.8 * letra).mean() >= 0.85 and letra >= 0.8 * alto)})
    if not med:
        return dict(vacio, hay=True, lineas=texto["bloques"], area=texto["area"], alineacion=texto["alineacion"])
    med.sort(key=lambda t: -t["alto"])
    niveles = []
    for t in med:                                                      # un nivel nuevo cuando la letra baja ≥ 25 %
        if niveles and t["alto"] > niveles[-1]["alto"] / 1.25:
            niveles[-1]["lineas"] += 1
        else:
            niveles.append({"alto": t["alto"], "lineas": 1})
    a0 = niveles[0]["alto"]
    niveles = [{"alto": _r(n["alto"], 4), "lineas": n["lineas"], "escala": _r(n["alto"] / a0)} for n in niveles[:4]]
    ar = np.array([t["area"] for t in med])
    peso = float((np.array([t["peso"] for t in med]) * ar).sum() / ar.sum())
    tr = [(t["tracking"], t["area"]) for t in med if t["tracking"] is not None]
    alta = float(sum(t["area"] for t in med if t["alta"]) / ar.sum())
    return {"hay": True, "lineas": texto["bloques"], "area": texto["area"], "alineacion": texto["alineacion"],
            "niveles": niveles, "escala": niveles[1]["escala"] if len(niveles) > 1 else None,
            "peso": _r(peso), "peso_clase": "fina" if peso < 0.09 else "regular" if peso < 0.15 else
            "negrita" if peso < 0.22 else "extra",
            "tracking": _r(sum(v * w for v, w in tr) / sum(w for _, w in tr)) if tr else None,
            "caja": "alta" if alta >= 0.7 else "baja_o_mixta" if alta <= 0.3 else "mixta", "clase": None,
            "confianza": "baja"}


def medir_tratamiento(rgb, lab, L, nativo):
    """Acabados que definen un estilo gráfico: duotono (el color es función del valor), desregistro de
    tintas (un canal desplazado respecto a otro) y viñeta (caída de luz hacia las cuatro esquinas)."""
    h, w = L.shape
    a, b = lab[..., 1].ravel(), lab[..., 2].ravel()
    bins = np.clip((L.ravel() * 32).astype(int), 0, 31)
    n = np.bincount(bins, minlength=32)
    var_t = float(a.var() + b.var())
    crom = float((np.hypot(a, b) > 0.03).mean())
    ajuste = 0.0
    if var_t > 1e-5:
        ma, mb = np.bincount(bins, a, 32) / np.maximum(n, 1), np.bincount(bins, b, 32) / np.maximum(n, 1)
        ajuste = max(0.0, 1 - float((a - ma[bins]).var() + (b - mb[bins]).var()) / var_t)
    n16 = n.reshape(16, 2).sum(1)
    continuo = int((n16 / n16.sum() > 0.01).sum()) >= 6               # con cuatro tintas planas el ajuste es trivial
    q = np.quantile(L, [0.05, 0.10, 0.90, 0.95])
    som, luz = (L >= q[0]) & (L <= q[1]), (L >= q[2]) & (L <= q[3])
    duo = {"hay": bool(crom > 0.25 and ajuste >= 0.9 and continuo), "ajuste": _r(ajuste),
           "sombra": _hex(rgb[som].mean(0)), "luz": _hex(rgb[luz].mean(0))}

    des = {"hay": False, "px": 0.0, "angulo": None, "respuesta": 0.0}
    if min(nativo.shape[:2]) >= 64:
        def grad(c):
            return np.hypot(cv2.Sobel(c, cv2.CV_32F, 1, 0), cv2.Sobel(c, cv2.CV_32F, 0, 1))
        gr, gb = grad(np.ascontiguousarray(nativo[..., 0])), grad(np.ascontiguousarray(nativo[..., 2]))
        if gr.std() > 1e-3 and gb.std() > 1e-3:
            (dx, dy), resp = cv2.phaseCorrelate(gr, gb, cv2.createHanningWindow(gr.shape[::-1], cv2.CV_32F))
            d = math.hypot(dx, dy)
            des = {"hay": bool(d >= 1.0 and resp >= 0.2), "px": _r(d, 2),
                   "angulo": _r(math.degrees(math.atan2(dy, dx)) % 360, 1) if d >= 0.5 else None, "respuesta": _r(resp)}

    s = cv2.GaussianBlur(L, (0, 0), max(h, w) / 20)
    yy, xx = np.mgrid[:h, :w]
    r = np.hypot((xx + 0.5) / w - 0.5, (yy + 0.5) / h - 0.5) / math.sqrt(0.5)
    centro, medio = float(np.median(s[r < 0.35])), float(np.median(s[(r > 0.5) & (r < 0.65)]))
    esq = [float(np.median(s[(r > 0.8) & m])) for m in ((xx < w / 2) & (yy < h / 2), (xx >= w / 2) & (yy < h / 2),
                                                         (xx < w / 2) & (yy >= h / 2), (xx >= w / 2) & (yy >= h / 2))]
    caida = centro - float(np.mean(esq))
    vin = {"hay": bool(caida >= 0.06 and centro - max(esq) >= 0.5 * caida and -0.01 <= centro - medio <= caida),
           "fuerza": _r(caida)}
    return {"duotono": duo, "desregistro": des, "vineta": vin}


def bandas_negras(L):
    """Bandas negras de letterbox/pillarbox, en fracción de cada lado (0 si no hay)."""
    h, w = L.shape
    osc = L < 0.16
    fil, col = osc.mean(1) > 0.985, osc.mean(0) > 0.985

    def cuenta(v):
        n = 0
        while n < len(v) and v[n]:
            n += 1
        return n
    b = {"arriba": cuenta(fil) / h, "abajo": cuenta(fil[::-1]) / h, "izq": cuenta(col) / w, "der": cuenta(col[::-1]) / w}
    b = {k: (_r(v) if v >= 0.02 else 0.0) for k, v in b.items()}
    if b["arriba"] + b["abajo"] > 0.6 or b["izq"] + b["der"] > 0.6:    # una imagen casi negra no tiene «bandas»
        return {k: 0.0 for k in b}
    return b


def firma(L, bandas):
    """Miniatura de luminancia del contenido (sin bandas negras), para que `--comparar` reconozca la misma
    imagen espejada, girada o recortada sin tener el archivo: solo con la ficha."""
    h, w = L.shape
    y0, y1 = round(bandas["arriba"] * h), h - round(bandas["abajo"] * h)
    x0, x1 = round(bandas["izq"] * w), w - round(bandas["der"] * w)
    f = cv2.resize(np.ascontiguousarray(L[y0:y1, x0:x1]), (FIRMA, FIRMA), interpolation=cv2.INTER_AREA)
    return {"lado": FIRMA, "L": base64.b64encode(np.clip(f * 255, 0, 255).astype(np.uint8).tobytes()).decode()}


def profundidad_proxy(rgb, lab=None, sal=None, texto=None):
    """Mapa 0..1 (1 = cerca) sin modelos: posición, nitidez, saliencia y croma, promediado por segmento
    de color para que cada forma se mueva rígida. Sirve para paralajes pequeños, no para geometría."""
    h, w = rgb.shape[:2]
    lab = oklab(rgb) if lab is None else lab
    sal = saliencia(lab) if sal is None else sal
    L = np.ascontiguousarray(lab[..., 0])

    def n(a):
        a = a - a.min()
        return a / a.max() if a.max() > 1e-6 else a * 0
    nit = n(cv2.GaussianBlur(np.abs(cv2.Laplacian(L, cv2.CV_32F)), (0, 0), max(h, w) / 30))
    cro = n(cv2.GaussianBlur(np.hypot(lab[..., 1], lab[..., 2]), (0, 0), max(h, w) / 60))
    pos = np.repeat(np.linspace(0, 1, h, dtype=np.float32)[:, None], w, 1)
    d = 0.30 * pos + 0.25 * nit + 0.30 * sal + 0.15 * cro
    s = 96 / max(h, w)
    tam = (max(8, round(w * s)), max(8, round(h * s)))
    pl = cv2.resize(lab, tam, interpolation=cv2.INTER_AREA)
    dp = cv2.resize(d, tam, interpolation=cv2.INTER_AREA)
    cv2.setRNGSeed(11)
    _, etq, _ = cv2.kmeans(pl.reshape(-1, 3).astype(np.float32), 6, None,
                           (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1e-3), 1, cv2.KMEANS_PP_CENTERS)
    etq = etq.reshape(tam[1], tam[0])
    seg = np.zeros_like(dp)
    for k in range(6):
        nc, comp = cv2.connectedComponents((etq == k).astype(np.uint8), connectivity=4)
        for c in range(1, nc):
            m = comp == c
            seg[m] = dp[m].mean()
    out = cv2.resize(0.7 * seg + 0.3 * dp, (w, h), interpolation=cv2.INTER_LINEAR)
    out = cv2.GaussianBlur(out, (0, 0), max(h, w) / 120)
    for k in (texto or {}).get("cajas", []):                          # el texto no se deforma
        x0, y0 = int(k["x"] * w), int(k["y"] * h)
        x1, y1 = int((k["x"] + k["w"]) * w) + 1, int((k["y"] + k["h"]) * h) + 1
        out[y0:y1, x0:x1] = out[y0:y1, x0:x1].mean()
    return n(out).astype(np.float32)


# ---------------------------------------------------------------- capas 2 y 3, reproducir

def _get(d, ruta):
    for k in ruta.split("."):
        d = d.get(k) if isinstance(d, dict) else None
        if d is None:
            return None
    return d


def reproducir(m):
    out = []
    for ruta, grupo, tol, como in METRICAS:
        v = _get(m, ruta)
        if isinstance(v, (int, float)):
            out.append({"metrica": ruta, "grupo": grupo, "objetivo": v, "tolerancia": tol, "como": como})
    return out


def pistas_mejora(m):
    """Heurísticas medidas: no son un juicio, son lo primero que miraría un director de arte."""
    c, v, co, t = m["composicion"], m["valores"], m["color"], m["texto"]
    p = []
    if v["rango"] < 0.45:
        p.append(f"Rango de valores corto ({v['rango']}): faltan negros o blancos; abrirlo da jerarquía.")
    n3 = v["notan3"]["proporciones"]
    if min(n3) > 0.25:
        p.append(f"Los tres valores ocupan casi lo mismo ({n3}): un reparto desigual (p. ej. 60/30/10) lee mejor.")
    if co["colores_efectivos"] > 5.5 and co["armonia"]["tipo"] == "policromatica":
        p.append(f"{co['colores_efectivos']} colores efectivos sin relación de tono: reducir a una familia y un acento.")
    if not any(k["papel"] == "acento" for k in co["paleta"]) and co["armonia"]["cromatico"] > 0.3:
        p.append("No hay acento: ningún color vivo ocupa poca área; uno pequeño dirige la mirada.")
    if c["tercios"]["distancia"] > 0.12 and c["centro"]["distancia"] > 0.12 and c["aurea"]["distancia"] > 0.12:
        p.append("El foco principal no cae ni en un punto fuerte ni en el centro: decidir una de las dos.")
    if len(c["puntos_fuertes"]) >= 4 and c["puntos_fuertes"][0]["peso"] < 0.2:
        p.append("Muchos focos con peso parecido: no hay un punto de entrada claro.")
    if c["espacio_negativo"] < 0.08 and m["textura"]["densidad_bordes"] > 0.15:
        p.append(f"Casi sin espacio negativo ({c['espacio_negativo']}) y mucho trazo: dejar aire alrededor del foco.")
    if abs(c["balance_x"]) > 0.45 and c["simetria"]["horizontal"] < 0.3:
        p.append(f"Peso muy cargado a un lado (balance_x {c['balance_x']}) sin contrapeso.")
    if t["hay"] and t["area"] > 0.3:
        p.append(f"El texto ocupa {round(t['area'] * 100)} % del cuadro: en video se lee un titular, no un párrafo.")
    return p


def es_grafica(m):
    """Pieza gráfica: texto, o formas planas de borde duro con aire. Nada se deforma y no hay horizonte."""
    return bool(m["texto"]["hay"] or (m["bordes"]["duros"] >= 0.97 and m["composicion"]["espacio_negativo"] > 0.3))


def traducir_video(m):
    """Capa 3 medible: qué modo de imagen_a_video conviene y cómo se vuelve movimiento cada rasgo."""
    c, v, t, pr, tx = m["composicion"], m["valores"], m["texto"], m["profundidad"], m["textura"]
    pts = c["puntos_fuertes"]
    grafico = es_grafica(m)
    modos, tr = [], []
    if pr["pista"] != "plana" and not t["hay"]:
        modos.append({"modo": "parallax", "por": f"profundidad {pr['pista']} (rango de enfoque {pr['rango_enfoque']})"})
    if grafico:
        modos.append({"modo": "revelado", "por": "pieza gráfica (texto o formas planas de borde duro): "
                      "se construye por valores sin deformar nada"})
        modos.append({"modo": "capas", "por": "formas separables por color: entran escalonadas"})
    rit = max(c["ritmo"]["x"]["fuerza"], c["ritmo"]["y"]["fuerza"])
    if rit >= 0.5:
        modos.append({"modo": "ciclo", "por": f"patrón repetido (fuerza {rit}): admite bucle"})
    if len(pts) >= 2:
        modos.append({"modo": "kenburns", "por": f"{len(pts)} puntos fuertes separados: la cámara los recorre"})
    for mo in ("kenburns", "parallax", "capas", "ciclo", "revelado"):
        if mo == "capas" and not grafico:                              # en foto las capas dejan costuras: no se ofrece
            continue
        if mo not in [x["modo"] for x in modos]:
            modos.append({"modo": mo, "por": "alternativa"})
    hz = c["lineas"]["horizonte"]
    if hz and hz["confianza"] < 0.6:
        hz = None
    if hz:
        inc = f", inclinado {hz['angulo']:+.0f}°" if hz.get("inclinado") else ""
        tr.append({"rasgo": f"horizonte en y={hz['y']}{inc}", "movimiento": "travelling lateral paralelo al horizonte; " +
                   ("mantener su inclinación, que es parte del encuadre" if inc else "nunca inclinarlo"),
                   "por": "la línea dominante fija el eje de la cámara"})
    li = c["lineas"]
    if li["diagonal"] > 0.5 and li["n"] >= 3:
        tr.append({"rasgo": f"líneas diagonales ({li['diagonal']})", "movimiento": "cámara a lo largo de la diagonal; "
                   "barridos y transiciones en ese ángulo", "por": "el movimiento sigue la dirección del trazo"})
    elif li["vertical"] > 0.6 and li["n"] >= 3:
        tr.append({"rasgo": f"líneas verticales ({li['vertical']})", "movimiento": "subida o bajada vertical; "
                   "cortinillas verticales", "por": "el movimiento sigue la dirección del trazo"})
    si = c["simetria"]["horizontal"]
    if si > 0.75:
        tr.append({"rasgo": f"simetría horizontal {si}", "movimiento": "empuje axial (acercar o alejar) centrado; "
                   "sin desplazamiento lateral", "por": "un lateral rompería el eje"})
    if pts:
        tr.append({"rasgo": f"foco principal en ({pts[0]['x']}, {pts[0]['y']})",
                   "movimiento": "la cámara termina o empieza ahí; el revelado nace de ese punto",
                   "por": "es donde entra la mirada"})
    if c["espacio_negativo"] > 0.35:
        tr.append({"rasgo": f"espacio negativo {c['espacio_negativo']}", "movimiento": "el texto animado y los "
                   "rótulos entran por el aire; el fondo plano admite grano o deriva lenta",
                   "por": "no compite con el foco"})
    if rit >= 0.35:
        eje = "x" if c["ritmo"]["x"]["fuerza"] >= c["ritmo"]["y"]["fuerza"] else "y"
        tr.append({"rasgo": f"ritmo en {eje} (periodo {c['ritmo'][eje]['periodo']})",
                   "movimiento": "entrada escalonada por módulo, un módulo por beat; bucle con desplazamiento "
                   "de un periodo", "por": "la repetición espacial se vuelve repetición temporal"})
    n3 = v["notan3"]["proporciones"]
    if v["contraste_global"] > 0.2:
        tr.append({"rasgo": f"notan marcado (oscuro/medio/claro {n3})", "movimiento": "revelado por valores: "
                   "primero la masa, luego el medio tono, al final el color",
                   "por": "la estructura de valores es la composición"})
    if t["hay"]:
        tr.append({"rasgo": f"texto ({round(t['area'] * 100)} % del área, alineado {t['alineacion']})",
                   "movimiento": "el texto es rígido: entra por líneas desde su alineación, no se deforma con "
                   "el paralaje", "por": "la legibilidad manda"})
    if tx["grano"] > 0.006:
        tr.append({"rasgo": f"grano {tx['grano']}", "movimiento": "grano vivo a 12–24 fps sobre la imagen quieta",
                   "por": "un grano congelado delata la foto fija"})
    if m["bordes"]["hay"] and m["bordes"]["duros"] < 0.4:
        tr.append({"rasgo": f"bordes suaves ({m['bordes']['suaves']})", "movimiento": "movimiento lento y continuo, "
                   "fundidos; nada de cortes secos", "por": "el filo del movimiento iguala el filo de la forma"})
    elif m["bordes"]["duros"] > 0.9:
        tr.append({"rasgo": f"bordes duros ({m['bordes']['duros']})", "movimiento": "movimientos con arranque y "
                   "freno marcados, cortes y cortinillas de borde limpio", "por": "el filo del movimiento iguala "
                   "el filo de la forma"})
    eje = (1.0, 0.0)
    if hz is None and li["vertical"] > 0.6 and li["n"] >= 3:
        eje = (0.0, 1.0)
    elif hz and hz.get("inclinado"):                                   # el travelling sigue al horizonte, no al cuadro
        eje = (_r(math.cos(math.radians(hz["angulo"]))), _r(math.sin(math.radians(hz["angulo"]))))
    pa, ti, trat = m.get("patron") or {}, m.get("tipografia") or {}, m.get("tratamiento") or {}
    if pa.get("hay"):
        tr.append({"rasgo": f"patrón de {pa['tipo']} (periodo {pa['periodo_px']} px, {pa['angulo']}°)",
                   "movimiento": "el patrón no se reescala ni se desenfoca: movimientos de cámara cortos; si se anima, "
                   "se desplaza un periodo exacto por bucle", "por": "un semitono reescalado hace muaré"})
    if ti.get("hay") and ti.get("peso") is not None:
        esc = f", segundo nivel al {round(ti['escala'] * 100)} %" if ti.get("escala") else ""
        tr.append({"rasgo": f"tipografía {ti['peso_clase']} (trazo {ti['peso']} del alto{esc}, caja {ti['caja']})",
                   "movimiento": "los rótulos nuevos usan ese peso y esa escala entre niveles; entran por renglones, "
                   "del nivel mayor al menor", "por": "la jerarquía de la letra es la del orden de lectura"})
    if (trat.get("desregistro") or {}).get("hay"):
        d = trat["desregistro"]
        tr.append({"rasgo": f"desregistro de tintas ({d['px']} px a {d['angulo']}°)", "movimiento": "las tintas entran "
                   "por separado y encajan con ese desfase; no corregirlo", "por": "el desregistro es el acabado"})
    if (trat.get("vineta") or {}).get("hay"):
        tr.append({"rasgo": f"viñeta ({trat['vineta']['fuerza']})", "movimiento": "la viñeta va pegada al cuadro, no a "
                   "la imagen: no se mueve con la cámara", "por": "es del objetivo, no de la escena"})
    return {"sugerido": {"modo": modos[0]["modo"], "modos": modos,
                         "camara": [{"x": 0.5, "y": 0.5, "zoom": 1.0}] +
                         [{"x": p["x"], "y": p["y"], "zoom": _r(1.25 + 0.5 * min(p["peso"], 0.5), 2)} for p in pts[:4]],
                         "paralaje_eje": list(eje), "bucle": rit >= 0.5, "pieza_grafica": grafico,
                         "grano": _r(min(0.5, tx["grano"] * 25), 2),
                         "duracion_s": _r(max(3.0, 1.5 * (1 + min(len(pts), 4))), 1)},
            "traduccion": tr, "que_se_anima": None, "camara": None, "ritmo": None, "transiciones": None, "plan": None}


FILOSOFIA = {"movimiento": None, "emocion": None, "regla_generadora": None, "significado": None,
             "donde_actua": None, "donde_no": None, "variacion": None, "anatomia": None,
             "reglas_que_rompe": [], "que_la_distingue": None, "tomar": [], "no_copiar": [], "como_mejorar": []}


# ---------------------------------------------------------------- ficha

def analizar(path, lado=LADO):
    """Mide la imagen. Devuelve (ficha, mapas) — los mapas (rgb, L, saliencia, notan…) son para la hoja y
    para imagen_a_video."""
    t0 = time.perf_counter()
    rgb, nativo, w0, h0, gris = cargar(path, lado, gris=True)
    lab = oklab(rgb)
    L = np.ascontiguousarray(np.clip(lab[..., 0], 0, 1))
    nL = np.ascontiguousarray(np.clip(oklab(nativo)[..., 0], 0, 1))
    u8 = np.clip(cv2.GaussianBlur(L, (0, 0), 1.0) * 255, 0, 255).astype(np.uint8)
    gx, gy = cv2.Sobel(u8, cv2.CV_16S, 1, 0), cv2.Sobel(u8, cv2.CV_16S, 0, 1)
    alto = float(np.clip(np.percentile(np.hypot(gx, gy), 93), 60, 300))  # umbral según el gradiente de esta imagen
    canny = cv2.Canny(gx, gy, 0.4 * alto, alto, L2gradient=True)
    sal = saliencia(lab)
    m = {"color": medir_color(rgb, lab), "valores": medir_valores(L),
         "composicion": medir_composicion(rgb, lab, L, sal, canny),
         "textura": medir_textura(L, nL, canny), "bordes": medir_bordes(L, nL)}
    sg = 1024 / max(gris.shape)                                       # el texto pequeño no se ve a 512 px
    m["texto"] = medir_texto(cv2.resize(gris, (round(gris.shape[1] * sg), round(gris.shape[0] * sg)),
                                        interpolation=cv2.INTER_AREA) if sg < 1 else gris)
    m["tipografia"] = medir_tipografia(gris, m["texto"])
    m["patron"] = medir_patron(L, nL, w0, h0)
    m["tratamiento"] = medir_tratamiento(rgb, lab, L, nativo)
    m["profundidad"] = medir_profundidad(L, lab, canny, m["bordes"]["duros"])
    c = m["composicion"]
    if m["patron"]["hay"] and m["patron"]["tipo"] == "rayas" and \
            min(m["patron"]["angulo"] % 90, 90 - m["patron"]["angulo"] % 90) > 10:
        c["reticula"]["columnas"] = c["reticula"]["filas"] = None       # un rayado en diagonal no es una retícula
    if m["texto"]["hay"] and c["lineas"]["horizonte"]:
        # en una pieza con texto, una franja o la base de unas tarjetas no es un horizonte: no guía la cámara
        c["lineas"]["horizonte_descartado"] = dict(c["lineas"]["horizonte"], motivo="pieza_grafica")
        c["lineas"]["horizonte"] = None
    ban = bandas_negras(L)
    ficha = {"version": VERSION, "archivo": str(path),
             "imagen": {"ancho": w0, "alto": h0, "aspecto": _r(w0 / h0),
                        "orientacion": "horizontal" if w0 > 1.05 * h0 else "vertical" if h0 > 1.05 * w0 else "cuadrada",
                        "bandas": ban},
             "firma": firma(L, ban), "metricas": m, "reproducir": reproducir(m), "pistas_mejora": pistas_mejora(m),
             "filosofia": json.loads(json.dumps(FILOSOFIA)), "video": traducir_video(m)}
    ficha["tiempo_ms"] = round((time.perf_counter() - t0) * 1000)
    return ficha, {"rgb": rgb, "lab": lab, "L": L, "sal": sal, "canny": canny}


def ficha(path):
    return analizar(path)[0]


CAPA2 = ("movimiento", "emocion", "regla_generadora", "donde_no", "que_la_distingue", "no_copiar", "como_mejorar")
CITAS_MIN = 2                    # afirmaciones de la filosofía que tienen que apoyarse en una cifra de la ficha


def filosofia_pendiente(f):
    """Lo que le falta a la capa 2 para servir de criterio (lista vacía = completa): los siete campos
    obligatorios con contenido y al menos `CITAS_MIN` afirmaciones con una cifra (un número de la ficha:
    «acento 3 % del área», «notan 60/30/10»). Una filosofía sin cifras no se puede comprobar."""
    fi = f.get("filosofia") or {}

    def texto(v):
        return " ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
    falta = [f"filosofia.{k}: sin rellenar" for k in CAPA2 if len(texto(fi.get(k)).strip()) < 8]
    con_cifra = sum(1 for k in FILOSOFIA if any(ch.isdigit() for ch in texto(fi.get(k))))
    if not falta and con_cifra < CITAS_MIN:
        falta.append(f"filosofia: {con_cifra} afirmaciones citan una cifra de la ficha; hacen falta {CITAS_MIN}")
    return falta


def validar(f, completa=False):
    """Errores de la ficha contra el esquema (lista vacía = válida). Sin jsonschema, claves obligatorias.
    Con `completa`, además exige la capa 2 (`filosofia_pendiente`): es lo que se pide antes de aprobar la biblia."""
    esq = json.loads(ESQUEMA.read_text())
    try:
        import jsonschema
    except ImportError:
        err = [f"falta '{k}'" for k in esq["required"] if k not in f] + \
              [f"falta 'metricas.{k}'" for k in esq["properties"]["metricas"]["required"] if k not in f.get("metricas", {})]
    else:
        v = jsonschema.Draft202012Validator(esq)
        err = [f"{'/'.join(str(p) for p in e.absolute_path) or '(raíz)'}: {e.message}" for e in v.iter_errors(f)]
    return err + (filosofia_pendiente(f) if completa else [])


# ---------------------------------------------------------------- hoja de diagnóstico

def _fuente(t):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
              "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, t)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=t)
    except TypeError:
        return ImageFont.load_default()


def _encaja(a, bw, bh):
    """ndarray uint8 RGB → imagen PIL que cabe en bw×bh."""
    im = Image.fromarray(a)
    s = min(bw / im.width, bh / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS if s < 1 else Image.NEAREST)


def _calor(s):
    """Mapa 0..1 → RGB (negro, azul, magenta, naranja, blanco)."""
    xs = np.array([0, 0.25, 0.5, 0.75, 1.0])
    cs = np.array([[8, 8, 20], [40, 60, 170], [190, 50, 130], [250, 150, 40], [255, 250, 220]], np.float32)
    return np.stack([np.interp(s, xs, cs[:, i]) for i in range(3)], -1).astype(np.uint8)


def hoja(f, mapas, out):
    """Hoja para que la mire el modelo: composición sobre el original, saliencia, notan, profundidad,
    bordes, paleta, histograma, tonos y cifras."""
    m = f["metricas"]
    rgb, L, sal = mapas["rgb"], mapas["L"], mapas["sal"]
    c = m["composicion"]
    W, P, AL = 1800, 20, 540
    f16, f13, f20 = _fuente(16), _fuente(13), _fuente(20)
    sheet = Image.new("RGB", (W, 1240), (16, 16, 18))
    dr = ImageDraw.Draw(sheet)
    bw = (W - 3 * P) // 2

    def panel(im, x, y, titulo, w=bw, h=AL):
        dr.text((x, y), titulo, fill=(235, 235, 235), font=f16)
        sheet.paste(im, (x, y + 24))
        dr.rectangle([x - 1, y + 23, x + im.width, y + 24 + im.height], outline=(70, 70, 76))
        return x, y + 24, im.width, im.height

    # 1 · composición sobre el original
    im = _encaja((rgb * 255).astype(np.uint8), bw, AL)
    ov = ImageDraw.Draw(im, "RGBA")
    w, h = im.size
    for a in (1 / 3, 2 / 3):
        ov.line([(a * w, 0), (a * w, h)], fill=(255, 255, 255, 150), width=1)
        ov.line([(0, a * h), (w, a * h)], fill=(255, 255, 255, 150), width=1)
    for a in (0.382, 0.618):
        ov.line([(a * w, 0), (a * w, h)], fill=(255, 210, 60, 110), width=1)
        ov.line([(0, a * h), (w, a * h)], fill=(255, 210, 60, 110), width=1)
    for li in c["lineas"]["principales"]:
        ov.line([(li["x1"] * w, li["y1"] * h), (li["x2"] * w, li["y2"] * h)], fill=(0, 230, 255, 230), width=2)
    if c["lineas"]["horizonte"]:
        y = c["lineas"]["horizonte"]["y"] * h
        dy = 0.5 * w * math.tan(math.radians(c["lineas"]["horizonte"].get("angulo", 0.0)))
        ov.line([(0, y - dy), (w, y + dy)], fill=(60, 255, 120, 255), width=3)
    mg = c["margen"]
    if not mg["a_sangre"]:
        ov.rectangle([mg["izq"] * w, mg["arriba"] * h, (1 - mg["der"]) * w, (1 - mg["abajo"]) * h],
                     outline=(255, 120, 220, 255), width=2)
    for k in m["texto"]["cajas"]:
        ov.rectangle([k["x"] * w, k["y"] * h, (k["x"] + k["w"]) * w, (k["y"] + k["h"]) * h],
                     outline=(255, 255, 0, 255), width=1)
    for i, p in enumerate(c["puntos_fuertes"]):
        x, y, r = p["x"] * w, p["y"] * h, 13
        ov.ellipse([x - r, y - r, x + r, y + r], fill=(230, 30, 40, 235), outline=(255, 255, 255, 255), width=2)
        ov.text((x - 4, y - 9), str(i + 1), fill=(255, 255, 255, 255), font=f16)
    x, y = c["centro_masa"]["x"] * w, c["centro_masa"]["y"] * h
    ov.line([(x - 14, y), (x + 14, y)], fill=(255, 255, 255, 255), width=3)
    ov.line([(x, y - 14), (x, y + 14)], fill=(255, 255, 255, 255), width=3)
    panel(im, P, P, "Composición")
    dr.text((P, P + 24 + AL + 6), "blanco: tercios · ámbar: áurea · rojo: focos en orden de saliencia · cruz: centro de masa · "
            "cian: líneas · verde: horizonte · rosa: margen · amarillo: texto", fill=(165, 165, 170), font=f13)
    # 2 · saliencia
    im = _encaja(_calor(sal), bw, AL)
    ov = ImageDraw.Draw(im)
    w, h = im.size
    ov.line([(w / 2, 0), (w / 2, h)], fill=(255, 255, 255), width=1)
    ov.line([(0, h / 2), (w, h / 2)], fill=(255, 255, 255), width=1)
    q = c["peso_cuadrantes"]
    for (k, px, py) in (("sup_izq", 0.02, 0.02), ("sup_der", 0.52, 0.02), ("inf_izq", 0.02, 0.52), ("inf_der", 0.52, 0.52)):
        ov.text((px * w + 4, py * h + 4), f"{round(q[k] * 100)} %", fill=(255, 255, 255), font=f20)
    panel(im, 2 * P + bw, P, "Saliencia y peso por cuadrante")

    # fila 2: notan 2, notan 3, profundidad proxy, bordes
    y2 = P + 24 + AL + 34
    sw = (W - 5 * P) // 4
    v = m["valores"]
    n2 = np.where(L >= v["notan2"]["umbral"], 235, 20).astype(np.uint8)
    a, b = v["notan3"]["umbrales"]
    n3 = np.select([L < a, L < b], [20, 128], 235).astype(np.uint8)
    prof = profundidad_proxy(rgb, mapas["lab"], sal, m["texto"])
    bor = np.zeros(L.shape + (3,), np.uint8)
    bor[mapas["canny"] > 0] = (240, 240, 240)
    for i, (arr, t) in enumerate(((np.stack([n2] * 3, -1), f"Notan 2 · oscuro {round(v['notan2']['oscuro'] * 100)} %"),
                                  (np.stack([n3] * 3, -1), "Notan 3 · " + "/".join(str(round(p * 100)) for p in
                                                                                 v["notan3"]["proporciones"]) + " %"),
                                  (_calor(prof), f"Profundidad proxy (claro = cerca) · {m['profundidad']['pista']}"),
                                  (bor, f"Bordes · duros {round(m['bordes']['duros'] * 100)} % · "
                                        f"densidad {m['textura']['densidad_bordes']}"))):
        panel(_encaja(arr, sw, 270), P + i * (sw + P), y2, t, sw, 270)

    # fila 3: paleta, histograma, tonos, cifras
    y3 = y2 + 24 + 270 + 18
    dr.text((P, y3), f"Paleta (OKLCH) · armonía {m['color']['armonia']['tipo']} · temperatura {m['color']['temperatura']}",
            fill=(235, 235, 235), font=f16)
    x = P
    ancho = 560
    for k in m["color"]["paleta"]:
        pw = max(3, round(k["proporcion"] * ancho))
        dr.rectangle([x, y3 + 26, x + pw, y3 + 86], fill=k["hex"])
        x += pw
    for i, k in enumerate(m["color"]["paleta"][:8]):
        yy = y3 + 96 + i * 21
        dr.rectangle([P, yy, P + 28, yy + 16], fill=k["hex"], outline=(90, 90, 90))
        dr.text((P + 36, yy), f"{k['hex']}  {k['proporcion'] * 100:4.1f} %  L {k['oklch'][0]:.2f} C {k['oklch'][1]:.2f} "
                              f"h {k['oklch'][2]:5.1f}  {k['papel']}", fill=(215, 215, 215), font=f13)
    hx = P + ancho + 40
    dr.text((hx, y3), f"Valores · clave {v['clave']} · mediana {v['mediana']} · rango {v['rango']}", fill=(235, 235, 235), font=f16)
    tope = max(v["histograma"]) or 1
    for i, hv in enumerate(v["histograma"]):
        g = int((i + 0.5) / 16 * 255)
        dr.rectangle([hx + i * 22, y3 + 150 - int(120 * hv / tope), hx + i * 22 + 20, y3 + 150], fill=(g, g, g),
                     outline=(90, 90, 90))
    for t, col in ((v["notan3"]["umbrales"][0], (255, 120, 60)), (v["notan3"]["umbrales"][1], (255, 120, 60)),
                   (v["mediana"], (60, 220, 255))):
        dr.line([(hx + t * 352, y3 + 26), (hx + t * 352, y3 + 152)], fill=col, width=2)
    dr.text((hx, y3 + 158), "naranja: umbrales del notan · cian: mediana", fill=(170, 170, 170), font=f13)
    # rueda de tonos
    cx, cy, R = hx + 470, y3 + 100, 70
    dr.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(90, 90, 90))
    for t in m["color"]["armonia"]["tonos"]:
        a = math.radians(t["tono"])
        r = R * (0.35 + 0.65 * min(1, t["peso"] * 1.6))
        dr.line([(cx, cy), (cx + r * math.cos(a), cy - r * math.sin(a))], fill=(255, 255, 255), width=4)
        dr.text((cx + (R + 8) * math.cos(a) - 10, cy - (R + 8) * math.sin(a) - 7), f"{round(t['tono'])}°",
                fill=(215, 215, 215), font=f13)
    dr.text((cx - R, y3), "Tonos (OKLCH)", fill=(235, 235, 235), font=f16)
    # cifras
    tx = hx + 600
    pts = c["puntos_fuertes"]
    lin = [f"{Path(f['archivo']).name} · {f['imagen']['ancho']}×{f['imagen']['alto']} · {f['tiempo_ms']} ms",
           f"foco 1: ({pts[0]['x']}, {pts[0]['y']})" if pts else "sin foco",
           f"tercios {c['tercios']['distancia']} ({c['tercios']['punto']}) · áurea {c['aurea']['distancia']} · "
           f"centro {c['centro']['distancia']}",
           f"simetría h {c['simetria']['horizontal']} v {c['simetria']['vertical']} · balance x {c['balance_x']} "
           f"y {c['balance_y']}",
           f"espacio negativo {c['espacio_negativo']} · líneas H/V/D {c['lineas']['horizontal']}/"
           f"{c['lineas']['vertical']}/{c['lineas']['diagonal']}",
           f"ritmo x {c['ritmo']['x']['periodo']} ({c['ritmo']['x']['fuerza']}) y {c['ritmo']['y']['periodo']} "
           f"({c['ritmo']['y']['fuerza']}) · retícula {c['reticula']['columnas']}×{c['reticula']['filas']}",
           f"contraste global {v['contraste_global']} local {v['contraste_local']} · entropía {m['textura']['entropia']}",
           f"alta frecuencia {m['textura']['alta_frecuencia']} · grano {m['textura']['grano']} · "
           f"croma {m['color']['croma_media']} (p90 {m['color']['croma_p90']})",
           f"texto: {'sí' if m['texto']['hay'] else 'no'} · área {m['texto']['area']} · {m['texto']['alineacion']}" +
           (f" · letra {m['tipografia']['peso_clase']} ({m['tipografia']['peso']}), {len(m['tipografia']['niveles'])} niveles"
            if m["tipografia"]["peso"] is not None else ""),
           (f"patrón de {m['patron']['tipo']}: {m['patron']['periodo_px']} px a {m['patron']['angulo']}°"
            if m["patron"]["hay"] else "sin patrón fino") +
           " · " + (", ".join(k for k in ("duotono", "desregistro", "vineta") if m["tratamiento"][k]["hay"]) or "sin tratamiento"),
           f"video sugerido: {f['video']['sugerido']['modo']} — {f['video']['sugerido']['modos'][0]['por']}"]
    dr.text((tx, y3), "Cifras", fill=(235, 235, 235), font=f16)
    for i, s in enumerate(lin):
        dr.text((tx, y3 + 26 + i * 20), s[:92], fill=(215, 215, 215), font=f13)
    alto = y3 + 96 + 8 * 21 + P
    sheet.crop((0, 0, W, alto)).save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("imagen", help="imagen, o ficha .json con --validar")
    ap.add_argument("--validar", action="store_true", help="valida una ficha .json contra el esquema y sale con 1 si falla")
    ap.add_argument("--completa", action="store_true", help="con --validar: exige además la capa 2 (filosofía) rellena y con cifras")
    ap.add_argument("--json", action="store_true", help="ficha completa por stdout")
    ap.add_argument("--hoja", help="PNG de diagnóstico")
    ap.add_argument("--ficha", help="escribe la ficha en este JSON")
    a = ap.parse_args()
    if not Path(a.imagen).is_file():
        sys.exit(f"{a.imagen}: no existe")
    if a.validar or a.completa:
        if Path(a.imagen).suffix.lower() != ".json":
            sys.exit("--validar espera una ficha .json (la que escribe --ficha o referencias.py en fichas/)")
        err = validar(json.loads(Path(a.imagen).read_text()), completa=a.completa)
        print(f"{a.imagen}: " + ("válida" + (" y completa" if a.completa else "") if not err else
                                 f"{len(err)} problemas\n  " + "\n  ".join(err[:20])))
        sys.exit(1 if err else 0)
    f, mapas = analizar(a.imagen)
    err = validar(f)
    if err:
        print("ficha no válida:\n  " + "\n  ".join(err[:10]), file=sys.stderr)
    if a.ficha:
        Path(a.ficha).parent.mkdir(parents=True, exist_ok=True)
        Path(a.ficha).write_text(json.dumps(f, ensure_ascii=False, indent=1))
    if a.hoja:
        Path(a.hoja).parent.mkdir(parents=True, exist_ok=True)
        hoja(f, mapas, a.hoja)
    if a.json:
        print(json.dumps(f, ensure_ascii=False, indent=1))
    else:
        m = f["metricas"]
        print(f"{Path(a.imagen).name}: {f['tiempo_ms']} ms · clave {m['valores']['clave']} · armonía "
              f"{m['color']['armonia']['tipo']} · {len(m['composicion']['puntos_fuertes'])} focos · video sugerido: "
              f"{f['video']['sugerido']['modo']}" + (f" · hoja {a.hoja}" if a.hoja else ""))
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
