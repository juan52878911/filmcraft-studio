"""verify en positivo y en negativo: lo que detecta tiene que poder detectarse (overlap, kf_check, cut_check,
duración, pop-ups sobre caras) y lo no medido no puede salir como «0 problemas»."""
import json
import math
import os
import shutil
import struct
import sys
import wave

import pytest

pytest.importorskip("PIL")
import verify  # noqa: E402
from fclib import TPS  # noqa: E402

DS_ID = "sbg-brutalista-s5"


# ---------- funciones puras ----------
def test_overlap():
    assert verify.overlap([0, 0, 1, 1], [0, 0, 0.5, 0.5]) == pytest.approx(1.0)        # b dentro de a
    assert verify.overlap([0, 0, 0.25, 0.5], [0, 0, 0.5, 0.5]) == pytest.approx(0.5)
    assert verify.overlap([0.6, 0.6, 1, 1], [0, 0, 0.5, 0.5]) == 0
    assert verify.overlap([0, 0, 1, 1], [0.2, 0.2, 0.2, 0.4]) == 0                     # área nula


def clip(cid, start, dur, item=2, source_in=0.0, speed=1, kfs=()):
    c = {"id": cid, "start": round(start * TPS), "duration": round(dur * TPS), "item": item,
         "source_in": round(source_in * TPS), "speed": speed}
    if kfs:
        c["effects"] = [{"effect": "motion", "params": {"scale": {"keyframes": [{"time": round(t * TPS)} for t in kfs]}}}]
    return c


def seq(main, dialogo=()):
    return {"video_tracks": [{"name": "Main", "clips": list(main)}], "audio_tracks": [{"name": "Dialogue", "clips": list(dialogo)}]}


def test_kf_check_marca_solo_lo_de_fuera():
    s = seq([clip(1, 0, 2, source_in=5, kfs=(5.0, 6.0, 7.0)),          # dentro (5–7)
             clip(2, 2, 2, source_in=0, speed=2, kfs=(3.9,)),           # dentro: 2 s a ×2 = 4 s de media
             clip(3, 4, 1, source_in=1, kfs=(0.5, 2.4))])              # 0.5 y 2.4 fuera de 1–2
    r = verify.kf_check(s)
    assert r["keyframes"] == 6 and r["n_fuera"] == 2
    assert {b["clip"] for b in r["fuera_de_rango"]} == {3}


def test_cut_check_dentro_y_fuera_de_palabra(tmp_path):
    (tmp_path / "v.palabras.json").write_text(json.dumps([{"w": "hola", "s": 1.0, "e": 1.5}, {"w": "mundo", "s": 2.0, "e": 2.6}]))
    s = seq([], [clip(1, 0, 1.2, source_in=0.0),          # salida en 1.2: dentro de «hola»
                 clip(2, 1.2, 0.3, source_in=1.6)])        # 1.6–1.9: fuera
    r = verify.cut_check(s, {2: "/x/v.mp4"}, tmp_path)
    assert r["bordes"] == 4 and r["medido"]
    assert [(c["clip"], c["borde"], c["palabra"]) for c in r["dentro_de_palabra"]] == [(1, "salida", "hola")]


def test_cut_check_sin_palabras_no_es_cero_problemas(tmp_path):
    r = verify.cut_check(seq([], [clip(1, 0, 1.2)]), {2: "/x/v.mp4"}, tmp_path)
    assert r["bordes"] == 0 and r["medido"] is False and r["clips_sin_palabras"]


def test_main_cuts():
    cuts, n = verify.main_cuts(seq([clip(2, 2, 1), clip(1, 0, 2), clip(3, 3, 1)]))
    assert cuts == [2.0, 3.0] and n == 3


def wav(p, segundos=5.0, db=-20.0, sr=48000):
    a = 10 ** (db / 20) * 32767
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(a * math.sin(2 * math.pi * 997 * i / sr))) for i in range(int(sr * segundos))))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sin ffmpeg")
def test_curva_no_pinta_mudo_el_arranque(tmp_path):
    """Con solo el corto plazo (S) los 3 primeros segundos salían a −70 aunque hubiera voz desde el inicio."""
    wav(tmp_path / "m.wav")
    r = verify.medir_wav(tmp_path / "m.wav")
    assert r["lufs"] is not None and len(r["curva_s"]) >= 4
    assert all(v > -40 for v in r["curva_s"][:3]), r["curva_s"]


# ---------- verify.py de punta a punta con un CLI y un detector falsos ----------
FAKE_CLI = r'''#!{py}
import json, math, shutil, struct, sys, wave
a = sys.argv[1:]
proj = a[a.index("--project") + 1]
if "--save-as" in a:
    shutil.copy(proj, a[a.index("--save-as") + 1]); sys.exit(0)
if "render" in a:
    from PIL import Image
    Image.new("RGB", (270, 480), "gray").save(a[a.index("--out") + 1]); sys.exit(0)
if "export" in a:
    out = a[a.index("export") + 1]
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
        amp = 10 ** (-20 / 20) * 32767
        w.writeframes(b"".join(struct.pack("<h", int(amp * math.sin(2 * math.pi * 997 * i / 48000))) for i in range(48000 * 4)))
    sys.exit(0)
sys.exit(1)
'''

FAKE_VISION = r'''#!{py}
import json, os, sys
cara = json.loads(os.environ.get("CARA_FALSA", "[]"))
for p in sys.argv[1:]:
    print(json.dumps({{"path": p, "faces": cara, "people": []}}))
'''


