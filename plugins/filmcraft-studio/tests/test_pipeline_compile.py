"""plan_compile: fundido final de la música = salida_s, sin negativos; cobertura por palabra; SFX inexistente."""
import json

import pytest

pytest.importorskip("PIL")
import plan_compile  # noqa: E402

M = {"bajo_voz_db": -18, "sin_voz_db": -8, "rampa_s": 0.4, "salida_s": 1.5}


def bloques(*tramos):
    return [{"start": a, "end": b, "tipo": t, "voz": v} for a, b, t, v in tramos]


def nivel_en(kfs, t):
    for (t0, v0), (t1, v1) in zip(kfs, kfs[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0) if t1 > t0 else v1
    return kfs[-1][1]


def comprobar(kfs, total):
    ts = [t for t, _ in kfs]
    assert ts == sorted(ts) and min(ts) >= 0
    assert kfs[-1] == [round(total, 3), -60] or total <= 0


def test_fundido_dura_salida_s():
    total = 30.0
    kfs = plan_compile.music_keyframes(bloques((0, 27, "contenido", True), (27, 30, "cierre", False)), total, M)
    comprobar(kfs, total)
    assert kfs[-2] == [28.5, -8]                         # empieza en total - salida_s…
    assert all(t <= 28.5 for t, _ in kfs[:-1])            # …y nada entre medias acorta el fundido


def test_cierre_corto_no_sube_con_voz():
    total = 30.0
    kfs = plan_compile.music_keyframes(bloques((0, 29, "contenido", True), (29, 30, "cierre", False)), total, M)
    comprobar(kfs, total)
    assert kfs[-2][0] == 28.5 and kfs[-2][1] == pytest.approx(-18)   # sigue agachada: hay voz en 28,5 s
    assert max(v for t, v in kfs if t >= 28.5) <= -18


def test_pieza_mas_corta_que_salida_s():
    kfs = plan_compile.music_keyframes(bloques((0, 1, "contenido", False)), 1.0, M)
    comprobar(kfs, 1.0)
    assert kfs[0][0] == 0


def test_monotona_y_continua_en_el_tiempo():
    total = 20.0
    kfs = plan_compile.music_keyframes(bloques((0, 5, "titulo", False), (5, 15, "contenido", True),
                                               (15, 20, "cierre", False)), total, M)
    comprobar(kfs, total)
    assert nivel_en(kfs, 10) == pytest.approx(-18)


def compilador(tmp_path, ds_extra=None):
    an = tmp_path / "analisis"
    an.mkdir()
    (an / "material.json").write_text(json.dumps({"videos": []}))
    ds = {"lienzo": {"fps": 30}, "sfx": {"_mapa_abs": {}}, **(ds_extra or {})}
    return plan_compile.Compiler({"bloques": []}, ds, an,
                                 {"obligatorios": {"valor": ["IA", "100 USD", "momento de premio"]}})


def test_cobertura_por_palabra_entera(tmp_path):
    c = compilador(tmp_path)
    cov = c.coverage([{"texto": "muchas gracias a todos"}], [{"texto": "son 1000 personas"}])
    assert cov == {"IA": False, "100 USD": False, "momento de premio": False}
    cov = c.coverage([{"texto": "la IA"}], [{"texto": "100 USD"}])
    assert cov["IA"] and cov["100 USD"]


def test_sfx_inexistente_avisa(tmp_path):
    c = compilador(tmp_path)
    assert c.sfx_dur(str(tmp_path / "no.wav")) == 0.5
    assert any("no existe" in x for x in c.avisos)
