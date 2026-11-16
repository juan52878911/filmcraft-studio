"""fcengine.Engine contra un backend falso: ticks de fotograma exactos, mediaTime con speed y caché de la secuencia."""
import pytest

import fcengine
from fclib import TPS


class Backend:
    def __init__(self, fps=(30000, 1001)):
        self.calls, self.inspects = [], 0
        self.fps = fps

    def x(self, cmd, params):
        self.calls.append((cmd, params))
        if cmd == "sequence.inspect":
            self.inspects += 1
            return {"settings": {"frame_rate": {"num": self.fps[0], "den": self.fps[1]}}, "video": [], "audio": []}
        if cmd == "timeline.place":
            return {"clips": [7, 8]}
        return {}

    def close(self):
        pass


def engine(**k):
    return fcengine.Engine(Backend(**k), "headless")


def test_tk_cae_en_el_fotograma_exacto():
    e = engine()
    fps = 30000 / 1001
    assert e.tk(1.0) == round(30 * TPS / fps)                      # 1 s a 29,97 -> fotograma 30
    assert e.snap(1.01) == pytest.approx(30 / fps)


def test_kf_tiempo_de_secuencia_y_media_con_speed():
    e = engine(fps=(30, 1))
    e.kf(5, "motion", "scale", [(0, 100, "easeOut"), (1.0, 120, "linear")], 10.0, source_in=2.0, speed=2.0)
    sets = [p for c, p in e.b.calls if c == "effects.setParam"]
    assert [s["time"] for s in sets] == [e.tk(10.0), e.tk(11.0)] and all(s["keyframe"] for s in sets)
    inter = [p for c, p in e.b.calls if c == "effects.setInterpolation"]
    assert len(inter) == 1 and inter[0]["mediaTime"] == round(2.0 * TPS)        # solo el no lineal
    e.b.calls.clear()
    e.kf(5, "motion", "scale", [(1.0, 100, "easeIn")], 10.0, source_in=2.0, speed=2.0)
    mt = [p for c, p in e.b.calls if c == "effects.setInterpolation"][0]["mediaTime"]
    assert mt == round(2.0 * TPS) + round((e.tk(11.0) - e.tk(10.0)) * 2.0)       # 1 s de secuencia = 2 s de media


def test_place_duracion_en_ticks_de_fotograma():
    e = engine(fps=(30, 1))
    e._items["/a.mp4"] = 3
    e.tref = lambda name: {"Main": "V2", "Dialogue": "A1"}[name]
    assert e.place("/a.mp4", "Main", 1.0, 2.0, source_in=0.5, audio_track="Dialogue") == [7, 8]
    p = [p for c, p in e.b.calls if c == "timeline.place"][0]
    assert p["time"] == e.tk(1.0) and p["duration"] == e.tk(3.0) - e.tk(1.0) and p["sourceIn"] == round(0.5 * TPS)
    assert p["track"] == "V2" and p["audioTrack"] == "A1"


def test_cache_de_secuencia_se_invalida_con_cambios_de_estructura():
    e = engine()
    e.fps
    e.fps
    assert e.b.inspects == 1
    e.x("effects.setParam", {})                                     # solo un valor: la caché vale
    e.fps
    assert e.b.inspects == 1
    e.x("timeline.place", {})
    e.fps
    assert e.b.inspects == 2
