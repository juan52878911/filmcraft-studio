"""Utilidades base de FilmCraft: tiempos, canal de control (socket) y CLI headless.

En vivo (app abierta con `--control 9876`):
    from fclib import FC, fr, ticks
    fc = FC(); fps = fc.fps(); fc.x("effects.setParam", {..., "time": fr(30, fps)})

Headless (sobre rutas nuevas o con la app cerrada):
    from fclib import headless
    headless("P.fcproj", "exec", "transcript.search", '{"query":"hola"}')

Para sesiones headless con ids devueltos entre comandos, usa fcengine.Engine.headless().
"""
import json
import os
import socket
import subprocess
from pathlib import Path

TPS = 254016000000                       # ticks por segundo
CLI = os.environ.get("FILMCRAFT_CLI", str(Path.home() / ".local/bin/filmcraft-cli"))
PORT = int(os.environ.get("FILMCRAFT_PORT", "9876"))


def ticks(seconds):
    return round(seconds * TPS)


def secs(t):
    return t / TPS


def fr(frame, fps):
    """Fotograma de la secuencia -> ticks. Los fps salen SIEMPRE de la secuencia (sequence.inspect)."""
    if not fps:
        raise ValueError("fr() necesita los fps de la secuencia")
    return round(frame * TPS / fps)


def seq_fps(seq):
    f = seq["settings"]["frame_rate"]
    return f["num"] / f["den"]


class FC:
    """Canal de control: una petición JSON por línea, una respuesta por línea."""

    def __init__(self, port=PORT, timeout=120):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.f = self.s.makefile("rw")
        self.n = 0

    def x(self, command, params=None):
        self.n += 1
        req = {"id": self.n, "method": "engine.execute", "params": {"command": command, "params": params or {}}}
        self.f.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.f.flush()
        r = json.loads(self.f.readline())
        if not r.get("ok"):
            raise RuntimeError(f"{command} {json.dumps(params, ensure_ascii=False)[:300]}: {r.get('error')}")
        return r.get("result")

    def seq(self):
        return self.x("sequence.inspect", {})

    def fps(self):
        return seq_fps(self.seq())

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def app_listening(port=PORT):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        return True
    except OSError:
        return False


def headless(project, *args, save=None, compact=True, check=True):
    """Ejecuta filmcraft-cli sobre un .fcproj. save=None | True (--save) | 'ruta' (--save-as)."""
    cmd = [CLI]
    if project:
        cmd += ["--project", str(project)]
    if save is True:
        cmd.append("--save")
    elif save:
        cmd += ["--save-as", str(save)]
    cmd += [str(a) for a in args]
    if compact:
        cmd.append("--compact")
    out = subprocess.run(cmd, capture_output=True, text=True)
    if check and out.returncode != 0:
        raise RuntimeError(f"filmcraft-cli {' '.join(map(str, args))}: {out.stderr.strip()[-500:]}")
    txt = out.stdout.strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return txt


def load_project(project):
    """El .fcproj es JSON legible: útil para verificar keyframes (tiempo en ticks de media)."""
    return json.load(open(project))
