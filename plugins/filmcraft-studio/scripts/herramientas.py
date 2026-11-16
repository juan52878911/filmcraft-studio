#!/usr/bin/env python3
"""Qué herramientas de video hay en esta máquina, con versión, para qué sirve cada una y cómo se instala.

Uso: herramientas.py [--json] [--para motor]      motor: camara, pantalla, codigo, 3d, 2d, montaje, audio, voz, ia, promo
     herramientas.py --doctor [--ds ID] [--para motor] [--json]   preflight: obligatorio / recomendado / opcional
                    (--para camara|montaje|voz: whisper-cli y su modelo son obligatorios; úsalo antes de montar;
                     --para promo|codigo|pantalla: FilmCraft CLI baja a recomendado y se comprueba VHS)

La preproducción lo corre antes de preguntar: solo se ofrecen motores que estén instalados (o se dice qué
instalar y se pide permiso). No instala nada.

--doctor comprueba lo que el plugin necesita para funcionar (FilmCraft: CLI en $FILMCRAFT_CLI o
filmcraft-cli, ffmpeg/ffprobe, Pillow y numpy), lo recomendado (app FilmCraft, whisper.cpp y su modelo
ggml, swiftc y sips en macOS, OpenCV, Blender, fuentes del DS con --ds) y lo opcional de otros
ecosistemas (bloques, Remotion/npx, HyperFrames, ElevenLabs/Suno por variable de entorno, MCP
filmcraft, jsonschema). Sale con 0 si todo lo obligatorio está y con 1 si falta algo, diciendo cómo
arreglarlo.
"""
import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

MAC = platform.system() == "Darwin"
BLOQUES = Path(os.environ.get("BLOQUES_HOME", Path.home() / "Documents/GitHub/bloques")) / "bin/bloques"


def _inst(mac, otro):
    return mac if MAC else otro

