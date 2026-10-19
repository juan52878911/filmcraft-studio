from palmier import *  # noqa: F401,F403
import sys
fc = FC(); tl, T, media = load()
R = 1920 / 1080                      # Palmier mide fuente y márgenes en esta escala
FONTS = {"IosevkaTermNFM-Heavy": ("IosevkaTerm Nerd Font Mono", "Heavy"), "Menlo-Bold": ("Menlo", "Bold"), "Menlo-Regular": ("Menlo", "Regular")}
TRK = {"Brand": 4, "Captions": 5, "Labels": 6, "Pills": 7, "Tags": 8, "Eco": 9}   # índices 0-based (V5..V10)
def hexc(c): return "#%02X%02X%02X" % tuple(round(c[k] * 255) for k in ("r", "g", "b"))
only = sys.argv[1:]                   # opcional: limitar a unas pistas
# quitar textos de pruebas anteriores en esas pistas
s = fc.seq()
old = [c["clip"] for t in s["video"] if t["name"] in [n for n in TRK if not only or n in only] for c in t["items"]]
if old: fc.x("edit.clear", {"clips": old})
n = 0
for tn, trk in TRK.items():
    if only and tn not in only: continue
    for c in T[tn]["clips"]:
        st = c["textStyle"]; fam, sty = FONTS[st["fontName"]]
        a, d = c["startFrame"], c["durationFrames"]
        cid = fc.x("graphics.newText", {"text": c["textContent"], "position": [100, 400], "size": st["fontSize"] * R, "font": fam, "fontStyle": sty,
                                        "seconds": d / FPS, "track": trk, "time": fr(a)})["clip"]
        props = {"align": st.get("alignment", "center").capitalize(), "fill_color": hexc(st["color"]), "shadow": False}
        bg = st["background"]
        if bg["enabled"]:
            props.update(background=True, background_color=hexc(bg["color"]), background_opacity=100,
                         background_size=bg["paddingX"] * R, background_radius=0)
        fc.x("graphics.set", {"clip": cid, "layer": 0, "props": props})
        L = fc.x("graphics.list", {"clip": cid})["layers"][0]
        x0, y0, x1, y1 = L["localBounds"]
        anchor = [(x0 + x1) / 2, (y0 + y1) / 2]
        tf = c["transform"]; target = [tf["centerX"] * W, tf["centerY"] * H]
        fc.x("graphics.set", {"clip": cid, "layer": 0, "props": {"anchor": anchor, "position": target}})
        anim = (c.get("textAnimation") or {}).get("preset")
        eff = L["effectIndex"]
        def kf(param, rows):
            for f, v in rows:
                fc.x("effects.setParam", {"clip": cid, "effect": eff, "param": param, "value": v, "time": fr(a + f), "keyframe": True})
        if anim == "popIn":
            kf("scale", [(0, 60), (8, 108), (14, 100)])
            kf("opacity", [(0, 0), (6, 100)])
        elif anim == "wordReveal":
            kf("opacity", [(0, 0), (14, 100)])
            kf("position", [(0, [target[0], target[1] + 40]), (16, target)])
        n += 1
print("textos", n)
fc.x("file.save", {})
