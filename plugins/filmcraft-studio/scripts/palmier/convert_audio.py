from palmier import *  # noqa: F401,F403
import math
fc = FC(); tl, T, media = load()
s = fc.seq()
SFPS = fc.fps()                      # fps de la secuencia de FilmCraft (startFrame va en ellos)
A1_ID = s["audio"][0]["id"]
# 1) diálogo a A1 (el importador lo repartió entre pistas de efectos)
dlg = [(c, t["id"]) for t in s["audio"] for c in t["items"] if c["name"].startswith("PXL_")]
fc.x("timeline.move", {"moves": [{"clip": c["clip"], "track": A1_ID, "time": ticks(c["startFrame"] / SFPS)} for c, _ in dlg], "insert": False, "linked": False})
s = fc.seq(); A1 = [t for t in s["audio"] if t["id"] == A1_ID][0]
byframe = {c["startFrame"]: c for c in A1["items"]}
# 2) niveles y fades del diálogo según Palmier
def vol_kf(cid, rows):
    for f, v in rows:
        fc.x("effects.setParam", {"clip": cid, "effect": "volume", "param": "level", "value": v, "time": fr(f), "keyframe": True})
for pc in T["Dialogue"]["clips"]:
    a, d = pc["startFrame"], pc["durationFrames"]
    c = byframe[a]; v = pc.get("volume", 1); db = 20 * math.log10(v) if v > 0 else -60
    fi, fo = pc.get("fadeInFrames") or 0, pc.get("fadeOutFrames") or 0
    if db <= -60:
        fc.x("effects.setParam", {"clip": c["clip"], "effect": "volume", "param": "level", "value": -60}); continue
    rows = []
    if fi: rows += [(a, -60), (a + fi, db)]
    if fo: rows += [(a + d - fo, db), (a + d - 1, -60)]
    if rows: vol_kf(c["clip"], rows)
    else: fc.x("effects.setParam", {"clip": c["clip"], "effect": "volume", "param": "level", "value": db})
# 3) ducking de la música
mus = [c for t in s["audio"] for c in t["items"] if c["name"].startswith("promo-tech-bed")][0]
vol_kf(mus["clip"], [(k["frame"], k["value"]) for k in T["Music"]["clips"][0]["volumeTrack"]["keyframes"]])
# 4) nombres de pista
for tr, n in (("A1", "Dialogue"), ("A2", "Hits"), ("A3", "SFX"), ("A4", "Music"), ("A5", "SFX 2")):
    fc.x("timeline.setTrack", {"track": tr, "name": n})
fc.x("file.save", {})
s = fc.seq()
print([(t["name"], len(t["items"])) for t in s["audio"]])
