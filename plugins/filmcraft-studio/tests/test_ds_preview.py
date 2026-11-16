"""ds_preview.py con DS de promo: lienzo por DS y roles opcionales (antes: KeyError 'escalon' y 1080x1920 fijo)."""
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import load_ds  # noqa: E402
import ds_preview  # noqa: E402

DS_IDS = sorted(p.name for p in (PLUGIN / "design-systems").iterdir() if (p / "ds.json").exists())


@pytest.mark.parametrize("ds_id", DS_IDS)
def test_maquetas_al_lienzo_del_ds(ds_id):
    ds = load_ds(ds_id)
    W, H = ds["lienzo"]["ancho"], ds["lienzo"]["alto"]
    for f in (ds_preview.mock_title, ds_preview.mock_eco, ds_preview.mock_outro):
        assert f(ds).size == (W, H)
    assert ds_preview.mock_content(ds, None).size == (W, H)


def test_rol_ausente_no_se_dibuja():
    ds = load_ds("promo-riso")
    assert "escalon" not in ds["roles_texto"]
    im = ds_preview.mock_content(ds, None)                  # antes: KeyError 'escalon'
    assert im.size == (1080, 1920)


def test_cli_con_ds_de_promo_16x9(tmp_path):
    out = tmp_path / "p.png"
    r = subprocess.run([sys.executable, str(SCRIPTS / "ds_preview.py"), "promo-tres-fases", "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "DS de promo" in r.stderr
    from PIL import Image
    with Image.open(out) as im:
        assert im.width > im.height                         # lámina con maquetas apaisadas


def test_sin_out_no_escribe_en_la_carpeta_del_ds(tmp_path):
    """Sin --out la lámina va a <datos>/previews/<id>/: no pisa la preview.png real de un promo ni escribe en el plugin."""
    import os
    ds_dir = SCRIPTS.parent / "design-systems" / "promo-tres-fases"
    antes = (ds_dir / "preview.png").stat().st_mtime_ns if (ds_dir / "preview.png").exists() else None
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(tmp_path))
    r = subprocess.run([sys.executable, str(SCRIPTS / "ds_preview.py"), "promo-tres-fases"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "previews" / "promo-tres-fases" / "preview.png").exists()
    despues = (ds_dir / "preview.png").stat().st_mtime_ns if (ds_dir / "preview.png").exists() else None
    assert antes == despues
