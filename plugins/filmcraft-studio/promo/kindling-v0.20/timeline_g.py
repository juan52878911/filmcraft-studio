"""Timeline del corte vertical en gradient map (termo@1): misma rejilla de 134 BPM y misma grabación real que
timeline_v.py, con otro guion (menos texto, terminal más corta y la congelación como momento firma):

  gancho      0–8    ignición en oscuro, "0.5s" a sangre, pila DOCKER COMPOSE / EN MICROVMS. / EN TU MAC.
  terminal    8–22   arranque → pausa en "0.5s" → uname aarch64 → congelado (4 beats quietos) → PONG
  silicon     22–28  "36 ms" a sangre y el chip como fuente de calor
  capacidades 28–40  tres de 4 beats: 50 copias, 1 DB por rama, MCP bajo demanda (una maqueta por idea)
  hol guard   40–46  entra con el frente de llama; un foco escanea el comando
  cierre      46–56  KINDLING; a los 10 min sin uso se congela solo y el frío se come el cuadro
"""
from timeline_v import (BEAT, CHAR_W, CMD_ROWS, FPS, H, ROW_H, ROW_TOP, SRC_ARCH, SRC_END, SRC_FROZEN, SRC_PONG,
                        SRC_UP, TERM_SRC, TEXT_X, W, b, interp, row_y)

TAIL = 1.6
BEATS = 56
TOTAL = BEATS * BEAT + TAIL

HOOK = (0, 8)
TERM = (8, 22)
SILICON = (22, 28)
FEATS = (28, 40)      # tres tarjetas de 4 beats
HOL = (40, 46)
END = (46, 56)

HOOK_CMD = "kling compose up -d"
HOOK_TYPE = (0.05, 0.42)  # se teclea pronto: la chispa necesita casi medio segundo para caer

# medidos en la grabación (primera aparición del texto en su fila): las salidas llegan algo después
# del final del tecleo que marcan SRC_FROZEN y SRC_PONG
SRC_FROZEN_OUT = 7.84
SRC_PONG_OUT = 10.9
SRC0 = 2.05               # la grabación entra justo antes de teclear "kling compose up -d" (sin el cat)

REMAP = [
    (b(8), SRC0),
    (b(10), SRC_UP),
    (b(12), SRC_UP + 0.12),       # pausa en "demo is up in 0.5s"
    (b(12.6), SRC_ARCH + 0.1),     # "Linux aarch64" ya está en pantalla cuando llega el zoom
    (b(14.5), SRC_ARCH + 0.4),
    (b(15), SRC_FROZEN_OUT),
    (b(19), SRC_FROZEN_OUT + 0.04),   # congelado: la grabación no avanza
    (b(21), SRC_PONG_OUT),
    (b(22), SRC_END - 0.04),
]

FREEZE = (b(15), b(19))
IDLE_FREEZE = (b(51), b(56) + TAIL)   # el cierre acaba congelado


def src_time(t):
    return interp(REMAP, t)


def out_time(s):
    return interp([(y, x) for x, y in REMAP], s)
