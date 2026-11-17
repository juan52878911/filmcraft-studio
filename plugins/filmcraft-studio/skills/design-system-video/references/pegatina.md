# Gramática pegatina@1

Reel vertical con un presentador a cámara y rótulos que parecen pegatinas. El ritmo lo ponen los rótulos, no los cortes: cada dato que se dice tiene su pegatina y algo nuevo aparece cada ~1,1 s. Está medida fotograma a fotograma sobre un reel de 720×1280 a 30 fps. Las cifras de abajo son a 720 px; el código las escala al lienzo.

## Qué la distingue

- **Cajas** planas con las esquinas vivas y una **sombra dura** desplazada de 4-8 px en el color contrario: navy bajo magenta y magenta bajo navy o blanco. Esa sombra es lo que parece un borde.
- **Inclinación** de −2° a −3° en las cajas de titular y de beneficio. Los kickers, la placa de nombre y el QR van rectos.
- **Zonas**:
  - los rótulos ocupan la banda de y 9-36 %, alineados a un margen izquierdo de 40 px (5,6 %);
  - el presentador queda en el 36-68 %;
  - los subtítulos van a y ≈ 70 %;
  - el 27 % inferior queda libre.
- **Animación** con curvas medidas y la misma salida para todo:
  - el rótulo entra unos 7 f antes de su palabra (`adelanto_f`);
  - sale con un fundido de 4 f (`salida.f`);
  - nada flota mientras está en reposo.
- **Subtítulos** de 1-3 palabras con la palabra clave en magenta. Se resalta el nombre propio, la cifra o el sustantivo del beneficio, nunca un verbo ni una palabra funcional.
- **Sonido**: sin música (`musica.ninguna`). Solo dos golpes graves, en el gancho y en el cierre, y una voz muy comprimida a −14 LUFS.
- **Cortes**:
  - entre localizaciones, desenfoque corto (`barrido_camara` con `f` 6);
  - jump cuts con punch-in del 111 %, tapados por la entrada de una tarjeta.

## Animaciones (`animaciones`, a `base_fps` 30)

| Clave | Uso | Curva |
|---|---|---|
| `golpe` | titular, «¡GRATIS!», concepto | `escala` 126 → 95 → 100 % en 9 f; `giro` −4° → +0,8° → 0 respecto a la inclinación |
| `desliza` | tarjetas, chip de fecha, placa | `dx` (fracción del ancho) con un rebote de unos 21 px que se asienta en 7 f; entra por el lado más cercano |
| `caida` | pills y viñetas | `escala` 113 → 100 % en 3 f, sin rebote |
| `pop` | piezas pequeñas, QR, flecha | `escala` 124 → 100 % en 6 f |
| `escribe` | kickers | Crop por la derecha a `cps_f` 1,5 caracteres por fotograma; la caja crece con el texto |

Cada curva es una lista de pares `[fotograma, valor]` con las claves `escala`, `giro`, `dx`/`dy` y `opacidad`. `pegatina.keyframes()` las convierte en keyframes. Si una curva cambia, cambia en el DS y no en el código.

## Roles (`roles_texto`): campos que añade

| Campo | Qué hace |
|---|---|
| `inclina` | Grados en reposo; con una lista, uno por variante |
| `sombra` | `{color, dist, angulo}`. Sombra dura: `blur` 0 y opacidad 100 |
| `contorno` | `{color, ancho}` del trazo, para los subtítulos sin caja |
| `prefijo` | `{texto, color}` que se antepone al texto, por ejemplo «▶ » en magenta para los kickers |
| `resalta`, `resalta_max` | Color y número máximo de palabras clave por golpe de subtítulo |
| `max_palabras` | Corta el subtítulo en golpes de 1-3 palabras |
| `pista_letras` | Tracking en milésimas de em (los kickers en mono van a 140) |

Con una animación pegatina, el rótulo dura hasta el final de su bloque. Si el titular (`titulo`/`cierre`) tiene una animación pegatina, se dibuja como una sola caja con golpe en lugar de aparecer palabra a palabra, y la letra se reduce para que quepa en el ancho.

## Tarjetas compuestas (`tarjetas` en el DS y `capas[].tarjeta` en el plan)

`pegatina.tarjeta()` dibuja cada tarjeta con PIL a la escala del lienzo. `apply_plan` la coloca a tamaño real y la anima como una capa.

| `tipo` | Campos | Aspecto |
|---|---|---|
| `ponente` | `foto`, `nombre`, `cargo` | foto con marco blanco y sombra magenta; placa navy con el nombre en blanco y el rol en menta |
| `fecha` | `dia`, `num`, `mes`, `hora` | cuadro magenta con el número, barra navy con «JUE · NOV» en gris y la hora en menta |
| `qr` | `img`, `texto`, `url` | panel navy con sombra magenta, QR sobre blanco, «ESCANEA Y REGÍSTRATE» y la URL |
| `logo` | `img`, `fondo`, `tam` | tarjeta blanca con sombra navy, o navy con sombra magenta |
| `flecha` | `sentido` | flecha curva magenta de trazo 8 px |

El DS da los valores por defecto de cada tipo (`anim`, `inclina`, `pos`, `pista`, `sfx`), y la capa del plan puede cambiarlos. Una tarjeta se ancla con `palabra` (o `t`) y dura hasta el final del bloque si el plan no da `dur`. Si dos tarjetas coinciden en el tiempo, la segunda pasa a otra pista libre para que FilmCraft no recorte la primera.

Ejemplo de plan:

```json
"capas": [{"tarjeta": {"tipo": "ponente", "foto": "ana.jpg", "nombre": "ANA TORRES", "cargo": "AWS COMMUNITY BUILDER"},
           "palabra": "Ana", "pos": [0.5, 0.24]},
          {"tarjeta": {"tipo": "fecha", "dia": "JUE", "num": "19", "mes": "NOV", "hora": "15:00 h"}, "palabra": "jueves"}]
```

En la raíz del plan, `"resaltar": ["carrera", "gratis"]` añade palabras a resaltar en los subtítulos, además de las cifras y los nombres propios.

## Límites

- No genera códigos QR (no hay ninguna librería instalada): hay que pasar la imagen en `img`.
- La flecha aparece entera; todavía no se dibuja con un trazo animado.
- La fuente original (Amazon Ember) no está instalada. La sustituyen Avenir Next Heavy y Demi Bold, y Menlo Bold.
- Los fondos decorados del DS base siguen en `fondos`, pero un reel con material grabado no los usa.
