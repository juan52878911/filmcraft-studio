# Leer referencias

Una referencia sirve por la **regla** que la genera, no por su resultado. El error más caro es copiar el aspecto: el mismo efecto aplicado a todo por igual da un clon que parece un filtro. Ese error salió en el estilo gradient map: el mapa de gradientes se puso en todo el texto, cuando en el poster el calor era de un lugar y cada parte del texto evolucionaba distinto.

## Cómo llegan

- **Archivos o carpetas**: van a `W/referencias/` y se miden con `referencias.py`.
- **URLs** (Behance, Dribbble, YouTube, webs): se abren con el navegador y se miran o se capturan para analizarlas. Descargar un video o un archivo necesita el permiso del usuario. Lo descargado es solo para analizarlo y nunca entra en el video.
- **Descripción** («como los créditos de X», «tipo Y2K»): pide una imagen o un enlace. Si no hay, describe lo que entiendes y confírmalo con una pregunta con opciones.
- **Anti-referencias**: igual de importantes. Leen las mismas casillas, pero en negativo.

## La ficha de cada referencia

`referencias.py RUTAS --out DIR` escribe por cada imagen `DIR/fichas/<nombre>.json` y `<nombre>_hoja.png` (una sola imagen: `ref_metricas.py IMG --ficha f.json --hoja h.png`). La ficha tiene tres capas (`schemas/referencia.schema.json`):

### Capa 1 — Métricas (las mide el script)

Posiciones normalizadas (0..1, origen arriba a la izquierda), distancias en fracción de la diagonal. Se mide a 512 px, así que no depende del tamaño del archivo; el texto, la tipografía, el patrón y el desregistro se miden a resolución nativa.

| Bloque | Qué dice | Para qué sirve |
|---|---|---|
| `color` | Paleta en OKLCH con proporción y papel (dominante, secundario, acento, apoyo), armonía (monocromática, análoga, complementaria, tríada…), temperatura (−1 fría … +1 cálida), croma, colores efectivos | La paleta del DS y su reparto de áreas: cuánto ocupa el acento |
| `valores` | Histograma, clave (alta, media, baja), rango, contraste global y local, notan de 2 y 3 valores con sus proporciones | El grade y la estructura de masas. El notan es la composición sin color |
| `composicion` | Puntos fuertes en orden de saliencia (también pegados al borde), centro de masa, distancia a tercios, proporción áurea, centro y diagonales, simetría, peso por cuadrantes, espacio negativo, líneas (H/V/D), horizonte (con su ángulo, hasta ±10°), orientación de bordes, margen, ritmo y retícula (hasta 16 módulos) | Dónde entra la mirada y por dónde sigue; cuánto aire hay; qué eje manda |
| `textura` | Entropía, densidad de bordes, alta frecuencia, grano | Cuánto detalle y cuánto ruido lleva el estilo |
| `bordes` | `duros`: reparto continuo, por masa tonal, entre filo de vector (1) y difuminado (0); `ancho_px`: ancho mediano del borde; nitidez | Vector o pintura; cortes o fundidos. Una foto nítida ronda 0,6–0,95; un vector, ≥ 0,98 |
| `profundidad` | Rango de enfoque, gradiente atmosférico, pista (plana, atmosférica, foco selectivo) | Si admite paralaje |
| `texto` | Área, bloques, alineación y cajas, incluidos los titulares de cartel (letras de hasta el 80 % del alto). Heurístico: confirma mirando la hoja | Cuánto texto cabe y cómo se alinea; lo que la cámara no puede cortar |
| `tipografia` | Niveles de tamaño y su `escala` (segundo nivel / titular), número de líneas, `peso` (grosor del trazo / alto de la mayúscula: ~0,12 regular, ~0,19 negrita, ≥ 0,22 extra), `tracking` (hueco entre letras / alto), caja alta o mixta. `clase` (serif, palo seco, mono…) **la pones tú** mirando la imagen | La jerarquía y el peso de los rótulos del DS |
| `patron` | Patrón fino repetido: tipo (`puntos` = semitono o cuadrícula, `rayas`), periodo en px y en fracción del lado, ángulo y fuerza | El semitono o el rayado del estilo, con su lineatura y su ángulo. Una trama ya no sale como «retícula» |
| `tratamiento` | `duotono` (el color es función del valor; tintas de sombra y de luz), `desregistro` (px y ángulo entre tintas), `vineta` (caída de luz a las esquinas) | Los acabados que hacen un riso, un mapa de degradado o una foto de objetivo |

