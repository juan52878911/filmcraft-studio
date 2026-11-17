"""pegatina@1 sin FilmCraft: curvas → keyframes, palabras clave de los subtítulos, tarjetas dibujadas,
Styler con inclinación, sombra, prefijo, resaltado y escritura, y lo que cambia en plan_compile."""
import copy

import pytest

pytest.importorskip("PIL")
import fcstyle  # noqa: E402
import pegatina  # noqa: E402
import plan_compile  # noqa: E402
from common import load_ds  # noqa: E402
from montaje_sintetico import DS_ID, MotorInt, analisis  # noqa: E402

ANIM = {"base_fps": 30,
        "golpe": {"escala": [[0, 126], [5, 95], [9, 100]], "giro": [[0, -4], [5, 0.8], [9, 0]], "opacidad": [[0, 0], [1, 100]]},
        "desliza": {"dx": [[0, -0.044], [3, 0.029], [7, 0]], "opacidad": [[0, 0], [2, 100]]},
        "caida": {"escala": [[0, 113], [3, 100]], "opacidad": [[0, 50], [1, 100]]},
        "pop": {"escala": [[0, 124], [6, 100]], "opacidad": [[0, 0], [2, 100]]},
        "escribe": {"cps_f": 1.5}, "salida": {"f": 4}, "adelanto_f": 7}


def ds_pegatina():
    ds = copy.deepcopy(load_ds(DS_ID))
    ds["gramatica"] = "pegatina@1"
    ds["animaciones"].update(ANIM)
    ds["animaciones"]["base_fps"] = 30
    r = ds["roles_texto"]
    r["subtitulo"].update(max_palabras=3, resalta="acento1", resalta_max=2, contorno={"color": "oscuro", "ancho": 4})
    r["kicker"] = {"fuente": "meta", "tam": 33, "color": "claro", "fondo": "oscuro", "margen": 14, "pista": "Tags",
                   "pos": [0.07, 0.12], "align": "Left", "anim": "escribe", "prefijo": {"texto": "▶ ", "color": "acento1"}}
    r["pill"].update(anim="caida", inclina=-2.7, sombra={"color": "acento1", "dist": 8, "angulo": 135})
    ds["marca"]["barra"] = ""
    ds["musica"]["ninguna"] = True
    ds["tarjetas"] = {"logo": {"anim": "desliza", "inclina": -3, "pos": [0.27, 0.13], "pista": "Tarjeta"}}
    return ds


# ---------- curvas ----------
def test_golpe_escala_giro_y_salida():
    ds = {"lienzo": {"ancho": 1080, "alto": 1920}, "animaciones": ANIM}
    k = pegatina.keyframes(ds, "golpe", 2.0, [100, 200], rot=-3, escala=100)
    assert [v for _, v, _ in k["scale"]] == [126, 95, 100]
    assert k["rotation"][0][1] == -7 and k["rotation"][-1][1] == -3          # −3° en reposo
    op = k["opacity"]
    assert op[0][1] == 0 and op[-1] == (2.0, 0, "linear")                     # sale en fundido
    assert abs(op[-2][0] - (2.0 - 4 / 30)) < 1e-9 and op[-2][1] == 100


def test_desliza_por_la_derecha_invierte_el_desplazamiento():
    ds = {"lienzo": {"ancho": 1080, "alto": 1920}, "animaciones": ANIM}
    izq = pegatina.keyframes(ds, "desliza", 2.0, [500, 300])["position"]
    der = pegatina.keyframes(ds, "desliza", 2.0, [500, 300], desde=-1)["position"]
    assert izq[0][1][0] < 500 < izq[1][1][0] and der[0][1][0] > 500 > der[1][1][0]
    assert izq[-1][1] == [500, 300] and der[-1][1] == [500, 300]


def test_sin_salida_si_no_da_tiempo():
    ds = {"lienzo": {"ancho": 1080, "alto": 1920}, "animaciones": ANIM}
    op = pegatina.keyframes(ds, "golpe", 0.1, [0, 0])["opacity"]
    assert op[-1][1] == 100                                                   # no hay hueco para el fundido


def test_escritura_por_caracteres():
    assert pegatina.escritura({"animaciones": ANIM}, 15) == 10 / 30


# ---------- palabras clave ----------
def test_palabras_clave_reglas():
    pal = ["¿Se", "puede", "construir"]
    assert pegatina.palabras_clave(pal, [True, False, False]) == []           # mayúscula de inicio de frase
    pal = ["Nos", "acompaña", "Ana"]
    assert pegatina.palabras_clave(pal, [True, False, False]) == [2]
    pal = ["19", "de", "noviembre"]
    assert pegatina.palabras_clave(pal, [False] * 3, extra=["noviembre"]) == [0, 2]
    pal = ["Torres,", "AWS", "Community"]
    assert pegatina.palabras_clave(pal, [False] * 3, maximo=2) == [0, 1]       # como mucho 2
    assert pegatina.palabras_clave(["En", "La", "Nube"], [False] * 3) == [2]  # nunca funcionales


def test_rangos_sin_puntuacion():
    pal = ["¿Istmo?", "y", "gratis."]
    t = " ".join(pal)
    assert [t[a:b] for a, b in pegatina.rangos(pal, [0, 2])] == ["Istmo", "gratis"]


