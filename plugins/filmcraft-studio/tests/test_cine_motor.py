"""Prueba de humo del motor `cine` de punta a punta, con un video generado por ffmpeg:
medir-video → criterios → puntuar → nota (con juicio de muestra y comparación con la mejor versión),
y elegir-ds con una paleta. Sin binario o sin ffmpeg, se salta."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
CINE = PLUGIN / "bin" / "cine"

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="hace falta ffmpeg")


def cine(*args, ok=(0,)):
    r = subprocess.run([str(CINE), *map(str, args)], capture_output=True, text=True)
    if r.returncode == 127:
        pytest.skip("bin/cine sin compilar (motor/compilar.sh)")
    assert r.returncode in ok, (r.returncode, r.stderr)
    return r


def js(*args, ok=(0,)):
    return json.loads(cine(*args, ok=ok).stdout)


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    """4,5 s en 1080x1920 a 30 fps: rojo 2 s, negro 0,5 s (a mitad: el motor debe verlo), amarillo 2 s,
    con un tono normalizado a −14 LUFS."""
    d = tmp_path_factory.mktemp("cine")
    v = d / "promo-9x16.mp4"
    f = ("color=c=red:s=1080x1920:r=30:d=2[a];color=c=black:s=1080x1920:r=30:d=0.5[b];"
         "color=c=yellow:s=1080x1920:r=30:d=2[c];[a][b][c]concat=n=3:v=1:a=0[v];"
         "sine=f=440:d=4.5,volume=0.3,loudnorm=I=-14:TP=-2:LRA=7[s]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", f, "-map", "[v]", "-map", "[s]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", str(v)], check=True)
    return d, v


def test_medir_criterios_puntuar_nota(video):
    d, v = video
    m = d / "medidas-9x16.json"
    cine("medir-video", v, "--out", m)
    med = json.loads(m.read_text())
    assert (med["formato"]["w"], med["formato"]["h"], med["formato"]["fps"]) == (1080, 1920, 30.0)
    assert 4.4 <= med["duracion_s"] <= 4.6
    assert len(med["cortes"]) >= 2                                   # rojo → negro → amarillo
    assert any(a >= 1.9 and b <= 2.6 for a, b in med["negros"])     # el negro de 2,0–2,5 s
    assert med["audio"]["lufs"] is not None and med["audio"]["curva_s"]

    biblia = d / "biblia.json"
    biblia.write_text(json.dumps({"estado": "aprobada", "ds": {"id": "promo-riso"}, "criterios": [
        {"id": "c1", "que": "9:16 1080x1920 de 4–5 s, 30 fps", "como": "ffprobe"},
        {"id": "c2", "que": "9:16 < 5 MB", "como": "ls"},
        {"id": "c3", "que": "sin negros a mitad", "como": "medir-video", "medida": [{"ruta": "n:negros", "max": 0}]},
        {"id": "c4", "que": "el cierre cierra la metáfora", "como": "critico-juicio", "juicio": True}]}))
    r = js("criterios", "--biblia", biblia, "--medidas", m, ok=(1,))      # c3 no cumple: sale con 1
    estados = {c["id"]: c["estado"] for c in r["criterios"]}
    assert estados == {"c1": "cumple", "c2": "cumple", "c3": "no cumple", "c4": "juicio"}
    md = cine("criterios", "--biblia", biblia, "--medidas", m, "--md", ok=(1,)).stdout
    assert md.startswith("| Criterio |") and "| c3 |" in md

    ejes = d / "ejes.json"
    cine("puntuar", "--ds", "promo-riso", "--biblia", biblia, "--medidas", m, "--out", ejes)
    e = json.loads(ejes.read_text())
    p = e["puntuaciones"]
    assert p["imagen"] == 4.0                                        # un negro a mitad resta 1
    assert p["criterios"] == 3.0                                     # un criterio medido no cumple
    lufs = med["audio"]["lufs"]
    if abs(lufs + 14) <= 1 and med["audio"]["pico_dbtp"] <= -1:
        assert p["audio"] == 5.0
    assert any(b["eje"] == "criterios" for b in e["bloqueantes"])
    assert [c["id"] for c in e["para_ia"]["criterios_de_juicio"]] == ["c4"]

    juicio = d / "juicio.json"
    juicio.write_text(json.dumps({"puntuaciones": {"historia": 4, "copy": 4, "originalidad": 5},
                                  "veredicto_estilo": "distinto", "criterios": [{"id": "c4", "estado": "cumple"}],
                                  "bloqueantes": [], "arreglos": [{"eje": "historia", "que": "gancho con la cifra"}],
                                  "no_tocar": ["el amarillo final"]}))
    n = js("nota", "--ejes", ejes, "--juicio", juicio, "--mejor", "4.5", "--bloq-anterior", "no", ok=(1,))
    assert n["veredicto"] == "no publicable"                         # hay un bloqueante medido
    assert n["clase"] == "Regresión" and n["mejor"] == "anterior"    # bloqueante nuevo: sin A/B
    assert not n["ab_necesario"]
    assert len(n["arreglos"]) <= 5 and n["arreglos"][-1] == "[historia] gancho con la cifra"


def test_elegir_ds_por_paleta():
    ds = json.loads((PLUGIN / "design-systems" / "sbg-brutalista-s5" / "ds.json").read_text())
    rk = js("elegir-ds", "--paleta", ",".join(ds["match"]["paleta_ref"]), "--para", "camara", "--json")
    assert rk[0]["id"] == "sbg-brutalista-s5" and rk[0]["color"] == 1.0
    assert not any(r["id"].startswith("promo-") for r in rk)
