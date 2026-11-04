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

## Crear otra gramática

Escribe aquí sus reglas (lienzo, tintas o paleta, tipografías, firma visual y sonora, cámara, transición, música), añade su kit a `promo_sfx.py` y un DS `promo-<nombre>` con `promo.firma`. Antes de animar, enseña dos fotogramas fijos (gancho y firma) junto a los demás estilos.
