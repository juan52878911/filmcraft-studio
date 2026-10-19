# Color en FilmCraft (Lumetri)

Principios adaptados y parafraseados de la guía de color de davinci-resolve-mcp (MIT) y del modelo ASC CDL de video-use (MIT), traducidos a Lumetri de FilmCraft. Atribución en `../NOTICE.md`.

## Orden de corrección

1. Transformación técnica y gestión de color: espacio de trabajo de la secuencia, LUT de entrada si el material es log o HDR.
2. Exposición y contraste: punto negro, punto blanco, densidad.
3. Balance de blancos y neutros.
4. Piel y colores de memoria (cielo, vegetación, luces prácticas, neutros conocidos).
5. Continuidad entre planos.
6. Look creativo.
7. Legalidad y entrega (niveles, gama).

No persigas un look antes de que la imagen sea técnicamente coherente. No iguales un plano destruyendo lo que más importa en él: la cara, el producto o el punto de la historia.

## Criterio de colorista

- Parte de fotogramas representativos, no de metadatos.
- Usa scopes y ojos. Ninguno basta solo: `scopes.read` da la waveform, el parade, el histograma y el vectorscopio.
- Fija negros, blancos y densidad antes del estilo.
- Protege caras, piel, productos y detalles de la historia antes que el fondo.
- **Técnica de foco:** pásate a propósito (más oscuro o claro, más cálido o frío) para encontrar el límite y vuelve al punto útil.
- Sé moderado cuando el material es frágil: comprimido, de 8 bits, con ruido, quemado o ya en espacio de visualización. El material de móvil suele serlo.
- Si piden un look por sensación ("cálido", "noir", "limpio"), tradúcelo a objetivos medibles: densidad, nivel de altas, color de sombras, saturación, protección de piel y continuidad.

## Herramientas de FilmCraft

| Necesidad | Herramienta |
|---|---|
| Primaria (exposición, contraste, altas, sombras, blancos, negros, temperatura, saturación) | Efecto `lumetri`, sección básica (`contrast`, `highlights`, `shadows`, `whites`, `blacks`, `temperature`, `tint`, `saturation`, `vibrance`, `exposure`) |
| Curvas, ruedas, HSL secundario, viñeta | Secciones de `lumetri` (actívalas con `lumetri.setSection`) |
| LUT de entrada o look creativo | `lumetri.setInputLut`, `lumetri.setLook`, `lut.import` |
| Igualar planos | `lumetri.applyMatch` con un fotograma de referencia y `faceDetection` |
| Medir | `scopes.read` (`waveform`, `parade`, `histogram`, `vectorscopeYuv`) |
| Look compartido | Capa de ajuste (`file.newAdjustmentLayer`) encima de los clips |
| Textura (claridad, nitidez, grano) | `unsharp_mask` (claridad: amount ~25, radius ~30), `sharpen` (~10–15), `noise` (amount ~4–6, color off) |

Escala aproximada al traducir desde Palmier o un CDL: el contraste de Palmier 1.15 ≈ Lumetri +15; los negros de Palmier −0.12 ≈ −12; la saturación de Palmier 1.05 ≈ 105.

## Flujo seguro

1. Antes de cambiar nada, renderiza fotogramas de referencia ("antes") en los mismos segundos que vas a comparar.
2. Ten clara la extensión: un clip, varios, toda la secuencia o una capa de ajuste. Para un look de secuencia, prefiere una capa de ajuste o duplica la secuencia.
3. Haz un cambio a la vez, vuelve a mirar y mide.
4. Para igualar, elige un plano héroe. Compara con él y con los planos vecinos, no con el plano aislado.
5. Prueba el look en los planos atípicos (contraluz, ventana, pantalla del proyector) antes de aplicarlo a todo.

## Rechaza tu propio grade

Mirar dice si el grade "se lee bien", pero no si dañó la imagen. Mide en varios fotogramas, no en uno:
- **Altas aplastadas:** el tope de la waveform pegado al 100 % en zonas que antes tenían detalle.
- **Sombras con ruido amplificado:** la base de la waveform levantada y granulosa.
- **Bandas en degradados** (cielo, pared blanca, pantalla).
- **Piel fuera de la línea de piel** del vectorscopio.

Si falla en algún fotograma, atenúa la corrección (por ejemplo al 80 %) y vuelve a medir. Si después de 3 intentos sigue fallando, no lo des por bueno: entrega el mejor intento y di qué falla.

## Material de eventos en aulas

En aulas con ventanales y proyector:
- Las paredes blancas se queman.
- Los ventanales meten dominante verde o cian.
- La pantalla del proyector sale lavada.

Prioridad: caras primero. Corrige el verde con HSL secundario en lugar de bajar la saturación global, y deja la pantalla del proyector como está si no carga la historia.

## Informe

Reporta:
- la extensión del cambio;
- los valores antes y después;
- los fotogramas usados (segundos);
- qué mediste con scopes;
- los límites: material comprimido, altas quemadas, lo que no se pudo revisar.

No digas que revisaste un grade si no renderizaste fotogramas.
