"""ref_metricas.py y referencias.py: imágenes sintéticas de composición conocida → métricas esperadas."""
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

cv2 = pytest.importorskip("cv2")
import ref_metricas as rm  # noqa: E402
import referencias as refs  # noqa: E402

W, H = 640, 360


def guardar(tmp_path, nombre, a):
    p = tmp_path / nombre
    (a if isinstance(a, Image.Image) else Image.fromarray(np.asarray(a, np.uint8))).save(p)
    return p


def lienzo(color, tam=(W, H)):
    return Image.new("RGB", tam, color)


def con_circulo(x, y, fondo=(18, 20, 28), color=(230, 40, 30), r=34, tam=(W, H)):
    im = lienzo(fondo, tam)
    cx, cy = x * tam[0], y * tam[1]
    ImageDraw.Draw(im).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    return im


def m(p):
    return rm.ficha(p)["metricas"]


def test_foco_en_un_tercio(tmp_path):
    f = rm.ficha(guardar(tmp_path, "tercio.png", con_circulo(1 / 3, 1 / 3)))
    c = f["metricas"]["composicion"]
    p = c["puntos_fuertes"][0]
    assert abs(p["x"] - 1 / 3) < 0.05 and abs(p["y"] - 1 / 3) < 0.05
    assert c["tercios"]["punto"] == "sup-izq" and c["tercios"]["distancia"] < 0.05
    assert c["centro"]["distancia"] > 0.12
    assert c["balance_x"] < -0.2 and c["balance_y"] < -0.2            # el peso está arriba a la izquierda
    assert c["peso_cuadrantes"]["sup_izq"] > 0.5
    assert c["espacio_negativo"] > 0.7
    assert f["metricas"]["valores"]["clave"] == "baja"
    assert f["video"]["sugerido"]["camara"][1]["x"] == p["x"]        # la cámara va al foco


def test_foco_centrado(tmp_path):
    c = m(guardar(tmp_path, "centro.png", con_circulo(0.5, 0.5)))["composicion"]
    assert c["centro"]["distancia"] < 0.04
    assert c["simetria"]["horizontal"] > 0.9 and c["simetria"]["vertical"] > 0.9
    assert abs(c["balance_x"]) < 0.1 and abs(c["balance_y"]) < 0.1


def test_paleta_y_acento(tmp_path):
    col = m(guardar(tmp_path, "acento.png", con_circulo(0.5, 0.5)))["color"]
    assert col["paleta"][0]["papel"] == "dominante" and col["paleta"][0]["oklch"][0] < 0.3
    acento = [k for k in col["paleta"] if k["papel"] == "acento"]
    assert acento and (acento[0]["oklch"][2] < 50 or acento[0]["oklch"][2] > 340)   # rojo
    assert abs(sum(k["proporcion"] for k in col["paleta"]) - 1) < 0.01
    assert col["temperatura"] > 0