Límites que conviene saber: el horizonte se descarta en piezas con texto (`lineas.horizonte_descartado` guarda lo medido) y un horizonte muy difuso puede no detectarse; un patrón de 1 px desaparece al reducir la imagen; `tipografia` no reconoce la familia.

`reproducir` da, por cada métrica, **objetivo, tolerancia y la palanca** que mueve ese número, en dos grupos: `estilo` (lo que se reproduce; incluye `tipografia.peso` y `tipografia.escala`) y `composicion` (lo que no se copia). La ficha lleva además una `firma` (miniatura de luminancia) para que `--comparar` reconozca la misma imagen espejada, girada o recortada. `pistas_mejora` son heurísticas medidas (rango de valores corto, sin acento, foco sin anclar, sin aire): puntos de partida para «cómo mejorarla», no un juicio.

La **hoja** enseña lo mismo para mirarlo: tercios, áurea, focos numerados, centro de masa, líneas, horizonte, margen y texto sobre el original; mapa de saliencia con el peso por cuadrante; notan de 2 y de 3; profundidad proxy; bordes; paleta, histograma y tonos. Mírala siempre: si un foco cae en un adorno o el «texto» es una textura, dilo en la lectura y no uses esa cifra.

### Capa 2 — Filosofía (la rellenas tú, mirando la imagen, la hoja y las cifras)

Campos de `filosofia`. Cada afirmación cita la cifra que la apoya («clave baja: mediana 0,24»; «acento al 4,6 % del área»).

**No es opcional.** El script deja la capa vacía y lo dice al acabar. Antes de aprobar la biblia:

```
referencias.py --validar W/referencias          # o: ref_metricas.py ficha.json --validar --completa
```

Sale con 1 mientras a alguna ficha le falte `movimiento`, `emocion`, `regla_generadora`, `donde_no`, `que_la_distingue`, `no_copiar` o `como_mejorar`, o mientras menos de dos afirmaciones citen una cifra. Volver a medir la carpeta conserva lo que ya escribiste. La capa se usa: `imagen_a_video.py --prompt-ia` y `--plan` meten la regla, la emoción y el «dónde no» en lo que generan; `--comparar` cita la regla y el «no copiar» de la referencia, que es lo que lee la crítica de originalidad; `agregado.json` junta las reglas de todas las referencias.

- `movimiento`: escuela o tradición de la que bebe (suizo, brutalismo, risografía, constructivismo, vaporwave…), sin nombrar obras ni autores concretos como modelo a copiar.
- `emocion`: qué busca provocar y con qué lo consigue.
- `regla_generadora`: el mecanismo que produce el aspecto. Por ejemplo, «el color es un mapa de temperatura sobre la intensidad».
- `significado`: qué representa esa variable. Por ejemplo, «el calor es energía y atención».
- `donde_actua` / `donde_no`: casi nunca actúa en todo. Por ejemplo, «el calor nace de una fuente; menos del 30 % del texto está caliente; lo frío queda nítido con un filo».
- `variacion`: en el espacio (por letra, por región, desde un punto) y en el tiempo (se enciende, se enfría, se contagia).
- `anatomia`: tamaños, desplazamientos y proporciones que se pueden copiar como números. Aquí entran las métricas: reparto del notan, área del acento, margen, periodo del ritmo.
- `reglas_que_rompe`: qué convención incumple a propósito (foco en el borde, sin jerarquía, texto cortado a sangre) y qué gana con ello.
- `que_la_distingue`: lo que no tendría una pieza media del mismo género.
- `tomar` / `no_copiar`: lista corta. Se toma la regla y las métricas de `estilo`. Nunca se toman composiciones concretas (grupo `composicion`), personajes, logotipos, tipografías con licencia que no tengamos ni textos.
- `como_mejorar`: qué haría mejor la pieza para este video; parte de `pistas_mejora` y descarta las que la referencia incumple a propósito.

