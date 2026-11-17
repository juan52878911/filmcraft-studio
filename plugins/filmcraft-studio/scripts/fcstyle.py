"""Textos del design system en FilmCraft: roles, colores, centrado y animaciones.

    st = Styler(engine, ds)
    st.text("etiqueta", "SAGEMAKER", start=12.27, dur=0.86, pos=(0.40, 0.20), variante=0)
    st.title("SESIÓN 5: IA Y MACHINE LEARNING EN AWS", start=6.3, dur=2.5)
    st.eco("100 USD", start=2.13, pos=(0.32, 0.20))

Las animaciones del DS están en fotogramas a `animaciones.base_fps`; aquí se pasan a segundos y se
redondean a fotogramas de la secuencia (e.snap), así funcionan igual a 30, 59,94 o 60 fps.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import color  # noqa: E402
import pegatina  # noqa: E402


def measure(ds, role, text, tam=None):
    """Tamaño normalizado (ancho, alto) de un bloque de texto con su margen, medido con PIL y la fuente del DS."""
    from common import pil_font
    from PIL import Image, ImageDraw
    r = ds["roles_texto"][role]
    f = pil_font(ds["fuentes"][r["fuente"]], tam or r["tam"])
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    lines = text.split("\n")
    w = max(d.textlength(ln, font=f) for ln in lines)
    asc, desc = f.getmetrics()
    h = (asc + desc) * len(lines) * 1.02
    m = r.get("margen", 0) if (r.get("fondo") or r.get("colores")) else 0
    return (w + 2 * m) / ds["lienzo"]["ancho"], (h + 2 * m) / ds["lienzo"]["alto"]


def wrap(text, max_chars):
    """Parte un texto en líneas de como mucho max_chars (sin partir palabras)."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


