"""Timeline compartido entre música y video: todo cae en la rejilla de 134 BPM."""

BPM = 134
BEAT = 60.0 / BPM          # 0.4478 s
FPS = 30
W, H = 1920, 1080
TAIL = 1.6                  # cola después del último compás
TOTAL = 48 * BEAT + TAIL    # 12 compases + cola ≈ 23.1 s


def b(n):
    """Tiempo (s) del beat n."""
    return n * BEAT


# Escenas (en beats)
HOOK = (0, 8)        # comando + "0.4s" + titular
TERM = (8, 28)       # grabación real de VHS
STATS = (28, 40)     # tres cifras del CHANGELOG
IDLE = (40, 44)      # idle_freeze
END = (44, 48)       # cierre + sting

# Eventos de la grabación real (s en la fuente, medidos con diff de filas a 25 fps)
SRC_UP = 75 / 25       # "demo is up in 0.4s"
SRC_FROZEN = 120 / 25  # "cache frozen in 375 ms"
SRC_PONG = 193 / 25    # "PONG"
SRC_END = 236 / 25

# Mapa salida -> fuente (lineal a trozos): cada evento cae en un beat
REMAP = [
    (b(8), 0.0),
    (b(14), SRC_UP),
    (b(20), SRC_FROZEN),
    (b(26), SRC_PONG),
    (b(28), SRC_END - 0.04),
]

HOOK_CMD = "kling compose up -d"
HOOK_TYPE = (0.08, 0.78)  # tecleo del comando del gancho; el "0.4s" cae en el beat 2

# Filas de comando de la grabación (para los clics de teclado) y su geometría en la fuente
TERM_SRC = (1600, 900, 25)
CMD_ROWS = [0, 6, 11, 13]


def row_y(i):
    return 60 + int(38.9 * i)


FREEZE = (b(20), b(26))   # la máquina está congelada: música filtrada, cámara quieta
IDLE_FREEZE = (b(42), b(44))


def interp(points, x):
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def src_time(t):
    return interp(REMAP, t)


def out_time(s):
    return interp([(y, x) for x, y in REMAP], s)
