"""Motor único de FilmCraft para los dos modos.

    from fcengine import Engine
    e = Engine.live()                         # app abierta (socket 9876)
    e = Engine.headless()                     # proyecto nuevo, sin ventana (filmcraft-cli mcp)
    e = Engine.headless("P.fcproj")           # abre un proyecto existente sin escribirlo
    e.x("file.saveAs", {"path": "nuevo.fcproj"})

Todo lo que depende de fotogramas usa los fps de la secuencia activa (e.fps), nunca un valor fijo.
Los keyframes se escriben solo con e.kf(): `time` en ticks de la secuencia y
`mediaTime` = source_in + desfase × speed para la interpolación.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fclib import CLI, FC, PORT, fr, seq_fps, ticks  # noqa: E402


class _MCP:
    """Sesión headless persistente: `filmcraft-cli [--project P] mcp` por stdio (JSON-RPC)."""

    def __init__(self, project=None):
        cmd = [CLI] + (["--project", str(project)] if project else []) + ["mcp"]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        self.n = 0
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "fcengine", "version": "1"}})
        self._rpc("notifications/initialized", {}, notify=True)

    def _rpc(self, method, params, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        if notify:
            return None
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("filmcraft-cli mcp terminó inesperadamente")
            r = json.loads(line)
            if r.get("id") == self.n:
                return r

    def x(self, command, params=None):
        r = self._rpc("tools/call", {"name": "command_run", "arguments": {"id": command, "params": params or {}}})
        if "error" in r:
            raise RuntimeError(f"{command}: {r['error'].get('message')}")
        res = r["result"]
        txt = res["content"][0]["text"] if res.get("content") else "null"
        if res.get("isError"):
            raise RuntimeError(f"{command} {json.dumps(params, ensure_ascii=False)[:300]}: {txt}")
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return txt

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


class Engine:
    def __init__(self, backend, mode, journal=None):
        self.b = backend
        self.mode = mode
        self.journal = journal          # ruta JSONL donde se registran los comandos
        self._seq = None
        self._items = {}                # ruta -> item id

    # ---------- construcción ----------
    @classmethod
    def live(cls, port=PORT, journal=None):
        return cls(FC(port), "live", journal)

    @classmethod
    def headless(cls, project=None, journal=None):
        return cls(_MCP(project), "headless", journal)

    def close(self):
        self.b.close()

    # ---------- comandos ----------
    def x(self, command, params=None):
        t0 = time.time()
        err = None
        try:
            r = self.b.x(command, params or {})
            return r
        except Exception as ex:
            err = str(ex)
            raise
        finally:
            if command not in ("sequence.inspect", "graphics.list", "project.inspect") and self.journal:
                with open(self.journal, "a") as f:
                    f.write(json.dumps({"id": command, "params": params or {}, "ms": round((time.time() - t0) * 1000),
                                        **({"error": err[:300]} if err else {})}, ensure_ascii=False) + "\n")
            if command.split(".")[0] in ("timeline", "sequence", "edit", "clip", "file") and command != "sequence.inspect":
                self._seq = None

    def seq(self, fresh=False):
        if fresh or self._seq is None:
            self._seq = self.b.x("sequence.inspect", {})
        return self._seq

    @property
    def fps(self):
        return seq_fps(self.seq())

    def f2s(self, frames):
        """Fotogramas de la secuencia -> segundos."""
        return frames / self.fps

    def snap(self, seconds):
        """Redondea al fotograma de la secuencia."""
        return round(seconds * self.fps) / self.fps

    def tk(self, seconds):
        """Segundos de la secuencia -> ticks EXACTOS de su fotograma más cercano (sin esto FilmCraft
        baja al fotograma anterior un tiempo que cae unos ticks antes del borde y los clips se pisan)."""
        return fr(round(seconds * self.fps), self.fps)

    # ---------- proyecto y pistas ----------
    def new_project(self, name, width, height, fps, video_tracks, audio_tracks):
        self.x("file.newProject", {"name": name})
        self.x("file.newSequence", {"name": name, "width": width, "height": height, "fps": fps,
                                    "video": len(video_tracks), "audio": len(audio_tracks)})
        self.name_tracks(video_tracks, audio_tracks)

    def name_tracks(self, video_tracks, audio_tracks):
        s = self.seq(True)
        need_v = len(video_tracks) - len(s["video"])
        need_a = len(audio_tracks) - len(s["audio"])
        if need_v > 0 or need_a > 0:
            self.x("sequence.addTracks", {"video": max(0, need_v), "audio": max(0, need_a)})
        for i, n in enumerate(video_tracks):
            self.x("timeline.setTrack", {"track": f"V{i + 1}", "name": n})
        for i, n in enumerate(audio_tracks):
            self.x("timeline.setTrack", {"track": f"A{i + 1}", "name": n})
        self.seq(True)

    def track(self, name):
        """Nombre de pista -> ('V'|'A', índice 0-based, id)."""
        s = self.seq()
        for kind, key in (("V", "video"), ("A", "audio")):
            for i, t in enumerate(s[key]):
                if t["name"] == name:
                    return kind, i, t["id"]
        raise KeyError(f"no hay pista '{name}'")

    def tref(self, name):
        k, i, _ = self.track(name)
        return f"{k}{i + 1}"

    def tindex(self, name):
        """Índice entero 0-based (lo que exige graphics.newText)."""
        return self.track(name)[1]

    def items_by_path(self):
        try:
            p = self.b.x("project.inspect", {})
        except Exception:
            return {}
        p = p.get("project", p)
        out = {}

        def walk(n):
            for c in n.get("children", []):
                if "children" in c:
                    walk(c)
                elif c.get("path"):
                    out[str(c["path"])] = c["item"]
        if "root" in p:
            walk(p["root"])
        return out

    def import_paths(self, paths):
        paths = [str(p) for p in paths]
        if not self._items:
            self._items.update(self.items_by_path())
        new = [p for p in dict.fromkeys(paths) if p not in self._items]
        if new:
            r = self.x("file.import", {"paths": new})
            if r.get("errors"):
                raise RuntimeError(f"file.import: {r['errors']}")
            self._items.update(zip(new, r["items"]))
        return {p: self._items[p] for p in paths}

    # ---------- clips ----------
    def place(self, path, track, start, dur=None, source_in=None, audio=True, audio_track=None, video=True):
        item = self.import_paths([path])[str(path)]
        p = {"item": item, "track": self.tref(track) if track else None, "time": self.tk(start)}
        if dur is not None:
            p["duration"] = self.tk(start + dur) - self.tk(start)
        if source_in is not None:
            p["sourceIn"] = ticks(source_in)
        if audio_track:
            p["audioTrack"] = self.tref(audio_track)
        p["audio"] = audio
        p["video"] = video
        p = {k: v for k, v in p.items() if v is not None}
        return self.x("timeline.place", p)["clips"]

    def clip(self, cid):
        s = self.seq()
        for key in ("video", "audio"):
            for t in s[key]:
                for c in t["items"]:
                    if c["clip"] == cid:
                        return c
        s = self.seq(True)
        for key in ("video", "audio"):
            for t in s[key]:
                for c in t["items"]:
                    if c["clip"] == cid:
                        return c
        raise KeyError(cid)

    def param(self, clip, effect, param, value):
        self.x("effects.setParam", {"clip": clip, "effect": effect, "param": param, "value": value})

    def kf(self, clip, effect, param, rows, clip_start, source_in=0.0, speed=1.0):
        """Keyframes. rows = [(desfase_s, valor, interp)] relativos al inicio del clip en la secuencia.

        time      = ticks de la secuencia (clip_start + desfase)
        mediaTime = ticks de la fuente (source_in + desfase × speed)
        """
        t0 = self.tk(clip_start)
        for rel, val, _ in rows:
            self.x("effects.setParam", {"clip": clip, "effect": effect, "param": param, "value": val,
                                        "time": self.tk(clip_start + rel), "keyframe": True})
        for rel, _, it in rows:
            if it and it != "linear":
                mt = ticks(source_in) + round((self.tk(clip_start + rel) - t0) * speed)
                self.x("effects.setInterpolation", {"clip": clip, "effect": effect, "param": param,
                                                    "mediaTime": mt, "interpolation": it})

    def select(self, clips):
        self.x("timeline.select", {"clips": list(clips)})

    def scale_to_frame(self, clips):
        self.select(clips)
        self.x("clip.scaleToFrameSize", {})

    # ---------- textos ----------
    def new_text(self, text, track, start, dur, font, style, size, clip=None):
        p = {"text": text, "position": [100, 400], "size": size, "font": font, "fontStyle": style}
        if clip is None:
            n = round((start + dur) * self.fps) - round(start * self.fps)
            p.update(seconds=n / self.fps, track=self.tindex(track), time=self.tk(start))
        else:
            p["clip"] = clip
        return self.x("graphics.newText", p)

    def layers(self, clip):
        return self.x("graphics.list", {"clip": clip})["layers"]

    def center_layer(self, clip, layer, cx, cy, align="Center"):
        """Coloca el bloque de texto con su centro (o su borde izquierdo si align=Left) en (cx, cy) del lienzo."""
        L = [l for l in self.layers(clip) if l["layer"] == layer][0]
        x0, y0, x1, y1 = L["localBounds"]
        ax = x0 if align == "Left" else (x0 + x1) / 2
        anchor = [ax, (y0 + y1) / 2]
        self.x("graphics.set", {"clip": clip, "layer": layer, "props": {"anchor": anchor, "position": [cx, cy]}})
        return L, (x1 - x0, y1 - y0)

    # ---------- guardar ----------
    def save(self):
        return self.x("file.save", {})

    def save_as(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return self.x("file.saveAs", {"path": str(path)})
