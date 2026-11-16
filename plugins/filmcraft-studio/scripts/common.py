"""Rutas del plugin, carga de design systems, fuentes, detector de caras y utilidades compartidas
(herramientas externas con error claro, color y contraste, palabras, loudness)."""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent           # raíz del plugin
SCRIPTS = ROOT / "scripts"
PLUGIN_DS = ROOT / "design-systems"                     # DS precargados (solo lectura)
DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".cache/filmcraft-studio")
USER_DS = Path(os.environ.get("FILMCRAFT_DS_CATALOGO") or DATA / "design-systems")   # catálogo del usuario
# El catálogo del usuario va PRIMERO: un DS aprobado con el id de uno precargado (modificar + aprobar) lo sustituye.
DS_DIRS = [USER_DS, PLUGIN_DS]
CINE = ROOT / "bin" / "cine"                              # motor determinista (Rust): validar-ds, elegir-ds, puntuar…


def cine_bin():
    """El binario de esta plataforma, como bin/cine (sin depender de uname ni dirname en el PATH)."""
    import platform
    so = {"darwin": "darwin", "linux": "linux", "windows": "windows"}.get(platform.system().lower(), platform.system().lower())
    arq = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower(), platform.machine())
    exe = ".exe" if so == "windows" else ""
    for c in (ROOT / "bin" / f"{so}-{arq}" / f"cine{exe}", ROOT / "motor" / "target" / "release" / f"cine{exe}"):
        if c.exists():
            return c
    return CINE
DRAFT_DS = DATA / "borradores"                            # DS sin aprobar (ds_studio.py)


def whisper_model_rutas():
    """Dónde se busca el modelo ggml de whisper.cpp, en orden (lo usan analyze_media, transcribe_fc y el doctor)."""
    rutas = [DATA / "models/ggml-medium.bin", Path.home() / ".cache/filmcraft-studio/models/ggml-medium.bin",
             Path.home() / ".cache/whisper/ggml-medium.bin", Path("/opt/homebrew/share/whisper-cpp/ggml-medium.bin"),
             Path("/usr/local/share/whisper-cpp/ggml-medium.bin")]
    return list(dict.fromkeys(rutas))      # sin CLAUDE_PLUGIN_DATA, las dos primeras coinciden


def whisper_model():
    """Modelo ggml de whisper.cpp: $FILMCRAFT_WHISPER_MODEL o el primero que exista de whisper_model_rutas().
    Si no hay ninguno devuelve la primera ruta (donde se aconseja descargarlo)."""
    if os.environ.get("FILMCRAFT_WHISPER_MODEL"):
        return os.environ["FILMCRAFT_WHISPER_MODEL"]
    rutas = whisper_model_rutas()
    return str(next((c for c in rutas if c.exists()), rutas[0]))


WHISPER_CLI = "whisper-cli"                 # el binario que llama transcribe_fc.py


WHISPER_DESCARGA = ("descárgalo con: curl -L --create-dirs -o '{dest}' "
                    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin "
                    "(o fija FILMCRAFT_WHISPER_MODEL=/ruta/al/modelo.bin)")


WHISPER_MODEL = whisper_model()
VIDEO_EXT = (".mp4", ".mov", ".m4v")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".heic", ".avif", ".webp")


def jload(p):
    with open(p) as f:
        return json.load(f)


