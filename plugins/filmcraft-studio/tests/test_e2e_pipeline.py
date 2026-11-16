"""Lo encontrado en la prueba de punta a punta contra FilmCraft real (material sintético, 13,5 s).

El SFX de cierre (impacto.wav, 2,36 s) empezaba en 11,5 s y llegaba a 13,86 s: la secuencia quedaba en 832
fotogramas en vez de 810, el export acababa con 0,37 s de negro y verify decía 13,5 s porque solo miraba vídeo.
"""
import pytest

pytest.importorskip("PIL")
import plan_compile  # noqa: E402
import verify  # noqa: E402

TPS = 254016000000


def _compilador():
    c = object.__new__(plan_compile.Compiler)
    c.ds = {"pistas": {"sfx": ["SFX", "SFX 2", "Hits"]}}
    return c


def test_sfx_no_pasa_del_final():
    evs = [{"start": 0.0, "dur": 2.36, "path": "impacto.wav"},
           {"start": 11.5, "dur": 2.36, "path": "impacto.wav"},
           {"start": 13.5, "dur": 0.5, "path": "pop.wav"}]          # empieza justo al final: sobra
    out = _compilador().alloc_sfx(evs, 13.5)
    assert len(out) == 2
    assert all(e["start"] + e["dur"] <= 13.5 + 1e-6 for e in out)
    cierre = out[-1]
    assert cierre["dur"] == pytest.approx(2.0) and cierre["recortado"] is True   # apply_plan respeta dur
    assert "recortado" not in out[0]


def test_sfx_sin_total_conserva_su_duracion():
    out = _compilador().alloc_sfx([{"start": 11.5, "dur": 2.36}])
    assert out[0]["dur"] == 2.36


def test_seq_end_cuenta_el_audio():
    seq = {"video_tracks": [{"items": [{"clip": 1, "start": 0, "duration": round(13.5 * TPS)}]}],
           "audio_tracks": [{"items": [{"clip": 2, "start": round(11.5 * TPS), "duration": round(2.36 * TPS)}]}]}
    assert verify.seq_end(seq) == pytest.approx(13.86)