# nombre, motores, binarios en PATH, rutas de app, argumento de versión, para qué, licencia, instalación
CATALOGO = [
    ("FilmCraft", ["montaje", "camara"], [], ["/Applications/FilmCraft.app"], None,
     "montaje, subtítulos, color, mezcla y ensamblado de todas las escenas (MCP filmcraft)", "Apache-2.0",
     "github.com/storytold/filmcraft (CLI en ~/.local/bin/filmcraft-cli o $FILMCRAFT_CLI)"),
    ("Blender", ["3d", "2d", "montaje"], ["blender"], ["/Applications/Blender.app/Contents/MacOS/Blender"],
     "--version", "3D, Grease Pencil, compositor y VSE sin interfaz (motor_blender.py)", "GPL",
     "brew install --cask blender"),
    ("ffmpeg", ["codigo", "montaje", "audio"], ["ffmpeg"], [], "-version",
     "codificar, recortar, escalar, filtros, loudness (ebur128/loudnorm)", "LGPL/GPL", "brew install ffmpeg"),
    ("VHS", ["pantalla"], ["vhs"], [], "--version", "terminal grabada desde un .tape reproducible", "MIT",
     "brew install vhs"),
    ("OBS Studio", ["pantalla", "camara"], ["obs"], ["/Applications/OBS.app"], None,
     "grabar pantalla, cámara y escenas compuestas", "GPL", "brew install --cask obs"),
    ("screencapture", ["pantalla"], ["screencapture"], [], None, "grabación de pantalla de macOS (-v)",
     "sistema", "—"),
    ("Python PIL + numpy", ["codigo"], [], [], None,
     "escenas dibujadas fotograma a fotograma (promo-codigo)", "HPND/BSD", "pip install pillow numpy"),
    ("OpenCV", ["codigo"], [], [], None, "seguimiento, máscaras, efectos por píxel", "Apache-2.0",
     "pip install opencv-python"),
    ("Manim", ["codigo", "2d"], ["manim"], [], "--version", "diagramas, matemáticas y tipografía animada",
     "MIT", "pip install manim"),
    ("Node.js", ["codigo"], ["node"], [], "--version",
     "Motion Canvas (MIT) y HyperFrames (HTML + GSAP a MP4) con npx", "MIT", "brew install node"),
    ("Synfig", ["2d"], ["synfig"], ["/Applications/Synfig Studio.app"], "--version",
     "animación vectorial 2D con huesos, render por CLI", "GPL", "brew install --cask synfig-studio"),
    ("Glaxnimate", ["2d"], ["glaxnimate"], ["/Applications/Glaxnimate.app"], "--version",
     "animación vectorial y Lottie", "GPL", "descarga oficial"),
    ("Inkscape", ["2d"], ["inkscape"], ["/Applications/Inkscape.app/Contents/MacOS/inkscape"], "--version",
     "vectores, SVG a PNG por CLI", "GPL", "brew install --cask inkscape"),
    ("Krita", ["2d"], ["krita"], ["/Applications/krita.app"], None, "pintura y animación cuadro a cuadro",
     "GPL", "brew install --cask krita"),
    ("ImageMagick", ["codigo"], ["magick"], [], "-version", "operaciones de imagen por lotes", "Apache-2.0",
     "brew install imagemagick"),
    ("Kdenlive / MLT", ["montaje"], ["melt", "kdenlive"], ["/Applications/kdenlive.app"], "--version",
     "montaje alternativo; melt renderiza proyectos MLT sin interfaz", "GPL", "brew install --cask kdenlive"),
    ("Natron", ["montaje"], ["natron", "NatronRenderer"], ["/Applications/Natron.app"], None,
     "composición por nodos", "GPL", "descarga oficial"),
    ("whisper.cpp", ["voz", "audio"], ["whisper-cli"], [], None, "transcripción con tiempos por palabra",
     "MIT", "brew install whisper-cpp"),
    ("Piper", ["voz"], ["piper"], [], None, "TTS local; revisa la licencia de cada voz", "GPL (piper1)",
     "pip install piper-tts"),
    ("Kokoro", ["voz"], [], [], None, "TTS local de buena calidad", "Apache-2.0 (pesos)", "pip install kokoro"),
    ("SoX", ["audio"], ["sox"], [], "--version", "efectos y conversión de audio por CLI", "GPL",
     "brew install sox"),
    ("Audacity", ["audio"], [], ["/Applications/Audacity.app"], None, "edición de audio a mano", "GPL",
     "brew install --cask audacity"),
    ("SuperCollider", ["audio"], ["sclang"], ["/Applications/SuperCollider.app"], None,
     "síntesis y música generativa", "GPL", "brew install --cask supercollider"),
    ("LMMS", ["audio"], ["lmms"], ["/Applications/LMMS.app"], None, "secuenciador de música", "GPL",
     "brew install --cask lmms"),
    ("bloques", ["codigo", "2d"], ["bloques"],
     [str(BLOQUES)], None,
     "vídeos como YAML de bloques (render, fotograma, hoja, export FCPXML/EDL)", "propia",
     "clona el repo y pon bin/ en el PATH o $BLOQUES_HOME"),
    ("Remotion", ["codigo"], ["remotion"], [], "--version", "vídeo con React (npx remotion render)",
     "licencia Remotion (gratis para individuos)", "npm i -D remotion @remotion/cli (necesita Node)"),
    ("HyperFrames", ["codigo"], ["hyperframes"], [], "--version", "HTML + GSAP a MP4", "ver repo",
     "npm i -g hyperframes (necesita Node)"),
    ("ComfyUI", ["ia"], ["comfy"], [os.environ.get("COMFYUI_HOME", str(Path.home() / "ComfyUI"))], None,
     "IA local de imagen y video (Wan 2.x, LTX-Video); revisa la licencia de cada modelo", "GPL",
     "pip install comfy-cli && comfy install"),
]

