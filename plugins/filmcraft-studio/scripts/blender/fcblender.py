"""Preludio que motor_blender.py pasa a Blender (-P): prepara la escena desde el DS y ejecuta ESCENA.py con `fc`.

No se llama a mano: Blender -b --factory-startup -P fcblender.py -- fc_blender.json
"""
import json
import math
import sys
from types import SimpleNamespace

import bpy

cfg = json.load(open(sys.argv[sys.argv.index("--") + 1]))
ds = cfg["ds"]
lz = ds["lienzo"]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x = int(lz["ancho"] * cfg["escala"]) // 2 * 2
sc.render.resolution_y = int(lz["alto"] * cfg["escala"]) // 2 * 2
sc.render.resolution_percentage = 100
sc.render.fps = max(1, round(lz["fps"]))           # 29,97 -> fps 30 / fps_base 1,001
sc.render.fps_base = sc.render.fps / lz["fps"]
sc.frame_start = 1
sc.frame_end = max(1, round(cfg["segundos"] * lz["fps"]))
sc.render.image_settings.file_format = "PNG"
sc.view_settings.view_transform = "Standard"     # los hex del DS salen tal cual (AgX/Filmic los desplazan)
sc.view_settings.look = "None"

if cfg["motor"] == "cycles":
    sc.render.engine = "CYCLES"
    sc.cycles.samples = cfg["muestras"]
    sc.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception as e:  # sin Metal: CPU
        print("GPU no disponible:", e)
else:
    for ident in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):   # el nombre cambió entre 4.2 y 5.x
        try:
            sc.render.engine = ident
            break
        except TypeError:
            continue
    try:
        sc.eevee.taa_render_samples = cfg["muestras"]
    except AttributeError:
        pass


def lineal(hexs, a=1.0):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (ch(int(hexs[1:3], 16)), ch(int(hexs[3:5], 16)), ch(int(hexs[5:7], 16)), a)


def color(rol, a=1.0):
    return lineal(ds["paleta"].get(rol, rol) if not rol.startswith("#") else rol, a)


_fuentes = {}


def fuente(rol):
    if rol not in _fuentes:
        path = cfg["fuentes"].get(rol)
        _fuentes[rol] = bpy.data.fonts.load(path) if path else None
    return _fuentes[rol]


def material(rol, emision=0.0, rugosidad=0.5, nombre=None):
    m = bpy.data.materials.new(nombre or f"{rol}_{emision}")
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = color(rol)
    b.inputs["Roughness"].default_value = rugosidad
    if emision:
        b.inputs["Emission Color" if "Emission Color" in b.inputs else "Emission"].default_value = color(rol)  # <4.0
        b.inputs["Emission Strength"].default_value = emision
    return m


def fondo(rol="fondo", fuerza=1.0):
    w = bpy.data.worlds.new("fondo")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = color(rol)
    bg.inputs["Strength"].default_value = fuerza
    sc.world = w


def ease(a, b, t):
    t = min(1.0, max(0.0, t))
    t = t * t * (3 - 2 * t)
    return a + (b - a) * t


fc = SimpleNamespace(ds=ds, p=cfg["p"], fps=lz["fps"], frames=sc.frame_end, escena=sc, color=color,
                     fuente=fuente, material=material, fondo=fondo, ease=ease, math=math,
                     f=lambda s: 1 + round(s * lz["fps"]))

src = open(cfg["escena"]).read()
exec(compile(src, cfg["escena"], "exec"), {"bpy": bpy, "fc": fc, "__name__": "__escena__"})

if cfg["fotogramas"]:
    for n in cfg["fotogramas"]:
        sc.frame_set(n)
        sc.render.filepath = f"{cfg['dir']}/f_{n:04d}.png"
        bpy.ops.render.render(write_still=True)
else:
    sc.render.filepath = f"{cfg['dir']}/f_"
    bpy.ops.render.render(animation=True)
