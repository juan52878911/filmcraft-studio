# Lo aprendido (investigación de noviembre de 2026 y promos de kindling v0.20)

## Por qué un promo de repo se ve genérico

- **El aspecto por defecto ya es otro.** El estudio de ADVIDS (100 videos de 92 empresas de software, enero–agosto de 2026) mide lo que hoy es habitual:
  - las pantallas del producto como protagonista pasaron del 37 % al 63 %;
  - la grabación real de pantalla, del 18 % al 30 %;
  - los fondos claros, del 35 % al 55 %;
  - el 3D bajó del 23 % al 13 %.

  El primer plano del producto llega de media en el segundo 18. Plano 2D, poco texto y fondo claro es ahora la base genérica. Brutalismo y minimalismo, con *dithering*, monoespaciada, gradiente morado e Inter, ya vienen en componentes listos.
- **La IA de video con texto solo da su estética media.** Kling y similares inventan una UI en vez de mostrar el repo. Cuando entra IA, que sea en 2–4 planos de relleno, siempre desde imagen propia (imagen a video), en planos de 2–4 s, con grade y grano comunes. Sora 2 cerró: la app el 2026-04-26 y la API el 2026-09-24.
- **La música de librería tipo «tech corporate»** y las curvas de animación por defecto terminan de darle aire de plantilla.

## Qué funciona

- **Producto real con la cámara encima, una acción cada vez**, como hace Linear. Las transiciones las hace la cámara; nada de voz en off, stock ni 3D abstracto; la duración y el easing salen de *tokens* de movimiento. El caso de Lago, rehecho con un agente y Remotion, pasó de unas 12 rondas de revisión a 1.
- **Una firma propia ligada a lo que hace el producto.** En kindling, «congelar»: se ve, se oye y lo cumple la cámara. Repetida en todos los estilos, es lo que hace reconocible la marca, más que el estilo de moda.
- **Kit rígido**: una tipografía de titular, una de terminal, un acento, dos curvas, una transición, un kit de SFX y un *sting* de 2 s.
- **Gancho en el primer segundo** con el resultado («0.4s»). Pensado para verse sin sonido: el texto lleva el mensaje y el audio lo refuerza.
- **Tres estilos distintos con el mismo guion** antes de decidir. Enseña fotogramas fijos, no videos, para elegir rápido.

## Música y sonido

- **Elige un micro-género con BPM antes de montar** (UK garage a 134, breakbeat lo-fi, ambiental con pulsos) y corta en los golpes.
- **Prompts para IA de música**: género + BPM + instrumentos + exclusiones («no ukelele») + marcas de estructura o de tiempo para que el *drop* caiga en la revelación. Nunca nombres de artistas.
- **Un SFX por acción en pantalla**: clics sacados de la propia grabación, lápiz, sello, hielo, imprenta…
- **Máster**: −14 LUFS integrados y −1 dBTP de pico. Solo YouTube publica objetivo; X, LinkedIn, TikTok y Meta no publican ninguno.
- **Ducking** de 6–12 dB bajo la voz.
- **Sintetizar con numpy** evita licencias y cuadra con la rejilla al fotograma.
- **Licencias de IA musical** (estado de noviembre de 2026):
  - **Suno**: uso comercial solo en planes de pago; tras el acuerdo con Warner, por lo general el usuario no es dueño de lo generado.
  - **Udio**: no permite descargas desde el acuerdo con UMG.
  - **ElevenLabs Music**: entrenado con licencias; publicidad, cine, TV y videojuegos necesitan licencia aparte.
  - **Lyria**: marca de agua SynthID.

## Datos y afirmaciones

- **Cada afirmación comparativa necesita una medida del repo.** «Igual o mejor que x86» no se sostenía: en el único cara a cara (`db branch`), el M4 con vz era más lento en 2 de 3 operaciones. La línea defendible fue «mismo orden de magnitud», con la fuente en pantalla.
- **Las cifras marcadas como STALE**, o medidas en montajes distintos (anidado o no, con jailer o sin él), no se ponen lado a lado.
- **Los logos de terceros no se usan.** Se escribe «Apple Silicon» y se dibuja un chip genérico; `uname -m → aarch64` en la terminal real lo demuestra mejor que un logo.

## Formatos

| Destino | Formato |
|---|---|
| X, LinkedIn, YouTube | 16:9, 20–30 s |
| Reels, Shorts, TikTok | 9:16, 20–30 s; titulares ajustados al ancho y rótulos en una franja baja |
| README de GitHub | MP4 o WebM de hasta 10 MB (cuenta gratuita) o 100 MB (de pago); un *loop* corto sin audio |
| Móvil, vía SendUserFile | menos de 30 MB |

## Errores que salieron en la hoja de fotogramas

- Un titular que se sale por la derecha.
- Glifos ausentes (`→`, `′`, `✓`).
- Un rótulo encima de la línea de terminal de al lado.
- La cámara que corta el margen izquierdo del texto.
- Una mancha de semitono tapando una cifra.
- Una división por cero cuando el radio de una animación vale 0.

Todos se vieron en la hoja de fotogramas antes del render completo, no en el video.