MODULOS = {"Python PIL + numpy": ["PIL", "numpy"], "OpenCV": ["cv2"], "Kokoro": ["kokoro"], "Manim": ["manim"]}


def version(cmd, arg):
    if not arg:
        return ""
    try:
        r = subprocess.run([cmd, arg], capture_output=True, text=True, timeout=8)
    except Exception:
        return ""
    for line in (r.stdout + r.stderr).splitlines():
        if line.strip():
            return line.strip()[:70]
    return ""


def detectar():
    out = []
    for nombre, motores, bins, apps, varg, uso, lic, inst in CATALOGO:
        ruta = next((shutil.which(b) for b in bins if shutil.which(b)), None)
        ruta = ruta or next((a for a in apps if Path(a).exists()), None)
        mods = MODULOS.get(nombre)
        if mods and not ruta:
            ok = all(importlib.util.find_spec(m) for m in mods)
            ruta = "python: " + ", ".join(mods) if ok else None
        ver = version(ruta, varg) if ruta and not ruta.startswith("python") and not ruta.endswith(".app") else ""
        out.append({"nombre": nombre, "motores": motores, "instalada": bool(ruta), "ruta": ruta or "",
                    "version": ver, "uso": uso, "licencia": lic, "instalar": inst})
    return out


MOTORES = ["camara", "pantalla", "codigo", "3d", "2d", "montaje", "audio", "voz", "ia", "promo"]
PROMO = {"codigo", "pantalla", "audio"}     # --para promo: los motores de una promo por código


# ---------- doctor ----------
def _which(*names):
    return next((shutil.which(n) for n in names if shutil.which(n)), None)


def filmcraft_cli():
    """Ruta del CLI como la resuelven los scripts (fclib.CLI) y el .mcp.json: $FILMCRAFT_CLI, PATH, ~/.local/bin."""
    env = os.environ.get("FILMCRAFT_CLI")
    if env:
        return env if Path(env).exists() else None, f"$FILMCRAFT_CLI={env}"
    c = _which("filmcraft-cli") or (str(Path.home() / ".local/bin/filmcraft-cli")
                                    if (Path.home() / ".local/bin/filmcraft-cli").exists() else None)
    return c, "filmcraft-cli"


def whisper_model():
    """Modelo y rutas buscadas, con la misma búsqueda que analyze_media/transcribe_fc (common.whisper_model)."""
    sys.path.insert(0, str(Path(__file__).parent))
    import common          # solo stdlib al importar
    return common.whisper_model(), common.whisper_model_rutas(), common.WHISPER_CLI


