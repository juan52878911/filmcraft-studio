#!/usr/bin/env python3
"""Mide las referencias que trae el usuario para la preproducción: lo que se puede medir, medido.

Uso:
    referencias.py RUTA [RUTA ...] --out CARPETA     (archivos o carpetas; las URLs no: ver la skill)
    referencias.py --comparar REF FOTO [--json] [--out comparacion.json]
    referencias.py --validar CARPETA|ficha.json ...    (capa 2 rellena; sale con 1 si falta)

Por tipo:
- imagen: tamaño y aspecto, paleta (k-means, como ds_from_image), luz media, contraste y saturación, y su
  **ficha** (ref_metricas.py): color en OKLCH y armonía, valores y notan, composición, textura, bordes,
  profundidad, texto, con objetivo y tolerancia por métrica, más los huecos de filosofía y de traducción a
  video que rellena el modelo. Ficha y hoja de diagnóstico en CARPETA/fichas/.
- video: duración, fps, aspecto, cortes (escena > 0,3), plano medio y cortes por minuto, paleta de los
  planos, loudness y BPM si tiene audio, y un fotograma por plano en la hoja.
- audio: duración, loudness integrado y BPM estimado (autocorrelación del flujo espectral).
- fuente (.ttf/.otf/.ttc): familia y estilo.

Escribe CARPETA/referencias.json y CARPETA/referencias.png (miniaturas con su paleta). Con dos imágenes o
más, CARPETA/agregado.json separa los rasgos comunes (el estilo) de los idiosincrásicos (de una pieza). Las
cifras son pistas para las preguntas, no decisiones: el ritmo de cortes de una referencia no obliga a copiarlo.

`--comparar REF FOTO` (imágenes o fichas .json) mide la distancia de un fotograma propio a una referencia,
métrica a métrica contra su tolerancia, en dos grupos: **estilo** (lo que se quiere reproducir) y
**composición** (lo que no se copia). Veredicto: reproduce el estilo, estilo distinto, misma maqueta o
clon probable. El color (paleta, tono principal y tonos de la paleta) es condición necesaria del estilo:
con otra paleta no se «reproduce el estilo» por muchas otras métricas que coincidan. La misma imagen
espejada, girada 90/180°, recortada o con bandas negras se reconoce por su firma y cuenta como la misma
composición. Sale con 0 siempre; el veredicto va en la salida, que además cita la capa 2 de la referencia.

`--validar RUTA...` (fichas o la carpeta de --out) exige la capa 2 de cada ficha rellena y con cifras:
es la comprobación previa a aprobar la biblia. Volver a medir una carpeta conserva la capa 2 ya escrita.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from common import ffprobe  # noqa: E402
from ds_from_image import palette  # noqa: E402

try:
    import ref_metricas as rm  # noqa: E402
except ImportError as e:            # sin opencv no hay ficha; lo demás sigue midiéndose
    rm = None
    print(f"aviso: sin ficha de referencia ({e}); pip install opencv-python", file=sys.stderr)

IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic"}
VID = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
AUD = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff"}
FNT = {".ttf", ".otf", ".ttc"}


def tono_imagen(im):
    a = np.asarray(im.convert("RGB").resize((160, int(160 * im.height / im.width) or 1)), np.float32) / 255
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return {"luz": round(float(lum.mean()), 3), "contraste": round(float(lum.std()), 3),
            "saturacion": round(float(sat.mean()), 3)}


def paleta_corta(path, n=6):
    cl, _ = palette(path, k=10, recorte="no")
    return [{"hex": c["vivo"] if c["sat"] > 0.35 else c["hex"], "area": c["area"]} for c in cl[:n]]


def loudness(path):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return {"lufs": float(i[-1]) if i else None, "pico_dbfs": float(p[-1]) if p else None}


def bpm(path, sr=11025, hop=256):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "120", "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    if len(x) < sr * 6:
        return None
    n = 1024
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(np.diff(mag, axis=0), 0).sum(1)
    flux = flux - flux.mean()
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    fps = sr / hop
    lags = np.arange(len(ac))
    ok = (lags >= fps * 60 / 180) & (lags <= fps * 60 / 70)
    if not ok.any():
        return None
    lag = int(lags[ok][np.argmax(ac[ok])])
    a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
    lag += 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0   # pico parabólico: el lag es entero
    return round(60 * fps / lag, 1)


def cortes(path, umbral=0.3):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-vf",
                        f"scale=320:-2,select='gt(scene,{umbral})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def fotograma(path, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                    "-vf", "scale=480:-2", str(out)], check=False)
    return out if out.exists() else None


def ficha_imagen(p, fichas, nombre=None):
    """Mide la ficha, la guarda con su hoja en `fichas` y devuelve (ficha, resumen para referencias.json)."""
    if rm is None:
        return None, {}
    f, mapas = rm.analizar(p)
    nombre = nombre or p.stem
    fichas.mkdir(parents=True, exist_ok=True)
    fj, fh = fichas / f"{nombre}.json", fichas / f"{nombre}_hoja.png"
    if fj.is_file():                                                   # volver a medir no borra lo que rellenó el modelo
        try:
            antes = json.loads(fj.read_text())
        except ValueError:
            antes = {}
        for k, v in (antes.get("filosofia") or {}).items():
            if v and k in f["filosofia"]:
                f["filosofia"][k] = v
        for k in ("que_se_anima", "camara", "ritmo", "transiciones", "plan"):
            if (antes.get("video") or {}).get(k):
                f["video"][k] = antes["video"][k]
    fj.write_text(json.dumps(f, ensure_ascii=False, indent=1))
    rm.hoja(f, mapas, fh)
    m = f["metricas"]
    return f, {"ficha": str(fj), "hoja_ficha": str(fh), "capa2_pendiente": rm.filosofia_pendiente(f),
               "resumen": {"clave": m["valores"]["clave"], "armonia": m["color"]["armonia"]["tipo"],
                           "temperatura": m["color"]["temperatura"], "notan3": m["valores"]["notan3"]["proporciones"],
                           "focos": m["composicion"]["puntos_fuertes"], "espacio_negativo": m["composicion"]["espacio_negativo"],
                           "texto": m["texto"]["area"], "video": f["video"]["sugerido"]["modo"]}}


def _lab(c):
    L, C, h = c["oklch"]
    return np.array([L, C * np.cos(np.radians(h)), C * np.sin(np.radians(h))])


def _maqueta(ga, gb):
    """Distancia 0..1 entre la «figura» de dos notan (las celdas que no son el valor dominante de cada
    imagen), con una celda de holgura. Contar celdas iguales no sirve: dos piezas casi vacías coinciden
    en el fondo sin parecerse en nada."""
    import cv2
    fa = (ga != np.bincount(ga.ravel(), minlength=3).argmax()).astype(np.uint8)
    fb = (gb != np.bincount(gb.ravel(), minlength=3).argmax()).astype(np.uint8)
    n = int(fa.sum() + fb.sum())
    if not n:
        return 0.0
    k = np.ones((3, 3), np.uint8)
    return float(1 - ((fa & cv2.dilate(fb, k)).sum() + (fb & cv2.dilate(fa, k)).sum()) / n)


# Lo que no cambia una imagen: espejarla, girarla o recortarla. (nombre, rejilla → rejilla, foco → foco)
GEOMETRIAS = (
    ("igual", lambda g: g, lambda p: p),
    ("espejo", lambda g: g[:, ::-1], lambda p: (1 - p[0], p[1])),
    ("giro_180", lambda g: g[::-1, ::-1], lambda p: (1 - p[0], 1 - p[1])),
    ("espejo_vertical", lambda g: g[::-1], lambda p: (p[0], 1 - p[1])),
    ("giro_90", lambda g: np.rot90(g), lambda p: (p[1], 1 - p[0])),
    ("giro_270", lambda g: np.rot90(g, 3), lambda p: (1 - p[1], p[0])),
)
DERIVADO_MIN = 0.86              # correlación de la firma a partir de la cual es la misma imagen (calibrado: R3)
RECORTES = (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6)
DETALLE_MIN = 0.12               # fracción de la firma con borde: por debajo, un recorte no prueba nada


def _firma(f):
    fi = f.get("firma")
    if not fi or not fi.get("L"):
        return None
    import base64
    n = fi["lado"]
    return np.frombuffer(base64.b64decode(fi["L"]), np.uint8).reshape(n, n).astype(np.float32) / 255


def derivado(ref, foto):
    """¿`foto` es la misma imagen que `ref` espejada, girada, recortada o con bandas? Compara las firmas
    (miniaturas de luminancia sin bandas negras) bajo las seis geometrías y con recortes del 60–100 % por
    cada eje, en los dos sentidos. La correlación es normalizada: no la mueven el brillo, el contraste ni
    el grano, y su valor absoluto tampoco la inversión. → {transformacion, recorte, correlacion} o None."""
    import cv2
    a, b = _firma(ref), _firma(foto)
    if a is None or b is None or a.std() < 0.008 or b.std() < 0.008:
        return None
    n = a.shape[0]

    def detalle(x):                                                    # una sola forma sobre fondo liso casa con
        g = np.hypot(cv2.Sobel(x, cv2.CV_32F, 1, 0), cv2.Sobel(x, cv2.CV_32F, 0, 1)) / 8   # cualquier recorte de sí misma
        return float((g > 0.03).mean())
    recortable = min(detalle(a), detalle(b)) >= DETALLE_MIN
    mejor = (0.0, None, None)
    for nombre, G, _ in GEOMETRIAS:
        tb = np.ascontiguousarray(G(b))
        for grande, peq, quien in ((a, tb, "foto"), (tb, a, "ref")):   # quien = cuál de las dos es el recorte
            for sx in RECORTES:
                for sy in RECORTES:
                    if (sx == sy == 1.0 and quien == "ref") or (not recortable and (sx, sy) != (1.0, 1.0)):
                        continue
                    t = peq if sx == sy == 1.0 else cv2.resize(peq, (round(n * sx), round(n * sy)),
                                                                interpolation=cv2.INTER_AREA)
                    if t.std() < 0.008:
                        continue
                    r = np.nan_to_num(cv2.matchTemplate(grande, t, cv2.TM_CCOEFF_NORMED), nan=0, posinf=0, neginf=0)
                    v = float(np.abs(r).max()) - 0.04 * (2 - sx - sy)   # un recorte pequeño casa más por azar
                    if v > mejor[0]:
                        mejor = (v, nombre, None if sx == sy == 1.0 else {"de": quien, "ancho": sx, "alto": sy})
    if mejor[0] < DERIVADO_MIN:
        return {"es": False, "correlacion": round(mejor[0], 3)}
    return {"es": True, "transformacion": mejor[1], "recorte": mejor[2], "correlacion": round(mejor[0], 3)}


def _especiales(a, b):
    """Distancias que no son un escalar: paleta, tonos, histograma, notan y focos. → ({ruta: distancia},
    geometría con la que mejor casan notan y focos)."""
    ma, mb = a["metricas"], b["metricas"]
    pa, pb = ma["color"]["paleta"], mb["color"]["paleta"]

    def ida(x, y):
        return sum(c["proporcion"] * min(np.linalg.norm(_lab(c) - _lab(k)) for k in y) for c in x) / \
            max(sum(c["proporcion"] for c in x), 1e-6)

    def vivos(pal, firme):
        # Colores con tono propio. Los que se buscan (firme) son los claros: croma ≥ 0,05 y ≥ 1 % del área;
        # donde se buscan vale cualquiera con algo de croma. Con un solo umbral, un acento que ronda el 1 %
        # entra en una ficha y no en la otra al recomprimir, y parecía «otra paleta».
        return [c["oklch"][2] for c in pal if (c["oklch"][1] >= 0.05 and c["proporcion"] >= 0.01) if firme] if firme \
            else [c["oklch"][2] for c in pal if c["oklch"][1] >= 0.03]

    def tonos(x, y):
        fx, ty = vivos(x, True), vivos(y, False)
        if not fx:
            return 0.0
        if not ty:
            return 180.0
        return float(np.mean([min(min(abs(h - k) % 360, 360 - abs(h - k) % 360) for k in ty) for h in fx]))
    pal_tonos = max(tonos(pa, pb), tonos(pb, pa))
    def firmes(t):                                                     # sin los tonos de croma casi neutra (si queda alguno)
        return [k for k in t if k.get("croma", 1.0) >= 0.06] or t
    ta, tb = firmes(ma["color"]["armonia"]["tonos"]), firmes(mb["color"]["armonia"]["tonos"])
    def principal(x, y):                                               # el tono dominante de x, frente a los fuertes de y:
        fuertes = [t for t in y if t["peso"] >= 0.5 * y[0]["peso"]]   # dos picos parejos se turnan el primer puesto
        return min(min(abs(x[0]["tono"] - t["tono"]) % 360, 360 - abs(x[0]["tono"] - t["tono"]) % 360) for t in fuertes)
    if ta and tb:
        tono = max(principal(ta, tb), principal(tb, ta))
    else:
        tono = 0.0 if not ta and not tb else 180.0
    ha, hb = np.cumsum(ma["valores"]["histograma"]), np.cumsum(mb["valores"]["histograma"])
    ra, rb = ma["valores"]["notan3"]["rejilla"], mb["valores"]["notan3"]["rejilla"]
    ga = np.array([[int(v) for v in f] for f in ra])
    gb = np.array([[int(v) for v in f] for f in rb])
    fa = [(p["x"], p["y"]) for p in ma["composicion"]["puntos_fuertes"]]
    fb = [(p["x"], p["y"]) for p in mb["composicion"]["puntos_fuertes"]]

    def cerca(x, y):
        return float(np.mean([min(np.hypot(p[0] - q[0], p[1] - q[1]) for q in y) for p in x])) / np.sqrt(2)
    tn = dict((r, t) for r, _, t, _ in rm.ESPECIALES)
    mejor = None
    for nombre, G, F in GEOMETRIAS[:2]:                                # la misma maqueta espejada es la misma maqueta. Los
        # giros solo se buscan en `derivado`, píxel a píxel: con medidas tan gruesas, seis geometrías hacen
        # que un círculo en un tercio «copie» a otro en el tercio opuesto
        g = np.ascontiguousarray(G(gb))
        if g.shape != ga.shape:                                        # otro aspecto: se compara estirado
            fy, fx = np.linspace(0, g.shape[0] - 1, ga.shape[0]).round().astype(int), \
                np.linspace(0, g.shape[1] - 1, ga.shape[1]).round().astype(int)
            g = g[fy][:, fx]
        fg = [F(p) for p in fb]
        focos = 0.5 * (cerca(fa, fg) + cerca(fg, fa)) if fa and fg else (0.0 if not fa and not fg else 1.0)
        notan = _maqueta(ga, g)
        coste = max(notan / tn["valores.notan3.rejilla"], focos / tn["composicion.puntos_fuertes"])
        if mejor is None or coste < mejor[0] - 1e-9:
            mejor = (coste, nombre, notan, focos)
    return {"color.paleta": 0.5 * (ida(pa, pb) + ida(pb, pa)), "color.tono_principal": float(tono),
            "color.paleta_tonos": float(pal_tonos),
            "valores.histograma": float(np.abs(ha - hb).sum() / 16), "valores.notan3.rejilla": mejor[2],
            "composicion.puntos_fuertes": float(mejor[3])}, mejor[1]


def _capa2(f):
    """Lo que la referencia dice de sí misma (capa 2), para que la crítica lo cite junto a las cifras."""
    fi = f.get("filosofia") or {}
    return {k: fi.get(k) for k in ("regla_generadora", "que_la_distingue", "donde_no", "no_copiar", "tomar") if fi.get(k)}


def comparar(ref, foto):
    """Distancia de `foto` a `ref` (fichas), métrica a métrica contra su tolerancia, y veredicto.

    «Reproduce el estilo» exige el 75 % de las métricas de estilo dentro de tolerancia **y** el color
    (paleta, tono principal y tonos de la paleta): son condición necesaria, no un voto más. «Misma
    composición» es la figura del notan y los focos dentro de tolerancia —bajo la geometría que mejor
    case: igual, espejo o giro— o que `derivado` reconozca la misma imagen espejada, girada o recortada."""
    filas = []
    for ruta, grupo, tol, como in rm.METRICAS:
        a, b = rm._get(ref["metricas"], ruta), rm._get(foto["metricas"], ruta)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            filas.append({"metrica": ruta, "grupo": grupo, "ref": a, "foto": b, "delta": round(b - a, 4),
                          "tolerancia": tol, "como": como})
    esp, geo = _especiales(ref, foto)
    for ruta, grupo, tol, como in rm.ESPECIALES:
        filas.append({"metrica": ruta, "grupo": grupo, "ref": None, "foto": None, "delta": round(esp[ruta], 4),
                      "tolerancia": tol, "como": como})
    for f in filas:
        f["razon"] = round(abs(f["delta"]) / f["tolerancia"], 2)      # 1 = justo en la tolerancia
        f["dentro"] = bool(f["razon"] <= 1)
    res = {}
    for g in ("estilo", "composicion"):
        fs = [f for f in filas if f["grupo"] == g]
        res[g] = {"dentro": int(sum(f["dentro"] for f in fs)), "total": len(fs),
                  "similitud": round(float(np.mean([min(1.0, max(0.0, 1 - (f["razon"] - 1) / 3)) for f in fs])), 3)}
    porm = {f["metrica"]: f for f in filas}
    color = {r.split(".", 1)[1]: bool(porm[r]["dentro"]) for r in rm.COLOR_NECESARIO}
    tonos_ok = color["tono_principal"] and color["paleta_tonos"]
    votos = bool(res["estilo"]["dentro"] >= 0.75 * res["estilo"]["total"])
    e = bool(votos and all(color.values()))
    der = derivado(ref, foto)
    es_der = bool(der and der["es"])
    # misma maqueta = misma figura del notan y mismos focos, no solo escalares parecidos; o la misma imagen
    c_med = bool(porm["valores.notan3.rejilla"]["dentro"] and porm["composicion.puntos_fuertes"]["dentro"]
                 and res["composicion"]["dentro"] >= 0.6 * res["composicion"]["total"])
    c = bool(c_med or es_der)
    # un recorte o unas bandas mueven los escalares de estilo sin cambiar la imagen: si es la misma imagen
    # y conserva los tonos, es un clon aunque no llegue al 75 %
    clon = bool((e and c) or (es_der and tonos_ok))
    como = ""
    if es_der and (der["transformacion"] != "igual" or der["recorte"]):
        partes = ([der["transformacion"].replace("_", " ")] if der["transformacion"] != "igual" else []) + \
                 (["recorte"] if der["recorte"] else [])
        como = f" ({' y '.join(partes)} de la misma imagen)"
    veredicto = (f"clon probable: mismo estilo y misma composición{como}" if clon else
                 "reproduce el estilo con composición propia" if e else
                 f"misma maqueta con otro estilo{como}" if c else "estilo distinto")
    fuera = sorted((f for f in filas if f["grupo"] == "estilo" and not f["dentro"]), key=lambda f: -f["razon"])
    if not all(color.values()):                                        # lo que impide el estilo va primero
        fuera.sort(key=lambda f: f["metrica"] not in rm.COLOR_NECESARIO)
    out = {"ref": ref["archivo"], "foto": foto["archivo"], "veredicto": veredicto, "reproduce_estilo": bool(e or clon),
           "riesgo_clon": clon, "resumen": res, "color": dict(color, votos_estilo=votos),
           "geometria": geo, "derivado": der,
           "ajustar": [{"metrica": f["metrica"], "sentido": "igualar" if f["ref"] is None else
                        "bajar" if f["delta"] > 0 else "subir", "delta": f["delta"], "tolerancia": f["tolerancia"],
                        "como": f["como"]} for f in fuera[:6]],
           "metricas": filas}
    capa2 = _capa2(ref)
    if capa2:
        out["filosofia_ref"] = capa2
    else:
        out["aviso"] = "la referencia no tiene la capa 2 (filosofía) rellena: la crítica no puede citar su regla ni su «no copiar»"
    return out


def agregar(fichas):
    """Varias referencias → rasgos comunes (todas dentro de la tolerancia: el estilo) e idiosincrásicos
    (alguna se aparta: cosa de esa pieza). `fichas` = {nombre: ficha}."""
    comunes, idio = [], []
    for ruta, grupo, tol, como in rm.METRICAS:
        vals = {n: rm._get(f["metricas"], ruta) for n, f in fichas.items()}
        vals = {n: v for n, v in vals.items() if isinstance(v, (int, float))}
        if len(vals) < 2:
            continue
        med = float(np.median(list(vals.values())))
        fuera = sorted(n for n, v in vals.items() if abs(v - med) > tol)
        if fuera:
            idio.append({"metrica": ruta, "grupo": grupo, "mediana": round(med, 3), "tolerancia": tol,
                         "valores": vals, "se_apartan": fuera})
        else:
            comunes.append({"metrica": ruta, "grupo": grupo, "objetivo": round(float(np.mean(list(vals.values()))), 3),
                            "tolerancia": tol, "min": min(vals.values()), "max": max(vals.values()), "como": como})
    cat = {}
    for nombre, ruta in (("clave", "valores.clave"), ("armonia", "color.armonia.tipo"),
                         ("profundidad", "profundidad.pista"), ("texto", "texto.hay")):
        vals = {n: rm._get(f["metricas"], ruta) for n, f in fichas.items()}
        cat[nombre] = {"comun": len(set(vals.values())) == 1, "valores": vals}
    for nombre, ruta in (("tipografia_peso", "tipografia.peso_clase"), ("tipografia_caja", "tipografia.caja"),
                         ("patron", "patron.tipo"), ("duotono", "tratamiento.duotono.hay"),
                         ("desregistro", "tratamiento.desregistro.hay"), ("vineta", "tratamiento.vineta.hay")):
        vals = {n: rm._get(f["metricas"], ruta) for n, f in fichas.items()}
        cat[nombre] = {"comun": len(set(vals.values())) == 1, "valores": vals}
    # capa 2: lo que cada referencia dice de sí misma. Si todas están rellenas, las reglas van juntas para
    # que la biblia saque la suya; si falta alguna, se dice cuál.
    capa2 = {n: {k: (f.get("filosofia") or {}).get(k) for k in ("regla_generadora", "que_la_distingue", "donde_no",
                                                                 "no_copiar")} for n, f in fichas.items()}
    pend = {n: rm.filosofia_pendiente(f) for n, f in fichas.items()}
    return {"n": len(fichas), "referencias": sorted(fichas), "comunes": comunes, "idiosincrasicos": idio,
            "categorias": cat, "filosofia": {"por_referencia": capa2,
                                             "pendiente": sorted(n for n, e in pend.items() if e)},
            "nota": "Lo común es el estilo: sus objetivos son criterios de aceptación. Lo idiosincrásico es de una "
                    "pieza: no se promedia ni se copia."}


def _ficha_de(ruta):
    p = Path(ruta).expanduser()
    if not p.is_file():
        sys.exit(f"{p}: no existe")
    return json.loads(p.read_text()) if p.suffix.lower() == ".json" else rm.ficha(p)


def medir(p, work):
    ext = p.suffix.lower()
    if ext in IMG:
        im = Image.open(p)
        return {"tipo": "imagen", "ancho": im.width, "alto": im.height, "aspecto": round(im.width / im.height, 3),
                **tono_imagen(im), "paleta": paleta_corta(p), "miniaturas": [str(p)]}
    if ext in VID:
        info = ffprobe(p)
        cs = cortes(p)
        bordes = [0.0] + cs + [info["dur"]]
        planos = [b - a for a, b in zip(bordes, bordes[1:]) if b - a > 0.04]
        mids = [(a + b) / 2 for a, b in zip(bordes, bordes[1:])]
        sel = mids if len(mids) <= 12 else [mids[int(i)] for i in np.linspace(0, len(mids) - 1, 12)]
        thumbs = [fotograma(p, t, work / f"{p.stem}_{i:02d}.jpg") for i, t in enumerate(sel)]
        thumbs = [str(t) for t in thumbs if t]
        if thumbs:
            mos = Image.new("RGB", (480 * len(thumbs), 270))
            for i, t in enumerate(thumbs):
                mos.paste(Image.open(t).convert("RGB").resize((480, 270)), (480 * i, 0))
            mos.save(work / f"{p.stem}_mosaico.png")
        d = {"tipo": "video", "duracion_s": round(info["dur"], 2), "fps": info["fps"], "ancho": info["w"],
             "alto": info["h"], "aspecto": round(info["w"] / info["h"], 3) if info["h"] else None,
             "cortes": len(cs), "cortes_por_min": round(len(cs) / max(info["dur"], 1e-3) * 60, 1),
             "plano_medio_s": round(float(np.mean(planos)), 2) if planos else None,
             "plano_min_s": round(min(planos), 2) if planos else None, "tiempos_corte": cs[:60],
             "paleta": paleta_corta(work / f"{p.stem}_mosaico.png") if thumbs else [],
             **(tono_imagen(Image.open(work / f"{p.stem}_mosaico.png")) if thumbs else {}), "miniaturas": thumbs}
        if info["audio"]:
            d.update(loudness(p), bpm=bpm(p))
        return d
    if ext in AUD:
        info = ffprobe(p)
        return {"tipo": "audio", "duracion_s": round(info["dur"], 2), **loudness(p), "bpm": bpm(p),
                "miniaturas": []}
    if ext in FNT:
        f = ImageFont.truetype(str(p), 40)
        fam, sty = f.getname()
        return {"tipo": "fuente", "familia": fam, "estilo": sty, "miniaturas": []}
    return None


def hoja(items, out):
    filas = [(n, d) for n, d in items if d.get("miniaturas")]
    if not filas:
        return None
    W, th = 1440, 200
    sheet = Image.new("RGB", (W, (th + 70) * len(filas)), (18, 18, 18))
    dr = ImageDraw.Draw(sheet)
    for r, (n, d) in enumerate(filas):
        y = r * (th + 70)
        x = 0
        for t in d["miniaturas"][:8]:
            im = Image.open(t).convert("RGB")
            im = im.resize((max(1, int(im.width * th / im.height)), th))
            if x + im.width > W:
                break
            sheet.paste(im, (x, y))
            x += im.width + 4
        for i, c in enumerate(d.get("paleta", [])):
            dr.rectangle([i * 60, y + th + 6, i * 60 + 56, y + th + 30], fill=c["hex"])
        meta = f"{n} · {d['tipo']}"
        if d["tipo"] == "video":
            meta += f" · {d['duracion_s']} s · plano medio {d['plano_medio_s']} s · {d['cortes_por_min']} cortes/min"
            if d.get("bpm"):
                meta += f" · {d['bpm']} BPM"
        meta += f" · luz {d.get('luz')} · sat {d.get('saturacion')}"
        dr.text((380, y + th + 12), meta, fill=(230, 230, 230))
    sheet.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rutas", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--comparar", nargs=2, metavar=("REF", "FOTO"), help="imágenes o fichas .json")
    ap.add_argument("--json", action="store_true", help="con --comparar: la comparación completa por stdout")
    ap.add_argument("--validar", metavar="RUTA", nargs="+", help="fichas .json o carpetas con fichas: exige la capa 2 "
                    "(filosofía) rellena y con cifras, además del esquema. Sale con 1 si alguna falla")
    a = ap.parse_args()
    if a.validar:
        if rm is None:
            sys.exit("--validar necesita opencv-python")
        rutas = []
        for r in a.validar:
            q = Path(r).expanduser()
            if q.is_dir():
                d = q / "fichas" if (q / "fichas").is_dir() else q
                rutas += sorted(x for x in d.glob("*.json") if x.name not in ("referencias.json", "agregado.json"))
            else:
                rutas.append(q)
        if not rutas:
            sys.exit("--validar: no hay fichas .json en esas rutas")
        mal = 0
        for q in rutas:
            if not q.is_file():
                print(f"{q}: no existe")
                mal += 1
                continue
            err = rm.validar(json.loads(q.read_text()), completa=True)
            mal += bool(err)
            print(f"{q}: " + ("completa" if not err else f"{len(err)} problemas\n  " + "\n  ".join(err[:12])))
        print(f"{len(rutas) - mal}/{len(rutas)} fichas completas" + ("" if not mal else
              " — rellena la capa 2 mirando la imagen y su hoja (references/referencias.md) antes de aprobar la biblia"))
        sys.exit(1 if mal else 0)
    if a.comparar:
        if rm is None:
            sys.exit("--comparar necesita opencv-python")
        c = comparar(_ficha_de(a.comparar[0]), _ficha_de(a.comparar[1]))
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(json.dumps(c, ensure_ascii=False, indent=1))
        if a.json:
            print(json.dumps(c, ensure_ascii=False, indent=1))
            return
        r = c["resumen"]
        print(f"{c['veredicto']}\n  estilo: {r['estilo']['dentro']}/{r['estilo']['total']} dentro de tolerancia "
              f"(similitud {r['estilo']['similitud']})\n  composición: {r['composicion']['dentro']}/"
              f"{r['composicion']['total']} (similitud {r['composicion']['similitud']})")
        col = c["color"]
        if not all(col[k] for k in ("paleta", "tono_principal", "paleta_tonos")):
            print("  color fuera de tolerancia (" + ", ".join(k for k in ("paleta", "tono_principal", "paleta_tonos")
                                                             if not col[k]) + "): sin el color no se reproduce el estilo")
        d = c["derivado"]
        if d and d["es"]:
            print(f"  misma imagen: {d['transformacion']}" + (f", recorte {d['recorte']}" if d["recorte"] else "") +
                  f" (correlación {d['correlacion']})")
        for f in c["ajustar"]:
            print(f"  {f['sentido']} {f['metrica']}: Δ {f['delta']:+} (tolerancia {f['tolerancia']}) — {f['como']}")
        fr = c.get("filosofia_ref")
        if fr:
            for k in ("regla_generadora", "no_copiar", "donde_no"):
                if fr.get(k):
                    print(f"  referencia · {k}: {'; '.join(fr[k]) if isinstance(fr[k], list) else fr[k]}")
        else:
            print(f"  aviso: {c['aviso']}")
        return
    if not a.rutas or not a.out:
        ap.error("faltan RUTA y --out (o usa --comparar REF FOTO)")
    work = Path(a.out)
    (work / "fotogramas").mkdir(parents=True, exist_ok=True)
    archivos = []
    for r in a.rutas:
        p = Path(r).expanduser()
        archivos += sorted(q for q in p.rglob("*") if q.is_file()) if p.is_dir() else [p]
    items, fichas, pendientes = [], {}, []
    for p in archivos:
        if not p.exists():
            print(f"{p}: no existe", file=sys.stderr)
            continue
        try:
            d = medir(p, work / "fotogramas")
        except Exception as e:  # una referencia rota no para las demás
            d = {"tipo": "error", "error": str(e), "miniaturas": []}
        if d:
            nombre = p.name if p.name not in {n for n, _ in items} else str(p)   # dos «ref.mp4» no se pisan
            if d["tipo"] == "imagen":
                try:
                    f, extra = ficha_imagen(p, work / "fichas", Path(nombre.replace("/", "_")).stem)
                    d.update(extra)
                    if f:
                        fichas[nombre] = f
                        if extra.get("capa2_pendiente"):
                            pendientes.append(nombre)
                except Exception as e:  # la ficha es un añadido: si falla, queda la medida básica
                    d["ficha_error"] = str(e)
            items.append((nombre, d))
            print(f"{nombre}: {d['tipo']}")
    if len(fichas) >= 2:
        (work / "agregado.json").write_text(json.dumps(agregar(fichas), ensure_ascii=False, indent=1))
        print(work / "agregado.json")
    (work / "referencias.json").write_text(json.dumps({n: d for n, d in items}, ensure_ascii=False, indent=1))
    print(work / "referencias.json", hoja(items, work / "referencias.png") or "(sin miniaturas)")
    if pendientes:
        print(f"capa 2 (filosofía) sin rellenar en {len(pendientes)} ficha(s): {', '.join(pendientes)}. Rellénala en "
              f"{work / 'fichas'} y comprueba con: referencias.py --validar {work}")


if __name__ == "__main__":
    main()
