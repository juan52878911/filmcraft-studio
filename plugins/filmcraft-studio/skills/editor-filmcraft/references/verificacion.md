# Verificación antes de entregar

Inspirado en la autoevaluación de video-use (MIT) y adaptado al render headless de FilmCraft. Si no renderizaste fotogramas o no mediste el audio, no digas que algo está verificado.

## Imagen

1. Guarda el proyecto (`file.save` por el canal de control o `--save`) y renderiza hojas headless:
   ```bash
   python3 scripts/render_sheet.py PROYECTO.fcproj hoja.jpg 1.2 6.4 12.9 …
   ```
2. Revisa cada corte (±1 s), cada transición (antes, pico, después) y cada pop-up (inicio, mitad, final). Comprueba:
   - salto, flash o negro inesperado en el corte;
   - texto que tapa caras, se sale del lienzo o se pisa con otro;
   - el orden de capas (mattes por encima de los textos);
   - animaciones que no arrancan, por la base de tiempo de los keyframes.
3. Para comprobar dónde están las personas sin el texto encima, oculta temporalmente las pistas de texto (`timeline.setTrack {"enabled":false}`) y vuelve a renderizar.
4. Si hay una versión de referencia (otro export o el editor anterior), compara fotograma a fotograma en los mismos segundos (diferencia media por píxel más una mirada en una hoja combinada).

## Audio

- Loudness integrada y pico real del export o de una mezcla `.wav` headless (`filmcraft-cli --project P export mix.wav`).
- Curva por segundo (`ebur128` con `metadata=1` y `lavfi.r128.S`) para ver el ducking y comparar con la referencia.
- Silencios reales (`silencedetect`) para validar los tiempos de la transcripción.

## Revisión crítica (piezas que se publican)

Para algo que se va a publicar, lanza un subagente crítico con el export, la lista de cortes y las referencias. Pídele que destroce, no que elogie:
- un veredicto;
- los problemas ordenados, con timecode y evidencia;
- los 5 arreglos a hacer primero.

## Límites

- Haz como máximo 3 pasadas de autoevaluación y arreglo. Si quedan problemas, repórtalos en vez de seguir en bucle.
- Exportar en FilmCraft es lento (~7 min por minuto 4K→1080). Para revisar bastan hojas de fotogramas y mezcla `.wav`. Exporta video solo al final o si lo piden, y nunca a la carpeta del usuario sin permiso.
