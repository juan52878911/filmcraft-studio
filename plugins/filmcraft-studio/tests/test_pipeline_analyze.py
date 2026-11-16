"""analyze_media: la caché no guarda fallos y depende de idioma/modelo; RAW relativo; anotaciones de whisper."""
import json

import pytest

import analyze_media
from common import ErrorExterno


def test_fallo_no_se_cachea(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")

    def falla():
        raise ErrorExterno("ffmpeg falló")
    with pytest.raises(ErrorExterno):
        analyze_media.cached(tmp_path, "v", "energy", src, falla)
    assert not (tmp_path / "v.energy.json").exists()
    assert analyze_media.cached(tmp_path, "v", "energy", src, lambda: [-20.0]) == [-20.0]


def test_energia_y_silencios_lanzan_si_ffmpeg_falla(tmp_path, monkeypatch):
    def run_falla(*a, **k):
        raise ErrorExterno("ffmpeg falló (código 1)")
    monkeypatch.setattr(analyze_media, "run", run_falla)
    with pytest.raises(ErrorExterno):
        analyze_media.energy(tmp_path / "v.mp4")
    with pytest.raises(ErrorExterno):
        analyze_media.silences(tmp_path / "v.mp4")


def test_clave_con_parametros(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    n = {"llamadas": 0}

    def fn():
        n["llamadas"] += 1
        return [n["llamadas"]]
    assert analyze_media.cached(tmp_path, "v", "words", src, fn, "lang=es|modelo=m") == [1]
    assert analyze_media.cached(tmp_path, "v", "words", src, fn, "lang=es|modelo=m") == [1]   # caché
    assert analyze_media.cached(tmp_path, "v", "words", src, fn, "lang=en|modelo=m") == [2]   # otro idioma
    assert analyze_media.cached(tmp_path, "v", "words", src, fn, "lang=en|modelo=large") == [3]
    j = json.loads((tmp_path / "v.words.json").read_text())
    assert j["_stamp"].startswith("v" + analyze_media.CACHE_VERSION)


def test_raw_relativo_a_la_carpeta(tmp_path):
    base = tmp_path / "RAW" / "evento"
    (base / "RAW").mkdir(parents=True)
    (base / "a.mp4").write_bytes(b"x")
    (base / "RAW" / "b.mp4").write_bytes(b"x")
    got = analyze_media.collect([base], (".mp4",))
    assert [p.name for p in got] == ["a.mp4"]            # la de dentro de RAW/ se excluye; la carpeta dada no


def test_refine_descarta_anotaciones():
    ws = [{"w": "(sonido", "s": 0, "e": 0.5}, {"w": "distorsionado)", "s": 0.5, "e": 1},
          {"w": "[música]", "s": 1, "e": 2}, {"w": "hola", "s": 2, "e": 2.4}]
    assert [w["w"] for w in analyze_media.refine(ws, [])] == ["hola"]
    ws = [{"w": "♪", "s": 0, "e": 0.2}, {"w": "la", "s": 0.2, "e": 0.4}, {"w": "♪", "s": 0.4, "e": 0.6},
          {"w": "Gracias.", "s": 1, "e": 1.5}, {"w": "(risas)", "s": 2, "e": 2.5}, {"w": "vale", "s": 3, "e": 3.2}]
    assert [w["w"] for w in analyze_media.refine(ws, [])] == ["Gracias.", "vale"]


def test_refine_anotacion_sin_cerrar_no_se_come_la_transcripcion():
    ws = [{"w": "(aplausos", "s": 0, "e": 0.5}] + [{"w": w, "s": 1 + i * 0.4, "e": 1.3 + i * 0.4} for i, w in
                                                   enumerate("hola a todos y bienvenidos a la sesión de hoy".split())]
    ws.append({"w": "adiós.", "s": 30, "e": 30.5})
    avisos = []
    out = [w["w"] for w in analyze_media.refine(ws, [], avisos)]
    assert out[-1] == "adiós." and "sesión" in out and avisos
    # con un hueco de más de 1 s tras la anotación, lo que sigue ya es voz
    ws = [{"w": "(música", "s": 0, "e": 0.5}, {"w": "suave", "s": 0.5, "e": 0.9}, {"w": "hola", "s": 3, "e": 3.4}]
    assert [w["w"] for w in analyze_media.refine(ws, [])] == ["hola"]
    # cerrada a las pocas palabras: se descarta entera, como antes
    ws = [{"w": "(sonido", "s": 0, "e": 0.3}, {"w": "de", "s": 0.3, "e": 0.5}, {"w": "fondo)", "s": 0.5, "e": 0.8},
          {"w": "vale", "s": 0.9, "e": 1.2}]
    assert [w["w"] for w in analyze_media.refine(ws, [])] == ["vale"]
