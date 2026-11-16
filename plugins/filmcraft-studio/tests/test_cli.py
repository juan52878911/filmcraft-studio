"""--help de los CLIs del pipeline: código 0 y sin traza (music_bed antes daba IndexError)."""
import importlib.util

import pytest

CLIS = ["apply_plan.py", "plan_compile.py", "verify.py", "report.py", "analyze_media.py", "transcribe_fc.py",
        "brief_infer.py", "music_bed.py", "camera_motion.py", "render_sheet.py", "freezones.py"]
NECESITA = {"camera_motion.py": "cv2", "music_bed.py": "numpy", "apply_plan.py": "PIL", "verify.py": "PIL",
            "plan_compile.py": "PIL", "render_sheet.py": "PIL"}


@pytest.mark.parametrize("script", CLIS)
def test_help(script, run_script):
    mod = NECESITA.get(script)
    if mod and importlib.util.find_spec(mod) is None:
        pytest.skip(f"sin {mod}")
    r = run_script(script, "--help")
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr and "usage" in r.stdout.lower()


def test_music_bed_sin_argumentos_es_error_de_uso(run_script):
    r = run_script("music_bed.py")
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_palmier_help_no_conecta(run_script, scripts_dir):
    r = run_script("palmier/convert_audio.py", "--help")
    assert r.returncode == 0 and "Traceback" not in r.stderr