### Capa 3 — Traducción a video

- `video.sugerido` y `video.traduccion` (medidos): qué modo de `imagen_a_video.py` conviene y, rasgo a rasgo, en qué movimiento se convierte. Horizonte → travelling paralelo (si está inclinado, con su inclinación; en una pieza con texto no hay horizonte). Patrón → movimientos cortos, sin reescalar. Tipografía → rótulos con ese peso y esa escala. Desregistro → las tintas entran por separado. Simetría alta → empuje axial. Ritmo espacial → entrada escalonada por módulo, uno por beat. Notan marcado → revelado por valores. Texto → rígido. Grano → grano vivo. Bordes duros → arranques y cortes secos; suaves → fundidos.
- `video.que_se_anima`, `camara`, `ritmo`, `transiciones`, `plan` (los rellenas tú): qué se mueve y qué queda quieto, de dónde a dónde va la cámara, cuántos beats dura cada fase y con qué transición entra y sale, coherente con la composición (por ejemplo, la cortinilla en el ángulo de la diagonal dominante). `plan` es una lista de `{t, que}`. Es el **vocabulario de movimientos** de la biblia.
- Para ver la traducción en movimiento antes de escribir una escena: `imagen_a_video.py` sobre un fotograma **propio** (`skills/director-video/references/imagen-a-video.md`). Animar la referencia misma solo sirve como estudio interno: nunca entra en el video.

### En la biblia

`biblia.json` → `referencias` lleva la ruta de la ficha y el resumen de la capa 2 (`regla`, `significado`, `donde_no`, `variacion`, `anatomia`, `tomar`, `no_tomar`), más la **traducción al producto**: qué significa esa regla en este video. Es la metáfora de la biblia; por ejemplo, «caliente = corre, frío = congelado».

En video se mide además plano medio, cortes por minuto, BPM y loudness. Los cortes se miden con un umbral de escena de 0,3: sobre fondos parecidos se escapan cortes, así que mira la hoja.

## Varias referencias

`agregado.json` reparte cada métrica en:
- `comunes`: todas las referencias caen dentro de la tolerancia. Eso es **el estilo**; su `objetivo` y su `tolerancia` son candidatos a criterio de aceptación.
- `idiosincrasicos`: alguna se aparta (`se_apartan` dice cuál). Es cosa de esa pieza: no se promedia ni se exige.
- `categorias`: clave, armonía, profundidad, texto, peso y caja de la tipografía, patrón, duotono, desregistro y viñeta, con si coinciden.
- `filosofia`: la regla generadora, lo que distingue, el «dónde no» y el «no copiar» de cada referencia, y cuáles siguen `pendiente`.

Si casi nada es común, las referencias no describen un estilo: pregunta cuál manda o qué tomar de cada una.

## Señales de que la lectura es un clon

- El efecto se aplica igual a todo el cuadro o a todo el texto.
- No sabes decir dónde NO actúa la regla.
- La paleta es la de la referencia, pero nada en el video la justifica.
- Las escenas comparten maqueta y solo cambia el texto.
- Si quitas el efecto, el video es una plantilla genérica.
- `referencias.py --comparar REF FOTOGRAMA` dice «clon probable» o «misma maqueta» (`originalidad.md`). Espejar, girar o recortar la referencia no lo evita.

## Ejemplo (gradient map, poster «Gradient Maps vol.02»)

- **Lectura de clon**: «texto con gradient map papel → azul → naranja → rojo y un halo».
- **Lectura buena**:
  - **Regla**: la imagen térmica de una impresión mal registrada; el mapa es una escala de temperatura.
  - **Dónde actúa**: el calor es del lugar, no de la letra.
  - **Cómo varía**: el calor baja a la mitad cada dos letras, contando desde la fuente; las letras frías quedan nítidas con un filo rojo de 2 px; el fondo también se calienta.
  - **Traducción a kindling**: caliente = la VM corre, frío = congelada. La firma es enfriar hasta el filo.

El resultado está en `skills/promo-codigo/references/gramaticas.md` del plugin (termo@1).
