"""promo_fondos.py / promo_sfx.py: conocen tres-fases y fallan con mensaje ante una gramática desconocida."""
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import promo_fondos  # noqa: E402
import promo_sfx  # noqa: E402


def test_tres_fases_registrada():
    assert "tres-fases" in promo_fondos.GEN
    assert "tres-fases" in promo_sfx.KITS


def test_gramatica_desconocida_en_fondos():
    with pytest.raises(SystemExit, match="sin generador"):
        promo_fondos.generador({"gramatica": "brutalista@1"})


def test_kits_cubren_los_sfx_de_sus_ds():
    """Cada sfx que un DS de promo pide en sus roles existe en el kit de su gramática."""
    for d in (PLUGIN / "design-systems").iterdir():
        j = json.loads((d / "ds.json").read_text())
        g = j["gramatica"].split("@")[0]
        if "promo" not in j or g not in promo_sfx.KITS:
            continue
        for rol, r in j["roles_texto"].items():
            if r.get("sfx"):
                assert r["sfx"] in promo_sfx.KITS[g], (d.name, rol, r["sfx"])


def test_promo_fondos_regenera_al_lienzo(tmp_path):
    d = tmp_path / "tf"
    shutil.copytree(PLUGIN / "design-systems/promo-tres-fases", d)
    r = subprocess.run([sys.executable, str(SCRIPTS / "promo_fondos.py"), str(d)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    from PIL import Image
    for p in list((d / "assets").glob("bg-*.png")) + list((d / "assets").glob("matte-*.png")):
        with Image.open(p) as im:
            assert im.size == (1920, 1080), p.name


def test_promo_fondos_brutalista_falla_con_mensaje():
    r = subprocess.run([sys.executable, str(SCRIPTS / "promo_fondos.py"), "sbg-brutalista-s5"], capture_output=True,
                       text=True)
    assert r.returncode == 1 and "conocidas" in r.stderr and "Traceback" not in r.stderr


def test_promo_sfx_solo_y_desconocida(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "promo_sfx.py"), "tres-fases", str(tmp_path), "--solo", "contador"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert [p.name for p in tmp_path.iterdir()] == ["contador.wav"]
    with wave.open(str(tmp_path / "contador.wav")) as w:
        assert w.getframerate() == 48000 and w.getnchannels() == 2
    r = subprocess.run([sys.executable, str(SCRIPTS / "promo_sfx.py"), "brutal", str(tmp_path)], capture_output=True,
                       text=True)
    assert r.returncode == 1 and "conocidas" in r.stderr