# ---------- tarjetas ----------
@pytest.mark.parametrize("spec", [{"tipo": "ponente", "nombre": "ANA TORRES", "cargo": "BUILDER"},
                                  {"tipo": "fecha", "dia": "JUE", "num": "19", "mes": "NOV", "hora": "15:00 h"},
                                  {"tipo": "qr", "url": "tuweb.com"}, {"tipo": "logo"}, {"tipo": "flecha", "sentido": "izq"}])
def test_tarjetas_escalan_con_el_lienzo(tmp_path, spec):
    ds = ds_pegatina()
    _, w1, h1 = pegatina.tarjeta(ds, spec, tmp_path / "a.png")
    ds["lienzo"] = {**ds["lienzo"], "ancho": 720, "alto": 1280}
    _, w2, h2 = pegatina.tarjeta(ds, spec, tmp_path / "b.png")
    assert abs(w1 / w2 - 1.5) < 0.06 and abs(h1 / h2 - 1.5) < 0.06


def test_tarjeta_desconocida(tmp_path):
    with pytest.raises(ValueError):
        pegatina.tarjeta(ds_pegatina(), {"tipo": "cohete"}, tmp_path / "x.png")


# ---------- Styler ----------
def setters(e, cmd):
    return [c[2] for c in e.calls if c[0] == "x" and c[1] == cmd]


def test_styler_pill_inclinada_con_sombra_y_caida():
    e = MotorInt()
    fcstyle.Styler(e, ds_pegatina()).text("pill", "te invitan", 1.0, 2.0, (0.1, 0.3))
    props = setters(e, "graphics.set")[0]["props"]
    assert props["rotation"] == -2.7 and props["shadow"] and props["shadow_blur"] == 0 and props["shadow_distance"] == 8
    kfs = {c[3]: c[4] for c in e.calls if c[0] == "kf"}
    assert kfs["scale"][0][1] == 113 and kfs["opacity"][-1][1] == 0


def test_styler_kicker_prefijo_y_escritura():
    e = MotorInt()
    out = fcstyle.Styler(e, ds_pegatina()).text("kicker", "NOS ACOMPAÑA", 1.0, 2.0, (0.07, 0.12))
    assert out["texto"] == "▶ NOS ACOMPAÑA"
    cs = setters(e, "graphics.setCharStyle")
    assert cs[0]["start"] == 0 and cs[0]["end"] == 1                          # el ▶ en otro color
    assert {"clips": [out["clip"]], "effect": "crop"} in setters(e, "effects.apply")
    crop = [c[4] for c in e.calls if c[0] == "kf" and c[2] == "crop"][0]
    assert crop[0][1] > crop[-1][1]                                           # se descubre de izquierda a derecha


def test_styler_resaltado_desplazado_por_el_prefijo():
    e = MotorInt()
    ds = ds_pegatina()
    ds["roles_texto"]["kicker"]["resalta"] = "acento2"
    fcstyle.Styler(e, ds).text("kicker", "HOLA ANA", 0, 1, (0.1, 0.1), resaltar=[[5, 8]])
    cs = setters(e, "graphics.setCharStyle")
    assert cs[-1]["start"] == 7 and cs[-1]["end"] == 10


# ---------- plan_compile ----------
def compilar_pegatina(tmp_path, bloques):
    an = analisis(tmp_path)
    return plan_compile.Compiler({"ds": DS_ID, "bloques": bloques, "resaltar": ["modelo"]}, ds_pegatina(), an).compile()


def test_compile_subtitulos_cortos_y_resaltados(tmp_path):
    c = compilar_pegatina(tmp_path, [{"id": "a", "tipo": "contenido", "planos": [{"src": "charla", "in": 0.3, "out": 20}]}])
    assert c["subtitulos"] and all(len(s["texto"].split()) <= 3 for s in c["subtitulos"])
    marcados = [s["texto"][a:b] for s in c["subtitulos"] for a, b in s.get("resaltar", [])]
    assert "modelo" in marcados
    assert c["marca"] == [] and c["musica"] is None                           # sin barra ni música


def test_compile_tarjetas_hasta_el_final_y_en_pistas_distintas(tmp_path):
    c = compilar_pegatina(tmp_path, [{"id": "a", "tipo": "contenido", "planos": [{"src": "charla", "in": 0.3, "out": 6}],
                                      "capas": [{"tarjeta": {"tipo": "logo"}, "t": 0.5},
                                                {"tarjeta": {"tipo": "logo"}, "t": 1.0, "pos": [0.7, 0.15]}],
                                      "textos": [{"rol": "pill", "texto": "hola", "palabra": "sesión"}]}])
    t1, t2 = c["capas"]
    fin = c["bloques"][0]["end"]
    assert abs(t1["start"] + t1["dur"] - fin) < 0.04 and t1["anim"] == "desliza" and t1["inclina"] == -3
    assert t1["pista"] != t2["pista"]
    pill = c["textos"][0]
    assert abs(pill["start"] + pill["dur"] - fin) < 0.04                      # el rótulo vive hasta el final del bloque
    w = next(x for x in __import__("montaje_sintetico").palabras() if x["w"] == "sesión")
    assert pill["start"] < w["s"]                                              # entra antes de su palabra
