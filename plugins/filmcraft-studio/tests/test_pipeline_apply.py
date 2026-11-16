"""apply_plan: repetir fases no duplica (G5 del modo asistido) y --deshacer limpia textos y SFX."""
import pytest

pytest.importorskip("PIL")
import apply_plan  # noqa: E402


class MotorFalso:
    """Ids de clip ENTEROS, como FilmCraft (estado.json real: {"v": 22, "a": 23}); con texto el test de
    deshacer tras recompilar pasaba aunque deshacer() no reconociera los clips borrados."""
    def __init__(self):
        self.calls = []

    def place(self, path, track, start, dur=None, **k):
        self.calls.append(("place", track, path))
        return [1000 + len(self.calls)]

    def kf(self, *a, **k):
        pass

    def param(self, *a, **k):
        pass

    def x(self, cmd, params=None):
        self.calls.append(("x", cmd, params))

    def snap(self, s):
        return s

    def places(self, track=None):
        return [c for c in self.calls if c[0] == "place" and (track is None or c[1] == track)]


DS = {"lienzo": {"ancho": 1080, "alto": 1920}, "audio": {}, "animaciones": {}}
COMP = {"duracion": 10, "segmentos": [],
        "sfx": [{"id": "sfx1", "bloque": "gancho", "path": "hit.wav", "pista": "SFX", "start": 0, "dur": .3, "db": -4},
                {"id": "sfx2", "bloque": "cierre", "path": "whoosh.wav", "pista": "SFX", "start": 9, "dur": .3, "db": -4}],
        "textos": [{"id": "gancho.t1", "bloque": "gancho"}],
        "musica": {"archivo": "m.wav", "dur": 10, "bpm": 112, "keyframes": [[0, -8]]},
        "bloques": [{"id": "gancho"}, {"id": "cierre"}],
        "grade": {"segmentos": []}}


def nuevo_estado():
    return {"clips": {}, "creados": {}, "textos": {}, "fases": {}}


def aplicar(e, st, blocks, fases):
    """Lo que hace main(): cada fase solo sobre los bloques que aún no la tienen."""
    ap = apply_plan.Applier(e, COMP, DS, ".", st)
    for f in fases:
        pend = apply_plan.pendientes(st, blocks, f)
        if pend:
            getattr(ap, f"phase_{f}")(pend)
            for b in pend:
                st["fases"].setdefault(b, []).append(f)


def test_g5_no_recoloca_sfx_ni_musica():
    e, st = MotorFalso(), nuevo_estado()
    todos = {"gancho", "cierre", "*"}
    aplicar(e, st, {"gancho"}, "B")                 # puerta del bloque gancho
    aplicar(e, st, {"cierre"}, "B")                 # puerta del bloque cierre
    aplicar(e, st, todos, "B")                      # G5: --bloques '*' --fases B,E
    aplicar(e, st, todos, "B")                      # repetir G5
    assert len([c for c in e.places("SFX") if c[2] == "hit.wav"]) == 1
    assert len([c for c in e.places("SFX") if c[2] == "whoosh.wav"]) == 1
    assert len(e.places("Music")) == 1
    assert sum(1 for c in e.calls if c[0] == "x" and c[1] == "mixer.addInsert") == 1


def test_guardas_por_id_aunque_se_llame_la_fase_dos_veces():
    e, st = MotorFalso(), nuevo_estado()
    ap = apply_plan.Applier(e, COMP, DS, ".", st)
    ap.phase_B({"gancho", "*"})
    ap.phase_B({"gancho", "*"})                     # llamada directa: las guardas por id evitan duplicar
    assert len(e.places("SFX")) == 1 and len(e.places("Music")) == 1


def test_pendientes():
    st = {"fases": {"gancho": ["A", "B"]}}
    assert apply_plan.pendientes(st, {"gancho", "cierre", "*"}, "B") == {"cierre", "*"}
    assert apply_plan.pendientes(st, {"gancho"}, "C") == {"gancho"}


def test_deshacer_limpia_clips_textos_sfx_y_fases():
    e, st = MotorFalso(), nuevo_estado()
    aplicar(e, st, {"gancho"}, "B")
    st["textos"]["gancho.t1"] = {"clip": 9}
    st["textos"]["otro.t1"] = {"clip": 10}
    st["creados"]["gancho"].append(9)
    ids = apply_plan.deshacer(e, COMP, st, "gancho")
    assert 9 in ids
    assert "sfx1" not in st["clips"]                # el SFX (id sin prefijo de bloque) también
    assert "gancho.t1" not in st["textos"] and "otro.t1" in st["textos"]
    assert "gancho" not in st["fases"]
    aplicar(e, st, {"gancho"}, "B")                 # tras deshacer se puede rehacer
    assert len([c for c in e.places("SFX") if c[2] == "hit.wav"]) == 2


def test_deshacer_tras_recompilar_no_deja_ids_viejos():
    """sfxN se renumera al recompilar: deshacer con el compilado nuevo no puede dejar el id viejo en el estado."""
    base = dict(COMP, bloques=[{"id": "gancho"}, {"id": "medio"}, {"id": "cierre"}])

    def sfx(*bl):
        return [{"id": f"sfx{i + 1}", "bloque": b, "path": f"{b}{i}.wav", "pista": "SFX", "start": i, "dur": .3, "db": -4}
                for i, b in enumerate(bl)]
    v1 = dict(base, sfx=sfx("gancho", "gancho", "medio", "cierre"))   # medio: sfx3
    v2 = dict(base, sfx=sfx("gancho", "medio", "cierre"))             # gancho pierde uno -> medio: sfx2

    e, st = MotorFalso(), nuevo_estado()

    def ap(comp, b):
        a = apply_plan.Applier(e, comp, DS, ".", st)
        if apply_plan.pendientes(st, {b}, "B"):
            a.phase_B({b})
            st["fases"].setdefault(b, []).append("B")
    ap(v1, "gancho")
    apply_plan.deshacer(e, v2, st, "gancho")
    assert "sfx2" not in st["clips"]                 # el sfx2 viejo era de gancho y su clip se borró
    for b in ("gancho", "medio", "cierre"):
        ap(v2, b)
    puestos = [c[2] for c in e.places("SFX")]
    assert any(p.startswith("medio") for p in puestos)
    assert sorted(st["clips"]) == ["sfx1", "sfx2", "sfx3"]


def test_deshacer_no_toca_clips_de_otros_bloques():
    e, st = MotorFalso(), nuevo_estado()
    aplicar(e, st, {"gancho"}, "B")
    aplicar(e, st, {"cierre"}, "B")
    cierre = dict(st["clips"]["sfx2"])
    apply_plan.deshacer(e, COMP, st, "gancho")
    assert st["clips"] == {"sfx2": cierre} and st["fases"] == {"cierre": ["B"]}


def test_fases_invalidas_dan_error_de_uso(tmp_path, run_script):
    (tmp_path / "c.json").write_text("{}")
    r = run_script("apply_plan.py", tmp_path / "c.json", "--headless", "--out", tmp_path / "x.fcproj", "--fases", "AZ")
    assert r.returncode == 2 and "--fases" in r.stderr and "Traceback" not in r.stderr