class Styler:
    def __init__(self, engine, ds):
        self.e = engine
        self.ds = ds
        self.W = ds["lienzo"]["ancho"]
        self.H = ds["lienzo"]["alto"]
        self.base = ds.get("animaciones", {}).get("base_fps", 60)

    def bf(self, frames):
        """Fotogramas del DS (a base_fps) -> segundos redondeados a la secuencia."""
        return self.e.snap(frames / self.base)

    def role(self, name):
        return self.ds["roles_texto"][name]

    def _pick(self, v, i):
        if isinstance(v, list):
            return v[i % len(v)]
        return v

    def text(self, role, text, start, dur, pos, variante=0, colores=None, anim=None, tam=None, pista=None, align=None,
             resaltar=None):
        """Crea un texto con el estilo del rol. pos = (cx, cy) normalizado (centro; borde izquierdo si align Left).

        pegatina@1: el rol puede llevar `inclina` (grados, o lista por variante), `sombra` dura
        {color, dist, angulo}, `contorno` {color, ancho}, `prefijo` {texto, color} y una animación de
        pegatina.ANIMS; `resaltar` = [[inicio, fin), …] en caracteres se pinta con el color `resalta` del rol.
        """
        r = self.role(role)
        f = self.ds["fuentes"][r["fuente"]]
        trk = pista or self._pick(r.get("pistas") or r["pista"], variante)
        pre = r.get("prefijo") or {}
        if pre.get("texto") and not text.startswith(pre["texto"].strip()):
            text = pre["texto"] + text
            resaltar = [[a + len(pre["texto"]), b + len(pre["texto"])] for a, b in (resaltar or [])]
        g = self.e.new_text(text, trk, start, dur, f["familia"], f.get("estilo", "Regular"), tam or r["tam"])
        clip, layer = g["clip"], g["layer"]
        tc, bc = colores or (r.get("color", "claro"), self._pick(r.get("fondo"), variante))
        al = align or r.get("align", "Center")
        props = {"align": al, "fill_color": color(self.ds, tc), "shadow": False}
        m = 0
        if bc:
            m = r.get("margen", 40)
            props.update(background=True, background_color=color(self.ds, bc), background_opacity=100,
                         background_size=m, background_radius=0)
        if r.get("sombra"):
            sb = r["sombra"]
            props.update(shadow=True, shadow_color=color(self.ds, sb.get("color", "oscuro")), shadow_opacity=100,
                         shadow_blur=sb.get("blur", 0), shadow_distance=sb.get("dist", 6), shadow_angle=sb.get("angulo", 135),
                         shadow_size=sb.get("tam", 0))
        if r.get("contorno"):
            cn = r["contorno"]
            props.update(stroke=True, stroke_color=color(self.ds, cn.get("color", "oscuro")), stroke_width=cn.get("ancho", 3))
        if r.get("pista_letras"):
            props["tracking"] = r["pista_letras"]
        rot = float(self._pick(r.get("inclina", 0), variante) or 0)
        if rot:
            props["rotation"] = rot
        self.e.x("graphics.set", {"clip": clip, "layer": layer, "props": props})
        if pre.get("texto") and pre.get("color"):
            self.e.x("graphics.setCharStyle", {"clip": clip, "layer": layer, "start": 0, "end": len(pre["texto"].rstrip()),
                                               "style": {"color": color(self.ds, pre["color"])}})
        if resaltar and r.get("resalta"):
            for a, b in resaltar:
                self.e.x("graphics.setCharStyle", {"clip": clip, "layer": layer, "start": a, "end": b,
                                                   "style": {"color": color(self.ds, r["resalta"])}})
        cx, cy = pos[0] * self.W, pos[1] * self.H
        L, (w, h) = self.e.center_layer(clip, layer, cx, cy, al)
        x0 = cx if al == "Left" else cx - w / 2
        box = [(x0 - m) / self.W, (cy - h / 2 - m) / self.H, (x0 + w + m) / self.W, (cy + h / 2 + m) / self.H]
        a = anim or r.get("anim", "ninguna")
        if a == "popIn":
            self.pop_in(clip, L["effectIndex"], start)
        elif a == "calorEntra":
            self.calor_entra(clip, L["effectIndex"], start)
        elif pegatina.es_pegatina(a):
            eff = L["effectIndex"]
            if a == "escribe":
                eff = self.escribe(clip, layer, start, text, len(pre.get("texto", "")), r, x0 - m, x0 + w + m)
            desde = -1 if (al != "Left" and cx > self.W * 0.55) else 1
            self.animar(clip, eff, eff, start, dur, a, [cx, cy], rot, desde=desde)
        return {"clip": clip, "layer": layer, "box": [round(b, 4) for b in box], "rol": role, "texto": text,
                "start": start, "dur": dur, "pista": trk}

    def animar(self, clip, eff, eff_op, start, dur, anim, pos, rot=0.0, escala=100.0, desde=1):
        """Entrada pegatina (golpe, desliza, caída, pop, escribe) y salida en fundido, sobre un efecto del clip.

        En un texto, `eff` y `eff_op` son el índice de su capa (graphic_text tiene escala, giro, posición y
        opacidad); en una imagen, "motion" y "opacity". pos en píxeles del lienzo.
        """
        rows = pegatina.keyframes(self.ds, anim, dur, pos, rot, escala, desde, bf=self.bf)
        for p, rr in rows.items():
            self.e.kf(clip, eff_op if p == "opacity" else eff, p, rr, start)

    def escribe(self, clip, layer, start, text, n_pre, r, x_ini, x_fin):
        """Kicker que se escribe: un Crop por la derecha que descubre la caja y el texto carácter a carácter."""
        from common import pil_font
        f = pil_font(self.ds["fuentes"][r["fuente"]], r["tam"])
        x_pre = x_ini + (f.getlength(text[:n_pre]) + r.get("margen", 0) if n_pre else 0)
        t = self.e.snap(pegatina.escritura(self.ds, max(1, len(text) - n_pre)))
        self.e.x("effects.apply", {"clips": [clip], "effect": "crop"})
        der = lambda x: round(max(0.0, min(100.0, 100 * (1 - x / self.W))), 3)   # noqa: E731
        self.e.kf(clip, "crop", "right", [(0, der(x_pre), "linear"), (t, der(x_fin + 2), "linear")], start)
        # el Crop entra delante en la pila: el índice de la capa de texto cambia
        return [l for l in self.e.layers(clip) if l["layer"] == layer][0]["effectIndex"]

    def pop_in(self, clip, eff, start):
        p = self.ds["animaciones"]["popIn"]
        self.e.kf(clip, eff, "scale", [(self.bf(f), v, "linear") for f, v in p["escala"]], start)
        self.e.kf(clip, eff, "opacity", [(self.bf(f), v, "linear") for f, v in p["opacidad"]], start)

    def calor_entra(self, clip, eff, start):
        """termo@1: el texto llega desenfocado y se enfoca (Gaussian Blur con keyframes) mientras aparece."""
        p = self.ds["animaciones"]["calorEntra"]
        self.e.x("effects.apply", {"clips": [clip], "effect": "gaussian_blur"})
        fx = self.e.clip(clip).get("effects", [])
        gi = max(i for i, f in enumerate(fx) if "gaussian" in str(f.get("id") or f.get("effect") or f.get("name")).lower())
        self.e.kf(clip, gi, "blurriness", [(self.bf(f), v, "linear") for f, v in p["desenfoque"]], start)
        self.e.kf(clip, eff, "opacity", [(self.bf(f), v, "linear") for f, v in p["opacidad"]], start)
        self.e.kf(clip, eff, "scale", [(self.bf(f), v, "linear") for f, v in p["escala"]], start)

    def wrap(self, text, max_chars):
        """Compatibilidad: Styler.wrap(None, …) sigue funcionando; usa la función de módulo wrap()."""
        return wrap(text, max_chars)

    def title(self, text, start, dur, role="titulo", lines=None, pista=None):
        """Aparición por palabras: una capa por palabra en un solo gráfico, alineado a la izquierda."""
        r = self.role(role)
        f = self.ds["fuentes"][r["fuente"]]
        lines = lines or (text.split("\n") if "\n" in text else self.wrap(text, r.get("max_chars", 12)))
        if pegatina.es_pegatina(r.get("anim")):
            # pegatina@1: el titular es UNA pegatina (caja, sombra dura, inclinación) que entra de golpe
            txt = "\n".join(lines)
            from common import pil_font
            tam, m = r["tam"], r.get("margen", 0) if r.get("fondo") else 0
            avail = self.W * (1 - r["x"] - 0.05) - 2 * m         # cabe con la caja, la sombra y el giro
            widest = max(pil_font(f, tam).getlength(ln) for ln in lines)
            if widest > avail:
                tam = round(tam * avail / widest, 1)
            _, h = measure(self.ds, role, txt, tam)
            out = self.text(role, txt, start, dur, (r["x"], r["y"] + h / 2), align="Left", pista=pista, tam=tam)
            out["palabras"] = len(txt.split())
            return out
        wr = self.ds["animaciones"]["wordReveal"]
        x0, y0 = r["x"] * self.W, r["y"] * self.H
        # tamaño que cabe en el ancho (fuentes proporcionales anchas) y avance real de cada palabra
        from common import pil_font
        tam = r["tam"]
        pf = pil_font(f, tam)
        widest = max(pf.getlength(ln) for ln in lines)
        avail = self.W - 2 * x0
        if widest > avail:
            tam = round(tam * avail / widest, 1)
            pf = pil_font(f, tam)
        sp = pf.getlength(" ")
        lh = tam * r.get("interlinea", 1.25)
        gid, k, out, maxw = None, 0, [], 0
        for i, line in enumerate(lines):
            x = x0
            for w in [w for w in line.split(" ") if w]:
                g = self.e.new_text(w, pista or r["pista"], start, dur, f["familia"], f.get("estilo", "Regular"), tam, clip=gid)
                gid, layer = g["clip"], g["layer"]
                self.e.x("graphics.set", {"clip": gid, "layer": layer,
                                          "props": {"align": "Left", "fill_color": color(self.ds, r["color"]), "shadow": False}})
                L = [l for l in self.e.layers(gid) if l["layer"] == layer][0]
                bx0, by0, bx1, _ = L["localBounds"]
                target = [x, y0 + i * lh]
                self.e.x("graphics.set", {"clip": gid, "layer": layer, "props": {"anchor": [bx0, by0], "position": target}})
                t0 = self.bf(k * wr["paso_f"])
                self.e.kf(gid, L["effectIndex"], "opacity", [(t0, 0, "linear"), (t0 + self.bf(wr["fade_f"]), 100, "linear")], start)
                self.e.kf(gid, L["effectIndex"], "position",
                          [(t0, [target[0], target[1] + wr["dy"]], "linear"), (t0 + self.bf(wr["fade_f"] + 2), target, "linear")], start)
                out.append(w)
                k += 1
                x += (bx1 - bx0) + sp
                maxw = max(maxw, x - sp - x0)
        box = [x0 / self.W, y0 / self.H, min(1, (x0 + maxw) / self.W), (y0 + lh * len(lines)) / self.H]
        return {"clip": gid, "box": [round(b, 4) for b in box], "rol": role, "texto": " / ".join(lines), "start": start,
                "dur": dur, "palabras": len(out)}

    def eco(self, text, start, pos, role="eco", n=None, pista=None):
        """Palabra ×3 en posiciones escalonadas, 8 f cada una (a base_fps), colores alternos."""
        r = self.role(role)
        n = n or len(r["colores"])
        fd = self.bf(r.get("frames", 8))
        gap = self.bf(2)
        out = []
        for i in range(n):
            tc, bc = r["colores"][i % len(r["colores"])]
            out.append(self.text(role, text, start + i * (fd + gap), fd, (pos[0], pos[1] + i * r.get("paso_y", 0.125)),
                                 colores=(tc, bc), anim="ninguna", pista=pista))
        return out
