"""Rutas del plugin, carga de design systems, fuentes y detector de caras."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent           # raíz del plugin
SCRIPTS = ROOT / "scripts"
DS_DIRS = [ROOT / "design-systems"]
DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".cache/filmcraft-studio")
USER_DS = Path(os.environ.get("FILMCRAFT_DS_CATALOGO") or DATA / "design-systems")   # catálogo del usuario
DS_DIRS.append(USER_DS)
DRAFT_DS = DATA / "borradores"                            # DS sin aprobar (ds_studio.py)
def _whisper_model():
    """Modelo ggml de whisper.cpp: $FILMCRAFT_WHISPER_MODEL o el primero que exista de los habituales."""
    if os.environ.get("FILMCRAFT_WHISPER_MODEL"):
        return os.environ["FILMCRAFT_WHISPER_MODEL"]
    for c in (DATA / "models/ggml-medium.bin", Path.home() / "Documents/GitHub/VibeVoiceNix/docker/modelos/ggml-medium.bin",
              Path("/opt/homebrew/share/whisper-cpp/ggml-medium.bin")):
        if c.exists():
            return str(c)
    return str(DATA / "models/ggml-medium.bin")


WHISPER_MODEL = _whisper_model()
VIDEO_EXT = (".mp4", ".mov", ".m4v")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".heic", ".avif", ".webp")


def jload(p):
    return json.load(open(p))


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
    raise FileNotFoundError(f"no encuentro el DS '{ds_id}' en {', '.join(map(str, DS_DIRS))}")


def list_ds():
    out = []
    for d in DS_DIRS:
        if d.exists():
            for c in sorted(d.iterdir()):
                if (c / "ds.json").exists() and ".anterior-" not in c.name:
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


def color(ds, ref):
    """'acento1' -> '#FF9900' según la paleta; un hex pasa tal cual."""
    if ref is None:
        return None
    if isinstance(ref, str) and ref.startswith("#"):
        return ref.upper()
    return ds["paleta"][ref].upper()


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------- fuentes ----------
FONT_DIRS = [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts"),
             Path("/System/Library/Fonts/Supplemental")]


def font_file(fuente):
    """Archivo de la fuente para PIL: usa 'archivo' del DS o busca por familia y estilo."""
    if fuente.get("archivo") and Path(fuente["archivo"]).exists():
        return fuente["archivo"]
    fam = fuente["familia"].replace(" ", "").lower()
    sty = fuente.get("estilo", "Regular").lower()
    cands = []
    for d in FONT_DIRS:
        if d.exists():
            for f in d.iterdir():
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
    b = DATA / "bin/vision_detect"
    src = SCRIPTS / "vision_detect.swift"
    if not b.exists() or b.stat().st_mtime < src.stat().st_mtime:
        b.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(src), "-o", str(b)], check=True, capture_output=True)
    return str(b)


def detect(images):
    """[ruta] -> {ruta: {"faces": [[x,y,w,h]], "people": [...]}} normalizado, origen arriba-izquierda."""
    out = {}
    images = [str(Path(i).resolve()) for i in images]
    for i in range(0, len(images), 200):
        r = subprocess.run([vision_bin()] + images[i:i + 200], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            j = json.loads(line)
            out[j["path"]] = j
    return out


def ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,r_frame_rate,avg_frame_rate:stream_side_data=rotation:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
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
    return {"dur": float(j.get("format", {}).get("duration", 0) or 0), "w": w, "h": h, "rot": rot,
            "fps": rate(v.get("r_frame_rate", "")), "fps_media": rate(v.get("avg_frame_rate", "")), "audio": a}
