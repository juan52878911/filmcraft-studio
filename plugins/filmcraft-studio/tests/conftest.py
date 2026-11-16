"""Configuración común de los tests del plugin (sin FilmCraft real).

- `scripts/` va al sys.path para importar los módulos como lo hacen los scripts.
- CLAUDE_PLUGIN_DATA apunta a un temporal ANTES de importar `common`: los tests nunca tocan el catálogo
  ni la caché del usuario (~/.cache/filmcraft-studio). FILMCRAFT_DS_CATALOGO se quita por lo mismo.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "scripts"
DATA = Path(tempfile.mkdtemp(prefix="fcs_tests_data_"))

os.environ["CLAUDE_PLUGIN_DATA"] = str(DATA)
os.environ.pop("FILMCRAFT_DS_CATALOGO", None)
os.environ.setdefault("PYTHONPYCACHEPREFIX", str(DATA / "pycache"))
sys.path.insert(0, str(SCRIPTS))


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(DATA, ignore_errors=True)


@pytest.fixture
def plugin_root():
    return PLUGIN


@pytest.fixture
def scripts_dir():
    return SCRIPTS


@pytest.fixture
def data_dir():
    """Carpeta de datos del plugin para esta sesión de tests (CLAUDE_PLUGIN_DATA)."""
    return DATA


@pytest.fixture
def run_script(tmp_path):
    """Ejecuta un script del plugin en un proceso aparte, con el entorno de los tests."""
    def _run(name, *args, env=None, cwd=None):
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True,
                              env=e, cwd=cwd or tmp_path)
    return _run
