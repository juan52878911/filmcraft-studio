"""cine validar-ds (antes ds_validate.py): tamaños, SFX de roles, animaciones, claves anidadas y esquema.
Se ejecuta el binario (bin/cine); sin binario compilado los tests se saltan."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
CINE = PLUGIN / "bin" / "cine"

DS_IDS = sorted(p.name for p in (PLUGIN / "design-systems").iterdir() if (p / "ds.json").exists())


def cine(*args, env=None):
    r = subprocess.run([str(CINE), *map(str, args)], capture_output=True, text=True, env=env)
    if r.returncode == 127:
        pytest.skip("bin/cine sin compilar (motor/compilar.sh)")
    return r


def check(d, estricto=False):
    r = cine("validar-ds", d, "--json", *(["--estricto"] if estricto else []))
    return json.loads(r.stdout)


def sin_fuentes(xs):
    """Las fuentes del Mac de quien escribió los DS no tienen por qué estar en la máquina del test."""
    return [e for e in xs if not (e.startswith("fuente '") and "no está instalada" in e)]


@pytest.mark.parametrize("ds_id", DS_IDS)
def test_los_ds_precargados_validan(ds_id):
    assert sin_fuentes(check(PLUGIN / "design-systems" / ds_id)["errores"]) == []


def test_hay_siete_ds():
    assert len(DS_IDS) == 7


def copia(tmp_path, ds_id="promo-riso"):
    d = tmp_path / ds_id
    shutil.copytree(PLUGIN / "design-systems" / ds_id, d)
    return d


def errores(d, cambia=None):
    raw = json.loads((d / "ds.json").read_text())
    if cambia:
        cambia(raw)
        (d / "ds.json").write_text(json.dumps(raw))
    r = check(d)
    return sin_fuentes(r["errores"]), r["avisos"]



def test_sfx_de_rol_fuera_del_mapa(tmp_path):
    err, _ = errores(copia(tmp_path), lambda j: j["sfx"]["mapa"].pop("tecla"))
    assert any("sfx 'tecla' no está en sfx.mapa" in e for e in err)


def test_fondo_de_otro_tamano(tmp_path):
    d = copia(tmp_path)
    from PIL import Image
    Image.new("RGB", (100, 100)).save(d / "assets/bg-title.png")
    err, _ = errores(d)
    assert any("fondos.titulo: mide 100x100" in e for e in err)


def test_fondo_con_tamano_de_variante_es_aviso(tmp_path):
    d = copia(tmp_path, "promo-tres-fases")
    from PIL import Image
    Image.new("RGB", (1080, 1920)).save(d / "assets/bg-plain.png")
    err, warn = errores(d)
    assert err == []
    assert any("variante '9x16'" in w for w in warn)


def test_animacion_sin_definir(tmp_path):
    err, _ = errores(copia(tmp_path), lambda j: j["roles_texto"]["titulo"].update(anim="calorEntra"))
    assert any("'calorEntra' sin definir" in e for e in err)


def test_clave_anidada_que_los_scripts_leen_a_pelo(tmp_path):
    err, _ = errores(copia(tmp_path), lambda j: j["continuidad"].pop("zoom_crash"))
    assert any("continuidad.zoom_crash" in e or "zoom_crash" in e for e in err)


def test_color_null_no_revienta(tmp_path):
    err, _ = errores(copia(tmp_path), lambda j: j["roles_texto"]["meta"].update(color=None))
    assert isinstance(err, list)


def test_clave_mal_escrita_en_un_rol(tmp_path):
    pytest.importorskip("jsonschema")
    err, _ = errores(copia(tmp_path), lambda j: j["roles_texto"]["subtitulo"].update(tamm=70))
    assert any("tamm" in e for e in err)


def test_comprobaciones_propias_ademas_del_esquema(tmp_path):
    err, _ = errores(copia(tmp_path), lambda j: j["musica"].pop("bajo_voz_db"))
    assert "falta 'musica.bajo_voz_db'" in err


def test_errores_sin_duplicados(tmp_path):
    err, _ = errores(copia(tmp_path), lambda j: j["sfx"]["mapa"].clear())
    assert len(err) == len(set(err))


def test_esquema_es_valido_2020_12():
    js = pytest.importorskip("jsonschema")
    for p in (PLUGIN / "schemas").glob("*.schema.json"):
        js.Draft202012Validator.check_schema(json.loads(p.read_text()))


def test_esquemas_de_ejemplos():
    js = pytest.importorskip("jsonschema")
    # Copias de un guion, una biblia y un plan reales de promos hechas con el plugin.
    for nombre in ("guion", "biblia", "plan"):
        f = PLUGIN / f"tests/fixtures/{nombre}.json"
        sch = json.loads((PLUGIN / f"schemas/{nombre}.schema.json").read_text())
        assert not list(js.Draft202012Validator(sch).iter_errors(json.loads(f.read_text()))), nombre
    brief = {"ds": {"valor": "promo-riso", "origen": "dado", "confianza": 1},
             "duracion_s": {"valor": 30, "origen": "defecto", "confianza": 0.5, "por": "rango del DS"}}
    sch = json.loads((PLUGIN / "schemas/brief.schema.json").read_text())
    assert not list(js.Draft202012Validator(sch).iter_errors(brief))
    brief["ds"]["origen"] = "inventado"
    assert list(js.Draft202012Validator(sch).iter_errors(brief))


def test_cli_todos_y_estricto(tmp_path):
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "data"), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    res = json.loads(cine("validar-ds", "--todos", "--json", env=env).stdout)
    assert len(res) == 7
    assert cine("validar-ds", env=env).returncode == 2       # sin DS ni --todos: uso


def test_estricto_convierte_avisos(tmp_path):
    d = copia(tmp_path, "promo-tres-fases")
    from PIL import Image
    Image.new("RGB", (1080, 1920)).save(d / "assets/bg-plain.png")
    r = check(d, estricto=True)
    assert not r["ok"] and any("(estricto)" in e for e in r["errores"])


# DS que daban OK y revientan plan_compile o apply_plan (re-auditoría 2, hallazgo 3): cada uno es error claro
ROTOS = {
    "eco sin colores": (lambda r: r["roles_texto"]["eco"].pop("colores"), "eco.colores"),
    "eco con colores vacío": (lambda r: r["roles_texto"]["eco"].__setitem__("colores", []), "pares"),
    "titulo sin x": (lambda r: r["roles_texto"]["titulo"].pop("x"), "titulo.x"),
    "cierre con y fuera": (lambda r: r["roles_texto"]["cierre"].__setitem__("y", 300), "entre 0 y 1"),
    "sin SFX 2": (lambda r: r["pistas"]["audio"].remove("SFX 2"), "'SFX 2'"),
    "sin Music": (lambda r: r["pistas"]["audio"].remove("Music"), "'Music'"),
    "sin Dialogue": (lambda r: r["pistas"]["audio"].remove("Dialogue"), "'Dialogue'"),
    "sin Main": (lambda r: r["pistas"]["video"].remove("Main"), "'Main'"),
    "sin Mattes": (lambda r: r["pistas"]["video"].remove("Mattes"), "'Mattes'"),
    "sin Fondo": (lambda r: r["pistas"]["video"].remove("Fondo"), "'Fondo'"),
    "matte de transición ausente": (lambda r: r["mattes"].pop("acento2"), "matte 'acento2'"),
    "glitch con matte ausente": (lambda r: r["transiciones"]["glitch"].__setitem__("matte", "nada"), "matte 'nada'"),
    "evitar_y mal formado": (lambda r: r["zonas"].__setitem__("evitar_y", [0.1, 0.2]), "evitar_y"),
    "SFX del mapa inexistente": (lambda r: r["sfx"]["mapa"].__setitem__("pop", "nada.wav"), "sfx.pop"),
    "color no hex": (lambda r: r["paleta"].__setitem__("fondo", "rojo"), "no hex"),
}


@pytest.mark.parametrize("caso", list(ROTOS))
def test_ds_roto_da_error(tmp_path, caso):
    cambia, texto = ROTOS[caso]
    err, _ = errores(copia(tmp_path, "sbg-brutalista-s5"), cambia)
    assert any(texto in e for e in err), err


def test_color_no_hex_por_cli_sin_traza(tmp_path):
    d = copia(tmp_path, "sbg-brutalista-s5")
    raw = json.loads((d / "ds.json").read_text())
    raw["paleta"]["claro"] = "blanco"
    (d / "ds.json").write_text(json.dumps(raw))
    r = cine("validar-ds", d)
    assert r.returncode == 1 and "no hex" in r.stdout


def test_ds_json_roto_es_error_y_no_traza(tmp_path):
    d = copia(tmp_path, "sbg-brutalista-s5")
    (d / "ds.json").write_text("{ roto")
    r = check(d)
    assert not r["ok"] and "no se puede cargar" in r["errores"][0]
