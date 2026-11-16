# Verificación antes de entregar

Inspirado en la autoevaluación de video-use (MIT) y adaptado al render headless de FilmCraft. Si no renderizaste fotogramas o no mediste el audio, no digas que algo está verificado.

## Imagen

1. Guarda el proyecto (`file.save` por el canal de control o `--save`) y renderiza hojas headless:
   ```bash
   python3 $S/render_sheet.py PROYECTO.fcproj hoja.jpg 1.2 6.4 12.9 …   # S viene del SKILL.md
   ```
2. Revisa cada corte (±1 s), cada transición (antes, pico, después) y cada pop-up (inicio, mitad, final). Comprueba:
   - salto, flash o negro inesperado en el corte;
   - texto que tapa caras, se sale del lienzo o se pisa con otro;
   - el orden de capas (mattes por encima de los textos);
   - animaciones que no arrancan, por la base de tiempo de los keyframes.
3. Para comprobar dónde están las personas sin el texto encima, oculta temporalmente las pistas de texto (`timeline.setTrack {"enabled":false}`) y vuelve a renderizar.
4. Si hay una versión de referencia (otro export o el editor anterior), compara fotograma a fotograma en los mismos segundos (diferencia media por píxel más una mirada en una hoja combinada).

## Audio

- `${CLAUDE_PLUGIN_ROOT}/bin/cine medir-video <export.mp4 | mix.wav> --out medidas.json` sobre el export o sobre una mezcla `.wav` headless (`filmcraft-cli --project P export mix.wav`): loudness integrada, pico real, curva por segundo (`audio.curva_s`) para ver el ducking y compararla con la referencia y, en un video, cortes, planos, negros y flashes.
- Con `compiled.json` (proyecto hecho con el plugin), `verify.py` mide lo mismo sobre la mezcla y además cortes en palabra, keyframes y textos frente a caras.
- Silencios reales (`silencedetect`) para validar los tiempos de la transcripción.

## Revisión crítica (piezas que se publican)

Lo medible se puntúa sin IA y el subagente solo juzga lo que no se cuenta:
1. `cine puntuar [--ds id] [--compiled compiled.json --verificacion verificacion.json] [--medidas medidas.json] [--biblia biblia.json] --out ejes.json`: audio, imagen, ritmo, lectura, obligatorios y criterios de 1 a 5, con bloqueantes y arreglos medidos.
2. Subagente `critico-juicio` con `ejes.json`, las hojas y la lista de cortes (historia, copy, originalidad); su JSON va a `juicio.json`.
3. `cine nota --ejes ejes.json --juicio juicio.json`: nota, veredicto (publicable / publicable con arreglos / no publicable) y los 5 arreglos a hacer primero. En la pasada siguiente, `--mejor <nota anterior> --bloq-anterior si|no` dice si es Mejora, Regresión (vuelve a la versión anterior) o Empate; A/B a ciegas (`cine ab`) solo si `ab_necesario`.

## Límites

- Haz como máximo 3 pasadas de autoevaluación y arreglo. Si quedan problemas, repórtalos en vez de seguir en bucle.
- Exportar en FilmCraft es lento (~7 min por minuto 4K→1080). Para revisar bastan hojas de fotogramas y mezcla `.wav`. Exporta video solo al final o si lo piden, y nunca a la carpeta del usuario sin permiso.
