from palmier import *  # noqa: F401,F403
fc = FC(); tl, T, media = load()
s = fc.seq()
main = [t for t in s["video"] if t["name"] == "Main"][0]
vids = {c["startFrame"]: c for c in main["items"] if not c["name"].lower().endswith((".png", ".jpg"))}
pal = {c["startFrame"]: c for c in T["Main"]["clips"] if c["mediaType"] == "video"}
def animated(c, eff, param):
    for e in c["effects"]:
        if e["effect"] == eff: return e["params"].get(param, {}).get("keyframes", 0) > 0
    return False
def put(cid, a, src_in, eff, param, rows, spd=1.0):
    for f, val, it in rows:
        fc.x("effects.setParam", {"clip": cid, "effect": eff, "param": param, "value": val, "time": fr(a + f), "keyframe": True})
    for f, val, it in rows:
        fc.x("effects.setInterpolation", {"clip": cid, "effect": eff, "param": param, "mediaTime": src_in + round(fr(f) * spd), "interpolation": INTERP.get(it, "linear")})
nm = nb = 0
for a, pc in sorted(pal.items()):
    c = vids[a]; cid = c["clip"]; src_in = c["sourceIn"]
    # quitar keyframes importados (base de tiempo equivocada) y dejar valores neutros
    for p in ("scale", "position"):
        if animated(c, "motion", p): fc.x("effects.toggleAnimation", {"clip": cid, "effect": "motion", "param": p})
    fc.x("effects.setParam", {"clip": cid, "effect": "motion", "param": "scale", "value": 100})
    fc.x("effects.setParam", {"clip": cid, "effect": "motion", "param": "position", "value": [W / 2, H / 2]})
    sk, pk = kfs(pc, "scaleTrack"), kfs(pc, "positionTrack")
    def size_at(f):
        if sk:
            prev = [k for k in sk if k["frame"] <= f] or sk[:1]; v = prev[-1]["value"]; return v["a"], v["b"]
        return pc["transform"]["width"], pc["transform"]["height"]
    if sk:
        put(cid, a, src_in, "motion", "scale", [(k["frame"], 100 * k["value"]["a"], k["interpolationOut"]) for k in sk], c.get("speed", 1.0)); nm += 1
    if pk:
        rows = []
        for k in pk:
            w_, h_ = size_at(k["frame"])
            rows.append((k["frame"], [(k["value"]["a"] + w_ / 2) * W, (k["value"]["b"] + h_ / 2) * H], k["interpolationOut"]))
        put(cid, a, src_in, "motion", "position", rows, c.get("speed", 1.0)); nm += 1
    for ef in pc.get("effects") or []:
        if ef["type"] == "blur.gaussian" and ef["params"]["radius"].get("track"):
            if not any(e["effect"] == "gaussian_blur" for e in c["effects"]):
                fc.x("effects.apply", {"clips": [cid], "effect": "gaussian_blur"})
            elif animated(c, "gaussian_blur", "blurriness"):
                fc.x("effects.toggleAnimation", {"clip": cid, "effect": "gaussian_blur", "param": "blurriness"})
            put(cid, a, src_in, "gaussian_blur", "blurriness", [(k["frame"], k["value"], k["interpolationOut"]) for k in ef["params"]["radius"]["track"]["keyframes"]], c.get("speed", 1.0))
            fc.x("effects.setParam", {"clip": cid, "effect": "gaussian_blur", "param": "repeat_edge", "value": True}); nb += 1
print("pistas de movimiento", nm, "desenfoques", nb)
fc.x("file.save", {})
