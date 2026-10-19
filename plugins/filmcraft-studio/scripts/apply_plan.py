#!/usr/bin/env python3
"""Aplica compiled.json a FilmCraft por fases, en headless o en la app abierta.

Headless (proyecto NUEVO; nunca toca un .fcproj existente):
    apply_plan.py WORK/compiled.json --headless --out WORK/Reel.fcproj

En vivo (app abierta con --control 9876), por bloques y fases, para el modo asistido:
    apply_plan.py WORK/compiled.json --live --nuevo WORK/Reel.fcproj      # G0: proyecto nuevo con las pistas del DS
    apply_plan.py WORK/compiled.json --live --bloques gancho --fases A,B,C,D
    apply_plan.py WORK/compiled.json --live --bloques '*' --fases B,E    # G5: música y grade
    apply_plan.py WORK/compiled.json --live --deshacer gancho           # borra lo creado para ese bloque

Fases: A cortes y continuidad · B audio (diálogo, SFX, música) · C textos · D transiciones · E grade.
El estado (ids de clips por segmento y bloque, cajas de texto) va en WORK/estado.json.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from common import SCRIPTS, jload, jsave, load_ds  # noqa: E402
from fcengine import Engine  # noqa: E402
from fcstyle import Styler  # noqa: E402

FASES = "ABCDE"


class Applier:
    def __init__(self, e, comp, ds, work, state):
        self.e, self.c, self.ds, self.work, self.st = e, comp, ds, Path(work), state
        self.W, self.H = ds["lienzo"]["ancho"], ds["lienzo"]["alto"]
        self.sty = Styler(e, ds)
        self.segs = {s["id"]: s for s in comp["segmentos"]}

    # ---------- estado ----------
    def keep(self, bloque, clips):
        self.st.setdefault("creados", {}).setdefault(bloque, []).extend(clips)

    def clip_of(self, sid):
        return self.st["clips"][sid]

    def bf(self, f):
        return self.sty.bf(f)

    def img_size(self, p):
        with Image.open(p) as im:
            return im.size

    # ---------- A: cortes y continuidad ----------
    def phase_A(self, blocks):
        e, c = self.e, self.c
        if "*" in blocks and "fondo" not in self.st.get("clips", {}):
            cl = e.place(self.ds["fondos"]["plano"], "Fondo", 0, c["duracion"], audio=False)
            self.st.setdefault("clips", {})["fondo"] = {"v": cl[0]}
            self.keep("*", cl)
        vids = []
        for s in c["segmentos"]:
            if s["bloque"] not in blocks:
                continue
            if s["tipo"] == "video":
                span = round(s["out"] - s["in"], 6)
                cl = e.place(s["path"], "Main", s["start"], span, source_in=s["in"], audio=not s["mute"],
                             audio_track=None if s["mute"] else "Dialogue")
                v, a = cl[0], (cl[1] if len(cl) > 1 else None)
                if s["speed"] != 1:
                    e.x("clip.speedDuration", {"clips": cl, "speed": s["speed"] * 100, "ripple": False,
                                               "interpolation": "opticalFlow"})
                vids.append(v)
            else:
                cl = e.place(s["path"], "Main", s["start"], s["dur"], audio=False)
                v, a = cl[0], None
                w, h = self.img_size(s["path"])
                fit = (max if s["tipo"] == "foto" else min)(self.W / w, self.H / h) * 100
                e.param(v, "motion", "scale", round(fit, 3))
            self.st.setdefault("clips", {})[s["id"]] = {"v": v, "a": a}
            self.keep(s["bloque"], cl)
        if vids:
            e.scale_to_frame(vids)
        for s in c["segmentos"]:
            if s["bloque"] not in blocks or s["tipo"] != "video":
                continue
            self.motion(s)
        for cp in c.get("capas", []):
            if cp["bloque"] in blocks:
                self.capa(cp)

    def motion(self, s):
        e, v = self.e, self.clip_of(s["id"])["v"]
        base = s.get("punch") or 100
        k = (s["start"], s["in"], s["speed"])
        if s.get("zoom"):
            z = s["zoom"]
            ax, ay = z.get("ancla", [0.5, 0.5])
            t0 = s["dur"] * z.get("desde", 0.0)
            t1 = s["dur"] * z.get("hasta", 1.0)
            rows_s, rows_p = [], []
            for t, sc in ((0, 100), (t0, 100), (t1, z.get("a", 150))):
                f = sc / 100
                rows_s.append((self.e.snap(t), sc, "linear"))
                rows_p.append((self.e.snap(t), [ax * self.W - (ax - 0.5) * self.W * f, ay * self.H - (ay - 0.5) * self.H * f], "linear"))
            rows_s = [r for i, r in enumerate(rows_s) if i == 0 or r[0] > rows_s[i - 1][0]]
            rows_p = [r for i, r in enumerate(rows_p) if i == 0 or r[0] > rows_p[i - 1][0]]
            e.kf(v, "motion", "scale", rows_s, *k)
            e.kf(v, "motion", "position", rows_p, *k)
        elif s.get("entrada") == "entrada":
            cfg = self.ds["continuidad"]["entrada"]
            a0, a1 = cfg["escala"]
            e.kf(v, "motion", "scale", [(0, base * a0 / 100, "easeOut"), (self.bf(cfg["f"]), base * a1 / 100, "linear")], *k)
            e.kf(v, "opacity", "opacity", [(0, 0, "linear"), (self.bf(cfg.get("fade_f", 6)), 100, "linear")], *k)
        elif base != 100:
            e.param(v, "motion", "scale", base)

    def capa(self, cp):
        e = self.e
        cl = e.place(cp["img"], cp["pista"], cp["start"], cp["dur"], audio=False)
        v = cl[0]
        w, h = self.img_size(cp["img"])
        fit = min(self.W / w, self.H / h) * 100 * (cp["escala"] if cp["pista"] == "Producto" else 1)
        e.param(v, "motion", "scale", round(fit, 3))
        x, y = cp["pos"][0] * self.W, cp["pos"][1] * self.H
        if cp.get("entra"):
            x0 = {"der": self.W * 1.5, "izq": -self.W * 0.5}.get(cp["entra"], x)
            e.kf(v, "motion", "position", [(0, [x0, y], "easeOut"), (self.bf(10), [x, y], "linear")], cp["start"])
        elif cp["pista"] == "Producto":
            e.param(v, "motion", "position", [x, y])
        self.st["clips"][cp["id"]] = {"v": v}
        self.keep(cp["bloque"], cl)

    # ---------- B: audio ----------
    def phase_B(self, blocks):
        e, c = self.e, self.c
        fade = self.bf(self.ds["audio"].get("fade_corte_f", 3))
        for s in c["segmentos"]:
            if s["bloque"] not in blocks or s["tipo"] != "video":
                continue
            a = self.clip_of(s["id"]).get("a")
            if not a:
                continue
            g = self.ds["audio"].get("dialogo_db", 0)
            e.kf(a, "volume", "level", [(0, -60, "linear"), (fade, g, "linear"), (s["dur"] - fade, g, "linear"),
                                        (s["dur"], -60, "linear")], s["start"], s["in"], s["speed"])
        for x in c["sfx"]:
            if x["bloque"] not in blocks:
                continue
            cl = e.place(x["path"], x["pista"], x["start"], min(x["dur"], c["duracion"] - x["start"]) if x.get("recortado") else None,
                         video=False)
            e.param(cl[0], "volume", "level", x["db"])
            self.st["clips"][x["id"]] = {"a": cl[0]}
            self.keep(x["bloque"], cl)
        if "*" in blocks:
            m = c["musica"]
            path = m.get("archivo")
            if not path:
                path = str(self.work / "musica.wav")
                subprocess.run([sys.executable, str(SCRIPTS / "music_bed.py"), path, str(m["dur"]), "--bpm", str(m["bpm"])],
                               check=True, capture_output=True)
            cl = e.place(path, "Music", 0, m["dur"], video=False)
            e.kf(cl[0], "volume", "level", [(t, db, "linear") for t, db in m["keyframes"]], 0)
            self.st["clips"]["musica"] = {"a": cl[0]}
            self.keep("*", cl)
            # limitador en el máster: el pico real queda por debajo del objetivo del DS
            if not self.st.get("limitador"):
                techo = self.ds["audio"].get("pico_dbtp", -1) - 0.5
                e.x("mixer.addInsert", {"strip": "Mix", "effect": "hard_limiter", "slot": 0})
                e.x("mixer.setInsert", {"strip": "Mix", "slot": 0, "params": {"max": techo}})
                self.st["limitador"] = techo

    # ---------- C: textos ----------
    def phase_C(self, blocks):
        c, sty = self.c, self.sty
        out = self.st.setdefault("textos", {})
        for m in c["marca"]:
            if m["bloque"] in blocks:
                r = sty.text("marca", self.ds["marca"]["barra"], m["start"], m["dur"], self.ds["roles_texto"]["marca"]["pos"])
                out[m["id"]] = r
                self.keep(m["bloque"], [r["clip"]])
        for s in c["subtitulos"]:
            if s["bloque"] in blocks:
                r = sty.text("subtitulo", s["texto"], s["start"], s["dur"], self.ds["roles_texto"]["subtitulo"]["pos"])
                out[s["id"]] = r
                self.keep(s["bloque"], [r["clip"]])
        for t in c["textos"]:
            if t["bloque"] not in blocks:
                continue
            if t["rol"] in ("titulo", "cierre"):
                r = sty.title(t["texto"], t["start"], t["dur"], role=t["rol"], pista=t.get("pista"))
                rs = [r]
            elif t["rol"] == "eco":
                rs = sty.eco(t["texto"], t["start"], t["pos"], pista=t.get("pista"))
            else:
                rs = [sty.text(t["rol"], t["texto"], t["start"], t["dur"], t["pos"], variante=t.get("variante", 0),
                               pista=t.get("pista"))]
            for i, r in enumerate(rs):
                out[f"{t['id']}" + (f".{i + 1}" if len(rs) > 1 else "")] = r
                self.keep(t["bloque"], [r["clip"]])

    # ---------- D: transiciones ----------
    def phase_D(self, blocks):
        e = self.e
        for tr in self.c["transiciones"]:
            if tr["bloque"] not in blocks:
                continue
            t, d = tr["t"], tr["dur"]
            sale, entra = self.segs[tr["sale"]], self.segs[tr["entra"]]
            if tr["tipo"] in ("flash", "glitch", "matte"):
                if tr["tipo"] == "matte":
                    st = max(0, t - d / 2)
                    cl = e.place(self.ds["mattes"][tr["matte"]], "Mattes", st, d, audio=False)
                    y = self.H / 2
                    e.kf(cl[0], "motion", "position", [(0, [self.W * 1.5, y], "easeOut"), (d / 2, [self.W / 2, y], "easeIn"),
                                                        (d, [-self.W / 2, y], "linear")], st)
                elif tr["tipo"] == "flash":
                    st = t if entra["tipo"] == "foto" else max(0, t - self.bf(2))
                    cl = e.place(self.ds["mattes"][tr["matte"]], "Mattes", st, d, audio=False)
                    e.kf(cl[0], "opacity", "opacity", [(0, 100, "linear"), (d, 0, "linear")], st)
                else:                                                           # glitch: dos golpes
                    st = max(0, t - self.bf(3))
                    cl = e.place(self.ds["mattes"][tr["matte"]], "Mattes", st, self.bf(3), audio=False)
                    cl += e.place(self.ds["mattes"]["blanco"], "Mattes", t + self.bf(1), self.bf(2), audio=False)
                self.keep(tr["bloque"], cl)
            elif tr["tipo"] == "barrido":
                f = d
                for seg, rows in ((sale, [(max(0, sale["dur"] - f), 0, "easeIn"), (sale["dur"] - self.bf(1), tr["blur"], "linear")]),
                                  (entra, [(0, tr["blur"], "easeOut"), (f, 0, "linear")])):
                    if seg["tipo"] != "video":
                        continue
                    v = self.clip_of(seg["id"])["v"]
                    e.x("effects.apply", {"clips": [v], "effect": "gaussian_blur"})
                    e.param(v, "gaussian_blur", "repeat_edge", True)
                    e.kf(v, "gaussian_blur", "blurriness", rows, seg["start"], seg["in"], seg["speed"])
            elif tr["tipo"] == "zoom_crash":
                z = self.ds["continuidad"]["zoom_crash"]
                if sale["tipo"] == "video":
                    v = self.clip_of(sale["id"])["v"]
                    b0 = sale.get("punch") or 100
                    e.kf(v, "motion", "scale", [(max(0, sale["dur"] - d), b0, "easeIn"), (sale["dur"] - self.bf(1), b0 * z["escala"][1] / 100, "linear")],
                         sale["start"], sale["in"], sale["speed"])
                if entra["tipo"] == "video":
                    v = self.clip_of(entra["id"])["v"]
                    e.kf(v, "motion", "scale", [(0, 125, "easeOut"), (d, entra.get("punch") or 100, "linear")],
                         entra["start"], entra["in"], entra["speed"])

    # ---------- E: grade ----------
    def phase_E(self, blocks):
        e, g = self.e, self.c["grade"]
        ids = [self.clip_of(s)["v"] for s in g["segmentos"] if self.segs[s]["bloque"] in blocks or "*" in blocks]
        ids = [i for i in ids if i]
        if not ids:
            return
        for eff in ("lumetri", "sharpen", "unsharp_mask", "noise"):
            if eff in g:
                e.x("effects.apply", {"clips": ids, "effect": eff})
        for cid in ids:
            for eff in ("lumetri", "sharpen", "unsharp_mask", "noise"):
                for p, v in (g.get(eff) or {}).items():
                    e.param(cid, eff, p, v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("compiled")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--headless", action="store_true")
    mode.add_argument("--live", action="store_true")
    ap.add_argument("--out", help="headless: ruta del .fcproj nuevo")
    ap.add_argument("--nuevo", help="live: crea un proyecto nuevo y lo guarda en esta ruta")
    ap.add_argument("--bloques", default="*", help="ids separados por comas; '*' = todos más lo global")
    ap.add_argument("--fases", default=FASES)
    ap.add_argument("--deshacer")
    ap.add_argument("--work")
    a = ap.parse_args()
    comp = jload(a.compiled)
    ds = load_ds(comp["ds"])
    work = Path(a.work or Path(a.compiled).parent)
    stf = work / "estado.json"
    state = jload(stf) if (stf.exists() and a.live and not a.nuevo) else {"clips": {}, "creados": {}, "textos": {}, "fases": {}}
    journal = work / "journal.jsonl"
    t0 = time.time()
    if a.headless:
        if not a.out:
            sys.exit("--headless necesita --out")
        if Path(a.out).exists():
            sys.exit(f"{a.out} ya existe: el modo headless solo escribe proyectos nuevos")
        e = Engine.headless(journal=journal)
        lz = ds["lienzo"]
        e.new_project(Path(a.out).stem, lz["ancho"], lz["alto"], comp["fps"], ds["pistas"]["video"], ds["pistas"]["audio"])
    else:
        e = Engine.live(journal=journal)
        if a.nuevo:
            lz = ds["lienzo"]
            e.new_project(Path(a.nuevo).stem, lz["ancho"], lz["alto"], comp["fps"], ds["pistas"]["video"], ds["pistas"]["audio"])
            e.save_as(a.nuevo)
            state["proyecto"] = a.nuevo
        else:
            e.name_tracks(ds["pistas"]["video"], ds["pistas"]["audio"])
        e._items.update(state.get("items", {}))
    ap_ = Applier(e, comp, ds, work, state)
    if a.deshacer:
        ids = state.get("creados", {}).pop(a.deshacer, [])
        if ids:
            e.x("edit.clear", {"clips": ids})
        for k in [k for k, v in state["clips"].items() if k.startswith(a.deshacer + ".")]:
            state["clips"].pop(k)
        state.get("fases", {}).pop(a.deshacer, None)
        e.save()
        jsave(stf, state)
        print(f"deshecho {a.deshacer}: {len(ids)} clips")
        return
    if a.nuevo and a.bloques == "*" and a.fases == FASES:
        state["items"] = e._items
        jsave(stf, state)
        print(f"proyecto nuevo en {a.nuevo}")
        return
    all_blocks = [b["id"] for b in comp["bloques"]]
    blocks = set(all_blocks + ["*"]) if a.bloques == "*" else set(a.bloques.split(","))
    for f in a.fases.split(",") if "," in a.fases else list(a.fases):
        tf = time.time()
        getattr(ap_, f"phase_{f}")(blocks)
        for b in blocks:
            state["fases"].setdefault(b, [])
            if f not in state["fases"][b]:
                state["fases"][b].append(f)
        print(f"fase {f}: {time.time() - tf:.1f} s", flush=True)
        if a.live:
            e.save()
    state["items"] = e._items
    if a.headless:
        r = e.save_as(a.out)
        state["proyecto"] = a.out
        print(f"guardado {a.out} ({r.get('bytes') if isinstance(r, dict) else r} bytes)")
    jsave(stf, state)
    e.close()
    print(f"listo en {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
