---
name: imagen-a-video
description: "Anima una imagen fija (foto, poster, flyer o fotograma) en un plano corto: cámara por los focos, paralaje, capas, bucle o revelado, guiado por la ficha medida de la imagen. Úsala con «anima esta imagen», «dale movimiento a esta foto» o «haz un loop del poster». Para un video entero: director-video."
---

# Imagen a video (un solo plano)

Encargo corto: sin preproducción ni biblia. El movimiento sale de la ficha de la imagen, no se inventa. Guía completa de modos, parámetros y profundidad: `${CLAUDE_PLUGIN_ROOT}/skills/director-video/references/imagen-a-video.md` (léela antes de elegir modo).

Antes de cada llamada a un script (el estado del shell no persiste entre llamadas):

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
export CLAUDE_PLUGIN_DATA=${CLAUDE_PLUGIN_DATA}
W="<carpeta de trabajo>"   # regla de W en ${CLAUDE_PLUGIN_ROOT}/skills/preproduccion/SKILL.md; sin repo ni evento, <carpeta de la imagen>/video/<nombre>/ (dilo)
```

1. **Ficha:** `python3 $S/ref_metricas.py IMG --ficha "$W/img.ficha.json" --hoja "$W/img.hoja.png"`. Mira la imagen y la hoja con Read.
2. **Plan:** `python3 $S/imagen_a_video.py IMG --ficha "$W/img.ficha.json" --plan`: modo sugerido y por qué. Si el usuario pidió un modo (bucle → `ciclo`, «que se construya» → `revelado`), manda el suyo; si la ficha lo desaconseja, dilo. Si `--plan` avisa de que falta la capa 2 (filosofía), no bloquea un plano suelto: sigue con las métricas; rellénala solo si el plano va a un video con biblia.
3. **Fotogramas para revisar:** el mismo comando con `--modo M --dur S --fps N [--lienzo ANCHOxALTO] --fotogramas 0.5,2,3.5 --out "$W/img.mp4"` (escribe PNG, no video). Enséñalos (Read y, si `SendUserFile` está disponible, envíalos; si no, la ruta absoluta) y espera «sigue» o una nota.
4. **Render:** el mismo comando sin `--fotogramas`. Sale un MP4 H.264 sin audio. Comprueba el último fotograma (`--fotogramas <dur − 0,1>`): nada deformado, ningún texto partido.
5. **Entrega:** la ruta absoluta y, en una línea, el modo y por qué. Ofrece después, sin hacerlo: otra duración o formato, un prompt para IA generativa (`--prompt-ia`, sin llamar a ninguna API) o un video completo con `director-video`, donde el plano entra como escena `codigo`.

No se instala ni se descarga nada sin permiso (modelos de profundidad incluidos). La imagen tiene que ser del usuario o con licencia: no se animan obras, logos ni marcas de terceros.