def montaje(w, malo):
    """WORK con un .fcproj de 4 s; `malo` mete un keyframe fuera, un corte en palabra y un SFX que pasa del final."""
    dia = [clip(20, 0, 2, source_in=0.0), clip(21, 2, 2, source_in=1.2 if malo else 1.6)]
    main = [clip(10, 0, 2, kfs=(0.5,) + ((9.0,) if malo else ())), clip(11, 2, 2, source_in=1.6)]
    audio = [{"name": "Dialogue", "clips": dia}, {"name": "SFX", "clips": [clip(30, 3.5, 1.0 if malo else 0.5, item=3)]}]
    proj = {"project": {"items": {
        "1": {"kind": {"Sequence": {"video_tracks": [{"name": "Main", "clips": main}], "audio_tracks": audio}}},
        "2": {"name": "v.mp4", "kind": {"Media": {"media": {"File": {"path": "/no/v.mp4"}}}}},
        "3": {"name": "pop.wav", "kind": {"Media": {"media": {"File": {"path": "/no/pop.wav"}}}}}}}}
    (w / "Reel.fcproj").write_text(json.dumps(proj))
    comp = {"ds": DS_ID, "fps": 30, "duracion": 4.0, "cobertura": {}, "bloques": [], "segmentos": [], "transiciones": [],
            "textos": [], "subtitulos": [], "sfx": [], "ajustes_corte": [], "avisos": [], "cortes": 1}
    (w / "compiled.json").write_text(json.dumps(comp))
    (w / "estado.json").write_text(json.dumps({"modo": "headless", "textos": {
        "t1": {"rol": "etiqueta", "start": 1.0, "dur": 1.0, "box": [0.1, 0.1, 0.5, 0.3], "texto": "Hola"}}}))
    (w / "brief.json").write_text(json.dumps({"duracion_s": {"valor": 4, "origen": "dado", "confianza": 1}}))
    (w / "plan.json").write_text(json.dumps({"titulo": "Prueba"}))
    an = w / "analisis"
    an.mkdir()
    (an / "v.palabras.json").write_text(json.dumps([{"w": "hola", "s": 1.0, "e": 1.5}, {"w": "mundo", "s": 2.0, "e": 2.6}]))


def falsos(tmp_path):
    data = tmp_path / "data"
    (data / "bin").mkdir(parents=True)
    cli, vis = tmp_path / "fc-cli", data / "bin" / "vision_detect"
    cli.write_text(FAKE_CLI.replace("{py}", sys.executable))
    vis.write_text(FAKE_VISION.format(py=sys.executable))
    for f in (cli, vis):
        f.chmod(0o755)
    os.utime(vis, (2e9, 2e9))                     # más nuevo que vision_detect.swift: no lo recompila
    return {"FILMCRAFT_CLI": str(cli), "CLAUDE_PLUGIN_DATA": str(data)}


def verificar(run_script, w, env):
    r = run_script("verify.py", w / "Reel.fcproj", "--compiled", w / "compiled.json", "--analisis", w / "analisis",
                   "--out", w / "verificacion", env=env)
    return r, json.loads((w / "verificacion/verificacion.json").read_text())


needs = pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("ffmpeg"), reason="detector de macOS y ffmpeg")


@needs
def test_verify_positivo(tmp_path, run_script):
    montaje(tmp_path, malo=False)
    env = falsos(tmp_path) | {"CARA_FALSA": "[[0.6, 0.6, 0.2, 0.2]]"}          # cara lejos del pop-up
    r, ver = verificar(run_script, tmp_path, env)
    assert r.returncode == 0, r.stderr
    assert ver["verificado"] and not ver["fallos"]
    assert ver["textos_vs_caras"]["medido"] and ver["textos_vs_caras"]["choques"] == []
    assert ver["keyframes"]["n_fuera"] == 0 and ver["keyframes"]["keyframes"] == 1
    assert ver["cortes_en_palabra"]["bordes"] == 4 and not ver["cortes_en_palabra"]["dentro_de_palabra"]
    assert ver["audio"]["lufs"] == pytest.approx(-23, abs=2) and ver["duracion_s"] == 4.0
    r = run_script("report.py", tmp_path)
    md = (tmp_path / "informe.md").read_text()
    for fila in ("| Cortes dentro", "| Keyframes", "| Pop-ups", "| Duración"):
        assert "✅" in next(l for l in md.splitlines() if l.startswith(fila)), fila


@needs
def test_verify_negativo(tmp_path, run_script):
    montaje(tmp_path, malo=True)
    env = falsos(tmp_path) | {"CARA_FALSA": "[[0.4, 0.25, 0.2, 0.1]]"}          # un cuarto de la cara bajo el pop-up
    r, ver = verificar(run_script, tmp_path, env)
    assert r.returncode == 2
    assert [c["texto"] for c in ver["textos_vs_caras"]["choques"]] == ["Hola"]
    assert ver["keyframes"]["n_fuera"] == 1
    assert [c["palabra"] for c in ver["cortes_en_palabra"]["dentro_de_palabra"]] == ["hola"]
    assert ver["duracion_s"] == 4.5 and any("algo pasa del final" in f for f in ver["fallos"])
    r = run_script("report.py", tmp_path)
    md = (tmp_path / "informe.md").read_text()
    for fila in ("| Cortes dentro", "| Keyframes", "| Pop-ups", "| Duración"):
        assert "⚠️" in next(l for l in md.splitlines() if l.startswith(fila)), fila


@needs
def test_sin_palabras_es_sin_medir(tmp_path, run_script):
    montaje(tmp_path, malo=False)
    (tmp_path / "analisis/v.palabras.json").unlink()
    r, ver = verificar(run_script, tmp_path, falsos(tmp_path))
    assert r.returncode == 2 and any("palabras.json" in f for f in ver["fallos"])
    run_script("report.py", tmp_path)
    fila = next(l for l in (tmp_path / "informe.md").read_text().splitlines() if l.startswith("| Cortes dentro"))
    assert "sin medir" in fila and "✅" not in fila
