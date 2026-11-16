"""apply_plan.main() de verdad (no un bucle copiado) con un motor falso de ids enteros: fases A–E, modo
asistido por bloques, repetir sin duplicar, fallo a mitad que guarda el estado y deshacer tras recompilar."""
import json
import sys

import pytest

pytest.importorskip("PIL")
import apply_plan  # noqa: E402
from common import load_ds  # noqa: E402
from montaje_sintetico import DS_ID, MotorInt, compilar, plan  # noqa: E402


@pytest.fixture
def work(tmp_path):
    c = compilar(tmp_path)
    c["musica"]["archivo"] = str(tmp_path / "m.wav")             # sin music_bed.py
    (tmp_path / "compiled.json").write_text(json.dumps(c))
    return tmp_path


def correr(monkeypatch, work, *args, motor=None):
    m = motor or MotorInt()
    monkeypatch.setattr(apply_plan.Engine, "headless", classmethod(lambda cls, **k: m))
    monkeypatch.setattr(apply_plan.Engine, "live", classmethod(lambda cls, **k: m))
    monkeypatch.setattr(sys, "argv", ["apply_plan.py", str(work / "compiled.json"), *map(str, args)])
    apply_plan.main()
    return m


def estado(work):
    return json.loads((work / "estado.json").read_text())


def test_headless_todas_las_fases(monkeypatch, work):
    comp = json.loads((work / "compiled.json").read_text())
    ds = load_ds(DS_ID)
    m = correr(monkeypatch, work, "--headless", "--out", work / "Reel.fcproj")
    # A: fondo, un clip por segmento en Main (vídeo con audio en Dialogue) y las capas
    assert len(m.places("Fondo")) == 1
    assert len(m.places("Main")) == len(comp["segmentos"])
    vid = [c for c in m.places("Main") if c[6] == "Dialogue"]
    assert len(vid) == sum(1 for s in comp["segmentos"] if s["tipo"] == "video" and not s["mute"])
    assert len(m.places("Producto")) == len(comp["capas"])
    # B: cada SFX una vez, en su pista y sin pasar del final; música y limitador una vez
    sfx = [c for c in m.places() if c[1] in ds["pistas"]["sfx"]]
    assert len(sfx) == len(comp["sfx"])
    recortados = [x for x in comp["sfx"] if x.get("recortado")]
    assert recortados                                             # el fixture tiene SFX que pasarían del final
    for x in recortados:                                          # apply respeta la duración recortada
        c = next(c for c in sfx if c[2] == x["path"] and abs(c[3] - x["start"]) < 1e-6)
        assert c[4] is not None and c[3] + c[4] <= comp["duracion"] + 1e-4
    assert len(m.places("Music")) == 1
    assert sum(1 for c in m.calls if c[0] == "x" and c[1] == "mixer.addInsert") == 1
    # el fundido de diálogo sube de −60 al nivel del DS y vuelve a −60
    vol = [c for c in m.calls if c[0] == "kf" and c[2] == "volume" and c[1] in {x[5][1] for x in vid}]
    assert vol and all(r[4][0][1] == -60 and r[4][-1][1] == -60 and r[4][1][1] == ds["audio"].get("dialogo_db", 0) for r in vol)
    # C: un texto (o una palabra de título) por cada texto, subtítulo y marca
    st = estado(work)
    assert set(st["textos"]) >= {t["id"] for t in comp["subtitulos"]} | {m_["id"] for m_ in comp["marca"]}
    assert "titulo.x2" in st["textos"] and st["textos"]["titulo.x2"]["palabras"] >= 1
    # D: mattes de matte/flash/glitch en Mattes y desenfoque del barrido
    n_mattes = sum({"matte": 1, "flash": 1, "glitch": 2}.get(t["tipo"], 0) for t in comp["transiciones"])
    assert len(m.places("Mattes")) == n_mattes
    assert any(c[0] == "x" and c[1] == "effects.apply" and c[2]["effect"] == "gaussian_blur" for c in m.calls)
    # E: grade solo a los planos de vídeo
    lum = [c for c in m.calls if c[0] == "x" and c[1] == "effects.apply" and c[2]["effect"] == "lumetri"]
    assert len(lum) == 1 and len(lum[0][2]["clips"]) == len(comp["grade"]["segmentos"])
    assert st["fases"]["*"] == list("ABCDE") and m.saved == [str(work / "Reel.fcproj")] and m.closed


def test_headless_no_pisa_un_proyecto(monkeypatch, work):
    (work / "Reel.fcproj").write_text("mío")
    with pytest.raises(SystemExit, match="ya existe"):
        correr(monkeypatch, work, "--headless", "--out", work / "Reel.fcproj")
    assert (work / "Reel.fcproj").read_text() == "mío"


def test_asistido_por_bloques_no_duplica(monkeypatch, work):
    m = MotorInt()
    correr(monkeypatch, work, "--live", "--bloques", "global", "--fases", "A", motor=m)
    assert len(m.places("Fondo")) == 1 and not m.places("Main")             # 'global' = solo lo de ningún bloque
    for b in ("gancho", "medio", "fotos", "titulo", "cierre"):
        correr(monkeypatch, work, "--live", "--bloques", b, "--fases", "A,B,C,D", motor=m)
    antes = len(m.places())
    correr(monkeypatch, work, "--live", "--bloques", "*", "--fases", "B,E", motor=m)     # G5
    nuevos = m.places()[antes:]
    assert [c[1] for c in nuevos] == ["Music"]                              # solo la música
    n = len(m.calls)
    correr(monkeypatch, work, "--live", "--bloques", "*", "--fases", "ABCDE", motor=m)   # repetir todo
    assert not [c for c in m.calls[n:] if c[0] in ("place", "text")]


