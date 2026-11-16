"""ds_studio.py: ids seguros, catálogo sin miniatura, DS de promo, vista previa que falla, papelera."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))   # por si se corre sin conftest


def run(tmp_path, *args):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(tmp_path / "data"), FILMCRAFT_DS_CATALOGO=str(tmp_path / "cat"),
               FILMCRAFT_CLI=str(tmp_path / "no-hay-filmcraft"), PYTHONPYCACHEPREFIX=str(tmp_path / "pyc"))
    return subprocess.run([sys.executable, str(SCRIPTS / "ds_studio.py"), *map(str, args)], capture_output=True,
                          text=True, env=env)


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


@pytest.mark.parametrize("malo", ["../design-systems", "..", "a/b", "Mayus", "-x", "x..y", "../../etc"])
def test_crear_rechaza_ids_peligrosos_sin_borrar_nada(tmp_path, malo):
    victima = tmp_path / "data" / "design-systems" / "mi-catalogo"
    victima.mkdir(parents=True)
    r = run(tmp_path, "crear", f"--id={malo}")
    assert r.returncode != 0
    assert "id de DS no válido" in r.stderr
    assert victima.exists()


@pytest.mark.parametrize("cmd", ["modificar", "aprobar", "ver", "descartar"])
def test_todos_los_subcomandos_validan_el_id(tmp_path, cmd):
    extra = ["--spec", "{}"] if cmd == "modificar" else []
    r = run(tmp_path, cmd, "../x", *extra)
    assert r.returncode != 0 and "id de DS no válido" in r.stderr


def test_check_id():
    import ds_studio
    assert ds_studio.check_id("promo-riso-2") == "promo-riso-2"
    for malo in ("", "../a", "a/b", "A", "a..b", "x" * 80):
        with pytest.raises(SystemExit):
            ds_studio.check_id(malo)


def test_crear_desde_promo_conserva_su_piel_y_base(tmp_path):
    r = run(tmp_path, "crear", "--id", "p2", "--base", "promo-riso")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    d = Path(out["borrador"])
    ds = json.loads((d / "ds.json").read_text())
    assert ds["derivado_de"]["base"] == "promo-riso"        # el id de origen, no el nuevo
    assert ds["id"] == "p2"
    # fondos con la piel riso (promo_fondos), no la rejilla brutalista de ds_assets
    assert md5(d / "assets/bg-title.png") == md5(PLUGIN / "design-systems/promo-riso/assets/bg-title.png")
    assert out["preview"] and Path(out["preview"]).exists()
    # crear otra vez sin --forzar no pisa el borrador
    r2 = run(tmp_path, "crear", "--id", "p2", "--base", "promo-riso")
    assert r2.returncode != 0 and "--forzar" in r2.stderr


def test_modificar_promo_no_pisa_los_fondos_con_brutalistas(tmp_path):
    r = run(tmp_path, "modificar", "promo-tres-fases", "--spec", '{"escala_texto": 1.05}')
    assert r.returncode == 0, r.stderr
    d = Path(json.loads(r.stdout)["borrador"])
    from PIL import Image
    with Image.open(d / "assets/bg-title.png") as im:
        assert im.size == (1920, 1080)
    assert json.loads(r.stdout)["validacion"]["ok"], r.stdout


def test_vista_previa_fallida_no_devuelve_la_vieja(tmp_path):
    assert run(tmp_path, "crear", "--id", "p3", "--base", "promo-riso").returncode == 0
    d = tmp_path / "data" / "borradores" / "p3"
    assert (d / "preview.png").exists()
    r = run(tmp_path, "modificar", "p3", "--spec", '{"roles_texto": {"titulo": {"fuente": "no-existe"}}}')
    out = json.loads(r.stdout)
    assert out["preview"] is None
    assert out.get("error_preview")
    assert not (d / "preview.png").exists()                # la vieja se borró: nadie la confunde con la nueva
    assert out["validacion"]["ok"] is False


def test_descartar_va_a_la_papelera_y_no_toca_aprobados(tmp_path):
    assert run(tmp_path, "crear", "--id", "p4", "--base", "promo-riso").returncode == 0
    r = run(tmp_path, "descartar", "p4")
    assert r.returncode == 0, r.stderr
    pap = Path(json.loads(r.stdout)["papelera"])
    assert (pap / "ds.json").exists()
    assert not (tmp_path / "data" / "borradores" / "p4").exists()
    r = run(tmp_path, "descartar", "promo-riso")
    assert r.returncode != 0
    assert (PLUGIN / "design-systems/promo-riso/ds.json").exists()


def test_ver(tmp_path):
    r = run(tmp_path, "ver", "promo-tres-fases")
    assert r.returncode == 0, r.stderr
    v = json.loads(r.stdout)
    assert v["donde"] == "precargado" and v["promo"] is True and v["lienzo"]["ancho"] == 1920


def test_catalogo_con_un_ds_sin_miniatura_no_revienta(tmp_path):
    cat = tmp_path / "cat"
    cat.mkdir()
    shutil.copytree(PLUGIN / "design-systems/promo-riso", cat / "sin-thumb",
                    ignore=shutil.ignore_patterns("thumb.png", "preview*.png"))
    j = json.loads((cat / "sin-thumb/ds.json").read_text())
    j["id"] = "sin-thumb"
    (cat / "sin-thumb/ds.json").write_text(json.dumps(j))
    shutil.copytree(cat / "sin-thumb", cat / "roto")
    j["id"] = "roto"
    j["fuentes"].pop("titular")                             # la maqueta no puede dibujar el título
    (cat / "roto/ds.json").write_text(json.dumps(j))
    hoja = tmp_path / "hoja.png"
    r = run(tmp_path, "catalogo", "--hoja", hoja)
    assert r.returncode == 0, r.stderr
    out = {c["id"]: c for c in json.loads(r.stdout)}
    assert Path(out["sin-thumb"]["miniatura"]).exists()     # generada (DS del usuario: en su carpeta)
    assert out["roto"]["miniatura"] is None and out["roto"]["error_miniatura"]
    assert "promo-tres-fases" in out and out["promo-tres-fases"]["miniatura"]
    assert hoja.exists()


def test_miniatura_de_precargado_va_a_datos(tmp_path, monkeypatch):
    import ds_studio
    fake_root = tmp_path / "plugin"
    d = fake_root / "design-systems" / "promo-riso"
    shutil.copytree(PLUGIN / "design-systems/promo-riso", d, ignore=shutil.ignore_patterns("thumb.png", "preview*.png"))
    monkeypatch.setattr(ds_studio, "ROOT", fake_root)
    monkeypatch.setattr(ds_studio, "THUMBS", tmp_path / "thumbs")
    t = ds_studio.thumb(d)
    assert t == tmp_path / "thumbs" / "promo-riso.png" and t.exists()
    assert not (d / "thumb.png").exists()


def test_tono_desconocido_da_mensaje():
    import ds_studio
    from common import jload
    ds = jload(PLUGIN / "design-systems/sbg-brutalista-s5/ds.json")
    with pytest.raises(SystemExit, match="desconocida"):
        ds_studio.apply_spec(ds, {"animacion": "calmada"})


def test_tema_claro_intercambia_claro_y_oscuro():
    import ds_studio
    from common import jload
    ds = jload(PLUGIN / "design-systems/sbg-brutalista-s5/ds.json")
    ds = ds_studio.apply_spec(ds, {"paleta": {"fondo": "#F5F1E8", "claro": "#1A1A1F"}})
    assert ds["paleta"]["oscuro"] == "#1A1A1F" and ds["paleta"]["claro"] == "#F5F1E8"


@pytest.mark.parametrize("spec", ['{"animacion": "calmada"}', '{"paleta": {"fondo": "#FFF"}}', '{"paleta": ',
                                  '{"escala_texto": -1}'])
def test_crear_con_spec_malo_no_deja_borrador(tmp_path, spec):
    r = run(tmp_path, "crear", "--id", "x1", "--spec", spec)
    assert r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip()
    assert not (tmp_path / "data" / "borradores" / "x1").exists()


def test_crear_con_flyer_malo_da_el_motivo(tmp_path):
    malo = tmp_path / "malo.png"
    malo.write_text("no es una imagen")
    for f in (tmp_path / "no-existe.png", malo):
        r = run(tmp_path, "crear", "--id", "x1", "--flyer", f)
        assert r.returncode != 0 and "Traceback" not in r.stderr.splitlines()[0]
        assert not (tmp_path / "data" / "borradores" / "x1").exists()
    assert "no existe" in run(tmp_path, "crear", "--id", "x1", "--flyer", tmp_path / "no-existe.png").stderr
    assert "cannot identify" in run(tmp_path, "crear", "--id", "x1", "--flyer", malo).stderr


def test_aprobar_muestra_el_motivo_y_modificar_vuelve_a_borrador(tmp_path):
    assert run(tmp_path, "crear", "--id", "x2").returncode == 0
    d = tmp_path / "data" / "borradores" / "x2"
    raw = json.loads((d / "ds.json").read_text())
    good = json.loads(json.dumps(raw))
    raw["roles_texto"]["eco"].pop("colores")
    (d / "ds.json").write_text(json.dumps(raw))
    r = run(tmp_path, "aprobar", "x2")
    assert r.returncode != 0 and "eco.colores" in r.stderr                  # antes: «la validación falla:» y nada
    assert not (tmp_path / "cat" / "x2").exists()
    (d / "ds.json").write_text(json.dumps(good))
    assert run(tmp_path, "aprobar", "x2").returncode == 0
    assert run(tmp_path, "modificar", "x2", "--spec", '{"escala_texto": 1.1}').returncode == 0
    st = json.loads((d / "ds.json").read_text())["estado"]
    assert st["borrador"] is True and "aprobado" not in st and st["iteracion"] == 2
