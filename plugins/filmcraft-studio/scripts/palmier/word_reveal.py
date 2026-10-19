"""Rehace los textos 'wordReveal' de Palmier: una capa por palabra dentro de un mismo gráfico, entradas escalonadas."""
from palmier import *  # noqa: F401,F403
fc = FC(); tl, T, media = load(); R = 1920 / 1080
STEP, FADE = 10, 8                       # fotogramas (60 fps) entre palabras y de cada entrada
s = fc.seq(); lab = [t for t in s["video"] if t["name"] == "Labels"][0]
for pc in [c for c in T["Labels"]["clips"] if (c.get("textAnimation") or {}).get("preset") == "wordReveal"]:
    a, d = pc["startFrame"], pc["durationFrames"]; st = pc["textStyle"]
    old = [c for c in lab["items"] if c["startFrame"] == a][0]["clip"]
    # medir el bloque completo para sacar rejilla de caracteres (fuente monoespaciada)
    L = fc.x("graphics.list", {"clip": old})["layers"][0]
    x0, y0, x1, y1 = L["localBounds"]; anc = L["anchor"]; pos = L["position"]
    left, top = pos[0] - (anc[0] - x0), pos[1] - (anc[1] - y0)          # esquina del bloque en el lienzo
    lines = pc["textContent"].split("\n"); lh = (y1 - y0) / len(lines); cw = (x1 - x0) / max(len(l) for l in lines)
    fc.x("edit.clear", {"clips": [old]})
    words = []
    for i, line in enumerate(lines):
        j = 0
        for w in line.split(" "):
            if w: words.append((w, i, j))
            j += len(w) + 1
    gid = None
    for k, (w, i, j) in enumerate(words):
        p = {"text": w, "position": [100, 400], "size": st["fontSize"] * R, "font": "IosevkaTerm Nerd Font Mono", "fontStyle": "Heavy"}
        if gid is None: p.update(seconds=d / FPS, track=6, time=fr(a))
        else: p["clip"] = gid
        r = fc.x("graphics.newText", p); gid = r["clip"]; layer = r["layer"]
        fc.x("graphics.set", {"clip": gid, "layer": layer, "props": {"align": "Left", "fill_color": "#FFFFFF", "shadow": False}})
        Lw = [l for l in fc.x("graphics.list", {"clip": gid})["layers"] if l["layer"] == layer][0]
        bx0, by0 = Lw["localBounds"][0], Lw["localBounds"][1]
        target = [left + j * cw, top + i * lh]
        fc.x("graphics.set", {"clip": gid, "layer": layer, "props": {"anchor": [bx0, by0], "position": target}})
        eff = Lw["effectIndex"]; t0 = a + k * STEP
        for f, v in ((t0, 0), (t0 + FADE, 100)):
            fc.x("effects.setParam", {"clip": gid, "effect": eff, "param": "opacity", "value": v, "time": fr(f), "keyframe": True})
        for f, v in ((t0, [target[0], target[1] + 30]), (t0 + FADE + 2, target)):
            fc.x("effects.setParam", {"clip": gid, "effect": eff, "param": "position", "value": v, "time": fr(f), "keyframe": True})
    print(pc["textContent"].replace("\n", " / "), "->", len(words), "capas")
fc.x("file.save", {})
