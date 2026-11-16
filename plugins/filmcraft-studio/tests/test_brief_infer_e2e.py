"""brief_infer: fallos de la prueba e2e (B1: rutas por subcadena de la ruta absoluta; B2: obligatorio con la
entrada completa del vocabulario aunque el ponente diga solo el núcleo)."""
import json
from pathlib import Path

import brief_infer as bi
import common

PLUGIN = Path(__file__).resolve().parent.parent


def test_componentes_no_suben_hasta_la_raiz():
    rutas = ["/private/tmp/x-Users-juan-Documents-GitHub-kindling/abc/e2e/material/videos/charla.mp4"]
    c = bi.componentes(rutas)
    assert c == ["material", "videos", "charla.mp4"]
    assert not any("kindling" in x for x in c)
    # varias rutas: la carpeta común y lo que cuelga de ella
    c = bi.componentes(["/a/Reto de certificacion S5/videos/1.mp4", "/a/Reto de certificacion S5/fotos/2.jpg"])
    assert "Reto de certificacion S5" in c and "videos" in c and "fotos" in c and "a" in c


def test_casa_ruta_por_palabra_entera():
    assert bi.casa_ruta("kindling", ["kindling-1.0", "videos"])
    assert not bi.casa_ruta("kindling", ["-Users-juan-GitHub-kindlingx"])
    assert not bi.casa_ruta("promo", ["promocion"])
    assert bi.casa_ruta("Reto de certificación", ["Reto de certificacion S5"])     # tildes y mayúsculas
    assert not bi.casa_ruta("Reto de certificacion", ["Reto", "de certificacion"])  # en un mismo componente
    assert bi.casa_ruta("RetoCertEAN", ["RetoCertEAN-2025"])


def test_match_ds_material_de_camara_bajo_carpeta_kindling():
    ruta = "/tmp/-Users-juan-Documents-GitHub-kindling/sesion/e2e/material/videos/charla.mp4"
    rk = bi.match_ds(None, [ruta])
    assert all(det["ruta"] == 0.0 for _, _, det in rk)            # «kindling» está demasiado arriba
    cam = bi.match_ds(None, [ruta], "camara")
    assert cam and not any(i.startswith("promo-") for _, i, _ in cam)
    promo = bi.match_ds(None, "/x/kindling/videos-1.0", "promo")
    assert promo and all(bi.es_promo(common.load_ds(i)) for _, i, _ in promo)
    assert promo[0][2]["ruta"] == 1.0


def _analisis(tmp_path, palabras, carpeta="material/videos"):
    an = tmp_path / "an"
    an.mkdir()
    vid = tmp_path / "-Users-juan-GitHub-kindling" / carpeta / "charla.mp4"
    (an / "p.json").write_text(json.dumps([{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.3} for i, w in enumerate(palabras)]))
    (an / "material.json").write_text(json.dumps({"lang": "es", "videos": [
        {"stem": "charla", "path": str(vid), "frases": [{}], "energia_media_db": -20, "palabras_json": "p.json"}]}))
    return an


def test_brief_sin_dado_no_elige_promo_para_camara(tmp_path, run_script):
    an = _analisis(tmp_path, ["hola", "a", "todos"])
    r = run_script("brief_infer.py", "--analisis", an, "--out", tmp_path / "b.json")
    assert r.returncode == 0, r.stderr
    b = json.loads((tmp_path / "b.json").read_text())
    assert not bi.es_promo(common.load_ds(b["ds"]["valor"]))
    assert "kling" not in str(b["cta"]["valor"]).lower()
    assert "para" not in b
    # pedido explícitamente, sí puede salir uno de promo
    r = run_script("brief_infer.py", "--analisis", an, "--out", tmp_path / "c.json", "--dado", '{"para": "promo"}')
    assert r.returncode == 0, r.stderr
    c = json.loads((tmp_path / "c.json").read_text())
    assert bi.es_promo(common.load_ds(c["ds"]["valor"])) and "para" not in c


def test_obligatorio_tal_como_se_dice(tmp_path):
    ds = {"vocabulario": "Amazon SageMaker, Amazon Rekognition, AWS Lambda"}
    an = _analisis(tmp_path, ["usamos", "SageMaker,", "y", "también", "Amazon", "Rekognition", "con", "SageMaker."])
    cands = {c["texto"]: c for c in bi.candidates(an, ds) if c["tipo"] == "servicio"}
    assert set(cands) == {"SageMaker", "Amazon Rekognition"}      # la forma dicha, sin duplicar
    assert cands["SageMaker"]["veces"] == 2
    assert common.cubre("SageMaker", ["SAGEMAKER"])


def test_obligatorio_prefiere_la_forma_corta_dicha(tmp_path):
    ds = {"vocabulario": "Amazon SageMaker"}
    an = _analisis(tmp_path, ["con", "Amazon", "SageMaker", "y", "luego", "SageMaker"])
    cands = [c for c in bi.candidates(an, ds) if c["tipo"] == "servicio"]
    assert [c["texto"] for c in cands] == ["SageMaker"] and cands[0]["veces"] == 2


def test_entregar_usa_el_mismo_fallback_del_cli_que_fclib():
    md = (PLUGIN / "commands" / "entregar.md").read_text()
    fallback = '${FILMCRAFT_CLI:-$(command -v filmcraft-cli || echo "$HOME/.local/bin/filmcraft-cli")}'
    assert fallback in md
    assert "${FILMCRAFT_CLI:-filmcraft-cli}" not in md
    src = (PLUGIN / "scripts" / "fclib.py").read_text()
    assert '".local/bin/filmcraft-cli"' in src                     # mismo orden: env → PATH → ~/.local/bin


def test_solo_flyer_el_original_gana_con_confianza():
    """Sin rutas, el color era el 50 % de un score con un 0 de rutas: el flyer original sacaba 0,47 contra su DS."""
    flyer = PLUGIN / "design-systems" / "sbg-brutalista-s5" / "assets" / "flyer.jpg"
    rk = bi.match_ds(str(flyer), "")
    assert rk[0][1] == "sbg-brutalista-s5" and rk[0][0] >= 0.9
    assert rk[0][0] - rk[1][0] >= 0.1
    b = bi.infer({"videos": []}, {}, flyer=str(flyer))
    assert b["ds"]["valor"] == "sbg-brutalista-s5" and b["ds"]["confianza"] >= 0.6