def test_fallo_a_mitad_guarda_lo_creado(monkeypatch, work):
    m = MotorInt(falla_en=lambda track, path: track == "Mattes")             # fase D revienta
    correr(monkeypatch, work, "--live", "--bloques", "gancho", "--fases", "AB", motor=m)
    with pytest.raises(RuntimeError):
        correr(monkeypatch, work, "--live", "--bloques", "medio", "--fases", "ABCD", motor=m)
    st = estado(work)
    assert st.get("ultimo_error") and st["fases"]["medio"] == ["A", "B", "C"]
    creados = set(st["creados"]["medio"])
    assert creados and creados <= {i for c in m.places() for i in c[5]} | {c[5] for c in m.textos()}
    assert not creados & set(st["creados"]["gancho"])
    # deshacer borra exactamente lo creado y deja el bloque limpio para rehacerlo
    m2 = MotorInt()
    correr(monkeypatch, work, "--live", "--deshacer", "medio", motor=m2)
    clear = [c for c in m2.calls if c[0] == "x" and c[1] == "edit.clear"]
    assert set(clear[0][2]["clips"]) == creados
    st = estado(work)
    assert "medio" not in st["fases"] and not [k for k in st["clips"] if k.startswith("medio.")]


def test_deshacer_tras_recompilar_con_ids_enteros(monkeypatch, work, tmp_path):
    m = MotorInt()
    for b in ("gancho", "medio"):
        correr(monkeypatch, work, "--live", "--bloques", b, "--fases", "AB", motor=m)
    sfx_viejos = {k for k in estado(work)["clips"] if k.startswith("sfx")}
    # recompilar quitando el SFX del gancho: los sfxN de medio se renumeran
    p = plan()
    p["bloques"][1].pop("sfx")
    c = compilar(tmp_path / "v2", p)
    c["musica"]["archivo"] = str(work / "m.wav")
    (work / "compiled.json").write_text(json.dumps(c))
    correr(monkeypatch, work, "--live", "--deshacer", "gancho", motor=m)
    st = estado(work)
    assert sfx_viejos
    assert all(not k.startswith("gancho.") for k in st["clips"])
    # ningún sfxN que quede en el estado apunta a un clip borrado
    borrados = {i for c in m.calls if c[0] == "x" and c[1] == "edit.clear" for i in c[2]["clips"]}
    assert not [k for k, v in st["clips"].items() if v.get("a") in borrados or v.get("v") in borrados]
    correr(monkeypatch, work, "--live", "--bloques", "gancho,medio", "--fases", "AB", motor=m)
    st = estado(work)
    esperados = {x["id"] for x in c["sfx"] if x["bloque"] in ("gancho", "medio")}
    assert esperados <= set(st["clips"])


def test_deshacer_bloque_inexistente(monkeypatch, work):
    with pytest.raises(SystemExit, match="no hay bloque"):
        correr(monkeypatch, work, "--live", "--deshacer", "nadie")


def test_fase_B_sin_A_da_mensaje(monkeypatch, work):
    with pytest.raises(SystemExit, match="fase A"):
        correr(monkeypatch, work, "--live", "--bloques", "gancho", "--fases", "B")


def test_aplica_el_ds_con_el_que_se_compilo(monkeypatch, work, tmp_path):
    """plan.ds = ruta a una copia: apply_plan usa la copia (ds_dir), no el precargado con el mismo id."""
    import shutil
    from common import ds_del_compilado
    copia = tmp_path / "copia"
    shutil.copytree(load_ds(DS_ID)["_dir"], copia)
    raw = json.loads((copia / "ds.json").read_text())
    raw["audio"]["dialogo_db"] = -7.5
    (copia / "ds.json").write_text(json.dumps(raw))
    c = compilar(tmp_path / "w", plan(ds=str(copia)))
    assert c["ds_dir"] == str(copia)
    assert ds_del_compilado(c)["audio"]["dialogo_db"] == -7.5
    with pytest.raises(SystemExit, match="recompila"):
        ds_del_compilado(dict(c, ds="otro-id"))
    shutil.rmtree(copia)
    assert ds_del_compilado(c)["_dir"] == load_ds(DS_ID)["_dir"]     # carpeta borrada: por id, con aviso


def test_fase_A_dos_veces_no_duplica(work):
    comp = json.loads((work / "compiled.json").read_text())
    ds = load_ds(DS_ID)
    m, st = MotorInt(), {"clips": {}, "creados": {}, "textos": {}, "fases": {}}
    a = apply_plan.Applier(m, comp, ds, work, st)
    a.phase_A({"gancho", "*"})
    a.phase_A({"gancho", "*"})                                     # guardas por id, no solo por fase
    assert len(m.places("Main")) == 1 and len(m.places("Fondo")) == 1


def test_grade_solo_a_los_bloques_pedidos(monkeypatch, work):
    m = MotorInt()
    correr(monkeypatch, work, "--live", "--bloques", "gancho,medio", "--fases", "A", motor=m)
    correr(monkeypatch, work, "--live", "--bloques", "gancho", "--fases", "E", motor=m)
    st = estado(work)
    lum = [c for c in m.calls if c[0] == "x" and c[1] == "effects.apply" and c[2]["effect"] == "lumetri"]
    assert len(lum) == 1 and lum[0][2]["clips"] == [st["clips"]["gancho.p1"]["v"]]
