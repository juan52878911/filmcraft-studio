"""Canal de control en vivo (fclib.FC) contra un servidor falso: lo encontrado en la prueba de punta a punta."""
import json
import socket
import threading

import pytest

import fclib


def _server(*handlers):
    """Servidor en un puerto libre; atiende una conexión por handler, en orden. handler(fichero)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(4)

    def run():
        for h in handlers:
            c, _ = s.accept()
            f = c.makefile("rw")
            try:
                h(f)
            finally:
                c.close()
        s.close()

    threading.Thread(target=run, daemon=True).start()
    return s.getsockname()[1]


def _responde(f, result):
    r = json.loads(f.readline())
    f.write(json.dumps({"id": r["id"], "ok": True, "result": result}) + "\n")
    f.flush()


def test_fc_sigue_sirviendo_tras_un_timeout():
    """Antes: tras un timeout (un file.import lento) toda llamada posterior fallaba con
    «cannot read from timed out object» y había que rehacer la sesión."""
    ev = threading.Event()

    def lento(f):
        f.readline()
        ev.wait(5)                                 # no contesta a tiempo; luego el cliente se va

    port = _server(lento, lambda f: _responde(f, "bien"))
    fc = fclib.FC(port, timeout=0.3)
    with pytest.raises(RuntimeError, match="no respondió"):
        fc.x("file.import", {"paths": ["/x.png"]})
    ev.set()
    assert fc.x("sequence.inspect") == "bien"
    fc.close()


def test_fc_ignora_respuestas_con_otro_id():
    def h(f):
        r = json.loads(f.readline())
        f.write(json.dumps({"id": r["id"] - 1, "ok": True, "result": "vieja"}) + "\n")
        f.write(json.dumps({"id": r["id"], "ok": True, "result": "buena"}) + "\n")
        f.flush()

    fc = fclib.FC(_server(h), timeout=5)
    assert fc.x("sequence.inspect") == "buena"
    fc.close()


def test_fc_el_error_de_canal_cerrado_cita_el_puerto_usado():
    port = _server(lambda f: f.readline())        # cierra sin responder
    fc = fclib.FC(port, timeout=5)
    with pytest.raises(RuntimeError, match=f"puerto {port}"):
        fc.x("sequence.inspect")
    fc.close()
