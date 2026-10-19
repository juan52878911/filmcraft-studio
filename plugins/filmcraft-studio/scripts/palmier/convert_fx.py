from palmier import *  # noqa: F401,F403
fc = FC(); tl, T, media = load()
s = fc.seq()
main = [t for t in s["video"] if t["name"] == "Main"][0]
vids = {c["startFrame"]: c["clip"] for c in main["items"] if not c["name"].lower().endswith((".png", ".jpg"))}
pal = {c["startFrame"]: c for c in T["Main"]["clips"] if c["mediaType"] == "video"}
assert sorted(vids) == sorted(pal), (sorted(vids), sorted(pal))
ids = list(vids.values())
# grade del reel (Palmier: contraste 1.15, negros -0.12, altas -0.15, saturación 1.05) y textura
for eff in ("lumetri", "sharpen", "unsharp_mask", "noise"):
    fc.x("effects.apply", {"clips": ids, "effect": eff})
for cid in ids:
    for p, v in (("contrast", 15), ("blacks", -12), ("highlights", -15), ("saturation", 105)):
        fc.x("effects.setParam", {"clip": cid, "effect": "lumetri", "param": p, "value": v})
    fc.x("effects.setParam", {"clip": cid, "effect": "sharpen", "param": "amount", "value": 12})
    for p, v in (("amount", 25), ("radius", 30), ("threshold", 0)):      # "claridad": contraste local suave
        fc.x("effects.setParam", {"clip": cid, "effect": "unsharp_mask", "param": p, "value": v})
    fc.x("effects.setParam", {"clip": cid, "effect": "noise", "param": "amount", "value": 6})
    fc.x("effects.setParam", {"clip": cid, "effect": "noise", "param": "color", "value": False})
# desenfoques animados de los barridos
n = 0
for a, c in pal.items():
    for ef in c.get("effects") or []:
        if ef["type"] == "blur.gaussian" and ef["params"]["radius"].get("track"):
            cid = vids[a]
            fc.x("effects.apply", {"clips": [cid], "effect": "gaussian_blur"})
            ks = ef["params"]["radius"]["track"]["keyframes"]
            for k in ks:
                fc.x("effects.setParam", {"clip": cid, "effect": "gaussian_blur", "param": "blurriness", "value": k["value"], "time": fr(a + k["frame"]), "keyframe": True})
            for k in ks:
                fc.x("effects.setInterpolation", {"clip": cid, "effect": "gaussian_blur", "param": "blurriness", "mediaTime": fr(k["frame"]), "interpolation": INTERP.get(k["interpolationOut"], "linear")})
            fc.x("effects.setParam", {"clip": cid, "effect": "gaussian_blur", "param": "repeat_edge", "value": True})
            n += 1
print("clips", len(ids), "blurs", n)
fc.x("file.save", {})
