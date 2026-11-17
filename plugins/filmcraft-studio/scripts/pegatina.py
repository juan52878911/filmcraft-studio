"""Gramática pegatina@1: rótulos como pegatinas sobre un presentador a cámara.

Medida sobre un reel vertical a 30 fps (ver skills/design-system-video/references/pegatina.md):
- cajas planas de esquinas vivas, inclinadas −2 a −3°, con sombra dura desplazada del color contrario;
- entradas medidas por fotograma: golpe (titular), desliza con rebote (tarjetas), caída (pills),
  pop (elementos pequeños) y escribe (kickers, 1,3-1,7 caracteres por fotograma); salida en fundido de 3-4 f;
- subtítulos de 1-3 palabras con la palabra clave (nombre propio, cifra o sustantivo del beneficio) resaltada;
- tarjetas compuestas (ponente, fecha, QR, logo, flecha) dibujadas a la escala del lienzo y animadas como capa.

Aquí está todo lo que no depende de FilmCraft: curvas → keyframes, elección de palabras clave y el dibujo de las
tarjetas. fcstyle.Styler y apply_plan lo aplican al motor.
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FUNCIONALES, color, norm, pil_font  # noqa: E402

ANIMS = ("golpe", "desliza", "caida", "pop", "escribe")
BASE_W = 720            # las medidas de la gramática se tomaron a 720 px de ancho


def es_pegatina(anim):
    return anim in ANIMS


# ---------- curvas → keyframes ----------
def keyframes(ds, anim, dur, pos, rot=0.0, escala=100.0, desde=1, bf=None):
    """Keyframes (segundos desde el inicio del clip) de una entrada pegatina más la salida en fundido.

    pos = posición en reposo en píxeles del lienzo; rot = inclinación en reposo; escala = escala en reposo;
    desde = +1 entra por la izquierda, −1 por la derecha (solo «desliza»). bf convierte fotogramas del DS
    (a animaciones.base_fps) en segundos de la secuencia. Devuelve {param: [(t, valor, interp), …]} con
    las claves scale, rotation, position y opacity (las que la curva usa).
    """
    an = ds.get("animaciones", {})
    base = an.get("base_fps", 30)
    bf = bf or (lambda f: f / base)
    W = ds["lienzo"]["ancho"]
    p = an.get(anim) or {}
    out = {}
    fin = 0.0
    if p.get("escala"):
        out["scale"] = [(bf(f), round(escala * v / 100, 3), "linear") for f, v in p["escala"]]
    if p.get("giro"):
        out["rotation"] = [(bf(f), round(rot + v, 3), "linear") for f, v in p["giro"]]
    if p.get("dx"):          # fracción del ancho del lienzo; positivo = pasado del sitio en el sentido de entrada
        out["position"] = [(bf(f), [round(pos[0] + desde * v * W, 2), pos[1]], "linear") for f, v in p["dx"]]
    elif p.get("dy"):
        out["position"] = [(bf(f), [pos[0], round(pos[1] + v * ds["lienzo"]["alto"], 2)], "linear") for f, v in p["dy"]]
    for rows in out.values():
        fin = max(fin, rows[-1][0])
    op = [(bf(f), v, "linear") for f, v in (p.get("opacidad") or [[0, 100]])]
    fin = max(fin, op[-1][0])
    sal = an.get("salida", {}).get("f")
    if sal:
        ts = dur - bf(sal)
        if ts > fin + 1e-6:
            if op[-1][1] != 100:
                op.append((op[-1][0], 100, "linear"))
            op += [(ts, 100, "linear"), (dur, 0, "linear")]
    if len(op) > 1 or op[0][1] != 100:
        out["opacity"] = _sin_repetidos(op)
    return {k: _sin_repetidos(v) for k, v in out.items()}


def _sin_repetidos(rows):
    """FilmCraft no admite dos keyframes en el mismo instante: el último gana."""
    out = []
    for r in rows:
        if out and abs(out[-1][0] - r[0]) < 1e-6:
            out[-1] = r
        else:
            out.append(r)
    return out


def escritura(ds, n_chars):
    """Segundos que tarda en escribirse un kicker de n_chars (a escribe.cps_f caracteres por fotograma del DS)."""
    an = ds.get("animaciones", {})
    cps = (an.get("escribe") or {}).get("cps_f", 1.5)
    return math.ceil(n_chars / cps) / an.get("base_fps", 30)


# ---------- palabras clave de los subtítulos ----------
NUM = re.compile(r"\d")


def palabras_clave(palabras, inicio_frase, extra=(), maximo=2):
    """Índices de las palabras a resaltar en un golpe de subtítulo.

    palabras = textos del golpe; inicio_frase[i] = True si la palabra i abre frase (su mayúscula no cuenta).
    Prioridad: las que pide el plan (`extra`, comparadas sin puntuación), cifras y nombres propios
    (mayúscula a mitad de frase). Nunca palabras funcionales. Como mucho `maximo`.
    """
    extra = {norm(x) for x in extra}
    cand = []
    for i, w in enumerate(palabras):
        n = norm(w)
        if not n or n in FUNCIONALES:
            continue
        limpio = re.sub(r"^[¿¡\"'«(]+", "", w)
        if n in extra:
            cand.append((0, i))
        elif NUM.search(w):
            cand.append((1, i))
        elif limpio[:1].isupper() and not inicio_frase[i]:
            cand.append((2, i))
    return sorted(i for _, i in sorted(cand)[:maximo])


def rangos(palabras, indices):
    """Rangos [inicio, fin) en caracteres del texto ' '.join(palabras), sin la puntuación de los bordes."""
    out, pos = [], 0
    for i, w in enumerate(palabras):
        if i in indices:
            m = re.match(r"^([¿¡\"'«(]*)(.*?)([.,;:?!»\")]*)$", w)
            a = pos + len(m.group(1))
            b = pos + len(w) - len(m.group(3))
            if b > a:
                out.append([a, b])
        pos += len(w) + 1
    return out


# ---------- tarjetas compuestas (PIL, a la escala del lienzo) ----------
def _k(ds):
    return ds["lienzo"]["ancho"] / BASE_W


def _fuente(ds, nombre, tam):
    return pil_font(ds["fuentes"][nombre], max(6, round(tam)))


def _lienzo(w, h):
    from PIL import Image
    return Image.new("RGBA", (int(math.ceil(w)), int(math.ceil(h))), (0, 0, 0, 0))


def _caja(d, x0, y0, x1, y1, fill, sombra=None, dist=0):
    if sombra:
        d.rectangle([x0 + dist, y0 + dist, x1 + dist, y1 + dist], fill=sombra)
    d.rectangle([x0, y0, x1, y1], fill=fill)


def _imagen(path, w, h, cubrir=True):
    from PIL import Image, ImageOps
    im = Image.open(path).convert("RGBA")
    return ImageOps.fit(im, (int(w), int(h))) if cubrir else ImageOps.contain(im, (int(w), int(h)))


def _texto(d, xy, txt, font, fill, tracking=0.0):
    """Texto con tracking (em) dibujado letra a letra si hace falta."""
    if not tracking:
        d.text(xy, txt, font=font, fill=fill)
        return d.textlength(txt, font=font)
    x, y = xy
    em = font.size * tracking
    for ch in txt:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + em
    return x - xy[0] - em


def _ancho(d, txt, font, tracking=0.0):
    return d.textlength(txt, font=font) + (max(0, len(txt) - 1) * font.size * tracking if tracking else 0)


def tarjeta(ds, spec, out):
    """Dibuja la tarjeta `spec` (dict con «tipo») en un PNG con transparencia y devuelve (ruta, ancho, alto).

    Tipos: ponente {foto, nombre, cargo}, fecha {dia, num, mes, hora}, qr {img, texto, url},
    logo {img, fondo}, flecha {sentido: der|izq}. Colores de la paleta del DS; medidas a 720 px escaladas al lienzo.
    """
    from PIL import ImageDraw
    k = _k(ds)
    c = lambda ref: color(ds, ref)                         # noqa: E731
    oscuro, claro, ac1 = c("oscuro"), c("claro"), c("acento1")
    ac2 = c("acento2") if "acento2" in ds["paleta"] else claro
    gris = ds["paleta"].get("gris", "#C9D0D8")
    s = round(8 * k)                                       # sombra dura
    tipo = spec["tipo"]
    if tipo == "ponente":
        fw, fh, marco = 197 * k, 180 * k, round(4 * k)
        fn, fc = _fuente(ds, "ui", 30 * k), _fuente(ds, "meta", 17 * k)
        tmp = ImageDraw.Draw(_lienzo(8, 8))
        nombre, cargo = spec.get("nombre", ""), spec.get("cargo", "")
        pw = max(fw, _ancho(tmp, nombre, fn) + 36 * k, _ancho(tmp, cargo, fc, 0.08) + 36 * k)
        ph = 92 * k if cargo else 58 * k
        W, H = pw + s, fh + 2 * marco + 10 * k + ph + s
        im = _lienzo(W, H)
        d = ImageDraw.Draw(im)
        fx = (pw - fw) / 2
        _caja(d, fx, 0, fx + fw + 2 * marco, fh + 2 * marco, claro, ac1, s)
        if spec.get("foto"):
            im.alpha_composite(_imagen(spec["foto"], fw, fh), (int(fx + marco), marco))
        y = fh + 2 * marco + 10 * k
        _caja(d, 0, y, pw, y + ph, oscuro, ac1, round(5 * k))
        d.text((18 * k, y + 12 * k), nombre, font=fn, fill=claro)
        if cargo:
            _texto(d, (18 * k, y + 56 * k), cargo, fc, ac2, 0.08)
    elif tipo == "fecha":
        fn, fs, fh = _fuente(ds, "titular", 76 * k), _fuente(ds, "meta", 24 * k), _fuente(ds, "titular", 40 * k)
        tmp = ImageDraw.Draw(_lienzo(8, 8))
        num = str(spec.get("num", ""))
        cw = max(127 * k, _ancho(tmp, num, fn) + 30 * k)
        linea = " · ".join(x for x in (spec.get("dia", ""), spec.get("mes", "")) if x)
        hora = spec.get("hora", "")
        bw = max(_ancho(tmp, linea, fs, 0.14), _ancho(tmp, hora, fh)) + 48 * k
        W, H = cw + bw + s, 146 * k + s
        im = _lienzo(W, H)
        d = ImageDraw.Draw(im)
        _caja(d, 0, 0, cw + bw, 146 * k, oscuro, ac1, s)
        d.rectangle([0, 0, cw, 146 * k], fill=ac1)
        nw = _ancho(d, num, fn)
        a, b = fn.getmetrics()
        d.text(((cw - nw) / 2, (146 * k - a - b) / 2), num, font=fn, fill=oscuro)
        _texto(d, (cw + 24 * k, 28 * k), linea, fs, gris, 0.14)
        d.text((cw + 24 * k, 68 * k), hora, font=fh, fill=ac2)
    elif tipo == "qr":
        q = 204 * k
        ft, fu = _fuente(ds, "titular", 34 * k), _fuente(ds, "meta", 18 * k)
        lineas = (spec.get("texto") or "ESCANEA Y\nREGÍSTRATE").split("\n")
        tmp = ImageDraw.Draw(_lienzo(8, 8))
        tw = max([_ancho(tmp, ln, ft) for ln in lineas] + [_ancho(tmp, spec.get("url", ""), fu)])
        W, H = q + 26 * k + tw + 44 * k + s, max(240 * k, q + 30 * k) + s
        im = _lienzo(W, H)
        d = ImageDraw.Draw(im)
        _caja(d, 0, 0, W - s, H - s, oscuro, ac1, s)
        d.rectangle([13 * k, 15 * k, 13 * k + q, 15 * k + q], fill=claro)
        if spec.get("img"):
            im.alpha_composite(_imagen(spec["img"], q - 12 * k, q - 12 * k, cubrir=False), (int(19 * k), int(21 * k)))
        y = 50 * k
        for ln in lineas:
            d.text((q + 39 * k, y), ln, font=ft, fill=claro)
            y += ft.size * 1.15
        if spec.get("url"):
            d.text((q + 39 * k, y + 14 * k), spec["url"], font=fu, fill=ac2)
    elif tipo == "logo":
        lw, lh = spec.get("tam", [211, 99])
        lw, lh = lw * k, lh * k
        fondo = c(spec.get("fondo", "claro"))
        sombra = oscuro if fondo == claro else ac1
        W, H = lw + s, lh + s
        im = _lienzo(W, H)
        d = ImageDraw.Draw(im)
        _caja(d, 0, 0, lw, lh, fondo, sombra, s)
        if spec.get("img"):
            lg = _imagen(spec["img"], lw - 36 * k, lh - 28 * k, cubrir=False)
            im.alpha_composite(lg, (int((lw - lg.width) / 2), int((lh - lg.height) / 2)))
    elif tipo == "flecha":
        W, H = 130 * k, 130 * k
        im = _lienzo(W, H)
        d = ImageDraw.Draw(im)
        p0, p1, p2 = (10 * k, 10 * k), (110 * k, 15 * k), (105 * k, 115 * k)
        pts = [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / 30 for i in range(31)]]
        d.line(pts, fill=ac1, width=round(8 * k), joint="curve")
        tip = pts[-1]
        d.polygon([(tip[0] - 18 * k, tip[1] - 22 * k), (tip[0] + 18 * k, tip[1] - 22 * k), (tip[0], tip[1] + 6 * k)], fill=ac1)
        if spec.get("sentido") == "izq":
            from PIL import ImageOps
            im = ImageOps.mirror(im)
    else:
        raise ValueError(f"tarjeta de tipo '{tipo}' desconocida (ponente, fecha, qr, logo, flecha)")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return str(out), im.width, im.height
