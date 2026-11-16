"""imagen_a_video.py: cada modo produce los fotogramas y la duración pedidos, y el movimiento sigue a la ficha."""
import argparse
import json
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageDraw

cv2 = pytest.importorskip("cv2")
import imagen_a_video as iav  # noqa: E402
import ref_metricas as rm  # noqa: E402

FFMPEG = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="sin ffmpeg/ffprobe")
W, H = 480, 270


@pytest.fixture
def imagen(tmp_path):
    """Fondo oscuro con degradado, un círculo rojo (foco principal) arriba a la derecha y uno azul menor."""
    y = np.linspace(20, 60, H)[:, None, None]
    a = np.clip(np.zeros((H, W, 3)) + y, 0, 255).astype(np.uint8)
    im = Image.fromarray(a)
    d = ImageDraw.Draw(im)
    d.ellipse([0.7 * W - 36, 0.3 * H - 36, 0.7 * W + 36, 0.3 * H + 36], fill=(235, 40, 30))
    d.ellipse([0.25 * W - 16, 0.7 * H - 16, 0.25 * W + 16, 0.7 * H + 16], fill=(40, 90, 230))
    p = tmp_path / "img.png"
    im.save(p)
    return p


def args(imagen, modo, **kw):
    base = dict(imagen=str(imagen), modo=modo, dur=1.0, fps=12, out=None, ficha=None, lienzo=None, max=480,
                amp=0.012, zoom=0.06, orden="saliencia", grano="0", profundidad="proxy", motor="auto",
                fotogramas=None, crf=23, semilla=7)
    base.update(kw)
    return argparse.Namespace(**base)


def escena(imagen, modo, **kw):
    a = args(imagen, modo, **kw)
    ficha, modo, tam, f, plan, *_ = iav.preparar(a)
    return ficha, tam, f, plan


def sonda(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=nb_read_frames,width,height,r_frame_rate,pix_fmt,codec_name:format=duration",
                        "-of", "json", str(p)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    return j["streams"][0], float(j["format"]["duration"])


@FFMPEG
@pytest.mark.parametrize("modo", iav.MODOS)
def test_cada_modo_renderiza_n_fotogramas(tmp_path, imagen, run_script, modo):
    out = tmp_path / f"{modo}.mp4"
    r = run_script("imagen_a_video.py", imagen, "--modo", modo, "--dur", "1.5", "--fps", "12", "--max", "480",
                   "--out", out)
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert info["modo"] == modo and info["fotogramas"] == 18 and info["dur_s"] == 1.5
    assert info["render_s"] > 0 and info["ms_por_fotograma"] > 0
    s, dur = sonda(out)
    assert int(s["nb_read_frames"]) == 18
    assert dur == pytest.approx(1.5, abs=0.05)
    assert (s["width"], s["height"]) == (480, 270) and s["r_frame_rate"] == "12/1"
    assert s["codec_name"] == "h264" and s["pix_fmt"] == "yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf", "select=eq(n\\,0)+eq(n\\,17)",
                    "-fps_mode", "passthrough", str(tmp_path / "f%d.png")], check=True)
    a, b = (np.asarray(Image.open(tmp_path / f"f{i}.png"), np.int16) for i in (1, 2))
    assert np.abs(a - b).mean() > 0.3                                  # se mueve: no es la foto repetida


@FFMPEG
def test_lienzo_vertical_y_fps_fraccionario(tmp_path, imagen, run_script):
    out = tmp_path / "v.mp4"
    r = run_script("imagen_a_video.py", imagen, "--modo", "kenburns", "--dur", "1", "--fps", "24", "--lienzo",
                   "270x480", "--out", out)
    assert r.returncode == 0, r.stderr
    s, dur = sonda(out)
    assert (s["width"], s["height"]) == (270, 480) and int(s["nb_read_frames"]) == 24


def test_modo_por_defecto_es_el_sugerido_por_la_ficha(imagen):
    a = args(imagen, None)
    ficha, modo, *_ = iav.preparar(a)
    assert modo == ficha["video"]["sugerido"]["modo"] and modo in iav.MODOS


