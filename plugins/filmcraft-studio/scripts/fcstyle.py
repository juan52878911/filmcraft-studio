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

    def text(self, role, text, start, dur, pos, variante=0, colores=None, anim=None, tam=None, pista=None, align=None):
        """Crea un texto con el estilo del rol. pos = (cx, cy) normalizado (centro; borde izquierdo si align Left)."""
        r = self.role(role)
        f = self.ds["fuentes"][r["fuente"]]
        trk = pista or self._pick(r.get("pistas") or r["pista"], variante)
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
        self.e.x("graphics.set", {"clip": clip, "layer": layer, "props": props})
        cx, cy = pos[0] * self.W, pos[1] * self.H
        L, (w, h) = self.e.center_layer(clip, layer, cx, cy, al)
        x0 = cx if al == "Left" else cx - w / 2
        box = [(x0 - m) / self.W, (cy - h / 2 - m) / self.H, (x0 + w + m) / self.W, (cy + h / 2 + m) / self.H]
        a = anim or r.get("anim", "ninguna")
        if a == "popIn":
            self.pop_in(clip, L["effectIndex"], start)
        return {"clip": clip, "layer": layer, "box": [round(b, 4) for b in box], "rol": role, "texto": text,
                "start": start, "dur": dur, "pista": trk}

    def pop_in(self, clip, eff, start):
        p = self.ds["animaciones"]["popIn"]
        self.e.kf(clip, eff, "scale", [(self.bf(f), v, "linear") for f, v in p["escala"]], start)
        self.e.kf(clip, eff, "opacity", [(self.bf(f), v, "linear") for f, v in p["opacidad"]], start)

    def size_of(self, role, text, tam=None):
        return measure(self.ds, role, text, tam)

    def wrap(self, text, max_chars):
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

    def title(self, text, start, dur, role="titulo", lines=None, pista=None):
        """Aparición por palabras: una capa por palabra en un solo gráfico, alineado a la izquierda."""
        r = self.role(role)
        f = self.ds["fuentes"][r["fuente"]]
        wr = self.ds["animaciones"]["wordReveal"]
        lines = lines or (text.split("\n") if "\n" in text else self.wrap(text, r.get("max_chars", 12)))
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