def jsave(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


# ---------- design systems ----------
def ds_dir(ds_id):
    p = Path(ds_id).expanduser()
    if p.is_dir() and (p / "ds.json").exists():
        return p
    if p.name == "ds.json" and p.exists():
        return p.parent
    for d in DS_DIRS + [DRAFT_DS]:
        if (d / ds_id / "ds.json").exists():
            return d / ds_id
    raise FileNotFoundError(f"no encuentro el DS '{ds_id}' en {', '.join(map(str, DS_DIRS + [DRAFT_DS]))}")


def list_ds():
    """Carpetas de los DS aprobados, una por id: la del usuario tapa a la precargada con el mismo id."""
    out, seen = [], set()
    for d in DS_DIRS:
        if d.exists():
            for c in sorted(d.iterdir()):
                if (c / "ds.json").exists() and ".anterior-" not in c.name and c.name not in seen:
                    seen.add(c.name)
                    out.append(c)
    return out


def load_ds(ds_id):
    """Carga ds.json y resuelve rutas relativas (assets/…) a absolutas."""
    d = ds_dir(ds_id)
    ds = jload(d / "ds.json")
    ds["_dir"] = str(d)

    def res(v):
        if isinstance(v, str) and v.startswith("assets/"):
            return str(d / v)
        if isinstance(v, str) and v.startswith("~/"):
            return str(Path(v).expanduser())
        return v
    for k in ("fondos", "mattes"):
        ds[k] = {n: res(v) for n, v in ds.get(k, {}).items()}
    sfx = ds.get("sfx", {})
    base = Path(res(sfx.get("dir", ""))) if sfx.get("dir") else d
    sfx["_mapa_abs"] = {n: str(base / v) for n, v in sfx.get("mapa", {}).items()}
    for f in ds.get("fuentes", {}).values():
        if f.get("archivo"):
            f["archivo"] = res(f["archivo"])
    if ds.get("match", {}).get("flyer"):
        ds["match"]["flyer"] = res(ds["match"]["flyer"])
    return ds


def ds_del_compilado(comp):
    """El DS con el que se compiló: `ds_dir` (ruta) si el compilado la trae; el id del catálogo si no.

    Un plan con `ds` = ruta (un borrador, una copia) compila con esa carpeta; resolver solo el id por el
    catálogo aplicaría otro DS con el mismo id sin decir nada."""
    d = comp.get("ds_dir")
    if d:
        if not (Path(d) / "ds.json").exists():        # p. ej. un borrador que ya se aprobó y se movió
            print(f"aviso: compiled.json se compiló con el DS de {d}, que ya no está; uso el id {comp['ds']!r} "
                  "del catálogo", file=sys.stderr)
            return load_ds(comp["ds"])
        ds = load_ds(d)
        if ds.get("id") != comp["ds"]:
            raise SystemExit(f"el DS de {d} tiene id {ds.get('id')!r} y compiled.json dice {comp['ds']!r}: recompila el plan")
        try:
            otro = ds_dir(comp["ds"])
        except FileNotFoundError:
            otro = None
        if otro is not None and Path(otro).resolve() != Path(d).resolve():
            print(f"aviso: uso el DS con el que se compiló ({d}), no el del catálogo con el mismo id ({otro})",
                  file=sys.stderr)
        return ds
    return load_ds(comp["ds"])


def color(ds, ref):
    """'acento1' -> '#FF9900' según la paleta; un hex pasa tal cual."""
    if ref is None:
        return None
    if isinstance(ref, str) and ref.startswith("#"):
        return ref.upper()
    return ds["paleta"][ref].upper()


def hex2rgb(h):
    """'#FF9900' o 'F90' -> (255, 153, 0)."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb[:3])


def mix(a, b, t):
    """Mezcla lineal de dos hex: t=0 -> a, t=1 -> b."""
    ra, rb = hex2rgb(a), hex2rgb(b)
    return rgb2hex([x + (y - x) * t for x, y in zip(ra, rb)])


def lum(h):
    """Luminancia relativa WCAG 2 (0 negro, 1 blanco) de un hex o de una tupla RGB."""
    rgb = hex2rgb(h) if isinstance(h, str) else h
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """Contraste WCAG entre dos colores (1 a 21)."""
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------- palabras ----------
def norm(w):
    """Palabra en minúsculas sin puntuación (conserva tildes)."""
    return re.sub(r"[^\wáéíóúñü]", "", w.lower())


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


FUNCIONALES = {"que", "nos", "de", "del", "la", "el", "los", "las", "y", "o", "a", "en", "por", "para", "con", "un",
               "una", "se", "le", "les", "lo", "al", "es", "si", "no", "mi", "tu", "su", "pero", "como"}


def tokens(texto):
    """Palabras normalizadas (sin tildes ni puntuación) de un texto."""
    return [t for t in (sin_tildes(norm(x)) for x in str(texto).split()) if t]


# prefijos de marca que se omiten al hablar y al rotular («SageMaker» por «Amazon SageMaker»)
MARCAS = {"amazon", "aws", "google", "microsoft", "azure", "apple"}


def cubre(obligatorio, textos):
    """¿Aparece el obligatorio en los textos? Por palabras ENTERAS (no subcadenas): todas las palabras con
    contenido del obligatorio deben estar entre las de los textos ('IA' no lo cubre «gracias»; '100 USD' no
    lo cubre «1000 personas»). Un prefijo de marca (MARCAS) es opcional si queda el núcleo: «SAGEMAKER»
    cubre «Amazon SageMaker», pero «Amazon» solo no cubre nada más que «Amazon»."""
    q = tokens(obligatorio)
    if not q:
        return False
    contenido = [t for t in q if t not in FUNCIONALES] or q
    contenido = [t for t in contenido if t not in MARCAS] or contenido
    vistos = set()
    for t in textos:
        vistos.update(tokens(t))
    return all(t in vistos for t in contenido)


# ---------- herramientas externas ----------
class ErrorExterno(RuntimeError):
    """Una herramienta externa (ffmpeg, ffprobe, whisper-cli, swiftc, filmcraft-cli…) falta o ha fallado."""


def cine(*args, json_out=True):
    """Ejecuta el binario `cine` (bin/cine elige el de la plataforma). Con json_out, devuelve su JSON.
    Lanza ErrorExterno si el binario no está compilado o no da JSON."""
    try:
        r = subprocess.run([str(cine_bin()), *map(str, args)], capture_output=True, text=True)
    except OSError as ex:
        raise ErrorExterno(f"no se pudo ejecutar {cine_bin()}: {ex}") from ex
    if r.returncode == 127:
        raise ErrorExterno(r.stderr.strip() or "bin/cine sin compilar: sh motor/compilar.sh")
    if not json_out:
        return r
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as ex:
        raise ErrorExterno(f"cine {args[0] if args else ''} no dio JSON (código {r.returncode}): {(r.stderr or r.stdout)[-300:]}") from ex


def tiene(binario):
    return bool(shutil.which(binario) or (os.sep in str(binario) and Path(binario).exists()))


def run(cmd, que=None, check=True, **kw):
    """subprocess.run con lista de argumentos y error legible: comprueba que el binario existe y, con
    check, que sale con 0; si no, lanza ErrorExterno con las últimas líneas de stderr."""
    cmd = [str(c) for c in cmd]
    que = que or Path(cmd[0]).name
    if not tiene(cmd[0]):
        raise ErrorExterno(f"{que}: no encuentro «{cmd[0]}» en el PATH")
    kw.setdefault("capture_output", True)
    r = subprocess.run(cmd, **kw)
    if check and r.returncode != 0:
        err = r.stderr if isinstance(r.stderr, str) else (r.stderr or b"").decode("utf-8", "replace")
        cola = "\n".join((err or "").strip().splitlines()[-6:])
        raise ErrorExterno(f"{que} falló (código {r.returncode}): {cola or 'sin salida de error'}")
    return r


def necesita(modulo, pip=None):
    """Importa un módulo opcional o sale con el comando de instalación."""
    import importlib
    try:
        return importlib.import_module(modulo)
    except ImportError:
        sys.exit(f"falta el módulo de Python «{modulo}»: pip install {pip or modulo}")


def es_macos():
    return sys.platform == "darwin"


def requiere_macos(que):
    if not es_macos():
        raise ErrorExterno(f"{que} necesita macOS (Apple Vision / herramientas del sistema); "
                           f"en {sys.platform} no está disponible")


def cli(main):
    """Ejecuta main() y convierte un ErrorExterno en un mensaje sin traza y código 2."""
    try:
        return main()
    except ErrorExterno as ex:
        print(f"error: {ex}", file=sys.stderr)
        sys.exit(2)


# ---------- fuentes ----------
FONT_DIRS = [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts"),
             Path("/System/Library/Fonts/Supplemental")]
# Linux y Windows: carpetas con subcarpetas (se recorren enteras)
FONT_TREES = [Path.home() / ".local/share/fonts", Path.home() / ".fonts", Path("/usr/share/fonts"),
              Path("/usr/local/share/fonts"), Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]


def _font_files():
    for d in FONT_DIRS:
        if d.exists():
            yield from d.iterdir()
    if not es_macos():
        for d in FONT_TREES:
            if d.exists():
                yield from d.rglob("*")


def font_file(fuente):
    """Archivo de la fuente para PIL: usa 'archivo' del DS o busca por familia y estilo."""
    if fuente.get("archivo") and Path(fuente["archivo"]).exists():
        return fuente["archivo"]
    fam = fuente["familia"].replace(" ", "").lower()
    sty = fuente.get("estilo", "Regular").lower()
    cands = []
    for f in _font_files():
        n = f.name.lower().replace(" ", "")
        if f.suffix.lower() in (".ttf", ".otf", ".ttc") and n.startswith(fam[:6]):
            cands.append(f)
    for f in cands:
        n = f.stem.lower().replace(" ", "")
        if fam in n.replace("-", "") and n.endswith(sty):
            return str(f)
    if fam == "menlo":
        return "/System/Library/Fonts/Menlo.ttc"
    return str(cands[0]) if cands else None


def pil_font(fuente, size):
    from PIL import ImageFont
    f = font_file(fuente)
    if not f:
        return ImageFont.load_default()
    if f.lower().endswith(".ttc"):                      # colección: busca la cara por su estilo
        want = fuente.get("estilo", "Regular").lower()
        for i in range(16):
            try:
                ft = ImageFont.truetype(f, int(size), index=i)
            except OSError:
                break
            if ft.getname()[1].lower() == want:
                return ft
        return ImageFont.truetype(f, int(size), index=0)
    return ImageFont.truetype(f, int(size))


# ---------- detector de caras y personas (Apple Vision) ----------
def vision_bin():
    requiere_macos("el detector de caras")
    b = DATA / "bin/vision_detect"
    src = SCRIPTS / "vision_detect.swift"
    if not b.exists() or b.stat().st_mtime < src.stat().st_mtime:
        b.parent.mkdir(parents=True, exist_ok=True)
        run(["swiftc", "-O", str(src), "-o", str(b)], que="swiftc (compilar vision_detect; instala Xcode CLT)")
    return str(b)


def detect(images):
    """[ruta] -> {ruta: {"faces": [[x,y,w,h]], "people": [...]}} normalizado, origen arriba-izquierda.

    Lanza ErrorExterno si el detector falla o no devuelve una línea por imagen: una visión vacía
    significaría «no hay caras» y los textos acabarían encima de la gente. Las imágenes que el detector
    no pudo leer vuelven con "error"."""
    out = {}
    images = [str(Path(i).resolve()) for i in images]
    for i in range(0, len(images), 200):
        lote = images[i:i + 200]
        r = run([vision_bin()] + lote, que="vision_detect", text=True)
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                raise ErrorExterno(f"vision_detect: línea no válida: {line[:200]}") from None
            out[j["path"]] = j
        falta = [p for p in lote if p not in out]
        if falta:
            raise ErrorExterno(f"vision_detect no devolvió {len(falta)} de {len(lote)} imágenes (p. ej. {falta[0]})")
    return out


def ffprobe(path, check=False):
    """Duración, tamaño (ya rotado), fps y audio de un medio.

    Si ffprobe falla o el medio no tiene duración: con check=True lanza ErrorExterno; sin check avisa por
    stderr y devuelve dur 0 (comportamiento antiguo, para quien lo use así)."""
    try:
        r = run(["ffprobe", "-v", "error", "-show_entries",
                 "stream=codec_type,width,height,r_frame_rate,avg_frame_rate:stream_side_data=rotation:format=duration",
                 "-of", "json", str(path)], que=f"ffprobe {Path(path).name}", text=True, check=check)
    except ErrorExterno:
        if check:
            raise
        print(f"aviso: ffprobe no está disponible para {path}", file=sys.stderr)
        return {"dur": 0.0, "w": None, "h": None, "rot": 0, "fps": None, "fps_media": None, "audio": False}
    try:
        j = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        j = {}
    try:
        dur_ok = float(j.get("format", {}).get("duration") or 0) > 0
    except ValueError:
        dur_ok = False
    if r.returncode != 0 or not dur_ok:
        msg = f"ffprobe no da duración para {path}: {(r.stderr or '').strip()[-200:] or 'sin duración'}"
        if check:
            raise ErrorExterno(msg)
        print(f"aviso: {msg}", file=sys.stderr)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = any(s.get("codec_type") == "audio" for s in j.get("streams", []))
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = v.get("width"), v.get("height")
    if rot in (90, -90, 270, -270) and w:
        w, h = h, w
    def rate(r):
        try:
            n, d = r.split("/")
            return round(int(n) / int(d), 3)
        except Exception:
            return None
    try:
        dur = float(j.get("format", {}).get("duration", 0) or 0)
    except ValueError:
        dur = 0.0
    return {"dur": dur, "w": w, "h": h, "rot": rot,
            "fps": rate(v.get("r_frame_rate", "")), "fps_media": rate(v.get("avg_frame_rate", "")), "audio": a}


def duracion(path):
    """Duración en segundos; lanza ErrorExterno con el motivo si ffprobe no la da."""
    return ffprobe(path, check=True)["dur"]


# ---------- loudness ----------
def parse_ebur128(stderr, stdout=""):
    """Salida de ffmpeg -af ebur128=peak=true[:metadata=1,ametadata=print:file=-] -> cifras.

    curva_s: LUFS por segundo (si se pidió el metadata). Toma el corto plazo (S, ventana de 3 s) del primer
    fotograma de cada segundo; mientras el filtro aún no tiene 3 s de señal S vale −120,7, y entonces se usa
    la media energética del momentáneo (M, 400 ms) de ese segundo para no pintar mudo un arranque con voz.
    El silencio de verdad (o lo que no se pueda medir) queda en −70."""
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", stderr)
    LRA = re.findall(r"LRA:\s+(-?[\d.]+) LU", stderr)
    peaks = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", stderr)

    def val(x):
        return None if x is None or "inf" in x or float(x) <= -70 else float(x)

    segs = {}                                   # segundo -> {"S": primer S, "M": [M válidos]}
    t = None
    for line in (stdout or "").splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = int(float(m.group(1)))
            seg = segs.setdefault(t, {"S": "pend", "M": []})
            continue
        m = re.match(r"\s*lavfi\.r128\.([MS])=(-?[\d.inf]+)", line)
        if t is None or not m:
            continue
        if m.group(1) == "S":
            if seg["S"] == "pend":
                seg["S"] = val(m.group(2))
        else:
            v = val(m.group(2))
            if v is not None:
                seg["M"].append(v)
    curve = []
    for k in sorted(segs):
        sv, ms = segs[k]["S"], segs[k]["M"]
        if sv in (None, "pend") and ms:
            sv = 10 * math.log10(sum(10 ** (x / 10) for x in ms) / len(ms))
        curve.append(round(sv, 1) if isinstance(sv, float) and sv > -70 else -70.0)
    return {"lufs": float(I[-1]) if I else None, "lra": float(LRA[-1]) if LRA else None,
            "pico_dbtp": float(peaks[-1]) if peaks else None, "curva_s": curve}


def loudness(path, curva=False):
    """Loudness integrada (LUFS), LRA y pico verdadero (dBTP; ffmpeg lo rotula dBFS) de un medio con ebur128; lanza ErrorExterno si ffmpeg falla
    o no da la cifra."""
    af = "ebur128=peak=true" + (":metadata=1,ametadata=print:file=-" if curva else "")
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", af, "-f", "null", "-"],
            que=f"ffmpeg ebur128 {Path(path).name}", text=True)
    res = parse_ebur128(r.stderr, r.stdout)
    if res["lufs"] is None:
        raise ErrorExterno(f"ebur128 no dio loudness para {path}")
    return res
