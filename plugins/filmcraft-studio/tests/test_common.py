"""common.py: precedencia del catálogo, cobertura por palabra, color, herramientas externas, loudness."""
import json
import shutil
import sys

import pytest

import common
from common import ErrorExterno


def test_catalogo_del_usuario_tapa_al_precargado(tmp_path):
    ds_id = "sbg-brutalista-s5"
    assert (common.PLUGIN_DS / ds_id / "ds.json").exists()
    dest = common.USER_DS / ds_id
    shutil.copytree(common.PLUGIN_DS / ds_id, dest)
    try:
        j = json.loads((dest / "ds.json").read_text())
        j["_marca_test"] = True
        (dest / "ds.json").write_text(json.dumps(j))
        assert common.ds_dir(ds_id) == dest
        assert common.load_ds(ds_id).get("_marca_test") is True
        ids = [d.name for d in common.list_ds()]
        assert ids.count(ds_id) == 1                       # sin duplicados por id
        assert dest in common.list_ds()
    finally:
        shutil.rmtree(dest)
    assert common.ds_dir(ds_id) == common.PLUGIN_DS / ds_id


def test_sin_ruta_personal_de_whisper():
    src = (common.SCRIPTS / "common.py").read_text()
    assert "VibeVoiceNix" not in src
    assert "Documents/GitHub" not in src


@pytest.mark.parametrize("obl,textos,esperado", [
    ("IA", ["muchas gracias a todos"], False),             # subcadena de «gracias»
    ("100 USD", ["son 1000 personas"], False),             # subcadena de «1000»
    ("100 USD", ["ganamos 100 USD en créditos"], True),
    ("IA", ["la IA generativa"], True),
    ("SageMaker", ["usamos sagemaker,"], True),            # mayúsculas y puntuación
    ("créditos", ["100 creditos"], True),                  # tildes
    ("Rekognition y Bedrock", ["Rekognition"], False),     # todas las palabras con contenido
    ("", ["algo"], False),
    ("Amazon SageMaker", ["SAGEMAKER"], True),             # e2e B2: el prefijo de marca es opcional
    ("Amazon SageMaker", ["Amazon"], False),               # pero el núcleo no
    ("Amazon", ["Amazon"], True),                          # una marca sola sigue contando
    ("AWS Lambda", ["lambda y bedrock"], True),
])
def test_cubre_por_palabra_entera(obl, textos, esperado):
    assert common.cubre(obl, textos) is esperado


def test_color_y_contraste():
    assert common.hex2rgb("#FF9900") == (255, 153, 0)
    assert common.hex2rgb("F90") == (255, 153, 0)
    assert common.rgb2hex((255, 153, 0)) == "#FF9900"
    assert round(common.contrast("#FFFFFF", "#000000"), 2) == 21.0
    assert common.contrast("#777777", "#777777") == pytest.approx(1.0)
    assert common.mix("#000000", "#FFFFFF", 0.5) in ("#808080", "#7F7F7F")


def test_run_sin_binario_da_error_claro():
    with pytest.raises(ErrorExterno, match="no encuentro"):
        common.run(["no-existe-este-binario-fcs"])


def test_run_con_codigo_distinto_de_cero():
    with pytest.raises(ErrorExterno, match="código 3"):
        common.run([sys.executable, "-c", "import sys; sys.stderr.write('mal'); sys.exit(3)"], text=True)


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="sin ffprobe")
def test_ffprobe_falla_con_mensaje(tmp_path):
    malo = tmp_path / "roto.mp4"
    malo.write_bytes(b"esto no es un video")
    with pytest.raises(ErrorExterno):
        common.duracion(malo)
    info = common.ffprobe(malo)                           # sin check: comportamiento antiguo (dur 0) con aviso
    assert info["dur"] == 0


def _detector_falso(tmp_path, cuerpo):
    b = tmp_path / "vision_falso"
    b.write_text("#!/bin/sh\n" + cuerpo + "\n")
    b.chmod(0o755)
    return str(b)


def test_detect_falla_si_el_detector_falla(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "vision_bin", lambda: _detector_falso(tmp_path, "exit 1"))
    with pytest.raises(ErrorExterno):
        common.detect([tmp_path / "a.jpg"])


def test_detect_falla_si_faltan_imagenes(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "vision_bin", lambda: _detector_falso(tmp_path, "exit 0"))
    with pytest.raises(ErrorExterno, match="no devolvió"):
        common.detect([tmp_path / "a.jpg"])


def test_detect_lee_una_linea_por_imagen(tmp_path, monkeypatch):
    img = (tmp_path / "a.jpg").resolve()
    linea = json.dumps({"path": str(img), "faces": [[0.1, 0.1, 0.2, 0.2]], "people": []})
    monkeypatch.setattr(common, "vision_bin", lambda: _detector_falso(tmp_path, f"echo '{linea}'"))
    d = common.detect([img])
    assert d[str(img)]["faces"] == [[0.1, 0.1, 0.2, 0.2]]


def test_requiere_macos(monkeypatch):
    monkeypatch.setattr(common.sys, "platform", "linux")
    with pytest.raises(ErrorExterno, match="macOS"):
        common.requiere_macos("el detector de caras")


EBUR = """[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -14.3 LUFS
    Threshold: -24.5 LUFS

  Loudness range:
    LRA:         5.1 LU

  True peak:
    Peak:       -1.2 dBFS
"""
META = "frame:0 pts:0 pts_time:0.1\nlavfi.r128.S=-120.7\nframe:1 pts:1 pts_time:1.1\nlavfi.r128.S=-16.2\n"


def test_parse_ebur128():
    r = common.parse_ebur128(EBUR, META)
    assert r["lufs"] == -14.3 and r["lra"] == 5.1 and r["pico_dbtp"] == -1.2
    assert r["curva_s"] == [-70.0, -16.2]                   # sin M que lo supla, el −120 inicial queda en −70
    assert common.parse_ebur128("nada")["lufs"] is None


def _bloque(t, m, s):
    return f"frame:0 pts:0 pts_time:{t}\nlavfi.r128.M={m}\nlavfi.r128.S={s}\nlavfi.r128.I=-70.000\n"


def test_parse_ebur128_arranque_con_voz_usa_el_momentaneo():
    # e2e: voz desde el primer segundo (M ≈ −17) pero S a −120,7 hasta llenar su ventana de 3 s.
    meta = (_bloque(0, -120.691, -120.691) + _bloque(0.5, -17.0, -120.691)
            + _bloque(1, -16.0, -120.691) + _bloque(2, -18.0, -120.691)
            + _bloque(3, -22.0, -19.046) + _bloque(4, -120.691, -120.691))
    c = common.parse_ebur128(EBUR, meta)["curva_s"]
    assert c[0] == -17.0 and c[1] == -16.0 and c[2] == -18.0   # ni un −70 con voz
    assert c[3] == -19.0                                       # con la ventana llena manda S
    assert c[4] == -70.0                                       # silencio de verdad sigue a −70
    assert len(c) == 5
