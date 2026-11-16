"""brief_infer: sin --analisis (video sin material de cámara) infiere de --dado con confianza baja."""
import json


def test_brief_sin_analisis(tmp_path, run_script):
    dado = {"ds": "sbg-brutalista-s5", "objetivo": "explicar el producto", "duracion_s": 45, "mensaje": "uno solo"}
    r = run_script("brief_infer.py", "--out", tmp_path / "brief.json", "--dado", json.dumps(dado))
    assert r.returncode == 0, r.stderr
    b = json.loads((tmp_path / "brief.json").read_text())
    assert b["ds"]["valor"] == "sbg-brutalista-s5" and b["ds"]["origen"] == "dado"
    assert b["objetivo"] == {"valor": "explicar el producto", "origen": "dado", "confianza": 1.0, "por": ""}
    assert b["duracion_s"]["valor"] == 45
    assert b["mensaje"]["valor"] == "uno solo"                       # campos extra de la biblia se conservan
    assert b["obligatorios"]["valor"] == [] and b["obligatorios"]["confianza"] < 0.6
    assert b["tono"]["confianza"] < 0.6 and b["idioma"]["confianza"] < 0.6
    assert b["candidatos"] == []


def test_brief_errores_de_uso(tmp_path, run_script):
    r = run_script("brief_infer.py")
    assert r.returncode == 2 and "--out" in r.stderr and "Traceback" not in r.stderr
    r = run_script("brief_infer.py", "--out", tmp_path / "b.json", "--analisis", tmp_path / "no")
    assert r.returncode == 2 and "material.json" in r.stderr
    r = run_script("brief_infer.py", "--out", tmp_path / "b.json", "--dado", "{no json")
    assert r.returncode == 2 and "--dado" in r.stderr


def test_brief_idioma_del_analisis(tmp_path, run_script):
    an = tmp_path / "an"
    an.mkdir()
    (an / "material.json").write_text(json.dumps({"lang": "en", "videos": [
        {"stem": "v", "path": "/x/v.mp4", "frases": [{}], "energia_media_db": -20, "palabras_json": None}]}))
    r = run_script("brief_infer.py", "--analisis", an, "--out", tmp_path / "b.json", "--dado", '{"ds": "sbg-brutalista-s5"}')
    assert r.returncode == 0, r.stderr
    b = json.loads((tmp_path / "b.json").read_text())
    assert b["idioma"]["valor"] == "en" and b["idioma"]["confianza"] >= 0.6
