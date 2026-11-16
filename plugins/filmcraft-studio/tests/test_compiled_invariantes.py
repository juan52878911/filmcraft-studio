"""plan_compile de punta a punta sobre un análisis de fixture: invariantes de compiled.json.

Nada pasa de `duracion` (un clip que sobra alarga la secuencia y el export acaba en negro), ids únicos y
estables al recompilar, subtítulos ≤ max_chars, bordes de plano fuera de palabra y textos en zona libre.
"""
import json

import pytest

pytest.importorskip("PIL")
import plan_compile  # noqa: E402
from common import load_ds  # noqa: E402
from montaje_sintetico import DS_ID, compilar, palabras, plan  # noqa: E402

EPS = 1e-4


@pytest.fixture(scope="module")
def comp(tmp_path_factory):
    return compilar(tmp_path_factory.mktemp("comp"))


def fin(x):
    return x["start"] + x["dur"]


def test_nada_pasa_del_final(comp):
    T = comp["duracion"]
    assert T == pytest.approx(13.4)
    for k in ("segmentos", "textos", "subtitulos", "capas", "sfx", "marca"):
        for x in comp[k]:
            assert fin(x) <= T + EPS, (k, x["id"], fin(x), T)
    assert all(kf[0] <= T + EPS for kf in comp["musica"]["keyframes"])
    assert comp["musica"]["dur"] == T


def test_capa_y_eco_del_cierre_se_recortan_y_avisan(comp):
    capa = comp["capas"][0]
    assert capa["start"] == pytest.approx(12.9) and capa["dur"] == pytest.approx(0.5)
    eco = next(t for t in comp["textos"] if t["texto"] == "FIN")
    assert fin(eco) <= comp["duracion"] + EPS and eco["start"] < 13.3     # se adelanta: el eco no se puede acortar
    assert any("capa pasaba del final" in a for a in comp["avisos"])
    assert any("«FIN»" in a and "pasaba del final" in a for a in comp["avisos"])
    # sus SFX (tres blips) caen dentro
    blips = [s for s in comp["sfx"] if s["clave"] == "blip" and s["bloque"] == "cierre"]
    assert len(blips) == 3 and all(fin(s) <= comp["duracion"] + EPS for s in blips)


def test_textos_dentro_de_su_bloque(comp):
    bl = {b["id"]: b for b in comp["bloques"]}
    for t in comp["textos"]:
        b = bl[t["bloque"]]
        assert b["start"] - EPS <= t["start"] and fin(t) <= b["end"] + EPS, t["id"]


def test_ids_unicos(comp):
    clips = [x["id"] for k in ("segmentos", "capas", "sfx", "marca") for x in comp[k]]
    assert len(clips) == len(set(clips))
    textos = [x["id"] for k in ("textos", "subtitulos") for x in comp[k]]
    assert len(textos) == len(set(textos))
    assert all(t["sale"] in {s["id"] for s in comp["segmentos"]} for t in comp["transiciones"])


def test_recompilar_es_determinista(comp, tmp_path):
    otra = compilar(tmp_path)
    for k in ("segmentos", "textos", "subtitulos", "sfx", "capas", "transiciones", "marca"):
        assert [(x["id"], x.get("start", x.get("t")), x["dur"]) for x in otra[k]] == \
            [(x["id"], x.get("start", x.get("t")), x["dur"]) for x in comp[k]], k


def test_subtitulos_caben_en_max_chars(comp):
    mx = load_ds(DS_ID)["roles_texto"]["subtitulo"]["max_chars"]
    assert comp["subtitulos"]
    for s in comp["subtitulos"]:
        assert len(s["texto"]) <= mx or " " not in s["texto"], s


def test_bordes_fuera_de_palabra(comp):
    ws = palabras()
    for s in comp["segmentos"]:
        if s["tipo"] != "video":
            continue
        for t in (s["in"], s["out"]):
            assert not any(w["s"] + 0.01 < t < w["e"] - 0.01 for w in ws), (s["id"], t)
    # 0.45 caía en «hola» (0.3–0.6): se movió y quedó apuntado
    assert any(a["palabra"] == "hola" and a.get("in") == 0.45 for a in comp["ajustes_corte"])


def test_tiempos_en_fotogramas(comp):
    fps = comp["fps"]
    for s in comp["segmentos"]:
        assert abs(s["start"] * fps - round(s["start"] * fps)) < 1e-3


def test_texto_anclado_a_palabra(comp):
    ia = next(t for t in comp["textos"] if t["texto"] == "IA")
    s = next(x for x in comp["segmentos"] if x["id"] == "gancho.p1")
    w = next(w for w in palabras() if w["w"] == "sesión")
    assert ia["start"] == pytest.approx(s["start"] + (w["s"] - s["in"]) / s["speed"], abs=1 / 30)


