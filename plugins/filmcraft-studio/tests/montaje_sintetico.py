"""Montaje sintético para los tests: análisis de fixture, plan con todos los tipos de bloque y un motor falso
de FilmCraft que devuelve ids de clip ENTEROS (como el real: estado.json {"v": 22, "a": 23})."""
import json
from pathlib import Path

import plan_compile
from common import load_ds

DS_ID = "sbg-brutalista-s5"
PALABRAS = ("hola a todos bienvenidos a la sesión de hoy sobre inteligencia artificial en la nube "
            "vamos a ver cómo entrenar un modelo con datos reales y cuánto cuesta de verdad gracias").split()


def palabras(t0=0.3, paso=0.4, largo=0.3):
    """Una palabra cada `paso` s; la última termina con punto (cierra subtítulo)."""
    ws = [{"w": w, "s": round(t0 + i * paso, 3), "e": round(t0 + i * paso + largo, 3)} for i, w in enumerate(PALABRAS)]
    ws[-1]["w"] += "."
    return ws


def analisis(d, dur=20.0):
    an = Path(d) / "analisis"
    an.mkdir(parents=True, exist_ok=True)
    (an / "material.json").write_text(json.dumps({"videos": [
        {"stem": "charla", "path": str(Path(d) / "charla.mp4"), "dur": dur, "w": 1920, "h": 1080, "fps": 30, "audio": True}]}))
    (an / "charla.palabras.json").write_text(json.dumps(palabras()))
    return an


def plan(ds=DS_ID):
    """Gancho, contenido con barrido/matte/flash/glitch, fotos, tarjeta y cierre con capa y eco al final."""
    fotos = [str(Path(load_ds(DS_ID)["fondos"]["plano"]))] * 3
    return {"ds": ds, "bloques": [
        {"id": "gancho", "tipo": "gancho", "planos": [{"src": "charla", "in": 0.45, "out": 3.1}],     # 0.45 cae en «hola»
         "textos": [{"rol": "etiqueta", "texto": "IA", "palabra": "sesión"}]},
        {"id": "medio", "tipo": "contenido", "transicion": "barrido", "planos": [
            {"src": "charla", "in": 3.1, "out": 5.0},
            {"src": "charla", "in": 5.2, "out": 7.0, "entrada": "matte"},
            {"src": "charla", "in": 7.2, "out": 8.5, "entrada": "glitch"}],
         "textos": [{"rol": "eco", "texto": "100 USD", "t": 0.5}],
         "sfx": [{"tipo": "pop", "t": 0.2}]},
        {"id": "fotos", "tipo": "fotos", "fotos": fotos},
        {"id": "titulo", "tipo": "tarjeta"},
        {"id": "cierre", "tipo": "cierre", "dur": 2.0,
         "capas": [{"t": 1.5, "dur": 1.5}],                         # pasaría 1 s del final
         "textos": [{"rol": "eco", "texto": "FIN", "t": 1.9}],     # el eco dura más que lo que queda
         "sfx": [{"tipo": "titulo", "t": 1.7}]},                    # 0,5 s desde 13,1: pasaría del final
    ]}


def compilar(d, p=None, brief=None):
    an = analisis(d)
    p = p or plan()
    ds = load_ds(p["ds"])
    return plan_compile.Compiler(p, ds, an, brief).compile()


class MotorInt:
    """Engine falso: ids de clip enteros y crecientes, como FilmCraft."""

    def __init__(self, falla_en=None):
        self.n, self.calls, self._items, self.falla_en = 100, [], {}, falla_en
        self.saved, self.closed = [], False

    def _id(self):
        self.n += 1
        return self.n

    def place(self, path, track, start, dur=None, source_in=None, audio=True, audio_track=None, video=True):
        if self.falla_en and self.falla_en(track, path):
            raise RuntimeError(f"timeline.place falló en {track}")
        cl = [self._id()]
        if audio and video:
            cl.append(self._id())
        self.calls.append(("place", track, str(path), start, dur, tuple(cl), audio_track))
        return cl

    def x(self, cmd, params=None):
        self.calls.append(("x", cmd, params))
        return {}

    def kf(self, clip, effect, param, rows, *a):
        self.calls.append(("kf", clip, effect, param, rows))

    def param(self, clip, effect, param, value):
        self.calls.append(("param", clip, effect, param, value))

    def snap(self, s):
        return round(round(s * 30) / 30, 6)

    def scale_to_frame(self, clips):
        self.calls.append(("scale_to_frame", tuple(clips)))

    def new_text(self, text, track, start, dur, font, style, size, clip=None):
        cid = clip or self._id()
        self.calls.append(("text", track, text, start, dur, cid))
        return {"clip": cid, "layer": len([c for c in self.calls if c[0] == "text" and c[5] == cid]) - 1}

    def center_layer(self, clip, layer, cx, cy, align="Center"):
        return {"effectIndex": 0}, (200.0, 80.0)

    def layers(self, clip):
        n = len([c for c in self.calls if c[0] == "text" and c[5] == clip])
        return [{"layer": i, "localBounds": [0, 0, 120, 60], "effectIndex": 0} for i in range(n)]

    def clip(self, cid):
        return {"effects": [{"effect": "gaussian_blur"}]}

    def new_project(self, *a):
        self.calls.append(("new_project",) + a)

    def name_tracks(self, *a):
        pass

    def save(self):
        self.saved.append(None)

    def save_as(self, path):
        Path(path).write_text("{}")
        self.saved.append(str(path))
        return {"bytes": 2}

    def close(self):
        self.closed = True

    # consultas para los tests
    def places(self, track=None):
        return [c for c in self.calls if c[0] == "place" and (track is None or c[1] == track)]

    def textos(self):
        return [c for c in self.calls if c[0] == "text"]
