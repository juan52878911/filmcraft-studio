# Estilo brutalista (reels del AWS SBG EAN)

Receta aprobada por Juan en los reels "¿Por qué trabajar en Tech?" (paleta cian) y "#RetoCertEAN Sesión 5" (paleta del flyer). Úsala cuando pida "el mismo estilo", "brutalista" o un reel del SBG. Cambia la paleta según el flyer de cada evento.

## Identidad

- **Sin degradados, esquinas redondeadas ni sombras suaves.** Todo texto va sobre un bloque sólido.
- **Paleta:** sale del flyer del evento. Muestrea sus colores con PIL antes de diseñar.
  - Sesión 5: navy `#161D27` (fondo y texto oscuro), naranja `#FF9900`, morado `#AD5CFF`, rosa `#FF52EA` y blanco.
  - Charla Tech: blanco `#FEFEFE`, rejilla `#D6D6D6`, cian `#40B4FF` y negro `#010101`.
- **Tipografías:** IosevkaTerm Nerd Font Mono Heavy para titulares y ecos; Menlo Bold para subtítulos, pills y marca; Menlo Regular para metadatos.
- **Fondos:** rejilla de celdas de 40 px con "píxeles" de color en las esquinas, generados con PIL (`gen_bgs.py` en la carpeta `04 - Grafica` del proyecto). Variantes `bg-title`, `bg-plain`, `bg-cap` (franja central de color) y `bg-outro`, más mattes sólidos de cada color y uno blanco.
- **Grade del metraje:** contraste +15, negros −12, altas −15, saturación 105, claridad ligera, sharpen suave y grano 6 %.

## Pistas (de abajo arriba, índices 0-based)

0 Fondo · 1 Main · 2 Tarjeta · 3 Producto · 4 Brand · 5 Captions · 6 Labels · 7 Pills · 8 Tags · 9 Eco · 10 Mattes.

Los mattes de transición van arriba del todo: tapan también los textos.

## Tamaños de texto (px de FilmCraft a 1080 de ancho; Palmier × 1,78)

| Elemento | Fuente | Tamaño | Colores | Posición |
|---|---|---|---|---|
| Barra de marca "AWS STUDENT BUILDER GROUP · EAN" | Menlo Bold | ~36 | navy sobre naranja | y 0,06, toda la pieza salvo título y cierre |
| Subtítulos | Menlo Bold | ~75 | blanco sobre navy | y 0,78, ≤ 20 caracteres por línea |
| Etiqueta de concepto ("SAGEMAKER", "ACCESIBILIDAD") | Iosevka Heavy | ~115–150 | navy sobre naranja/rosa, o blanco sobre navy | zona libre, popIn |
| Eco (palabra ×3) | Iosevka Heavy | ~150–195 | alterna blanco/navy y navy/naranja | 3 posiciones escalonadas, 8 f cada una a 60 fps |
| Pill | Menlo Bold | ~46–55 | navy sobre color | popIn |
| Tarjeta de nombre | Menlo Bold | ~50 | navy sobre naranja | junto a la persona, sin taparla |
| Título y cierre | Iosevka Heavy | ~155–215 | blanco | alineado a la izquierda, x 0,07–0,08, aparición por palabras |

## Colocar los pop-ups (regla de Juan)

Los anuncios no tapan a la gente.

1. Oculta las pistas de texto y renderiza el inicio, la mitad y el final de cada pop-up.
2. Mapea las zonas libres en la rejilla 0–1: pared, ventana, pizarra, techo, suelo.
3. Coloca el bloque en el lado contrario de la persona, alternando lados entre escenas para dar dinamismo.
4. Bloques apilados: deja ~0,085 de separación vertical en Iosevka de 64 pt (Palmier). Si son escalones, desplaza también en x.
5. No pegues un bloque grande a la barra de marca (y 0,06): empieza en y ≥ 0,14.
6. Vuelve a renderizar con los textos visibles y confirma.

## Continuidad entre tomas (receta aprobada)

- **Entrada de toma:** escala 1,08 → 1 en ~16 f (60 fps) y fundido de entrada de 6 f.
- **Jump cut del mismo ponente:** punch-in estático de 1,12.
- **Empuje de salida:** 1 → 1,05 en los últimos ~8 f.
- **Zoom-crash:** la saliente pasa de 1 a 1,25–1,4 en ~10 f y la entrante de 1,25 a 1.
- **Transiciones entre escenas distintas** (cada una con su efecto de sonido, ver `audio-mezcla.md`):
  - flash blanco de 3–6 f;
  - barrido de matte con keyframes de posición (1 → 0 → −1, 14 f);
  - persiana con keyframes de recorte (abajo 1 → 0, luego arriba 0 → 1);
  - glitch con recorte en hold y la toma entrante temblando 3 f;
  - eco de texto ×3;
  - y, sobre todo, **barridos de la propia cámara** (`transiciones-camara.md`).

## Estructura típica del reel de evento (45–60 s, 9:16)

1. **Gancho en frío (0–6 s):** la frase con más carga, con un número si lo hay ("nos dan 100 dólares"), más eco y golpe de sonido.
2. **Tarjeta de título (2,5 s):** hashtag en pill, sesión o tema en Iosevka y subtítulo en pill.
3. **3–5 momentos de contenido:** cada concepto con su etiqueta y punch-ins en los jump cuts.
4. **Momento humano:** premio, celebración o regalo (por ejemplo, el chico que se gana la figurita de Claude). Usa el movimiento real de la cámara como transición.
5. **Invitados y patrocinadores:** tarjeta de nombre y carrusel de producto que continúa el sentido del paneo.
6. **Fotos en stop-motion:** 10–14 f cada una, con flash y obturador.
7. **Cierre (3 s):** "#RETO / CERT / EAN" por palabras, "SÍGUENOS · @awssbgean" y la línea de la sesión.

## Base musical

`promo-tech-bed-112bpm` sintetizada (`synth_bed.py`, ajusta `BARS` a la duración). Va a −18 dB bajo la voz y a −6/−8 dB en el título y el cierre, con salida en rampa.
