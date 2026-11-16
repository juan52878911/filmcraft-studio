"""verify.py puede fallar (CLI roto -> código 2, verificado false) y report.py no pinta ✅ lo no medido."""
import json
import shutil

import pytest

pytest.importorskip("PIL")
from fclib import TPS  # noqa: E402

DS_ID = "sbg-brutalista-s5"


def montaje(w):
    """WORK mínimo: .fcproj con un plano, compiled, estado con un pop-up, brief y plan."""
    proj = {"project": {"items": {
        "1": {"kind": {"Sequence": {"video_tracks": [{"name": "Main", "clips": [
            {"id": 10, "start": 0, "duration": 2 * TPS, "item": 2, "source_in": 0},
            {"id": 11, "start": 2 * TPS, "duration": 2 * TPS, "item": 2, "source_in": 0}]}],
            "audio_tracks": []}}},
        "2": {"name": "v.mp4", "kind": {"Media": {"media": {"File": {"path": "/no/v.mp4"}}}}}}}}
    (w / "Reel.fcproj").write_text(json.dumps(proj))
    comp = {"ds": DS_ID, "fps": 30, "duracion": 4.0, "cobertura": {"IA": True}, "bloques": [], "segmentos": [],
            "transiciones": [], "textos": [], "subtitulos": [], "sfx": [], "ajustes_corte": [], "avisos": [], "cortes": 1}
    (w / "compiled.json").write_text(json.dumps(comp))
    (w / "estado.json").write_text(json.dumps({"modo": "headless", "textos": {
        "t1": {"rol": "etiqueta", "start": 1.0, "dur": 1.0, "box": [0.1, 0.1, 0.5, 0.3], "texto": "Hola"}}}))
    (w / "brief.json").write_text(json.dumps({"duracion_s": {"valor": 30, "origen": "dado", "confianza": 1}}))
    (w / "plan.json").write_text(json.dumps({"titulo": "Prueba"}))
    (w / "analisis").mkdir()


@pytest.mark.skipif(not shutil.which("false"), reason="sin /usr/bin/false")
def test_verify_falla_si_el_cli_falla(tmp_path, run_script):
    montaje(tmp_path)
    r = run_script("verify.py", tmp_path / "Reel.fcproj", "--compiled", tmp_path / "compiled.json",
                   "--analisis", tmp_path / "analisis", "--out", tmp_path / "verificacion",
                   env={"FILMCRAFT_CLI": shutil.which("false")})
    assert r.returncode == 2, r.stderr
    out = json.loads(r.stdout)
    assert out["estado"] == "error" and out["choques_texto"] is None and out["lufs"] is None
    ver = json.loads((tmp_path / "verificacion/verificacion.json").read_text())
    assert ver["verificado"] is False and ver["fallos"]
    assert ver["textos_vs_caras"]["medido"] is False

    # el informe no da por buenos los pop-ups ni la loudness
    r = run_script("report.py", tmp_path)
    assert r.returncode == 0, r.stderr
    md = (tmp_path / "informe.md").read_text()
    fila_pop = next(l for l in md.splitlines() if l.startswith("| Pop-ups"))
    fila_lufs = next(l for l in md.splitlines() if l.startswith("| Loudness"))
    assert "✅" not in fila_pop and "sin medir" in fila_pop
    assert "✅" not in fila_lufs and "sin medir" in fila_lufs
    assert "Verificación incompleta" in md
    assert "Modo **headless**" in md


def test_report_usa_los_lufs_del_ds(tmp_path, run_script, data_dir):
    montaje(tmp_path)
    # un DS del usuario con el mismo id y otro objetivo: tiene precedencia y el informe lo usa
    from common import PLUGIN_DS
    dest = data_dir / "design-systems" / DS_ID
    shutil.copytree(PLUGIN_DS / DS_ID, dest)
    try:
        j = json.loads((dest / "ds.json").read_text())
        j["audio"]["lufs"] = -16
        (dest / "ds.json").write_text(json.dumps(j))
        ver = {"proyecto": str(tmp_path / "Reel.fcproj"), "modo": "live", "verificado": True, "fallos": [],
               "duracion_s": 4.0, "cortes": 1, "planos": 2, "cobertura": {"IA": True},
               "audio": {"lufs": -16.2, "pico_dbtp": -1.5, "lra": 4, "curva_s": []},
               "keyframes": {"keyframes": 0, "n_fuera": 0}, "cortes_en_palabra": {"bordes": 0, "dentro_de_palabra": []},
               "textos_vs_caras": {"popups": 1, "momentos": 1, "momentos_medidos": 1, "medido": True, "choques": []}}
        (tmp_path / "verificacion").mkdir()
        (tmp_path / "verificacion/verificacion.json").write_text(json.dumps(ver))
        r = run_script("report.py", tmp_path)
        assert r.returncode == 0, r.stderr
        md = (tmp_path / "informe.md").read_text()
        fila = next(l for l in md.splitlines() if l.startswith("| Loudness"))
        assert "✅" in fila and "objetivo -16" in fila          # −16,2 está bien contra −16 (no contra −14)
        assert "en vivo" in md
    finally:
        shutil.rmtree(dest)


def test_text_tracks_incluye_las_del_ds():
    import verify
    ds = {"roles_texto": {"x": {"pista": "MiPista"}, "y": {"pistas": ["Otra", "Labels"]}}}
    t = verify.text_tracks(ds)
    assert "MiPista" in t and "Otra" in t and t.count("Labels") == 1


def test_sheet_con_etiquetas_por_fotograma(tmp_path):
    from PIL import Image
    import verify
    p = tmp_path / "a.png"
    Image.new("RGB", (40, 70)).save(p)
    assert verify.sheet([(1.5, p, "REF 1.5"), (1.5, p, "AUTO 1.5")], tmp_path / "h.jpg")
