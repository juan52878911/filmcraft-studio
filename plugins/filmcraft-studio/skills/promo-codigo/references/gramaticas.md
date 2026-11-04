# Gramáticas de promo

Cada DS `promo-*` declara su gramática en `ds.json` (`gramatica`) y los detalles que usa el render en la clave `promo`. Las tres comparten la rejilla de 134 BPM, la grabación real y la idea de que **la pausa se ve y se oye**: algo se apaga cuando la máquina se congela.

## temperatura@1 · `promo-brasa-escarcha`

- **Lienzo** 1920x1080, fondo brasa #14100D, texto hueso #EDE6DD. DIN Condensed Bold para titulares y cifras; Iosevka Term para todo lo que sale de una terminal.
- **Firma**: brasa (#FF5A1F) = corre; escarcha (#8FD3FF) = congelado. Al congelar la imagen se desatura hacia azul hielo, el grano se queda quieto, la cámara se para, la batería se va y suena hielo crujiendo; al despertar, *ping* e impacto.
- **Cámara**: push-in suave hasta la línea que importa, golpe de zoom +6 % en el beat del resultado, rótulos con nombre (`ARRANQUE EN CALIENTE`) junto a la línea.
- **Transición**: barrido horizontal con desenfoque de movimiento (7 fotogramas).
- **Música**: UK garage 2-step en Fa menor (Fm9 · Dbmaj9 · Bbm9 · Eb7), *sidechain* del kick, riser antes de despertar, *sting* de campana de 4 notas.
- **Progreso**: barra de 6 px abajo con el color de la temperatura.

## plano@1 · `promo-blueprint`

- **Lienzo** 1920x1080, azul plano #0A1F3D con rejilla (40 px, mayor cada 200), trazo blanco, anotaciones cian #6EC8FF, Helvetica Neue Condensed Black y SF Mono.
- **Firma**: todo se *traza*: perímetros en sentido horario, cotas que crecen desde el centro, texto tecleado. Congelado = rayado de sección a 45°; lo que corre lleva un único punto de brasa (#FF5A1F), el hilo con la otra gramática.
- **Narrativa**: la arquitectura como diagrama (host → compose.yml → microVM, con la cota del tiempo de arranque), la grabación real como *DETALLE A* con marcas de registro y anotaciones numeradas ①②③, cifras como barras a escala lineal real (si la nueva casi no se ve, se dice) y cajetín final.
- **Música**: electrónica ambiental, arpegio de pulsos en semicorcheas, kick a medio tiempo, tic de reloj; SFX de lápiz en cada trazo, garabato al rayar, sello en los golpes, papel que se desliza en los cambios.

## riso@1 · `promo-riso`

- **Lienzo** 1080x1920 (también 16:9). Papel #F4EFE4 con fibra; dos tintas que se **multiplican**: rosa flúor #FF48B0 y azul #0078BF, con el registro desplazado (7, −4) px. Helvetica Neue Condensed Black e Iosevka Bold.
- **Firma**: congelado = **una sola tinta**: la pasada rosa no imprime, entra semitono azul parejo, el temblor y el grano se paran y la cinta frena (*tape stop*); al despertar, la rosa vuelve con un golpe de registro (34, −20 px) y la imprenta pasa una hoja.
- **Animación** a dos (15 fps) con temblor de ±2 px por pasada; círculos y tachones a mano en rosa; semitono radial como mancha de fondo; marcas de registro en el cierre.
- **Vertical**: titulares ajustados al ancho (`fit`), apilados y alternando tinta; franja de rótulos abajo (y > 0,74); la cámara deja la fila enfocada en y ≈ 0,4.
- **Música**: breakbeat lo-fi (kick, snare con *ghosts*, swing) con piano eléctrico FM, vinilo, saturación de cinta y reducción de bits.

## termo@1 · `promo-gradient-map`

- **Filosofía**: no es «texto con halo». Es la imagen térmica de una impresión mal registrada. El gradient map (papel #E9E4D4 → azul #3466E0 → naranja #FFAC40 → rojo #F4403A → granate #2E121C) es una escala de **temperatura**, y la temperatura es **del lugar, no de la letra**. Cada escena pone fuentes de calor (una forma fundida, un foco, el cursor, la chispa) en un campo T, y cada glifo lee T en su caja. Errores que delatan un clon: el mismo halo centrado en todo, el núcleo intacto y el frío aplicado a todo el cuadro de golpe.
- **Anatomía** (de la referencia): una letra caliente lleva un halo de 22–30 px corrido (−10, +8) y un núcleo que se funde a granate. Una tibia lleva halo de 12–16 px a media ganancia. Una fría queda en tinta nítida con un filo rojo de 2 px y uno azul de 1 px. El calor baja a la mitad cada dos letras, contando desde el lado de la fuente. En cada plano está caliente menos del 30 % del texto, y el fondo también se calienta (bruma azul alrededor de las fuentes).
- **Lienzo** 1080x1920, papel con polvo y salpicaduras rojas. Arial Black ensanchada ×1,16 glifo a glifo; Iosevka Bold para el cuerpo, en tinta pura.
- **Arranque (ignición)**: el video empieza en el extremo frío del mapa (#0B0D16: todo apagado, 0 RAM). El comando se teclea en brasa y el Enter suelta una chispa que cae. Al tocar el suelo, enciende un frente de llama con lenguas que sube en dos beats; en su borde aparecen solas las bandas del mapa y detrás queda la escena. El frente es térmico y abstracto, no fuego realista.
- **Movimientos** (`termo.movimientos` del DS): *brasa*, *foco_recorre*, *contagio*, *desregistro*, *llamarada*, *a_sangre*, *látigo*, *titular_rotado*, *frente_llama*, *enfria_a_filo*, *hielo_que_sube*, *despertar*, *fusión* y *pulso*. Todo va a 30 fps, salvo las formas y el grano, que van a 12.
- **Contra lo genérico** (lecciones de la crítica):
  - Cifras y formas *a sangre*, recortadas por los bordes, con una forma por plano.
  - El mapa también dentro del glifo caliente.
  - **Una maqueta por idea**: el golden que se multiplica, el grafo de git con el titular rotado, el titular dentro del enchufe. Nunca la plantilla forma/titular/párrafo/comando repetida.
  - Poco texto (titular, un dato y el comando) y nada de rótulos de plantilla.
  - Cortes secos en el beat y solo dos transiciones firma, la llama y el hielo.
  - Cada forma significa algo del producto.
  - El cierre evoluciona: termina congelado y solo el cursor queda caliente.
  - En la terminal, zoom al resultado, pausa, látigo entre filas y filas fuera de foco al 10 %, para que no se corte nada sin intención.
- **Firma**: caliente = corre, frío = congelado. Al congelar, las letras pierden temperatura hasta quedarse en su filo, y el mapa frío avanza por regiones desde un punto; al despertar retrocede con una llamarada.
- **Técnica**: T a 1/4 de resolución (suma de gaussianas). Por glifo: radio = 28·calor, desplazamiento = (−10, +8)·calor, núcleo = 1 − 0,22·T y filo si el calor es < 0,3. El LUT frío se mezcla con un mapa por regiones, no con un escalar.
- **Música**: UK garage 2-step a 134 BPM: pads de sierras desafinadas con vibrato lento, stabs de órgano y sub con portamento. En el arranque todo va filtrado a 420 Hz; la chispa es un silbido que baja y la ignición, un golpe con el fuego rugiendo mientras el filtro se abre. Al congelar, el filtro cae a 180 Hz y queda una campana de cristal FM. SFX: `chispa`, `ignicion`, `onda`, `enfoque`, `congelar`, `cierre`.
- **Sobre otro material**: FilmCraft no tiene gradient map de varios tonos (Tint mapea a dos), así que el look se aplica con `scripts/promo_gradmap.py DS entrada salida --fuente x,y,sigma,ganancia [--invertir] [--niveles a,b] [--frio a-b]`. Sin fuentes, el halo va en todo, que es justo lo que el estilo evita.

## Crear otra gramática

Escribe aquí sus reglas (lienzo, tintas o paleta, tipografías, firma visual y sonora, cámara, transición, música), añade su kit a `promo_sfx.py` y un DS `promo-<nombre>` con `promo.firma`. Antes de animar, enseña dos fotogramas fijos (gancho y firma) junto a los demás estilos.
