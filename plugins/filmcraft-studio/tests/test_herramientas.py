"""herramientas.py --doctor: código de salida según lo obligatorio, sin instalar nada."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "scripts"


def doctor(tmp_path, path, extra=None, *args):
    env = {"PATH": path, "HOME": str(tmp_path / "home"), "FILMCRAFT_CLI": str(tmp_path / "no-hay"),
           "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"), "PYTHONPYCACHEPREFIX": str(tmp_path / "pyc")}
    env.update(extra or {})
    return subprocess.run([sys.executable, str(SCRIPTS / "herramientas.py"), "--doctor", "--json", *args],
                          capture_output=True, text=True, env=env)


def test_doctor_con_path_vacio_sale_1(tmp_path):
    r = doctor(tmp_path, "")
    assert r.returncode == 1, r.stderr
    j = json.loads(r.stdout)
    assert j["ok"] is False
    falta = {c["nombre"] for c in j["comprobaciones"] if c["nivel"] == "obligatorio" and not c["ok"]}
    assert {"ffmpeg", "ffprobe", "FilmCraft CLI"} <= falta
    assert all(c["arreglo"] for c in j["comprobaciones"] if not c["ok"])   # cada fallo dice cómo arreglarlo


def test_doctor_con_lo_obligatorio_sale_0(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    for n in ("ffmpeg", "ffprobe", "filmcraft-cli"):
        (b / n).write_text("#!/bin/sh\nexit 0\n")
        (b / n).chmod(0o755 | stat.S_IEXEC)
    r = doctor(tmp_path, str(b), {"FILMCRAFT_CLI": str(b / "filmcraft-cli")})
    j = json.loads(r.stdout)
    assert r.returncode == 0, [c for c in j["comprobaciones"] if not c["ok"] and c["nivel"] == "obligatorio"]


def test_doctor_no_imprime_secretos(tmp_path):
    r = doctor(tmp_path, "", {"ELEVENLABS_API_KEY": "sk-secreto-123"})
    assert "sk-secreto-123" not in r.stdout
    c = next(c for c in json.loads(r.stdout)["comprobaciones"] if c["nombre"].startswith("ElevenLabs"))
    assert c["ok"] and c["nivel"] == "opcional"


def test_doctor_ds_inexistente(tmp_path):
    r = doctor(tmp_path, "", None, "--ds", "no-existe")
    assert r.returncode == 1


def test_licencia_filmcraft_apache():
    sys.path.insert(0, str(SCRIPTS))
    import herramientas
    fc = next(h for h in herramientas.CATALOGO if h[0] == "FilmCraft")
    assert fc[6] == "Apache-2.0"
    op = (PLUGIN / "skills/editor-filmcraft/references/filmcraft-operativa.md").read_text()
    assert "Apache-2.0" in op


def test_para_valida_el_motor(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "herramientas.py"), "--para", "3D-mal"], capture_output=True,
                       text=True, env=dict(os.environ, PYTHONPYCACHEPREFIX=str(tmp_path / "pyc")))
    assert r.returncode == 2


def _bin_obligatorio(tmp_path, *extra):
    b = tmp_path / "bin"
    b.mkdir(exist_ok=True)
    for n in ("ffmpeg", "ffprobe", "filmcraft-cli", *extra):
        (b / n).write_text("#!/bin/sh\nexit 0\n")
        (b / n).chmod(0o755 | stat.S_IEXEC)
    return b


def _modelo(j):
    return next(c for c in j["comprobaciones"] if c["nombre"] == "modelo ggml de whisper")


def test_doctor_para_camara_exige_whisper_y_su_modelo(tmp_path):
    b = _bin_obligatorio(tmp_path, "whisper-cli")
    env = {"FILMCRAFT_CLI": str(b / "filmcraft-cli"), "FILMCRAFT_WHISPER_MODEL": str(tmp_path / "no-hay.bin")}
    assert doctor(tmp_path, str(b), env).returncode == 0                       # sin --para: recomendado
    r = doctor(tmp_path, str(b), env, "--para", "camara")
    j = json.loads(r.stdout)
    assert r.returncode == 1 and _modelo(j)["nivel"] == "obligatorio" and not _modelo(j)["ok"]
    (tmp_path / "no-hay.bin").write_bytes(b"x")
    assert doctor(tmp_path, str(b), env, "--para", "camara").returncode == 0


def test_doctor_busca_el_modelo_donde_analyze_media(tmp_path):
    """Misma búsqueda que common.whisper_model: <datos>/models, ~/.cache/filmcraft-studio/models y ~/.cache/whisper."""
    if any(Path(d, "ggml-medium.bin").exists() for d in ("/opt/homebrew/share/whisper-cpp", "/usr/local/share/whisper-cpp")):
        pytest.skip("hay un modelo de sistema que gana a las rutas de usuario")
    b = _bin_obligatorio(tmp_path, "whisper-cli")
    env = {"FILMCRAFT_CLI": str(b / "filmcraft-cli")}
    r = doctor(tmp_path, str(b), env, "--para", "camara")
    assert r.returncode == 1 and "~/.cache/whisper" in _modelo(json.loads(r.stdout))["arreglo"]
    for rel in ("data/models", "home/.cache/filmcraft-studio/models", "home/.cache/whisper"):
        m = tmp_path / rel / "ggml-medium.bin"
        m.parent.mkdir(parents=True)
        m.write_bytes(b"x")
        r = doctor(tmp_path, str(b), env, "--para", "camara")
        assert r.returncode == 0 and _modelo(json.loads(r.stdout))["detalle"] == str(m), rel
        m.unlink()


def _por_nombre(j, nombre):
    return next((c for c in j["comprobaciones"] if c["nombre"] == nombre), None)


def test_doctor_para_promo_no_exige_filmcraft_y_mira_vhs(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    for n in ("ffmpeg", "ffprobe"):
        (b / n).write_text("#!/bin/sh\nexit 0\n")
        (b / n).chmod(0o755 | stat.S_IEXEC)
    assert doctor(tmp_path, str(b)).returncode == 1                       # sin --para: FilmCraft CLI obligatorio
    r = doctor(tmp_path, str(b), None, "--para", "promo")
    j = json.loads(r.stdout)
    assert r.returncode == 0, [c for c in j["comprobaciones"] if c["nivel"] == "obligatorio" and not c["ok"]]
    assert _por_nombre(j, "FilmCraft CLI")["nivel"] == "recomendado"
    vhs = _por_nombre(j, "VHS (terminal grabada)")
    assert vhs and not vhs["ok"] and "vhs" in vhs["arreglo"]
    (b / "vhs").write_text("#!/bin/sh\nexit 0\n")
    (b / "vhs").chmod(0o755 | stat.S_IEXEC)
    assert _por_nombre(json.loads(doctor(tmp_path, str(b), None, "--para", "promo").stdout),
                       "VHS (terminal grabada)")["ok"]
    assert _por_nombre(json.loads(doctor(tmp_path, str(b)).stdout), "VHS (terminal grabada)") is None


def test_para_promo_filtra_herramientas(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "herramientas.py"), "--para", "promo", "--json"],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONPYCACHEPREFIX=str(tmp_path / "pyc")))
    assert r.returncode == 0, r.stderr
    nombres = {h["nombre"] for h in json.loads(r.stdout)}
    assert {"VHS", "ffmpeg"} <= nombres and "Blender" not in nombres
