# Portar una timeline de Palmier Pro a FilmCraft

Conversores probados en el reel #RetoCertEAN (comparado fotograma a fotograma; audio idéntico, −14,7 LUFS).

1. Exporta FCPXML desde Palmier (`export_project mode=fcpxml`) e impórtalo en un proyecto nuevo de FilmCraft abierto con `--control 9876`.
2. Selecciona el video principal y activa `clip.scaleToFrameSize`.
3. Exporta las variables y ejecuta en orden:
   ```bash
   export PALMIER_PROJECT="/ruta/Proyecto.palmier" PALMIER_TIMELINE="Reel X" PALMIER_GRAFICA="/ruta/04 - Grafica"
   python3 convert_stills.py && python3 convert_fx.py && python3 convert_motion.py && python3 convert_texts.py && python3 word_reveal.py && python3 convert_audio.py
   ```
4. Compara con `../render_sheet.py` en los mismos segundos que el export de Palmier.

Los fotogramas de Palmier se convierten con los fps de su timeline (`palmier.FPS`); los de FilmCraft, con los de la secuencia (`fc.fps()`).
