"""Timeline del corte vertical (9:16): gancho, terminal real, Apple Silicon, cuatro features, HOL Guard y cierre."""

BPM = 134
BEAT = 60.0 / BPM
FPS = 30
W, H = 1080, 1920
TAIL = 1.6
BEATS = 56
TOTAL = BEATS * BEAT + TAIL   # 14 compases + cola ≈ 26.7 s


def b(n):
    return n * BEAT


HOOK = (0, 8)
TERM = (8, 30)
SILICON = (30, 36)
FEATS = (36, 48)     # cuatro tarjetas de 3 beats
HOL = (48, 52)
END = (52, 56)

HOOK_CMD = "kling compose up -d"
HOOK_TYPE = (0.08, 0.78)

# Grabación vertical (VHS 1000x1000, 25 fps): filas a 44.4 px, 17.1 px por carácter
TERM_SRC = (1000, 1000, 25)
ROW_TOP, ROW_H, CHAR_W, TEXT_X = 62, 44.4, 17.1, 44
CMD_ROWS = {0: 25, 6: 67, 12: 135, 14: 188, 16: 261}  # fila de comando -> fotograma en que llega su salida


def row_y(i):
    return int(ROW_TOP + ROW_H * i)


SRC_UP = 80 / 25        # "demo is up in 0.5s"
SRC_ARCH = 135 / 25     # "Linux aarch64"
SRC_FROZEN = 188 / 25   # "cache frozen in 322 ms"
SRC_PONG = 261 / 25     # "PONG"
SRC_END = 305 / 25

REMAP = [
    (b(8), 0.0),
    (b(14), SRC_UP),
    (b(18), SRC_ARCH),
    (b(22), SRC_FROZEN),
    (b(28), SRC_PONG),
    (b(30), SRC_END - 0.04),
]

FREEZE = (b(22), b(28))
IDLE_FREEZE = (b(46), b(48))


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
