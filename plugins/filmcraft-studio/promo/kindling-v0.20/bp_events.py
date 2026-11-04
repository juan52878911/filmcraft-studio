"""Eventos de dibujo del estilo Blueprint, compartidos por el video y el audio (lápiz, rayado, sellos)."""
from timeline import BEAT, b

# (inicio, fin) de cada trazo largo: suena el lápiz mientras dura
DRAWS = [
    (0.00, 0.90),            # caja del host
    (0.05, 0.45),            # compose.yml
    (0.30, 0.70),            # flecha compose up
    (0.50, 0.90),            # microVM
    (b(2), b(2) + 0.25),     # cota 0.4 s
    (b(5), b(6)),            # cajetín
    (b(8), b(8) + 0.5),      # marco del detalle
    (b(28) + 0.1, b(28) + 0.7),
    (b(32) + 0.1, b(32) + 0.7),
    (b(36) + 0.1, b(36) + 0.7),
    (b(40), b(42)),          # regla de 10 min
    (b(44), b(44) + 0.6),    # cajetín final
]
HATCHES = [(b(20), b(20) + 0.3), (b(42), b(42) + 0.3)]  # rayado de congelación
STAMPS = [b(2), b(44)]
SLIDES = [b(8), b(28), b(40), b(44)]
STAT_STARTS = [b(28), b(32), b(36)]
STAT_BEATS = 4 * BEAT
