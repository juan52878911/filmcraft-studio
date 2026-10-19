from palmier import *  # noqa: F401,F403
fc = FC(); tl, T, media = load()
# pistas FilmCraft (abajo -> arriba): V1 Fondo, V2 Main, V3 Tarjeta, V4 Producto, V5 Brand, V6 Captions,
# V7 Labels, V8 Pills, V9 Tags, V10 Eco, V11 Mattes
TRK = {"Fondo": "V1", "Main": "V2", "Tarjeta": "V3", "Producto": "V4", "Mattes": "V11"}
names = {"V1":"Fondo","V2":"Main","V3":"Tarjeta","V4":"Producto","V5":"Brand","V6":"Captions","V7":"Labels","V8":"Pills","V9":"Tags","V10":"Eco","V11":"Mattes"}
for v,n in names.items(): fc.x("timeline.setTrack", {"track": v, "name": n})
# limpiar la prueba anterior
s = fc.seq()
old = [c["clip"] for t in s["video"] if t["name"] in ("Mattes","Video 11") for c in t["items"]]
if old: fc.x("edit.clear", {"clips": old})
# importar imágenes
need = {}
for tn in TRK:
    for c in T[tn]["clips"]:
        if c["mediaType"] == "image": need[c["mediaRef"]] = path_of(media[c["mediaRef"]])
paths = sorted(set(need.values()))
r = fc.x("file.import", {"paths": paths})
item_of_path = dict(zip(paths, r["items"]))
log = []
def setkf(clip, effect, param, rows, start):
    """rows: [(frame_rel, value, interp)]"""
    for f, val, it in rows:
        fc.x("effects.setParam", {"clip": clip, "effect": effect, "param": param, "value": val, "time": fr(start + f), "keyframe": True})
    for f, val, it in rows:
        fc.x("effects.setInterpolation", {"clip": clip, "effect": effect, "param": param, "mediaTime": fr(f), "interpolation": INTERP.get(it, "linear")})
for tn, trk in TRK.items():
    for c in T[tn]["clips"]:
        if c["mediaType"] != "image": continue
        e = media[c["mediaRef"]]; sw, sh = e["sourceWidth"], e["sourceHeight"]
        a, d = c["startFrame"], c["durationFrames"]
        clip = fc.x("timeline.place", {"item": item_of_path[need[c["mediaRef"]]], "track": trk, "frame": a, "duration": fr(d), "audio": False})["clips"][0]
        base = min(W / sw, H / sh) * 100           # "encajar" de Palmier
        tf = c["transform"]
        sk, pk = kfs(c, "scaleTrack"), kfs(c, "positionTrack")
        def size_at(f):
            if sk:
                prev = [k for k in sk if k["frame"] <= f] or sk[:1]
                v = prev[-1]["value"]; return v["a"], v["b"]
            return tf["width"], tf["height"]
        if sk:
            setkf(clip, "motion", "scale", [(k["frame"], base * k["value"]["a"] * (1 if tf["width"] else 1), k["interpolationOut"]) for k in sk], a)
        elif abs(tf["width"] - 1) > 1e-6 and sw / sh == W / H:
            fc.x("effects.setParam", {"clip": clip, "effect": "motion", "param": "scale", "value": base * tf["width"]})
        else:
            fc.x("effects.setParam", {"clip": clip, "effect": "motion", "param": "scale", "value": base})
        if pk:
            rows = []
            for k in pk:
                w_, h_ = size_at(k["frame"])
                rows.append((k["frame"], [(k["value"]["a"] + w_ / 2) * W, (k["value"]["b"] + h_ / 2) * H], k["interpolationOut"]))
            setkf(clip, "motion", "position", rows, a)
        ck = kfs(c, "cropTrack")
        if ck:
            fc.x("effects.apply", {"clips": [clip], "effect": "crop"})
            for side in ("left", "top", "right", "bottom"):
                setkf(clip, "crop", side, [(k["frame"], k["value"][side] * 100, k["interpolationOut"]) for k in ck], a)
        if c.get("opacity", 1) < 1:
            fc.x("effects.setParam", {"clip": clip, "effect": "opacity", "param": "opacity", "value": c["opacity"] * 100})
        for ef in c.get("effects") or []:
            if ef["type"] == "blur.gaussian":
                fc.x("effects.apply", {"clips": [clip], "effect": "gaussian_blur"})
                tr_ = ef["params"]["radius"].get("track")
                if tr_:
                    setkf(clip, "gaussian_blur", "blurriness", [(k["frame"], k["value"], k["interpolationOut"]) for k in tr_["keyframes"]], a)
                else:
                    fc.x("effects.setParam", {"clip": clip, "effect": "gaussian_blur", "param": "blurriness", "value": ef["params"]["radius"]["value"]})
        log.append((tn, e["name"], a, d, clip))
for l in log: print(l)
fc.x("file.save", {})