def test_notan_y_simetria_de_dos_mitades(tmp_path):
    a = np.zeros((H, W, 3), np.uint8)
    a[:, W // 2:] = 255
    mm = m(guardar(tmp_path, "mitades.png", a))
    v, c = mm["valores"], mm["composicion"]
    assert abs(v["notan2"]["oscuro"] - 0.5) < 0.02
    assert v["contraste_global"] > 0.45 and v["rango"] > 0.95
    assert c["simetria"]["vertical"] > 0.95 and c["simetria"]["horizontal"] < 0.05
    assert c["lineas"]["vertical"] > 0.7 > c["lineas"]["horizontal"]   # con una sola línea pesa el reparto a priori
    assert mm["bordes"]["duros"] > 0.8
    assert mm["color"]["armonia"]["tipo"] == "acromatica"
    assert all(f[:6] == "000000" and f[-6:] == "222222" for f in v["notan3"]["rejilla"])


def test_ritmo_y_reticula_de_franjas(tmp_path):
    x = np.arange(W)
    a = np.where((x // (W // 16)) % 2 == 0, 30, 220).astype(np.uint8)   # 8 periodos
    a = np.repeat(np.repeat(a[None, :, None], H, 0), 3, 2)
    c = m(guardar(tmp_path, "franjas.png", a))["composicion"]
    assert c["ritmo"]["x"]["periodo"] == pytest.approx(1 / 8, abs=0.01) and c["ritmo"]["x"]["fuerza"] > 0.6
    assert c["reticula"]["columnas"] == 8
    assert c["ritmo"]["y"]["fuerza"] < 0.2
    assert c["orientacion_bordes"]["dominante"] == 90.0 and c["orientacion_bordes"]["anisotropia"] > 0.9


def test_horizonte(tmp_path):
    a = np.zeros((H, W, 3), np.uint8)
    a[:int(0.6 * H)] = (150, 190, 235)
    a[int(0.6 * H):] = (40, 80, 45)
    li = m(guardar(tmp_path, "horizonte.png", a))["composicion"]["lineas"]
    assert li["horizonte"] is not None and li["horizonte"]["y"] == pytest.approx(0.6, abs=0.03)
    assert li["horizontal"] > 0.75 and li["horizonte"]["inclinado"] is False
    tr = rm.ficha(tmp_path / "horizonte.png")["video"]["traduccion"]
    assert any("horizonte" in t["rasgo"] for t in tr)


@pytest.mark.parametrize("colores,tipo", [
    (((230, 120, 20), (20, 110, 230)), "complementaria"),
    (((128, 128, 128), (60, 60, 60)), "acromatica"),
    (((230, 60, 30), (235, 140, 20)), "analoga"),
])
def test_armonia(tmp_path, colores, tipo):
    a = np.zeros((H, W, 3), np.uint8)
    a[:, :W // 2], a[:, W // 2:] = colores
    assert m(guardar(tmp_path, f"{tipo}.png", a))["color"]["armonia"]["tipo"] == tipo


def test_temperatura(tmp_path):
    cal = m(guardar(tmp_path, "calida.png", lienzo((235, 130, 30))))["color"]["temperatura"]
    fri = m(guardar(tmp_path, "fria.png", lienzo((30, 110, 235))))["color"]["temperatura"]
    gri = m(guardar(tmp_path, "gris.png", lienzo((128, 128, 128))))["color"]["temperatura"]
    assert cal > 0.6 and fri < -0.6 and abs(gri) < 0.05


def test_grano_y_bordes(tmp_path):
    rng = np.random.default_rng(3)
    liso = np.full((512, 512, 3), 128, np.float32)
    ruido = np.clip(liso + rng.normal(0, 0.03 * 255, (512, 512, 1)), 0, 255)
    assert m(guardar(tmp_path, "liso.png", liso))["textura"]["grano"] < 0.002
    g = m(guardar(tmp_path, "ruido.png", ruido))["textura"]["grano"]
    assert 0.012 < g < 0.05                                           # σ = 0,03 en sRGB; se mide en L de OKLab
    duro = con_circulo(0.5, 0.5, fondo=(240, 240, 240), color=(20, 20, 20), r=110)
    suave = duro.filter(ImageFilter.GaussianBlur(10))
    bd, bs = m(guardar(tmp_path, "duro.png", duro))["bordes"], m(guardar(tmp_path, "suave.png", suave))["bordes"]
    assert bd["duros"] > 0.8 and bs["duros"] < 0.3


def test_margen(tmp_path):
    im = lienzo((245, 245, 240))
    ImageDraw.Draw(im).rectangle([0.2 * W, 0.25 * H, 0.8 * W, 0.75 * H], fill=(30, 60, 160))
    mg = m(guardar(tmp_path, "margen.png", im))["composicion"]["margen"]
    assert mg["a_sangre"] is False
    assert mg["izq"] == pytest.approx(0.2, abs=0.02) and mg["der"] == pytest.approx(0.2, abs=0.02)
    assert mg["arriba"] == pytest.approx(0.25, abs=0.02) and mg["abajo"] == pytest.approx(0.25, abs=0.02)


def test_ficha_valida_y_rapida_en_2k(tmp_path):
    rng = np.random.default_rng(1)
    a = rng.integers(0, 255, (1440, 2560, 3), np.uint8)
    a[400:900, 600:1500] = (240, 60, 40)
    p = guardar(tmp_path, "2k.png", a)
    f = rm.ficha(p)
    assert rm.validar(f) == []
    assert f["imagen"] == {"ancho": 2560, "alto": 1440, "aspecto": 1.778, "orientacion": "horizontal",
                           "bandas": {"arriba": 0.0, "abajo": 0.0, "izq": 0.0, "der": 0.0}}
    assert f["firma"]["lado"] == 48 and len(f["firma"]["L"]) == 48 * 48 * 4 // 3
    assert f["tiempo_ms"] < 2000
    assert {r["grupo"] for r in f["reproducir"]} == {"estilo", "composicion"}
    assert all(r["tolerancia"] > 0 and r["como"] for r in f["reproducir"])
    assert f["filosofia"]["regla_generadora"] is None and f["video"]["plan"] is None   # capas 2 y 3: del modelo
    pytest.importorskip("jsonschema")
    del f["metricas"]["valores"]["notan3"]
    f["filosofia"]["inventado"] = "x"
    err = rm.validar(f)
    assert any("notan3" in e for e in err) and any("inventado" in e for e in err)


def test_imagen_plana_no_rompe(tmp_path):
    f = rm.ficha(guardar(tmp_path, "plana.png", lienzo((90, 90, 90), (64, 48))))
    assert rm.validar(f) == []
    assert f["metricas"]["composicion"]["lineas"]["n"] == 0 and f["metricas"]["texto"]["hay"] is False


def test_cli_json_y_hoja(tmp_path, run_script):
    p = guardar(tmp_path, "cli.png", con_circulo(2 / 3, 1 / 3))
    r = run_script("ref_metricas.py", p, "--json", "--hoja", tmp_path / "hoja.png", "--ficha", tmp_path / "f.json")
    assert r.returncode == 0, r.stderr
    f = json.loads(r.stdout)
    assert f["metricas"]["composicion"]["tercios"]["punto"] == "sup-der"
    assert json.loads((tmp_path / "f.json").read_text())["version"] == rm.VERSION
    hoja = Image.open(tmp_path / "hoja.png")
    assert hoja.width == 1800 and hoja.height > 800
    assert run_script("ref_metricas.py", tmp_path / "no-existe.png").returncode != 0


# ---------------------------------------------------------------- comparar y agregar

def test_comparar_clon_estilo_y_distinto(tmp_path):
    ref = rm.ficha(guardar(tmp_path, "ref.png", con_circulo(1 / 3, 1 / 3)))
    igual = rm.ficha(guardar(tmp_path, "igual.png", con_circulo(1 / 3 + 0.01, 1 / 3, color=(225, 45, 35))))
    otra = rm.ficha(guardar(tmp_path, "otra.png", con_circulo(0.72, 0.68)))
    inv = rm.ficha(guardar(tmp_path, "inv.png", con_circulo(0.72, 0.68, fondo=(240, 240, 235), color=(20, 60, 200))))

    c = refs.comparar(ref, igual)
    assert c["riesgo_clon"] and c["veredicto"].startswith("clon probable")
    assert all(f["dentro"] for f in c["metricas"])

    c = refs.comparar(ref, otra)                                       # mismo estilo, otra maqueta
    assert c["reproduce_estilo"] and not c["riesgo_clon"]
    assert c["veredicto"] == "reproduce el estilo con composición propia"
    fuera = {f["metrica"] for f in c["metricas"] if not f["dentro"]}
    assert "composicion.puntos_fuertes" in fuera and "valores.notan3.rejilla" in fuera
    assert all(f["grupo"] == "composicion" for f in c["metricas"] if not f["dentro"])

    c = refs.comparar(ref, inv)
    assert c["veredicto"] == "estilo distinto" and not c["reproduce_estilo"]
    ajustar = {a["metrica"]: a for a in c["ajustar"]}
    assert ajustar["valores.mediana"]["sentido"] == "bajar"             # la foto es mucho más clara que la referencia
    assert all(a["como"] for a in c["ajustar"])


def test_comparar_cli(tmp_path, run_script):
    a = guardar(tmp_path, "a.png", con_circulo(1 / 3, 1 / 3))
    b = guardar(tmp_path, "b.png", con_circulo(0.7, 0.7))
    r = run_script("referencias.py", "--comparar", a, b, "--json", "--out", tmp_path / "cmp.json")
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)
    assert c == json.loads((tmp_path / "cmp.json").read_text())
    assert c["resumen"]["estilo"]["total"] == sum(1 for f in c["metricas"] if f["grupo"] == "estilo")
    r = run_script("referencias.py", "--comparar", a, a)
    assert r.returncode == 0 and r.stdout.startswith("clon probable")
    assert run_script("referencias.py", a).returncode != 0             # sin --out ni --comparar


def test_agregar_comun_e_idiosincrasico(tmp_path):
    fichas = {n: rm.ficha(guardar(tmp_path, n, con_circulo(x, y)))
              for n, x, y in (("a.png", 0.25, 0.3), ("b.png", 0.5, 0.5), ("c.png", 0.75, 0.7))}
    ag = refs.agregar(fichas)
    comunes = {c["metrica"]: c for c in ag["comunes"]}
    idio = {c["metrica"]: c for c in ag["idiosincrasicos"]}
    assert {"color.temperatura", "valores.mediana", "bordes.duros"} <= set(comunes)   # el estilo
    assert "composicion.centro_masa.x" in idio                                         # la maqueta de cada una
    assert set(idio["composicion.centro_masa.x"]["se_apartan"]) == {"a.png", "c.png"}
    assert ag["categorias"]["clave"] == {"comun": True, "valores": {n: "baja" for n in fichas}}
    assert comunes["valores.mediana"]["tolerancia"] > 0


def test_referencias_cli_escribe_fichas_y_agregado(tmp_path, run_script):
    d = tmp_path / "refs"
    d.mkdir()
    guardar(d, "uno.png", con_circulo(1 / 3, 1 / 3))
    guardar(d, "dos.png", con_circulo(2 / 3, 2 / 3))
    out = tmp_path / "out"
    r = run_script("referencias.py", d, "--out", out)
    assert r.returncode == 0, r.stderr
    j = json.loads((out / "referencias.json").read_text())
    assert set(j) == {"uno.png", "dos.png"}
    for n, e in j.items():
        assert e["tipo"] == "imagen" and "paleta" in e and "luz" in e      # lo de antes sigue
        f = json.loads(open(e["ficha"]).read())
        assert rm.validar(f) == [] and e["resumen"]["clave"] == "baja"
        assert Image.open(e["hoja_ficha"]).width == 1800
    ag = json.loads((out / "agregado.json").read_text())
    assert ag["n"] == 2 and ag["comunes"] and ag["idiosincrasicos"]
    assert (out / "referencias.png").exists()


# ---------------------------------------------------------------- ronda 3: medidas que faltaban o fallaban

FUENTES = ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf")


def fuente(t):
    from PIL import ImageFont
    for f in FUENTES:
        try:
            return ImageFont.truetype(f, t)
        except OSError:
            continue
    pytest.skip("sin una fuente TrueType en negrita")


def cartel(tam=(1280, 720), titular="KINDLING 1.0", fondo=(20, 22, 30)):
    """Titular grande y dos renglones menores, alineados a la izquierda; un círculo naranja a la derecha."""
    w, h = tam
    im = lienzo(fondo, tam)
    d = ImageDraw.Draw(im)
    d.text((0.08 * w, 0.18 * h), titular, font=fuente(int(0.16 * h)), fill=(250, 250, 250))
    d.text((0.08 * w, 0.42 * h), "microVMs que arrancan en milisegundos", font=fuente(int(0.06 * h)), fill=(200, 200, 210))
    d.text((0.08 * w, 0.52 * h), "y se pliegan cuando no hacen falta", font=fuente(int(0.06 * h)), fill=(200, 200, 210))
    d.ellipse([0.78 * w, 0.62 * h, 0.9 * w, 0.62 * h + 0.12 * w], fill=(240, 120, 30))
    return im


def paisaje(tam=(960, 540), ang=0.0, seed=0):
    """Cielo y tierra con textura y un sol: una «foto» con horizonte, opcionalmente inclinado."""
    w, h = tam
    yy, xx = np.mgrid[:h, :w]
    abajo = yy > 0.55 * h + (xx - w / 2) * np.tan(np.radians(ang))
    rng = np.random.default_rng(seed)
    a = np.where(abajo[..., None], np.array([70, 100, 60]), np.array([150, 190, 240])).astype(np.float32)
    a += cv2.GaussianBlur(rng.normal(0, 40, (h, w, 1)).astype(np.float32), (0, 0), 6)[..., None] * abajo[..., None]
    a += (np.linspace(30, -10, h)[:, None, None]) * ~abajo[..., None]
    cv2.circle(a, (int(0.7 * w), int(0.25 * h)), int(0.05 * w), (255, 235, 170), -1)
    return Image.fromarray(np.clip(cv2.GaussianBlur(a, (0, 0), 1.2), 0, 255).astype(np.uint8))


@pytest.mark.parametrize("x,y", [(0.9, 0.15), (0.06, 0.9), (0.93, 0.5)])
def test_foco_cerca_del_borde(tmp_path, x, y):
    """Antes el margen reflejado de la saliencia inventaba un lóbulo a 0,28 del sujeto."""
    p = m(guardar(tmp_path, "borde.png", con_circulo(x, y, fondo=(128, 128, 128), r=22)))["composicion"]["puntos_fuertes"]
    assert abs(p[0]["x"] - x) < 0.04 and abs(p[0]["y"] - y) < 0.05


@pytest.mark.parametrize("ang", [-8, -4, 5, 10])
def test_horizonte_inclinado(tmp_path, ang):
    f = rm.ficha(guardar(tmp_path, "inclinado.png", paisaje(ang=ang)))
    hz = f["metricas"]["composicion"]["lineas"]["horizonte"]
    assert hz is not None and hz["inclinado"] and abs(hz["angulo"] - ang) <= 1.5 and abs(hz["y"] - 0.55) < 0.04
    assert f["video"]["sugerido"]["paralaje_eje"][1] * ang > 0          # el travelling sigue la inclinación
    assert any("inclinado" in t["rasgo"] for t in f["video"]["traduccion"])


def test_horizonte_no_sale_de_un_subrayado_ni_de_una_pieza_con_texto(tmp_path):
    """El subrayado de un título o la base de unas tarjetas no separan dos regiones; y con texto no guía la cámara."""
    im = cartel()
    w, h = im.size
    ImageDraw.Draw(im).rectangle([0.08 * w, 0.38 * h, 0.92 * w, 0.385 * h], fill=(250, 250, 250))   # subrayado a todo lo ancho
    f = rm.ficha(guardar(tmp_path, "subrayado.png", im))
    assert f["metricas"]["composicion"]["lineas"]["horizonte"] is None
    assert not any("horizonte" in t["rasgo"] for t in f["video"]["traduccion"])
    im = cartel()
    ImageDraw.Draw(im).rectangle([0, 0.8 * h, w, h], fill=(90, 60, 160))        # franja inferior: sí separa dos regiones
    li = rm.ficha(guardar(tmp_path, "franja.png", im))["metricas"]["composicion"]["lineas"]
    assert li["horizonte"] is None and li["horizonte_descartado"]["motivo"] == "pieza_grafica"
    grad = np.repeat(np.linspace(40, 220, H)[:, None], W, 1)                     # un degradado no tiene horizonte
    assert m(guardar(tmp_path, "grad.png", np.stack([grad] * 3, -1)))["composicion"]["lineas"]["horizonte"] is None


def test_bordes_duros_gradua_con_el_desenfoque(tmp_path):
    """Antes saltaba de 1 a 0 y daba 0,95–1 en cualquier imagen real: no discriminaba."""
    base = con_circulo(0.5, 0.5, fondo=(240, 240, 240), color=(20, 20, 20), r=220, tam=(1600, 900))
    d = [m(guardar(tmp_path, f"b{r}.png", base.filter(ImageFilter.GaussianBlur(r))))["bordes"] for r in (0, 4, 6, 8, 15)]
    v = [b["duros"] for b in d]
    assert v[0] == 1.0 and v[-1] < 0.05 and v == sorted(v, reverse=True)
    assert 0.6 < v[1] < 0.95 and 0.3 < v[2] < 0.7 and 0.05 < v[3] < 0.4      # valores intermedios, no un escalón
    anchos = [b["ancho_px"] for b in d]
    assert anchos == sorted(anchos) and anchos[-1] > 4 * anchos[0]
    mixta = con_circulo(0.72, 0.5, fondo=(240, 240, 240), color=(20, 20, 20), r=200, tam=(1600, 900)).filter(ImageFilter.GaussianBlur(15))
    ImageDraw.Draw(mixta).rectangle([150, 250, 550, 650], fill=(20, 20, 20))     # una forma nítida junto a una difusa
    assert 0.25 < m(guardar(tmp_path, "mixta.png", mixta))["bordes"]["duros"] < 0.85   # reparte por masa, no todo o nada


def semitono(paso, ang, tam=(1600, 900)):
    w, h = tam
    im = lienzo((245, 240, 225), tam)
    d = ImageDraw.Draw(im)
    c, s = np.cos(np.radians(ang)), np.sin(np.radians(ang))
    n = int(max(w, h) / paso) + 2
    for j in range(-n, 2 * n):
        for i in range(-n, 2 * n):
            x, y = (i * c - j * s) * paso, (i * s + j * c) * paso
            if -paso < x < w + paso and -paso < y < h + paso:
                d.ellipse([x - 0.3 * paso, y - 0.3 * paso, x + 0.3 * paso, y + 0.3 * paso], fill=(220, 50, 30))
    return im


@pytest.mark.parametrize("paso,ang", [(16, 0), (10, 0), (16, 45), (12, 15)])
def test_semitono_es_un_patron_no_una_reticula(tmp_path, paso, ang):
    """Antes una trama de 16 px salía como «retícula 26×29»."""
    mm = m(guardar(tmp_path, "semitono.png", semitono(paso, ang)))
    pa = mm["patron"]
    assert pa["hay"] and pa["tipo"] == "puntos" and pa["fuerza"] > 0.8
    assert abs(pa["periodo_px"] - paso) <= 1.0 and abs(pa["periodo"] - paso / 1600) < 0.001
    assert min(abs(pa["angulo"] - ang), 90 - abs(pa["angulo"] - ang)) <= 2
    assert mm["composicion"]["reticula"] == {"columnas": None, "filas": None, "confianza": mm["composicion"]["reticula"]["confianza"]}
    assert mm["texto"]["hay"] is False


def test_rayado_diagonal_y_ausencia_de_patron(tmp_path):
    im = lienzo((240, 240, 240), (1600, 900))
    d = ImageDraw.Draw(im)
    for i in range(-10, 20):
        d.line((i * 150, 900, i * 150 + 900, 0), fill=(20, 20, 20), width=12)
    mm = m(guardar(tmp_path, "rayas.png", im))
    pa = mm["patron"]
    assert pa["tipo"] == "rayas" and abs(pa["angulo"] - 135) <= 2 and abs(pa["periodo_px"] - 150 / np.sqrt(2)) < 4
    assert mm["composicion"]["reticula"]["columnas"] is None and mm["composicion"]["reticula"]["filas"] is None
    for n, im in (("circulo.png", con_circulo(0.5, 0.5)), ("cartel.png", cartel()), ("paisaje.png", paisaje())):
        assert m(guardar(tmp_path, n, im))["patron"]["hay"] is False, n
    im = lienzo((245, 245, 245), (1600, 900))                             # una retícula de maqueta sigue siendo retícula
    d = ImageDraw.Draw(im)
    for i in range(4):
        for j in range(3):
            d.rectangle((i * 400 + 30, j * 300 + 30, (i + 1) * 400 - 30, (j + 1) * 300 - 30), fill=(30, 60, 160))
    mm = m(guardar(tmp_path, "ret.png", im))
    assert mm["patron"]["hay"] is False and (mm["composicion"]["reticula"]["columnas"], mm["composicion"]["reticula"]["filas"]) == (4, 3)


def test_texto_grande_de_cartel(tmp_path):
    """«Aa» al 55 % del alto: antes `hay: false` (el filtro descartaba cajas de más del 22 % del alto)."""
    im = lienzo((250, 250, 250), (1600, 900))
    ImageDraw.Draw(im).text((800, 450), "Aa", font=fuente(500), fill=(10, 10, 10), anchor="mm")
    mm = m(guardar(tmp_path, "aa.png", im))
    t = mm["texto"]
    assert t["hay"] and t["bloques"] == 1 and 0.3 < t["cajas"][0]["h"] < 0.6 and t["alineacion"] == "centro"
    assert mm["tipografia"]["hay"] and mm["tipografia"]["peso_clase"] in ("negrita", "extra")
    for n, im in (("circulo.png", con_circulo(0.5, 0.5, r=120)), ("dos.png", con_circulo(0.3, 0.5, r=90))):
        if n == "dos.png":
            ImageDraw.Draw(im).rectangle([380, 100, 560, 280], fill=(230, 40, 30))
        assert m(guardar(tmp_path, n, im))["texto"]["hay"] is False, n     # formas macizas no son letras


def test_tipografia_niveles_peso_y_alineacion(tmp_path):
    mm = m(guardar(tmp_path, "cartel.png", cartel()))
    ti = mm["tipografia"]
    assert ti["hay"] and ti["lineas"] == 3 and ti["alineacion"] == "izquierda" and ti["clase"] is None
    assert [n["lineas"] for n in ti["niveles"]] == [1, 2] and ti["niveles"][0]["escala"] == 1.0
    assert ti["escala"] == pytest.approx(0.06 / 0.16, abs=0.12)          # el segundo nivel, frente al titular
    assert ti["peso_clase"] in ("negrita", "extra") and 0.16 < ti["peso"] < 0.3 and 0 < ti["tracking"] < 0.4
    assert ti["area"] == mm["texto"]["area"] > 0.05
    rep = {r["metrica"]: r for r in rm.reproducir(mm)}
    assert rep["tipografia.peso"]["grupo"] == "estilo" and rep["tipografia.escala"]["objetivo"] == ti["escala"]
    fina = cartel()                                                      # la misma maqueta con trazo fino pesa menos
    from PIL import ImageFont
    try:
        f = ImageFont.truetype(FUENTES[0].replace(" Bold", ""), 115)
    except OSError:
        return
    im = lienzo((20, 22, 30), (1280, 720))
    ImageDraw.Draw(im).text((100, 130), "KINDLING 1.0", font=f, fill=(250, 250, 250))
    fi = m(guardar(tmp_path, "fina.png", im))["tipografia"]
    assert fi["peso"] < ti["peso"] - 0.03 and fi["peso_clase"] in ("fina", "regular") and fi["caja"] == "alta"
    sin = m(guardar(tmp_path, "sin.png", con_circulo(0.5, 0.5)))["tipografia"]
    assert sin["hay"] is False and sin["peso"] is None and sin["niveles"] == []


def test_tratamiento_duotono_desregistro_y_vineta(tmp_path):
    base = np.asarray(paisaje(seed=3), np.float32)
    g = cv2.GaussianBlur(np.random.default_rng(5).random((540, 960)).astype(np.float32), (0, 0), 25)
    g = ((g - g.min()) / (g.max() - g.min()))[..., None]                                   # tono continuo
    duo = (1 - g) * np.array([30, 0, 60]) + g * np.array([255, 230, 120])                  # mapa de degradado
    t = m(guardar(tmp_path, "duo.png", duo))["tratamiento"]
    assert t["duotono"]["hay"] and t["duotono"]["ajuste"] > 0.95 and not t["desregistro"]["hay"]
    dos = np.where(np.arange(960)[None, :, None] < 480, g * np.array([255, 90, 60]), g * np.array([60, 120, 255]))
    assert not m(guardar(tmp_path, "dos.png", dos))["tratamiento"]["duotono"]["hay"]       # mismo valor, dos tonos: no es duotono
    t0 = m(guardar(tmp_path, "base.png", base))["tratamiento"]
    assert not t0["duotono"]["hay"] and not t0["desregistro"]["hay"] and not t0["vineta"]["hay"]
    des = np.asarray(cartel(), np.uint8).copy()
    des[..., 0] = np.roll(des[..., 0], (3, 5), (0, 1))                                      # la tinta roja, 5 px a la derecha y 3 abajo
    d = m(guardar(tmp_path, "des.png", des))["tratamiento"]["desregistro"]
    assert d["hay"] and d["px"] == pytest.approx(np.hypot(5, 3), abs=0.7)
    assert any("desregistro" in x["rasgo"] for x in rm.ficha(tmp_path / "des.png")["video"]["traduccion"])
    h, w = base.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    r2 = ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2) / 0.5
    vin = np.full((h, w, 3), 180, np.float32) * (1 - 0.7 * r2)[..., None]
    v = m(guardar(tmp_path, "vin.png", vin))["tratamiento"]["vineta"]
    assert v["hay"] and v["fuerza"] > 0.1
    assert m(guardar(tmp_path, "circ.png", con_circulo(0.5, 0.5, fondo=(128, 128, 128))))["tratamiento"]["vineta"]["hay"] is False


def variantes(im):
    import io
    w, h = im.size
    b = io.BytesIO()
    im.save(b, "JPEG", quality=80)
    return {"x0.5": im.resize((w // 2, h // 2), Image.LANCZOS), "x0.37": im.resize((int(w * .37), int(h * .37)), Image.LANCZOS),
            "recorte2": im.crop((int(w * .02), int(h * .02), int(w * .98), int(h * .98))),
            "recorte5der": im.crop((0, 0, int(w * .95), h)), "jpeg80": Image.open(io.BytesIO(b.getvalue())).convert("RGB")}


def test_modo_de_video_sugerido_estable(tmp_path):
    """Reescalar, recortar un 2–5 % o recomprimir no cambia el modo ni si hay horizonte (antes, 15 de 62)."""
    for nombre, im in (("cartel", cartel()), ("paisaje", paisaje((1280, 720)).filter(ImageFilter.GaussianBlur(5))), ("circulo", con_circulo(0.4, 0.4, tam=(1280, 720))),
                       ("semitono", semitono(16, 0))):
        f0 = rm.ficha(guardar(tmp_path, f"{nombre}.png", im))
        for vn, vi in variantes(im).items():
            f1 = rm.ficha(guardar(tmp_path, f"{nombre}_{vn}.png", vi))
            assert f1["video"]["sugerido"]["modo"] == f0["video"]["sugerido"]["modo"], (nombre, vn)
            assert f1["video"]["sugerido"]["pieza_grafica"] == f0["video"]["sugerido"]["pieza_grafica"], (nombre, vn)
            assert bool(f1["metricas"]["composicion"]["lineas"]["horizonte"]) == \
                bool(f0["metricas"]["composicion"]["lineas"]["horizonte"]), (nombre, vn)
    assert "capas" not in [x["modo"] for x in rm.ficha(tmp_path / "paisaje.png")["video"]["sugerido"]["modos"]]   # en foto no se ofrece
    assert "capas" in [x["modo"] for x in rm.ficha(tmp_path / "cartel.png")["video"]["sugerido"]["modos"]]


# ---------------------------------------------------------------- ronda 3: --comparar

def tono(im, grados):
    a = np.asarray(im.convert("HSV")).copy()
    a[..., 0] = (a[..., 0].astype(int) + int(grados / 360 * 255)) % 256
    return Image.fromarray(a, "HSV").convert("RGB")


def poster(pal, seed, tam=(1280, 720)):
    """Cinco formas y un titular en posiciones al azar: misma paleta, otra maqueta por semilla."""
    w, h = tam
    rng = np.random.default_rng(seed)
    im = lienzo(pal[0], tam)
    d = ImageDraw.Draw(im)
    for i in range(5):
        x, y = rng.uniform(.05, .8) * w, rng.uniform(.05, .75) * h
        bw, bh = rng.uniform(.1, .3) * w, rng.uniform(.1, .3) * h
        (d.ellipse if i % 2 else d.rectangle)((x, y, x + bw, y + bh), fill=pal[1 + i % (len(pal) - 1)])
    d.text((rng.uniform(.05, .5) * w, rng.uniform(.1, .8) * h), "TITULAR 1.0", font=fuente(int(0.1 * h)), fill=pal[-1])
    return im


PALETA = [(18, 22, 40), (240, 90, 40), (250, 200, 60), (60, 180, 200), (245, 240, 230)]


def test_comparar_el_color_es_condicion_necesaria_del_estilo(tmp_path):
    """Otra maqueta con la paleta girada 120° daba «reproduce el estilo» en 19 de 24 pares: eran 2 votos de 23."""
    ref = rm.ficha(guardar(tmp_path, "ref.png", poster(PALETA, 1)))
    misma = refs.comparar(ref, rm.ficha(guardar(tmp_path, "misma.png", poster(PALETA, 2))))
    assert misma["veredicto"] == "reproduce el estilo con composición propia" and all(misma["color"].values())
    for s in (2, 3, 4):
        c = refs.comparar(ref, rm.ficha(guardar(tmp_path, f"giro{s}.png", tono(poster(PALETA, s), 120))))
        assert c["veredicto"] == "estilo distinto" and not c["reproduce_estilo"] and not c["riesgo_clon"]
        assert not c["color"]["tono_principal"] and not c["color"]["paleta_tonos"]
        assert c["ajustar"][0]["metrica"] in rm.COLOR_NECESARIO          # lo primero que hay que ajustar es el color
    c = refs.comparar(ref, rm.ficha(guardar(tmp_path, "mismagiro.png", tono(poster(PALETA, 1), 120))))
    assert c["veredicto"].startswith("misma maqueta con otro estilo") and not c["riesgo_clon"]   # se copió la maqueta
    gris = refs.comparar(ref, rm.ficha(guardar(tmp_path, "gris.png", poster(PALETA, 1).convert("L").convert("RGB"))))
    assert gris["veredicto"].startswith("misma maqueta con otro estilo") and gris["derivado"]["es"]


def test_comparar_no_da_falsos_clones_entre_maquetas_distintas(tmp_path):
    """Misma paleta, maquetas al azar: 24 de 132 pares (18 %) salían «clon probable» con notan ≤ 0,45 y focos ≤ 0,15."""
    fs = [rm.ficha(guardar(tmp_path, f"p{s}.png", poster(PALETA, 100 + s))) for s in range(8)]
    ver = [refs.comparar(a, b) for i, a in enumerate(fs) for b in fs[i + 1:]]
    assert sum(c["riesgo_clon"] for c in ver) <= 1                       # ≤ 1 de 28
    assert sum(c["reproduce_estilo"] for c in ver) >= 20                 # y el estilo se sigue reconociendo
    assert not any(c["derivado"] and c["derivado"]["es"] for c in ver)
    tn = {r: t for r, _, t, _ in rm.ESPECIALES}
    assert tn["valores.notan3.rejilla"] <= 0.2 and tn["composicion.puntos_fuertes"] <= 0.08


def test_comparar_reconoce_derivados_geometricos_y_fotometricos(tmp_path):
    """Espejo, giros, recortes y bandas negras: antes se escapaban 11 de 20. Brillo y grano siguen siendo clon."""
    from PIL import ImageEnhance, ImageOps
    im = poster(PALETA, 1)
    w, h = im.size
    ref = rm.ficha(guardar(tmp_path, "ref.png", im))
    ruido = np.asarray(im, np.float32) + np.random.default_rng(0).normal(0, 10, (h, w, 3))
    casos = {"espejo": (ImageOps.mirror(im), "espejo"), "giro_180": (im.rotate(180), "giro_180"),
             "giro_90": (im.rotate(90, expand=True), None), "giro_270": (im.rotate(270, expand=True), None),
             "recorte80": (im.crop((int(.1 * w), int(.1 * h), int(.9 * w), int(.9 * h))), "igual"),
             "recorte70izq": (im.crop((0, 0, int(.7 * w), h)), "igual"),
             "bandas": (ImageOps.expand(im, border=(0, int(.15 * h)), fill=(0, 0, 0)), "igual"),
             "pilares": (ImageOps.expand(im, border=(int(.12 * w), 0), fill=(0, 0, 0)), "igual"),
             "espejo_recorte": (ImageOps.mirror(im).crop((int(.1 * w), int(.1 * h), int(.9 * w), int(.9 * h))), "espejo"),
             "brillo": (ImageEnhance.Brightness(im).enhance(1.12), "igual"),
             "saturacion": (ImageEnhance.Color(im).enhance(0.7), "igual"),
             "contraste": (ImageEnhance.Contrast(im).enhance(1.25), "igual"),
             "grano": (Image.fromarray(np.clip(ruido, 0, 255).astype(np.uint8)), "igual"),
             "desenfoque": (im.filter(ImageFilter.GaussianBlur(3)), "igual")}
    for nombre, (v, geo) in casos.items():
        f = rm.ficha(guardar(tmp_path, f"{nombre}.png", v))
        c = refs.comparar(ref, f)
        assert c["riesgo_clon"] and c["veredicto"].startswith("clon probable"), (nombre, c["veredicto"], c["derivado"])
        assert c["derivado"]["es"] and c["derivado"]["correlacion"] >= refs.DERIVADO_MIN, nombre
        if geo:
            assert c["derivado"]["transformacion"] == geo, (nombre, c["derivado"])
        if nombre in ("bandas", "pilares"):
            ban = f["imagen"]["bandas"]
            assert (ban["arriba"] > 0.1 and ban["abajo"] > 0.1) if nombre == "bandas" else (ban["izq"] > 0.08 and ban["der"] > 0.08)
        if "recorte" in nombre:
            assert c["derivado"]["recorte"]["de"] == "foto" and "recorte" in c["veredicto"]
    otra = refs.comparar(ref, rm.ficha(guardar(tmp_path, "otra.png", paisaje())))
    assert otra["veredicto"] == "estilo distinto" and not otra["derivado"]["es"]
    # una sola forma sobre fondo liso casa con cualquier recorte de sí misma: eso no prueba un derivado
    c = refs.comparar(rm.ficha(guardar(tmp_path, "c1.png", con_circulo(1 / 3, 1 / 3))),
                      rm.ficha(guardar(tmp_path, "c2.png", con_circulo(0.6, 0.6))))
    assert not c["riesgo_clon"] and not (c["derivado"] and c["derivado"]["es"])


# ---------------------------------------------------------------- ronda 3: la capa 2 se exige y se lee

CAPA2 = {"movimiento": "cartel suizo pasado por terminal", "emocion": "calma técnica, sin urgencia",
         "regla_generadora": "un solo acento cálido (≤ 5 % del área) sobre un fondo oscuro que ocupa más del 60 %",
         "donde_no": "el acento nunca toca el titular; nada se mueve en el tercio inferior",
         "que_la_distingue": "titular en negrita al 16 % del alto con un segundo nivel al 38 %",
         "no_copiar": ["la posición exacta del círculo (0,84; 0,75)"], "como_mejorar": ["abrir el rango de valores"]}


def test_validar_completa_exige_la_capa_2(tmp_path, run_script):
    f = rm.ficha(guardar(tmp_path, "cartel.png", cartel()))
    assert rm.validar(f) == []                                          # la ficha recién medida es válida…
    err = rm.validar(f, completa=True)                                  # …pero no está completa
    assert len(err) == len(rm.CAPA2) and all("sin rellenar" in e for e in err)
    f["filosofia"].update(CAPA2)
    assert rm.validar(f, completa=True) == [] and rm.filosofia_pendiente(f) == []
    sin_cifras = json.loads(json.dumps(f))
    sin_cifras["filosofia"].update({k: "texto bonito sin ninguna medida" if isinstance(v, str) else ["texto sin medida"]
                                    for k, v in CAPA2.items()})
    assert any("cifra" in e for e in rm.validar(sin_cifras, completa=True))   # una filosofía sin cifras no se puede comprobar
    vacia, llena = tmp_path / "vacia.json", tmp_path / "llena.json"
    vacia.write_text(json.dumps(rm.ficha(tmp_path / "cartel.png")))
    llena.write_text(json.dumps(f))
    assert run_script("ref_metricas.py", vacia, "--validar").returncode == 0
    r = run_script("ref_metricas.py", vacia, "--validar", "--completa")
    assert r.returncode == 1 and "filosofia.regla_generadora" in r.stdout
    assert run_script("ref_metricas.py", llena, "--validar", "--completa").returncode == 0
    r = run_script("referencias.py", "--validar", vacia, llena)
    assert r.returncode == 1 and "1/2 fichas completas" in r.stdout


def test_referencias_conserva_la_capa_2_y_la_comparacion_la_cita(tmp_path, run_script):
    d = tmp_path / "refs"
    d.mkdir()
    guardar(d, "uno.png", cartel())
    guardar(d, "dos.png", poster(PALETA, 3))
    out = tmp_path / "out"
    r = run_script("referencias.py", d, "--out", out)
    assert r.returncode == 0 and "capa 2 (filosofía) sin rellenar en 2 ficha(s)" in r.stdout
    assert run_script("referencias.py", "--validar", out).returncode == 1
    fj = out / "fichas" / "uno.json"
    f = json.loads(fj.read_text())
    f["filosofia"].update(CAPA2)
    f["video"]["plan"] = [{"t": 0, "que": "entra el titular"}]
    fj.write_text(json.dumps(f))
    r = run_script("referencias.py", d, "--out", out)                   # volver a medir no borra lo que escribió el modelo
    f2 = json.loads(fj.read_text())
    assert f2["filosofia"]["regla_generadora"] == CAPA2["regla_generadora"] and f2["video"]["plan"] == f["video"]["plan"]
    assert "sin rellenar en 1 ficha(s): dos.png" in r.stdout
    ag = json.loads((out / "agregado.json").read_text())
    assert ag["filosofia"]["pendiente"] == ["dos.png"]
    assert ag["filosofia"]["por_referencia"]["uno.png"]["regla_generadora"] == CAPA2["regla_generadora"]
    c = refs.comparar(f2, rm.ficha(d / "dos.png"))
    assert c["filosofia_ref"]["no_copiar"] == CAPA2["no_copiar"] and "aviso" not in c
    assert "aviso" in refs.comparar(rm.ficha(d / "dos.png"), f2)         # sin capa 2 no hay nada que citar: se avisa
    r = run_script("referencias.py", "--comparar", fj, d / "dos.png")
    assert "referencia · regla_generadora: un solo acento" in r.stdout and "referencia · no_copiar" in r.stdout