def test_compiled_guarda_la_ruta_del_ds(comp, tmp_path):
    assert comp["ds"] == DS_ID and comp["ds_dir"] == load_ds(DS_ID)["_dir"]


def test_transiciones_con_su_matte(comp):
    ds = load_ds(DS_ID)
    tipos = {t["tipo"] for t in comp["transiciones"]}
    assert {"barrido", "matte", "glitch", "flash"} <= tipos
    for t in comp["transiciones"]:
        if t["tipo"] in ("matte", "flash", "glitch"):
            assert t["matte"] in ds["mattes"]


def test_fotos_de_mas_avisan(tmp_path):
    p = plan()
    p["bloques"][2]["fotos"] = p["bloques"][2]["fotos"] * 4            # 12 > fotos_max
    c = compilar(tmp_path, p)
    assert sum(1 for s in c["segmentos"] if s["tipo"] == "foto") == load_ds(DS_ID)["estructura"].get("fotos_max", 8)
    assert any("fotos y el DS admite" in a for a in c["avisos"])


def test_cli_sin_analisis_da_mensaje(tmp_path, run_script):
    (tmp_path / "plan.json").write_text(json.dumps({"ds": DS_ID, "bloques": [
        {"id": "a", "planos": [{"src": "nadie", "in": 0, "out": 1}]}]}))
    (tmp_path / "an").mkdir()
    (tmp_path / "an" / "material.json").write_text(json.dumps({"videos": []}))
    r = run_script("plan_compile.py", tmp_path / "plan.json", "--analisis", tmp_path / "an")
    assert r.returncode != 0 and "Traceback" not in r.stderr and "nadie" in r.stderr


def test_snap_cut_va_al_lado_correcto(tmp_path):
    c = plan_compile.Compiler.__new__(plan_compile.Compiler)
    c._words, c.ajustes, c.margin = {"v": [{"w": "uno", "s": 1.0, "e": 1.4}, {"w": "dos", "s": 2.0, "e": 2.4}]}, [], 0.1
    c.an = tmp_path
    assert c.snap_cut("v", 1.1, "in") == pytest.approx(0.9)       # entrada en la 1.ª mitad: antes de la palabra
    assert c.snap_cut("v", 1.3, "in") == pytest.approx(1.5)       # 2.ª mitad: después
    assert c.snap_cut("v", 1.3, "out") == pytest.approx(1.5)
    assert c.snap_cut("v", 1.1, "out") == pytest.approx(0.9)
    assert c.snap_cut("v", 1.7, "out") == 1.7                     # fuera de palabra: no se toca
    assert len(c.ajustes) == 4


def test_popup_esquiva_la_cara_de_la_vision(tmp_path, comp):
    import freezones
    from fcstyle import measure
    an = tmp_path / "analisis"
    compilar(tmp_path)                                               # crea el análisis
    cara = [0.35, 0.18, 0.3, 0.15]
    (an / "charla.vision.json").write_text(json.dumps({"data": [{"t": float(t), "faces": [cara], "people": []}
                                                                 for t in range(0, 20)]}))
    c = plan_compile.Compiler(plan(), load_ds(DS_ID), an).compile()
    ia, ia0 = (next(t for t in x["textos"] if t["texto"] == "IA") for x in (c, comp))
    assert ia["zona"]["personas"] > 0 and ia["zona"]["solape_cara"] == 0
    w, h = measure(load_ds(DS_ID), "etiqueta", "IA")
    occ = freezones.occupancy([{"t": 1.0, "faces": [cara], "people": []}], 0, 3)
    box = [ia["pos"][0] - w / 2, ia["pos"][1] - h / 2, ia["pos"][0] + w / 2, ia["pos"][1] + h / 2]
    box0 = [ia0["pos"][0] - w / 2, ia0["pos"][1] - h / 2, ia0["pos"][0] + w / 2, ia0["pos"][1] + h / 2]
    assert freezones.inter(box, occ[0][:4]) == 0 < freezones.inter(box0, occ[0][:4])   # sin visión caía encima


def test_vision_con_fallos_avisa(tmp_path):
    an = tmp_path / "analisis"
    compilar(tmp_path)
    (an / "charla.vision.json").write_text(json.dumps({"data": [{"t": float(t), "faces": [], "people": [],
                                                                  "error": "no se pudo leer"} for t in range(0, 20)]}))
    c = plan_compile.Compiler(plan(), load_ds(DS_ID), an).compile()
    assert any("el detector falló" in a for a in c["avisos"])