def test_kenburns_va_del_general_a_los_focos_por_saliencia(imagen):
    ficha, (w, h), f, plan = escena(imagen, "kenburns", dur=4.0)
    pts = ficha["metricas"]["composicion"]["puntos_fuertes"]
    assert abs(pts[0]["x"] - 0.7) < 0.06 and abs(pts[0]["y"] - 0.3) < 0.08   # el rojo es el foco principal
    paradas = plan["paradas"]
    assert paradas[0]["zoom"] < 1.1 and paradas[1]["zoom"] > 1.2
    for q, p in zip(paradas[1:], pts):                                 # cada parada es su foco, con la ventana dentro de la imagen
        assert abs(q["x"] - p["x"]) < 0.06 and abs(q["y"] - p["y"]) < 0.06
    assert plan["velocidad_punta"] <= iav.VEL_MAX + 1e-6
    orig = np.asarray(Image.open(imagen).convert("RGB"), np.int16)
    assert np.abs(f(0.0).astype(np.int16) - orig).mean() < 6           # empieza en el plano general
    medio = f(1 / (len(paradas) - 1))                                  # primera parada: el foco, centrado
    r, g, b = (medio[h // 2 - 10:h // 2 + 10, w // 2 - 10:w // 2 + 10, i].mean() for i in range(3))
    assert r > 180 and g < 90 and b < 90
    inv = escena(imagen, "kenburns", dur=4.0, orden="inverso")[3]["paradas"]
    assert inv[-1]["zoom"] < 1.1 and abs(inv[-2]["x"] - pts[0]["x"]) < 0.06 and abs(inv[-2]["y"] - pts[0]["y"]) < 0.06


def test_ciclo_no_tiene_costura(imagen):
    _, _, f, plan = escena(imagen, "ciclo")
    assert plan["bucle"] is True
    a, b, medio = f(0.0), f(1.0), f(0.5)
    assert np.array_equal(a, b)                                        # el fotograma N sería el 0
    assert np.abs(a.astype(np.int16) - f(0.25)).mean() > 0.2           # pero en medio se mueve
    n = 12                                                             # el salto último→primero es como cualquier otro
    paso = [np.abs(f(i / n).astype(np.int16) - f((i + 1) / n)).mean() for i in range(n)]
    assert paso[-1] <= 1.5 * max(paso[:-1]) + 0.05
    assert medio.shape == a.shape


def test_revelado_va_del_valor_dominante_a_la_imagen(imagen):
    ficha, (w, h), f, plan = escena(imagen, "revelado", zoom=0.0)
    orig = np.asarray(Image.open(imagen).convert("RGB"), np.int16)
    ini, fin = f(0.0), f(1.0)
    assert ini.std(axis=(0, 1)).max() < 1.0                            # arranca en un color plano
    assert plan["valor_dominante"] == "oscuro"
    assert np.abs(fin.astype(np.int16) - orig).mean() < 1.0            # termina en la imagen
    cubierto = [(np.abs(f(u).astype(np.int16) - ini).sum(2) > 12).mean() for u in (0.15, 0.3, 0.6)]
    assert cubierto[0] < cubierto[1] <= cubierto[2]                    # la figura crece
    temprano = np.abs(f(0.2).astype(np.int16) - ini).sum(2) > 12       # y nace en el foco principal
    ys, xs = np.nonzero(temprano)
    foco = plan["foco"]
    assert len(xs) and abs(xs.mean() / w - foco[0]) < 0.15 and abs(ys.mean() / h - foco[1]) < 0.2


def test_parallax_mueve_mas_lo_cercano_y_respeta_el_mapa(tmp_path, imagen):
    mapa = np.zeros((H, W), np.uint8)
    mapa[:, W // 2:] = 255                                             # derecha cerca, izquierda lejos
    Image.fromarray(mapa).save(tmp_path / "prof.png")
    _, (w, h), f, plan = escena(imagen, "parallax", profundidad=str(tmp_path / "prof.png"), motor="malla", zoom=0.0,
                                amp=0.03)
    assert plan["profundidad"] == "mapa:prof.png" and plan["motor"] == "malla"
    a, b = f(0.0).astype(np.int16), f(1.0).astype(np.int16)

    def cx(fr, canal, x0, x1):                                         # centro en x de un color en una franja
        m = (fr[:, x0:x1, canal] > 150) & (fr[:, x0:x1, 1] < 110)
        return np.nonzero(m)[1].mean() + x0
    rojo = cx(b, 0, w // 2, w) - cx(a, 0, w // 2, w)                   # cerca: se desplaza
    azul = cx(b, 2, 0, w // 2) - cx(a, 2, 0, w // 2)                   # lejos: al revés
    assert abs(rojo) > 4 and abs(azul) > 4 and rojo * azul < 0


def test_capas_entran_escalonadas_y_grafica_usa_motor_rigido(tmp_path):
    im = Image.new("RGB", (W, H), (20, 24, 36))
    d = ImageDraw.Draw(im)
    d.rectangle([40, 40, 200, 110], fill=(245, 245, 245))
    d.rectangle([280, 150, 440, 230], fill=(250, 150, 0))
    p = tmp_path / "grafica.png"
    im.save(p)
    ficha, _, f, plan = escena(p, "capas")
    orig = np.asarray(im, np.int16)
    assert len(plan["capas"]) >= 1 and plan["entradas_s"] == sorted(plan["entradas_s"])
    falta0 = np.abs(f(0.0).astype(np.int16) - orig).mean()
    falta1 = np.abs(f(1.0).astype(np.int16) - orig).mean()
    assert falta0 > 4 * max(falta1, 0.5)                               # al principio faltan las formas; al final están
    assert f(0.0)[70, 120].max() < 90                                  # donde irá la caja blanca aún hay fondo
    assert ficha["video"]["sugerido"]["pieza_grafica"] is True
    assert escena(p, "parallax")[3]["motor"] == "rigido"
    fr = escena(p, "parallax", amp=0.03)[2](1.0)                       # las cajas se mueven rígidas: siguen planas
    assert (fr[60:90, 80:160] > 235).all()


def test_grano_cambia_por_fotograma_y_auto_sigue_a_la_ficha(imagen):
    g = iav.grano((W, H), 0.5, 7)
    fr = np.full((H, W, 3), 128, np.uint8)
    a, b = iav.con_grano(fr, g, 0), iav.con_grano(fr, g, 1)
    assert a.std() > 2 and np.abs(a.astype(np.int16) - b).mean() > 1
    assert np.array_equal(iav.con_grano(fr, g, 0), iav.con_grano(fr, g, len(g)))   # se rota
    assert iav.grano((W, H), 0, 7) is None and iav.con_grano(fr, None, 3) is fr
    assert rm.ficha(imagen)["video"]["sugerido"]["grano"] < 0.05       # imagen limpia: auto no ensucia


@FFMPEG
def test_fotogramas_plan_y_prompt(tmp_path, imagen, run_script):
    r = run_script("imagen_a_video.py", imagen, "--modo", "revelado", "--dur", "2", "--fps", "12", "--fotogramas",
                   "0.5,1.9", "--out", tmp_path / "x.mp4")
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert len(info["png"]) == 2 and all(Image.open(p).size == (480, 270) for p in info["png"])
    assert not (tmp_path / "x.mp4").exists()
    r = run_script("imagen_a_video.py", imagen, "--plan")
    plan = json.loads(r.stdout)
    assert plan["sugerido"]["modo"] in iav.MODOS and plan["kenburns"][0]["zoom"] < 1.1
    r = run_script("imagen_a_video.py", imagen, "--prompt-ia", "--dur", "3")
    pr = json.loads(r.stdout)
    assert pr["prompt"].startswith("IMAGE-TO-VIDEO") and "3.0 s" in pr["prompt"] and "low-key" in pr["prompt"]
    assert "Avoid:" in pr["prompt"] and pr["modo_local_equivalente"] in iav.MODOS
    assert run_script("imagen_a_video.py", imagen, "--modo", "ciclo").returncode != 0      # falta --out


# ---------------------------------------------------------------- ronda 3

def _fuente(t):
    from PIL import ImageFont
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        try:
            return ImageFont.truetype(f, t)
        except OSError:
            continue
    pytest.skip("sin una fuente TrueType en negrita")


@pytest.fixture
def cartel(tmp_path):
    """Titular a la izquierda, tarjeta naranja a la derecha y dos pegatinas de adorno en las esquinas."""
    w, h = 1280, 640
    im = Image.new("RGB", (w, h), (20, 22, 34))
    d = ImageDraw.Draw(im)
    d.text((80, 170), "FILMCRAFT", font=_fuente(110), fill=(245, 245, 245))
    d.text((80, 290), "STUDIO", font=_fuente(110), fill=(245, 245, 245))
    d.text((80, 430), "design systems de video", font=_fuente(36), fill=(250, 160, 30))
    d.rectangle([880, 150, 1150, 420], fill=(250, 150, 0))
    d.rectangle([1200, 570, 1280, 640], fill=(230, 60, 220))             # adorno pegado a la esquina
    d.rectangle([0, 0, 60, 50], fill=(160, 90, 250))
    p = tmp_path / "cartel.png"
    im.save(p)
    return p


def _cortada(k, x, y, z):
    m = 0.5 / z
    ix = max(0.0, min(k["x"] + k["w"], x + m) - max(k["x"], x - m))
    iy = max(0.0, min(k["y"] + k["h"], y + m) - max(k["y"], y - m))
    return 0.02 < ix * iy / (k["w"] * k["h"]) < 0.98                     # ni entera dentro ni entera fuera


@pytest.mark.parametrize("orden", ["saliencia", "inverso"])
def test_kenburns_no_corta_titulares_ni_para_en_adornos(cartel, orden):
    """En el banner cortaba el titular a media palabra en 63 de 120 fotogramas y paraba en (0,976; 0,951)."""
    ficha = rm.ficha(cartel)
    cajas = ficha["metricas"]["texto"]["cajas"]
    alto = max(k["h"] for k in cajas)
    titulares = [k for k in cajas if k["h"] >= 0.6 * alto]
    assert len(cajas) >= 3 and len(titulares) == 2
    paradas, enc = iav.encuadres(ficha, 4.0, orden)
    for i in range(121):
        x, y, z = enc(i / 120)
        assert not any(_cortada(k, x, y, z) for k in titulares), (i, x, y, z)
        assert 0.5 / z - 1e-6 <= x <= 1 - 0.5 / z + 1e-6 and 0.5 / z - 1e-6 <= y <= 1 - 0.5 / z + 1e-6
    x, y, z = enc(1.0)                                                   # el encuadre final contiene el texto entero
    m = 0.5 / z
    assert all(x - m <= k["x"] and k["x"] + k["w"] <= x + m and y - m <= k["y"] and k["y"] + k["h"] <= y + m for k in cajas)
    foco = [q for q in paradas if q["zoom"] > 1.04]
    assert all(iav.BORDE_MIN <= q["x"] <= 1 - iav.BORDE_MIN and iav.BORDE_MIN <= q["y"] <= 1 - iav.BORDE_MIN for q in foco)
    pasos = [enc(i / 120) for i in range(121)]                           # y la cámara no corre
    v = [np.hypot(np.hypot(b[0] - a[0], b[1] - a[1]) * np.sqrt(a[2] * b[2]), np.log(b[2] / a[2])) * 30
         for a, b in zip(pasos, pasos[1:])]
    assert max(v) <= iav.VEL_MAX * 1.25


def test_kenburns_limita_la_velocidad_quitando_paradas(tmp_path):
    im = Image.new("RGB", (960, 540), (24, 26, 34))
    d = ImageDraw.Draw(im)
    for (x, y), c in zip(((0.15, 0.2), (0.85, 0.25), (0.2, 0.8), (0.82, 0.78)), ((235, 40, 30), (40, 90, 230), (250, 200, 40), (60, 200, 120))):
        d.ellipse([x * 960 - 34, y * 540 - 34, x * 960 + 34, y * 540 + 34], fill=c)
    p = tmp_path / "cuatro.png"
    im.save(p)
    ficha = rm.ficha(p)
    assert len(ficha["metricas"]["composicion"]["puntos_fuertes"]) >= 3
    corta, larga = iav.ruta_camara(ficha, 3.0), iav.ruta_camara(ficha, 20.0)
    assert len(corta) < len(larga) <= 5                                  # en 3 s no da tiempo a recorrerlos todos
    for ruta, dur in ((corta, 3.0), (larga, 20.0)):
        assert iav.velocidad_punta(ruta, dur) <= iav.VEL_MAX + 1e-6


def test_capas_en_foto_no_dejan_trazos_oscuros(tmp_path):
    """Sin fondo liso las capas se tocan: al separarse asomaba el relleno como trazos oscuros en las crestas."""
    h, w = 540, 960
    yy, xx = np.mgrid[:h, :w]
    a = np.zeros((h, w, 3), np.float32)
    for i, (c0, c1) in enumerate((((120, 150, 255), (200, 190, 255)), ((255, 110, 90), (230, 140, 160)),
                                  ((40, 110, 50), (90, 150, 70)), ((170, 220, 90), (210, 250, 110)))):
        cresta = h * (0.15 + 0.22 * i) + 60 * np.sin(xx / w * 3.1 + i)   # lomas suaves, una sobre otra
        t = np.clip((yy - cresta) / (0.3 * h), 0, 1)[..., None]
        capa = (1 - t) * np.array(c0, np.float32) + t * np.array(c1, np.float32)
        a = np.where((yy >= cresta)[..., None], capa, a)
    a = cv2.GaussianBlur(a, (0, 0), 5) + np.random.default_rng(2).normal(0, 4, a.shape)   # foto: bordes blandos y grano
    p = tmp_path / "lomas.png"
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(p)
    ficha, tam, f, plan = escena(p, "capas", max=960)
    assert ficha["video"]["sugerido"]["pieza_grafica"] is False and "aviso" in plan and plan["entradas_s"] == []
    assert "capas" not in [x["modo"] for x in ficha["video"]["sugerido"]["modos"]]
    src = cv2.cvtColor(np.asarray(Image.open(p).convert("RGB")), cv2.COLOR_RGB2GRAY)
    minimo = cv2.erode(src, np.ones((61, 61), np.uint8)).astype(int)     # lo más oscuro que hay cerca en el original
    for u in (0.0, 0.3, 1.0):
        fr = cv2.cvtColor(f(u), cv2.COLOR_RGB2GRAY).astype(int)
        assert (fr < minimo - 20).mean() < 0.001, u                      # nada más oscuro que su entorno original
    assert np.abs(f(0.0).astype(int) - np.asarray(Image.open(p).convert("RGB"), int)).mean() < 6   # sin entrada: la imagen está entera


def test_prompt_y_plan_leen_la_filosofia_y_no_inventan_horizontes(cartel, tmp_path, run_script):
    ficha = rm.ficha(cartel)
    im = Image.open(cartel).copy()
    ImageDraw.Draw(im).rectangle([0, 520, 1280, 640], fill=(90, 60, 160))    # franja a todo lo ancho: no es un horizonte
    franja = tmp_path / "franja.png"
    im.save(franja)
    pr = iav.prompt_ia(rm.ficha(franja))
    assert "horizon" not in pr["prompt"] and "never morphs or gets cropped" in pr["prompt"]
    assert pr["filosofia"]["usada"] == [] and pr["filosofia"]["pendiente"] and "capa 2" in pr["notas"][0]
    plan = iav.plan_de(ficha, 4.0)
    assert "aviso" in plan and plan["filosofia"] == {} and plan["texto_protegido"]["todo"]
    ficha["filosofia"].update({"movimiento": "cartel suizo pasado por terminal", "emocion": "calma técnica",
                               "regla_generadora": "un solo acento naranja (≤ 10 % del área) sobre fondo oscuro",
                               "donde_no": "el acento no toca el titular", "que_la_distingue": "titular al 17 % del alto",
                               "no_copiar": ["la tarjeta en (0,79; 0,45)"], "como_mejorar": ["quitar una pegatina"]})
    pr = iav.prompt_ia(ficha)
    assert "Rule of the style (must hold in every frame): un solo acento naranja" in pr["prompt"]
    assert "Mood: calma técnica." in pr["prompt"] and "never: el acento no toca el titular" in pr["prompt"]
    assert "titular al 17 % del alto" in pr["prompt"] and pr["filosofia"]["pendiente"] == []
    assert set(pr["filosofia"]["usada"]) == {"regla_generadora", "movimiento", "emocion", "que_la_distingue", "donde_no"}
    plan = iav.plan_de(ficha, 4.0)
    assert "aviso" not in plan and plan["filosofia"]["regla_generadora"].startswith("un solo acento")
    assert any("el acento no toca el titular" in c for c in plan["criterio"])
    fj = tmp_path / "ficha.json"
    fj.write_text(json.dumps(ficha))
    r = run_script("imagen_a_video.py", cartel, "--plan", "--ficha", fj)
    assert r.returncode == 0 and json.loads(r.stdout)["filosofia"]["donde_no"] == "el acento no toca el titular"
    # foto con horizonte inclinado: el prompt lo dice y pide conservar la inclinación
    h, w = 540, 960
    yy, xx = np.mgrid[:h, :w]
    abajo = yy > 0.55 * h + (xx - w / 2) * np.tan(np.radians(6))
    a = np.where(abajo[..., None], np.array([70, 100, 60]), np.array([150, 190, 240])).astype(np.float32)
    a += cv2.GaussianBlur(np.random.default_rng(1).normal(0, 40, (h, w, 1)).astype(np.float32), (0, 0), 6)[..., None] * abajo[..., None]
    foto = tmp_path / "foto.png"
    Image.fromarray(np.clip(cv2.GaussianBlur(a, (0, 0), 4), 0, 255).astype(np.uint8)).save(foto)
    pr = iav.prompt_ia(rm.ficha(foto))
    assert "tilted 6 degrees; keep that tilt" in pr["prompt"]
