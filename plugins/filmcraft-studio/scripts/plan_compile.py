#!/usr/bin/env python3
"""Compila plan.json (EDL de intención, en segundos de la fuente y por roles) a compiled.json.

Uso: plan_compile.py PLAN.json --analisis WORK/analisis [--brief WORK/brief.json] [--out WORK/compiled.json]

Determinista. Hace lo que no debe decidir un modelo a ojo:
- ajusta cada borde de plano a un límite de palabra (reglas duras), con margen según el ritmo del DS;
- calcula posiciones en la secuencia redondeadas a fotogramas de los fps del DS;
- ancla textos a palabras de la transcripción ("palabra") o a un desfase del bloque ("t");
- coloca pop-ups en zonas libres (caras y personas de la toma durante toda la duración del texto);
- genera subtítulos (≤ max_chars), barra de marca, SFX ligados a eventos, base musical con ducking,
  transiciones y grade desde el DS; comprueba que los obligatorios del brief quedan cubiertos.

Formato de plan.json: ver skills/montaje-headless/references/plan.md.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import jload, jsave, load_ds  # noqa: E402
from fcstyle import measure  # noqa: E402
from freezones import best_spot, occupancy  # noqa: E402

FUNCIONALES = {"que", "nos", "de", "del", "la", "el", "los", "las", "y", "o", "a", "en", "por", "para", "con", "un",
               "una", "se", "le", "les", "lo", "al", "es", "si", "no", "mi", "tu", "su", "pero", "como"}
POP_ROLES = {"etiqueta", "concepto", "escalon", "eco", "nombre"}
SIN_MARCA = {"tarjeta", "titulo", "cierre"}


def norm(w):
    return re.sub(r"[^\wáéíóúñü]", "", w.lower())


class Compiler:
    def __init__(self, plan, ds, analisis, brief=None):
        self.plan, self.ds, self.an = plan, ds, Path(analisis)
        self.brief = brief or {}
        self.fps = plan.get("fps") or ds["lienzo"]["fps"]
        self.mat = jload(self.an / "material.json")
        self.vid = {v["stem"]: v for v in self.mat["videos"]}
        self._words, self._vis, self._dur = {}, {}, {}
        self.avisos, self.ajustes = [], []
        mc = ds.get("ritmo", {}).get("margen_corte_ms", [30, 200])
        self.margin = (mc[0] + (mc[1] - mc[0]) * (0.25 if ds.get("ritmo", {}).get("energia") == "alta" else 0.6)) / 1000
        self.corr = {norm(k): v for k, v in plan.get("correcciones", {}).items()}
        self.base = ds.get("animaciones", {}).get("base_fps", 60)

    # ---------- utilidades ----------
    def snap(self, t):
        return round(round(t * self.fps) / self.fps, 6)

    def bf(self, f):
        return self.snap(f / self.base)

    def stem(self, src):
        s = Path(src).stem
        if s in self.vid:
            return s
        if s + "_voz" in self.vid:
            return s + "_voz"
        raise KeyError(f"no hay análisis de '{src}'")

    def words(self, stem):
        if stem not in self._words:
            p = self.an / f"{stem}.palabras.json"
            self._words[stem] = jload(p) if p.exists() else []
        return self._words[stem]

    def vision(self, stem):
        if stem not in self._vis:
            p = self.an / f"{stem}.vision.json"
            self._vis[stem] = jload(p)["data"] if p.exists() else []
        return self._vis[stem]

    def sfx_dur(self, path):
        if path not in self._dur:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                               capture_output=True, text=True)
            self._dur[path] = float(r.stdout.strip() or 0.5)
        return self._dur[path]

    def snap_cut(self, stem, t, kind):
        """Borde de plano fuera de cualquier palabra. kind = 'in' | 'out'."""
        ws = self.words(stem)
        for i, w in enumerate(ws):
            if w["s"] + 0.01 < t < w["e"] - 0.01:
                prev_e = ws[i - 1]["e"] if i else w["s"] - 1
                next_s = ws[i + 1]["s"] if i + 1 < len(ws) else w["e"] + 1
                mid = (w["s"] + w["e"]) / 2
                before = w["s"] - min(self.margin, max(0, (w["s"] - prev_e) / 2))
                after = w["e"] + min(self.margin, max(0, (next_s - w["e"]) / 2))
                if kind == "in":
                    nt = before if t < mid else after
                else:
                    nt = after if t > mid else before
                self.ajustes.append({"src": stem, kind: t, "a": round(nt, 3), "palabra": w["w"]})
                return round(nt, 3)
        return t

    def find_word(self, stem, palabra, t0, t1):
        """Primera aparición de `palabra` (1–3 palabras) dentro de [t0, t1] de la fuente."""
        ws = self.words(stem)
        q = [norm(x) for x in palabra.split()]
        for i, w in enumerate(ws):
            if w["s"] < t0 - 0.05 or w["s"] > t1:
                continue
            if [norm(x["w"]) for x in ws[i:i + len(q)]] == q:
                return w["s"], ws[i + len(q) - 1]["e"]
        return None

    # ---------- compilar ----------
    def compile(self):
        ds, plan = self.ds, self.plan
        segs, texts, sfx, trans, caps, capas = [], [], [], [], [], []
        T = 0.0
        blocks_out = []
        lado = None
        for bi, b in enumerate(plan["bloques"]):
            bid = b.get("id") or f"b{bi + 1}"
            tipo = b.get("tipo", "contenido")
            Tb = T
            bsegs = []
            if b.get("planos"):
                prev = None
                for pi, p in enumerate(b["planos"]):
                    stem = self.stem(p["src"])
                    info = self.vid[stem]
                    a = self.snap_cut(stem, float(p["in"]), "in")
                    z = self.snap_cut(stem, float(p["out"]), "out")
                    z = min(z, info["dur"] - 0.02)
                    sp = float(p.get("speed", 1))
                    dur = self.snap((z - a) / sp)
                    if dur <= 0:
                        self.avisos.append(f"{bid}.p{pi + 1}: duración nula, lo salto")
                        continue
                    ent = p.get("entrada")
                    if ent is None:
                        if pi == 0:
                            ent = (b.get("transicion") or ("corte" if bi == 0 else "entrada"))
                        elif prev and prev["stem"] == stem and a >= prev["out"] - 0.1:
                            ent = "jump"
                        else:
                            ent = "entrada"
                    punch = p.get("punch")
                    if punch is None:
                        punch = (112 if (prev and prev.get("punch", 100) == 100) else 100) if ent == "jump" else 100
                    s = {"id": f"{bid}.p{pi + 1}", "bloque": bid, "tipo": "video", "path": info["path"], "stem": stem,
                         "start": self.snap(T), "dur": dur, "in": a, "out": round(a + dur * sp, 4), "speed": sp,
                         "mute": bool(p.get("mute", sp != 1)), "punch": punch, "zoom": p.get("zoom"),
                         "entrada": ent, "nota": p.get("nota", "")}
                    bsegs.append(s)
                    prev = s
                    T = s["start"] + dur
            elif tipo == "fotos":
                fd = self.bf(b.get("f", ds["estructura"].get("foto_f", 20)))
                for fi, f in enumerate(b["fotos"][:ds["estructura"].get("fotos_max", 8)]):
                    s = {"id": f"{bid}.f{fi + 1}", "bloque": bid, "tipo": "foto", "path": f, "start": self.snap(T), "dur": fd,
                         "entrada": "flash" if fi else (b.get("transicion") or "flash")}
                    bsegs.append(s)
                    T += fd
                    sfx.append(self.ev("foto", s["start"], bid))
            else:                                                     # tarjeta / cierre
                d = self.snap(b.get("dur", ds["estructura"].get("cierre_s" if tipo == "cierre" else "titulo_s", 2.5)))
                fondo = b.get("fondo") or ("cierre" if tipo == "cierre" else "titulo")
                s = {"id": f"{bid}.t", "bloque": bid, "tipo": "imagen", "path": ds["fondos"][fondo], "start": self.snap(T),
                     "dur": d, "entrada": b.get("transicion") or ("flash" if tipo == "cierre" else "matte")}
                bsegs.append(s)
                T += d
            segs += bsegs
            Te = T
            blocks_out.append({"id": bid, "tipo": tipo, "start": round(Tb, 4), "end": round(Te, 4),
                               "segs": [s["id"] for s in bsegs], "resumen": b.get("resumen", "")})
            # textos por defecto de tarjeta y cierre
            tx = list(b.get("textos", []))
            if tipo in ("tarjeta", "titulo") and not b.get("textos"):
                m = ds["marca"]
                tx = [{"rol": "tag", "texto": m.get("hashtag", ""), "t": 0, "pos": [0.29, 0.16]},
                      {"rol": "titulo", "texto": m.get("titulo", ""), "t": 0},
                      {"rol": "pill", "texto": m.get("titulo_pill", ""), "t": 0.25, "pos": [0.5, 0.72]}]
                sfx.append(self.ev("titulo", Tb, bid))
            if tipo == "cierre" and not b.get("textos"):
                m = ds["marca"]
                tx = [{"rol": "cierre", "texto": "\n".join(m.get("cierre_palabras", [])), "t": 0},
                      {"rol": "meta", "texto": m.get("cierre_linea", ""), "t": 0.3, "pos": [0.5, 0.62]},
                      {"rol": "pill", "texto": m.get("cta", ""), "t": 0.5, "pos": [0.5, 0.69]},
                      {"rol": "pie", "texto": m.get("cierre_pie", ""), "t": 0}]
                sfx.append(self.ev("cierre", Tb, bid))
                sfx.append(self.ev("riser", max(0, Tb - 2.0), bid))
            # textos
            grupos = {}
            for ti, t in enumerate(tx):
                r = self.ds["roles_texto"][t["rol"]]
                st, seg = self.text_time(t, bsegs, Tb, Te)
                if st is None:
                    self.avisos.append(f"{bid}: no encontré '{t.get('palabra')}' para «{t['texto']}»; va al inicio del bloque")
                    st, seg = Tb, (bsegs[0] if bsegs else None)
                if t["rol"] == "eco":
                    n = len(r["colores"])
                    dur = n * (self.bf(r.get("frames", 8)) + self.bf(2))
                else:
                    seg_end = (seg["start"] + seg["dur"]) if seg else Te
                    dur = t.get("dur") or min(3.5, max(0.8, seg_end - st))
                    if tipo in ("tarjeta", "titulo", "cierre"):
                        dur = t.get("dur") or (Te - st)
                dur = self.snap(min(dur, max(0.2, Te - st)) if t["rol"] != "eco" else dur)
                item = {"id": f"{bid}.x{ti + 1}", "bloque": bid, "rol": t["rol"], "texto": t["texto"], "start": self.snap(st),
                        "dur": dur, "variante": t.get("variante", ti)}
                if t["rol"] in ("titulo", "cierre"):
                    pass
                elif t.get("pos"):
                    item["pos"] = t["pos"]
                elif r.get("pos"):
                    item["pos"] = r["pos"]
                elif t["rol"] in POP_ROLES or r.get("zona") == "libre":
                    g = t.get("grupo")
                    if g and g in grupos:
                        base, k = grupos[g]
                        grupos[g] = (base, k + 1)
                        item["pos"] = [round(base[0] + r.get("paso_x", 0.06) * (k + 1) * base[2], 4),
                                       round(base[1] + r.get("paso_y", 0.085) * (k + 1), 4)]
                        item["zona"] = {"grupo": g}
                    else:
                        size = self.block_size(t, tx, r)
                        pos, info = self.free_pos(seg, item["start"], item["start"] + dur, size, lado, t.get("preferir"))
                        lado = info.get("lado")
                        if g:
                            n_g = sum(1 for x in tx if x.get("grupo") == g)
                            w1, _ = measure(ds, t["rol"], t["texto"])
                            cx0 = pos[0] - size[0] / 2 + w1 / 2
                            cy0 = pos[1] - size[1] / 2 + measure(ds, t["rol"], t["texto"])[1] / 2
                            dirx = 1 if cx0 < 0.5 else -1
                            grupos[g] = ((cx0, cy0, dirx), 0)
                            pos = (round(cx0, 4), round(cy0, 4))
                            info["grupo_n"] = n_g
                        if t["rol"] == "eco":                     # pos = centro del PRIMER eco de la pila
                            h1 = measure(ds, "eco", t["texto"])[1]
                            pos = (pos[0], round(pos[1] - (size[1] - h1) / 2, 4))
                        item["pos"] = list(pos)
                        item["zona"] = info
                else:
                    item["pos"] = [0.5, 0.3]
                texts.append(item)
                if t["rol"] == "eco":
                    for k in range(len(r["colores"])):
                        sfx.append(self.ev(r.get("sfx", "blip"), item["start"] + k * (self.bf(r.get("frames", 8)) + self.bf(2)), bid))
                elif r.get("anim") == "popIn" and r.get("sfx") and t.get("sfx", True):
                    sfx.append(self.ev(r["sfx"], item["start"], bid))
            for e in b.get("sfx", []):
                sfx.append(self.ev(e["tipo"], Tb + e.get("t", 0), bid, e.get("db")))
            for ci, c in enumerate(b.get("capas", [])):
                st = Tb + c.get("t", 0)
                capas.append({"id": f"{bid}.c{ci + 1}", "bloque": bid, "img": c.get("img") or ds["fondos"].get(c.get("fondo", "cap")),
                              "pista": c.get("pista", "Producto"), "start": self.snap(st), "dur": self.snap(c.get("dur", 1.5)),
                              "entra": c.get("entra"), "escala": c.get("escala", 0.72), "pos": c.get("pos", [0.5, 0.5])})
                if c.get("sfx", "pop") and c.get("pista", "Producto") == "Producto":
                    sfx.append(self.ev(c.get("sfx", "pop"), st, bid))
            if b.get("subtitulos", True) and b.get("planos"):
                caps += self.captions(bsegs, bid)

        # transiciones en cada corte
        for i, s in enumerate(segs):
            ent = s.get("entrada", "corte")
            if i == 0 or ent in ("corte", "jump", "entrada"):
                continue
            prev = segs[i - 1]
            tr = {"id": f"{s['id']}.tr", "bloque": s["bloque"], "tipo": ent, "t": s["start"], "sale": prev["id"], "entra": s["id"]}
            cfg = self.ds["transiciones"].get({"barrido": "barrido_camara"}.get(ent, ent), {})
            if ent == "matte":
                ms = cfg.get("mattes", ["acento1"])
                tr["matte"] = ms[sum(1 for x in trans if x["tipo"] == "matte") % len(ms)]
                tr["dur"] = self.bf(cfg.get("f", 28))
            elif ent in ("flash", "glitch"):
                tr["matte"] = cfg.get("matte", "blanco")
                tr["dur"] = self.bf(cfg.get("f", 6 if ent == "flash" else 12))
                if s["tipo"] == "foto":
                    tr["dur"] = self.bf(4)
            elif ent in ("barrido", "barrido_camara"):
                tr["tipo"] = "barrido"
                tr["blur"] = cfg.get("blur", 20)
                tr["dur"] = self.bf(cfg.get("f", 8))
            elif ent == "zoom_crash":
                tr["dur"] = self.bf(self.ds["continuidad"]["zoom_crash"]["f"])
            trans.append(tr)
            key = cfg.get("sfx") or {"zoom_crash": "barrido"}.get(ent)
            if key and s["tipo"] != "foto":
                lead = 0.25 if ent in ("barrido", "barrido_camara", "matte") else 0.03
                sfx.append(self.ev(key, max(0, s["start"] - lead), s["bloque"]))
        if segs and segs[0]["bloque"] and plan["bloques"][0].get("tipo") == "gancho":
            sfx.append(self.ev("gancho", 0, segs[0]["bloque"]))

        self.alloc_text_tracks(texts)
        total = round(T, 4)
        marca = self.brand_spans(blocks_out, total)
        music = self.music(blocks_out, total)
        sfx = self.alloc_sfx([x for x in sfx if x])
        cobertura = self.coverage(texts, caps)
        return {"version": 1, "ds": ds["id"], "fps": self.fps, "lienzo": ds["lienzo"], "duracion": total,
                "bloques": blocks_out, "segmentos": segs, "textos": texts, "subtitulos": caps, "marca": marca,
                "capas": capas, "transiciones": trans, "sfx": sfx, "musica": music,
                "grade": {"segmentos": [s["id"] for s in segs if s["tipo"] == "video"], **self.ds["grade"]},
                "cortes": sum(1 for i in range(1, len(segs))), "ajustes_corte": self.ajustes, "cobertura": cobertura,
                "avisos": self.avisos}

    def text_time(self, t, bsegs, Tb, Te):
        if "palabra" in t:
            vids = [s for s in bsegs if s["tipo"] == "video"]
            if "plano" in t:
                vids = [bsegs[t["plano"]]] if t["plano"] < len(bsegs) else vids
            for s in vids:
                hit = self.find_word(s["stem"], t["palabra"], s["in"], s["out"])
                if hit:
                    st = s["start"] + (hit[0] - s["in"]) / s["speed"] + t.get("desfase", 0)
                    return st, s
            return None, None
        st = Tb + t.get("t", 0)
        seg = next((s for s in bsegs if s["start"] <= st < s["start"] + s["dur"]), bsegs[0] if bsegs else None)
        return st, seg

    def block_size(self, t, tx, r):
        ds = self.ds
        if t["rol"] == "eco":
            w, h = measure(ds, "eco", t["texto"])
            return w, h + r.get("paso_y", 0.125) * (len(r["colores"]) - 1)
        g = t.get("grupo")
        if g:
            items = [x for x in tx if x.get("grupo") == g]
            ws = [measure(ds, x["rol"], x["texto"]) for x in items]
            n = len(items)
            return (max(w for w, _ in ws) + r.get("paso_x", 0.06) * (n - 1),
                    ws[0][1] + r.get("paso_y", 0.085) * (n - 1))
        return measure(ds, t["rol"], t["texto"])

    def free_pos(self, seg, t0, t1, size, lado, preferir=None):
        if not seg or seg["tipo"] != "video":
            return best_spot([], size, self.ds, lado, preferir)
        a = seg["in"] + (t0 - seg["start"]) * seg["speed"]
        b = seg["in"] + (t1 - seg["start"]) * seg["speed"]
        sc, anc = seg.get("punch", 100), (0.5, 0.5)
        if seg.get("zoom"):
            sc, anc = seg["zoom"].get("a", 150), tuple(seg["zoom"].get("ancla", [0.5, 0.5]))
        occ = occupancy(self.vision(seg["stem"]), a, b, sc, anc)
        pos, info = best_spot(occ, size, self.ds, lado, preferir)
        info["personas"] = len(occ or [])
        if info.get("solape_cara"):
            self.avisos.append(f"{seg['id']}: el pop-up de {t0:.2f}s solapa caras ({info['solape_cara']})")
        elif info.get("solape"):
            self.avisos.append(f"{seg['id']}: el pop-up de {t0:.2f}s roza cuerpos ({info['solape']})")
        return pos, info

    def captions(self, bsegs, bid):
        r = self.ds["roles_texto"]["subtitulo"]
        mx = r.get("max_chars", 20)
        out = []
        for s in bsegs:
            if s["tipo"] != "video" or s["mute"]:
                continue
            ws = [w for w in self.words(s["stem"]) if w["s"] >= s["in"] - 0.05 and w["e"] <= s["out"] + 0.15
                  and not w["w"].startswith("[")]
            chunks, cur = [], []
            for w in ws:
                txt = self.corr.get(norm(w["w"]), w["w"])
                if cur and len(" ".join(x[0] for x in cur)) + 1 + len(txt) > mx:
                    carry = []                                  # no acabar una línea en palabra funcional
                    while len(cur) > 1 and norm(cur[-1][0]) in FUNCIONALES and not re.search(r"[.?!,:]$", cur[-1][0]):
                        carry.insert(0, cur.pop())
                    chunks.append(cur)
                    cur = carry
                cur.append((txt, w))
                if re.search(r"[.?!,:]$", txt) and len(" ".join(x[0] for x in cur)) >= 8:
                    chunks.append(cur)
                    cur = []
            if cur:
                chunks.append(cur)
            end_seg = s["start"] + s["dur"]
            for k, c in enumerate(chunks):
                st = max(s["start"], s["start"] + (c[0][1]["s"] - s["in"]) / s["speed"])
                nx = (s["start"] + (chunks[k + 1][0][1]["s"] - s["in"]) / s["speed"]) if k + 1 < len(chunks) else end_seg
                en = min(end_seg, nx, s["start"] + (c[-1][1]["e"] - s["in"]) / s["speed"] + 0.6)
                if k + 1 < len(chunks):
                    en = nx                                         # continuos, como el reel manual
                st, en = self.snap(st), self.snap(en)
                if en - st < 0.15:
                    continue
                out.append({"id": f"{s['id']}.s{k + 1}", "bloque": bid, "texto": " ".join(x[0] for x in c),
                            "start": st, "dur": round(en - st, 4)})
        return out

    def brand_spans(self, blocks, total):
        spans, cur = [], None
        for b in blocks:
            if b["tipo"] in SIN_MARCA:
                if cur:
                    spans.append(cur)
                    cur = None
                continue
            if cur is None:
                cur = {"bloque": b["id"], "start": b["start"], "dur": 0}
            cur["dur"] = round(b["end"] - cur["start"], 4)
        if cur:
            spans.append(cur)
        return [{"id": f"marca{i + 1}", **s} for i, s in enumerate(spans)]

    def music(self, blocks, total):
        m = self.ds["musica"]
        kfs = []
        ramp = m.get("rampa_s", 0.4)
        for b in blocks:
            lvl = m["sin_voz_db"] if b["tipo"] in ("tarjeta", "titulo", "cierre", "fotos") else m["bajo_voz_db"]
            kfs.append([round(b["start"], 3), lvl])
            kfs.append([round(max(b["start"], b["end"] - ramp), 3), lvl])
        kfs.append([round(total - m.get("salida_s", 1.5), 3), kfs[-1][1] if kfs else m["sin_voz_db"]])
        kfs.append([round(total, 3), -60])
        kfs.sort(key=lambda k: k[0])
        clean = []
        for t, v in kfs:
            if clean and abs(clean[-1][0] - t) < 1e-3:
                clean[-1] = [t, v]
            else:
                clean.append([t, v])
        return {"bloque": "*", "dur": total, "bpm": m.get("bpm", 112), "archivo": m.get("archivo"), "keyframes": clean}

    def ev(self, key, t, bid, db=None):
        p = self.ds["sfx"]["_mapa_abs"].get(key)
        if not p:
            self.avisos.append(f"sin SFX para '{key}'")
            return None
        return {"bloque": bid, "clave": key, "path": p, "start": self.snap(max(0, t)), "dur": self.sfx_dur(p),
                "db": db if db is not None else self.ds["sfx"].get("nivel_db", -4)}

    def alloc_text_tracks(self, texts):
        """Cada texto en la pista de su rol; si coincide en el tiempo con otro, en la siguiente pista de texto libre."""
        pool = [t for t in ("Labels", "Pills", "Tags", "Eco") if t in self.ds["pistas"]["video"]]
        busy = {}
        for t in sorted(texts, key=lambda x: x["start"]):
            r = self.ds["roles_texto"][t["rol"]]
            pref = r.get("pistas") or [r["pista"]]
            pref = [pref[t.get("variante", 0) % len(pref)]] if r.get("pistas") else pref
            a, b = t["start"], t["start"] + t["dur"]
            for tr in pref + [x for x in pool if x not in pref]:
                if all(b <= x0 + 1e-4 or a >= x1 - 1e-4 for x0, x1 in busy.get(tr, [])):
                    busy.setdefault(tr, []).append((a, b))
                    t["pista"] = tr
                    if tr not in pref:
                        self.avisos.append(f"{t['id']}: «{t['texto'][:20]}» pasa a la pista {tr} (la suya estaba ocupada)")
                    break
            else:
                self.avisos.append(f"{t['id']}: sin pista de texto libre para «{t['texto'][:20]}»")

    def alloc_sfx(self, evs):
        tracks = self.ds["pistas"].get("sfx", ["SFX"])
        busy = {t: [] for t in tracks}
        out = []
        for i, e in enumerate(sorted(evs, key=lambda e: e["start"])):
            for t in tracks:
                if all(e["start"] >= b or e["start"] + e["dur"] <= a for a, b in busy[t]):
                    busy[t].append((e["start"], e["start"] + e["dur"]))
                    out.append({**e, "id": f"sfx{i + 1}", "pista": t})
                    break
            else:
                e["dur"] = 0.25
                out.append({**e, "id": f"sfx{i + 1}", "pista": tracks[0], "recortado": True})
        return out

    def coverage(self, texts, caps):
        obl = (self.brief.get("obligatorios") or {}).get("valor") or []
        blob = " ".join(norm(x) for t in texts + caps for x in t["texto"].split())
        cov = {}
        for o in obl:
            parts = [norm(p) for p in o.split() if norm(p)]
            if o == "momento de premio":
                cov[o] = any(b["tipo"] == "humano" for b in self.plan["bloques"])
            else:
                cov[o] = bool(parts) and max(parts, key=len) in blob          # la palabra distintiva
        return cov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--analisis", required=True)
    ap.add_argument("--brief")
    ap.add_argument("--out")
    a = ap.parse_args()
    plan = jload(a.plan)
    ds = load_ds(plan["ds"])
    brief = jload(a.brief) if a.brief else None
    c = Compiler(plan, ds, a.analisis, brief).compile()
    out = a.out or str(Path(a.plan).with_name("compiled.json"))
    jsave(out, c)
    print(json.dumps({"compiled": out, "duracion": c["duracion"], "segmentos": len(c["segmentos"]), "cortes": c["cortes"],
                      "textos": len(c["textos"]), "subtitulos": len(c["subtitulos"]), "sfx": len(c["sfx"]),
                      "transiciones": len(c["transiciones"]), "ajustes_corte": len(c["ajustes_corte"]),
                      "cobertura": c["cobertura"], "avisos": c["avisos"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
