#!/usr/bin/env python3
"""Motor `3d`: renderiza una escena de Blender sin interfaz con el lienzo, la paleta y las fuentes del DS.

Uso:
  motor_blender.py ESCENA.py --ds DS --out escena.mp4 --segundos 4 [--fotogramas 1,48,96] [--escala 0.5]
                   [--motor eevee|cycles] [--muestras 64] [--lienzo 1920x1920] [--param texto=KINDLING --param ...]

ESCENA.py es un script de bpy que solo construye el contenido. Recibe un objeto `fc` ya preparado (escena
vacía, resolución, fps, rango, gestión de color «Standard» para que los hex del DS salgan tal cual):
  fc.ds, fc.p (parámetros --param), fc.fps, fc.frames, fc.color("acento1") -> RGBA lineal,
  fc.fuente("titular") -> bpy font, fc.material(rol, emision=0, rugosidad=0.5), fc.f(segundos) -> fotograma,
  fc.ease(a, b, t)  (smoothstep). Plantilla: scripts/blender/titular.py.

Con --fotogramas renderiza solo esos (la revisión de fotogramas fijos antes del render completo) y deja una
hoja; sin él, la animación entera a PNG y un MP4 H.264 sin audio (la música va aparte, en la rejilla).
Antes de renderizar borra los f_*.png de la pasada anterior, pero solo si los dejó el propio motor en el
mismo modo (marca .motor_blender en la carpeta); si no, se niega salvo con --forzar.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import font_file, load_ds  # noqa: E402

PRELUDIO = Path(__file__).parent / "blender" / "fcblender.py"


def blender_bin():
    for c in (shutil.which("blender"), "/Applications/Blender.app/Contents/MacOS/Blender"):
        if c and Path(c).exists():
            return c
    sys.exit("no encuentro Blender: brew install --cask blender (o pon blender en el PATH)")


def hoja(pngs, salida, cols=4):
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert("RGB") for p in pngs]
    w = 360
    ims = [im.resize((w, int(im.height * w / im.width))) for im in ims]
    h = max(im.height for im in ims)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (20, 20, 20))
    for i, (im, p) in enumerate(zip(ims, pngs)):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
        ImageDraw.Draw(sheet).text(((i % cols) * w + 8, (i // cols) * h + 6), Path(p).stem, fill=(255, 255, 0))
    sheet.save(salida)


MARCA = ".motor_blender"          # la deja cada pasada en su carpeta, con el modo: fotogramas | animacion


def modo_previo(work):
    """Modo de la pasada anterior del motor en esa carpeta (marca o, si es de antes, fc_blender.json); None si no hay."""
    m = work / MARCA
    if m.is_file():
        return m.read_text().strip() or None
    cfg = work / "fc_blender.json"
    if cfg.is_file():
        try:
            return "fotogramas" if json.loads(cfg.read_text()).get("fotogramas") else "animacion"
        except (ValueError, AttributeError):
            return None
    return None


def limpiar(work, modo, forzar=False):
    """Borra los f_*.png (y la hoja) de una pasada anterior del propio motor; solo esos ficheros, nada más.

    Solo si la carpeta la dejó este motor en el mismo modo: unos fotogramas sueltos (--fotogramas) no
    borran los de un render completo, ni nada que no haya escrito el motor. Si no, sale con error salvo
    con forzar. Después deja la marca para la pasada siguiente."""
    restos = [p for p in list(work.glob("f_*.png")) + [work / "hoja.png"] if p.is_file()]
    previo = modo_previo(work)
    if restos and previo != modo and not forzar:
        quien = f"un render en modo {previo}" if previo else "algo que no escribió motor_blender"
        sys.exit(f"{work} ya tiene {len(restos)} f_*.png/hoja.png de {quien}; no los borro. "
                 "Usa otra carpeta para --out o añade --forzar.")
    for p in restos:
        p.unlink()
    (work / MARCA).write_text(modo + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("escena")
    ap.add_argument("--ds", required=True)
    ap.add_argument("--out", required=True, help="MP4 (o carpeta con --fotogramas)")
    ap.add_argument("--segundos", type=float, required=True)
    ap.add_argument("--fotogramas", default="", help="lista 1,48,96: solo esos fotogramas y una hoja")
    ap.add_argument("--escala", type=float, default=1.0, help="fracción del lienzo del DS (0.5 para revisar)")
    ap.add_argument("--lienzo", default="", help="AxB en vez del lienzo del DS (p. ej. 1920x1920 para recortar a dos formatos)")
    ap.add_argument("--motor", choices=["eevee", "cycles"], default="eevee")
    ap.add_argument("--muestras", type=int, default=64)
    ap.add_argument("--param", action="append", default=[], help="clave=valor que la escena lee en fc.p")
    ap.add_argument("--forzar", action="store_true",
                    help="borra los f_*.png de la carpeta aunque no los haya dejado una pasada del motor en este modo")
    a = ap.parse_args()

    params = {}
    for kv in a.param:
        if "=" not in kv:
            ap.error(f"--param necesita clave=valor: {kv!r}")
        k, v = kv.split("=", 1)
        params[k] = v
    ds = load_ds(a.ds)
    fuentes = {}
    for rol, f in ds.get("fuentes", {}).items():
        f = dict(f, archivo=str(Path(f.get("archivo", "")).expanduser()) if f.get("archivo") else "")
        fuentes[rol] = font_file(f) or ""
    out = Path(a.out).resolve()
    work = (out if a.fotogramas else out.parent / (out.stem + "_fotogramas"))
    work.mkdir(parents=True, exist_ok=True)
    limpiar(work, "fotogramas" if a.fotogramas else "animacion", a.forzar)   # restos acabarían en el MP4 o la hoja
    if a.lienzo:
        w, h = (int(v) for v in a.lienzo.lower().split("x"))
        ds["lienzo"] = dict(ds["lienzo"], ancho=w, alto=h)
    cfg = {"ds": {k: v for k, v in ds.items() if k in ("id", "lienzo", "paleta", "marca", "grade", "ritmo", "promo")},
           "fuentes": fuentes, "segundos": a.segundos, "escala": a.escala, "motor": a.motor,
           "muestras": a.muestras, "fotogramas": [int(x) for x in a.fotogramas.split(",") if x],
           "p": params, "escena": str(Path(a.escena).resolve()),
           "dir": str(work)}
    cfg_path = work / "fc_blender.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))

    r = subprocess.run([blender_bin(), "-b", "--factory-startup", "-P", str(PRELUDIO), "--", str(cfg_path)],
                       capture_output=True, text=True)
    log = work / "blender.log"
    log.write_text(r.stdout + r.stderr)
    pngs = sorted(work.glob("f_*.png"))
    if r.returncode or not pngs or "Traceback" in r.stdout + r.stderr:
        sys.exit(f"Blender falló (log: {log}):\n" + "\n".join((r.stdout + r.stderr).splitlines()[-15:]))

    if a.fotogramas:
        hoja(pngs, work / "hoja.png")
        print(work / "hoja.png", len(pngs), "fotogramas")
        return
    fps = ds["lienzo"]["fps"]
    n = max(1, round(a.segundos * fps))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", str(work / "f_%04d.png"),
                    "-frames:v", str(n),
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                    str(out)], check=True)
    print(out, len(pngs), "fotogramas")


if __name__ == "__main__":
    main()
