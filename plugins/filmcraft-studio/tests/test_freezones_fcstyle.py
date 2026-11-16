"""freezones (dónde va un pop-up) y fcstyle (cómo se crea un texto del DS) sin FilmCraft."""
import pytest

pytest.importorskip("PIL")
import fcstyle  # noqa: E402
import freezones as fz  # noqa: E402
from common import load_ds  # noqa: E402
from montaje_sintetico import DS_ID, MotorInt  # noqa: E402

DS = {"zonas": {"evitar_y": [[0, 0.12], [0.72, 0.84]], "margen": 0.03, "y_min_bloque": 0.14}}


def caja(pos, size):
    return [pos[0] - size[0] / 2, pos[1] - size[1] / 2, pos[0] + size[0] / 2, pos[1] + size[1] / 2]


def test_best_spot_no_pisa_la_cara():
    cara = [0.35, 0.2, 0.3, 0.15]                              # x, y, w, h en la fuente
    occ = fz.occupancy([{"t": 1.0, "faces": [cara], "people": []}], 0.5, 1.5)
    assert occ and occ[0][4] == "cara"
    size = (0.3, 0.08)
    pos, info = fz.best_spot(occ, size, DS)
    assert info["solape_cara"] == 0 and fz.inter(caja(pos, size), occ[0][:4]) == 0
    # sin la cara, el mejor sitio es el centro arriba (cy ≈ 0.30), justo donde estaba la cara
    pos0, _ = fz.best_spot([], size, DS)
    assert fz.inter(caja(pos0, size), occ[0][:4]) > 0


def test_best_spot_evita_marca_y_subtitulos():
    size = (0.4, 0.1)
    pos, info = fz.best_spot([], size, DS)
    b = caja(pos, size)
    assert info["reserva"] == 0 and not (b[1] < 0.12 or (b[3] > 0.72 and b[1] < 0.84))
    assert b[1] >= 0.14 - 1e-6


def test_best_spot_alterna_lado():
    size = (0.3, 0.08)
    p1, i1 = fz.best_spot([], size, DS, lado_previo="izq")
    p2, i2 = fz.best_spot([], size, DS, lado_previo="der")
    assert i1["lado"] != "izq" and i2["lado"] != "der"


def test_best_spot_no_cabe():
    pos, info = fz.best_spot([], (1.2, 0.1), DS)
    assert info.get("aviso") == "no cabe" and info["solape"] is None


def test_occupancy_escala_y_ancla():
    b = fz.transform_box([0.4, 0.4, 0.2, 0.2], 200, (0.5, 0.5))
    assert b == pytest.approx([0.3, 0.3, 0.4, 0.4])
    assert fz.occupancy([], 0, 1) is None
    rows = [{"t": 0, "faces": [], "people": [[0, 0, 0.1, 0.1]]}, {"t": 10, "faces": [], "people": [[0.5, 0.5, 0.1, 0.1]]}]
    assert len(fz.occupancy(rows, 0, 1)) == 1                                     # solo los del intervalo ±1 s


def test_sin_vision_cuenta_los_fallos_del_detector():
    rows = [{"t": 0, "faces": []}, {"t": 1, "faces": [], "error": "no se pudo leer"}, {"t": 9, "error": "x"}]
    assert fz.sin_vision(rows, 0.5, 1.5) == 1 and fz.sin_vision(rows, 4, 5) == 0


# ---------- fcstyle ----------
def test_measure_y_wrap():
    ds = load_ds(DS_ID)
    w1, h1 = fcstyle.measure(ds, "etiqueta", "IA")
    w2, h2 = fcstyle.measure(ds, "etiqueta", "INTELIGENCIA ARTIFICIAL")
    assert 0 < w1 < w2 < 1.5 and h1 == pytest.approx(h2)
    _, h3 = fcstyle.measure(ds, "etiqueta", "UNO\nDOS")
    assert h3 > 1.8 * h1 - 0.02
    assert fcstyle.wrap("una frase bastante larga para partir", 12) == ["una frase", "bastante", "larga para", "partir"]


def test_styler_text_caja_y_color():
    ds = load_ds(DS_ID)
    e = MotorInt()
    r = fcstyle.Styler(e, ds).text("etiqueta", "IA", 1.0, 0.8, (0.5, 0.25))
    W, H = ds["lienzo"]["ancho"], ds["lienzo"]["alto"]
    m = ds["roles_texto"]["etiqueta"].get("margen", 40) if ds["roles_texto"]["etiqueta"].get("fondo") else 0
    assert r["box"] == pytest.approx([(0.5 * W - 100 - m) / W, (0.25 * H - 40 - m) / H, (0.5 * W + 100 + m) / W,
                                      (0.25 * H + 40 + m) / H], abs=1e-4)
    props = next(c[2]["props"] for c in e.calls if c[0] == "x" and c[1] == "graphics.set")
    assert props["fill_color"].startswith("#")
    if ds["roles_texto"]["etiqueta"].get("anim") == "popIn":
        assert any(c[0] == "kf" and c[3] == "scale" for c in e.calls)


def test_styler_eco_copias_escalonadas():
    ds = load_ds(DS_ID)
    e = MotorInt()
    r = ds["roles_texto"]["eco"]
    out = fcstyle.Styler(e, ds).eco("100 USD", 2.0, (0.4, 0.3))
    assert len(out) == len(r["colores"])
    starts = [o["start"] for o in out]
    assert starts == sorted(starts) and len(set(starts)) == len(starts)
    assert out[1]["box"][1] - out[0]["box"][1] == pytest.approx(r.get("paso_y", 0.125), abs=1e-3)


def test_styler_title_una_capa_por_palabra():
    ds = load_ds(DS_ID)
    e = MotorInt()
    r = fcstyle.Styler(e, ds).title("IA EN LA NUBE", 5.0, 2.0)
    assert r["palabras"] == 4 and len({c[5] for c in e.textos()}) == 1          # un solo gráfico
    assert r["box"][0] == pytest.approx(ds["roles_texto"]["titulo"]["x"])
