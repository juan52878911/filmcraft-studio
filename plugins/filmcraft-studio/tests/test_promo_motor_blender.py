"""motor_blender.py: limpia los fotogramas de una pasada anterior y valida --param (sin Blender)."""
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import motor_blender  # noqa: E402


def test_limpiar_solo_borra_fotogramas(tmp_path):
    (tmp_path / motor_blender.MARCA).write_text("fotogramas\n")
    for n in ("f_0001.png", "f_0009.png", "hoja.png", "blender.log", "otra.png"):
        (tmp_path / n).write_bytes(b"x")
    motor_blender.limpiar(tmp_path, "fotogramas")
    assert sorted(p.name for p in tmp_path.iterdir()) == [motor_blender.MARCA, "blender.log", "otra.png"]


def test_limpiar_no_borra_lo_que_no_es_suyo(tmp_path):
    (tmp_path / "f_0001.png").write_bytes(b"x")                     # carpeta ajena: sin marca
    with pytest.raises(SystemExit):
        motor_blender.limpiar(tmp_path, "fotogramas")
    assert (tmp_path / "f_0001.png").exists()
    motor_blender.limpiar(tmp_path, "fotogramas", forzar=True)
    assert not (tmp_path / "f_0001.png").exists()


def test_fotogramas_sueltos_no_borran_un_render_completo(tmp_path):
    (tmp_path / "fc_blender.json").write_text('{"fotogramas": []}')  # pasada anterior (sin marca): animación
    (tmp_path / "f_0001.png").write_bytes(b"x")
    with pytest.raises(SystemExit):
        motor_blender.limpiar(tmp_path, "fotogramas")
    assert (tmp_path / "f_0001.png").exists()
    motor_blender.limpiar(tmp_path, "animacion")                   # el mismo modo sí la limpia
    assert not (tmp_path / "f_0001.png").exists() and (tmp_path / motor_blender.MARCA).read_text().strip() == "animacion"


def test_carpeta_vacia_queda_marcada(tmp_path):
    motor_blender.limpiar(tmp_path, "fotogramas")
    assert (tmp_path / motor_blender.MARCA).read_text().strip() == "fotogramas"


def test_param_sin_igual_da_error_de_uso(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "motor_blender.py"), "x.py", "--ds", "promo-riso", "--out",
                        str(tmp_path / "a.mp4"), "--segundos", "1", "--param", "sin_igual"], capture_output=True, text=True)
    assert r.returncode == 2 and "clave=valor" in r.stderr