def fuente_instalada(f):
    """(ok, dónde): ruta de fuentes (common.font_file), fc-list o, en macOS, system_profiler."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from common import font_file
        ff = font_file(dict(f, archivo=str(Path(f["archivo"]).expanduser())) if f.get("archivo") else f)
        if ff and Path(ff).exists():
            return True, ff
    except Exception:  # noqa: BLE001
        pass
    fam = f.get("familia", "")
    if shutil.which("fc-list"):
        r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=20)
        if fam.lower() in r.stdout.lower():
            return True, "fc-list"
    if MAC and shutil.which("system_profiler"):
        try:
            r = subprocess.run(["system_profiler", "SPFontsDataType"], capture_output=True, text=True, timeout=90)
            if fam.lower() in r.stdout.lower():
                return True, "system_profiler"
        except subprocess.TimeoutExpired:
            pass
    return False, ""


PARA_VOZ = ("camara", "montaje", "voz")      # analyze_media/transcribe_fc no funcionan sin whisper y su modelo
PARA_SIN_FC = ("promo", "codigo", "pantalla")   # se renderizan sin FilmCraft; solo lo usan para ensamblar o subtitular


def doctor(ds_id=None, para=None):
    """Lista de comprobaciones {nombre, nivel, ok, detalle, arreglo}; nivel: obligatorio|recomendado|opcional.
    Con para=camara|montaje|voz, whisper.cpp y su modelo pasan a obligatorios; con para=promo|codigo|pantalla,
    el CLI de FilmCraft baja a recomendado y se comprueba VHS (la terminal grabada de la promo)."""
    out = []
    voz = "obligatorio" if para in PARA_VOZ else "recomendado"

    def add(nombre, nivel, ok, detalle="", arreglo=""):
        out.append({"nombre": nombre, "nivel": nivel, "ok": bool(ok), "detalle": detalle or "",
                    "arreglo": "" if ok else arreglo})
    add("python ≥ 3.9", "obligatorio", sys.version_info >= (3, 9), sys.version.split()[0], "instala Python 3.9 o más nuevo")
    for mod, pkg, nivel in (("PIL", "pillow", "obligatorio"), ("numpy", "numpy", "obligatorio"),
                            ("cv2", "opencv-python", "recomendado"), ("jsonschema", "jsonschema", "opcional")):
        add(f"python: {pkg}", nivel, importlib.util.find_spec(mod) is not None, "",
            f"pip install {pkg}  (o pip install -r requirements.txt)")
    cli, como = filmcraft_cli()
    add("FilmCraft CLI", "recomendado" if para in PARA_SIN_FC else "obligatorio", cli, cli or como,
        "instala FilmCraft (github.com/storytold/filmcraft) y deja filmcraft-cli en el PATH o en $FILMCRAFT_CLI")
    app = next((a for a in ("/Applications/FilmCraft.app", str(Path.home() / "Applications/FilmCraft.app"))
                if Path(a).exists()), None)
    add("FilmCraft.app", "recomendado" if MAC else "opcional", app, app or "",
        "la app hace falta para el montaje asistido (en vivo); el headless solo usa el CLI")
    for b in ("ffmpeg", "ffprobe"):
        add(b, "obligatorio", _which(b), _which(b) or "", _inst("brew install ffmpeg", "apt install ffmpeg"))
    if para in PARA_SIN_FC:
        add("VHS (terminal grabada)", "recomendado", _which("vhs"), _which("vhs") or "",
            _inst("brew install vhs", "instala vhs (github.com/charmbracelet/vhs)") +
            "; sin VHS la promo solo puede ser de escenas dibujadas")
    m, rutas, wcli = whisper_model()
    w = _which(wcli)
    add(f"whisper.cpp ({wcli})", voz, w, w or "", _inst("brew install whisper-cpp", "compila whisper.cpp y pon whisper-cli en el PATH"))
    env = os.environ.get("FILMCRAFT_WHISPER_MODEL")
    add("modelo ggml de whisper", voz, m and Path(m).exists(), m,
        (f"$FILMCRAFT_WHISPER_MODEL={env} no existe" if env else
         "no está en " + ", ".join(str(r).replace(str(Path.home()), "~") for r in rutas)) +
        "; descarga ggml-medium.bin (huggingface.co/ggerganov/whisper.cpp) en ~/.cache/whisper/ "
        "o apunta $FILMCRAFT_WHISPER_MODEL a él")
    if MAC:
        add("swiftc (detector de caras)", "recomendado", _which("swiftc"), _which("swiftc") or "", "xcode-select --install")
        add("sips", "recomendado", _which("sips"), _which("sips") or "", "viene con macOS; revisa el PATH")
    bl = _which("blender") or next((a for a in ("/Applications/Blender.app/Contents/MacOS/Blender",) if Path(a).exists()), None)
    add("Blender (motor 3d)", "opcional", bl, bl or "", _inst("brew install --cask blender", "instala Blender y ponlo en el PATH"))
    # MCP filmcraft: el .mcp.json del plugin lanza el CLI con `mcp --bridge`
    mcp = Path(__file__).resolve().parent.parent / ".mcp.json"
    add("MCP filmcraft (.mcp.json)", "opcional", mcp.exists() and cli, str(mcp) if mcp.exists() else "",
        "el MCP usa el mismo CLI: arregla «FilmCraft CLI»")
    # otros ecosistemas: se detectan, nunca son obligatorios
    bq = _which("bloques") or next((str(p) for p in (BLOQUES,) if p.exists()), None)
    add("bloques", "opcional", bq, bq or "", "pon bloques/bin en el PATH o $BLOQUES_HOME")
    add("Node/npx (Remotion, Motion Canvas)", "opcional", _which("npx"), _which("npx") or "",
        _inst("brew install node", "instala Node.js"))
    add("Remotion", "opcional", _which("remotion"), _which("remotion") or "", "npm i -D remotion @remotion/cli en el proyecto")
    add("HyperFrames", "opcional", _which("hyperframes"), _which("hyperframes") or "", "npm i -g hyperframes")
    for var, nombre in (("ELEVENLABS_API_KEY", "ElevenLabs (voz)"), ("SUNO_API_KEY", "Suno (música)")):
        add(nombre, "opcional", bool(os.environ.get(var)), f"${var} {'definida' if os.environ.get(var) else 'sin definir'}",
            f"exporta {var} (o conecta su MCP) si quieres usarlo")
    if ds_id:
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from common import jload, ds_dir
            fu = jload(ds_dir(ds_id) / "ds.json").get("fuentes", {})
        except Exception as ex:  # noqa: BLE001
            add(f"DS {ds_id}", "obligatorio", False, str(ex)[:200], "revisa el id con ds_studio.py catalogo")
            fu = {}
        for rol, f in fu.items():
            ok, donde = fuente_instalada(f)
            add(f"fuente {rol}: {f.get('familia')} {f.get('estilo', '')}".strip(), "obligatorio", ok, donde,
                "instala la fuente (FilmCraft la pide por familia; PIL por archivo) o cámbiala en el DS")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--para", choices=MOTORES, help="filtra por motor; con --doctor, camara|montaje|voz exigen whisper-cli y su modelo, "
                    "y promo|codigo|pantalla no exigen FilmCraft y comprueban VHS")
    ap.add_argument("--doctor", action="store_true", help="preflight: sale 1 si falta algo obligatorio")
    ap.add_argument("--ds", help="con --doctor: comprueba también las fuentes de este DS")
    a = ap.parse_args()
    if a.doctor:
        cs = doctor(a.ds, a.para)
        falta = [c for c in cs if c["nivel"] == "obligatorio" and not c["ok"]]
        if a.json:
            print(json.dumps({"ok": not falta, "comprobaciones": cs}, ensure_ascii=False, indent=1))
        else:
            for nivel in ("obligatorio", "recomendado", "opcional"):
                print(f"[{nivel}]")
                for c in (c for c in cs if c["nivel"] == nivel):
                    print(f"  {'✓' if c['ok'] else '✗' if nivel == 'obligatorio' else '·'} {c['nombre']:<34} "
                          f"{c['detalle'] if c['ok'] else c['arreglo']}")
            print("OK: está todo lo obligatorio" if not falta else
                  f"FALTA lo obligatorio: {', '.join(c['nombre'] for c in falta)}")
        sys.exit(1 if falta else 0)
    hs = [h for h in detectar() if not a.para or a.para in h["motores"]
          or (a.para == "promo" and PROMO & set(h["motores"]))]
    if a.json:
        print(json.dumps(hs, ensure_ascii=False, indent=1))
        return
    for h in sorted(hs, key=lambda h: not h["instalada"]):
        marca = "✓" if h["instalada"] else "·"
        extra = h["version"] or h["ruta"] if h["instalada"] else f"instalar: {h['instalar']}"
        print(f"{marca} {h['nombre']:<20} {'/'.join(h['motores']):<20} {h['uso']}\n    {extra}")


if __name__ == "__main__":
    main()
