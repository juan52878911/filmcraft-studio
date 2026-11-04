# Listón profesional y verificación

Un video se ve profesional cuando nada se nota: no hay texto ilegible, cortes a destiempo, saltos de volumen ni elementos que no pertenecen al estilo. Esta lista se repasa con la hoja de fotogramas y las medidas, no de memoria.

## Imagen

- **Un solo design system.** Toda tipografía, color, transición y grano sale del DS. Si una escena de IA o de pantalla desentona, se iguala con el grade del DS; si no se puede, se quita.
- **Jerarquía**: un elemento dominante por plano. Titular, dato o persona, nunca los tres a la vez.
- **Márgenes**: 5–8 % del ancho; nada importante en las franjas de interfaz de cada plataforma. En vertical, la franja inferior (y > 0,74) es para rótulos o se deja libre.
- **Tamaños mínimos a 1080 px de ancho**:
  - rótulos de 40 px o más;
  - pies y fuentes de 26 px o más, y siempre legibles en el móvil;
  - contraste de 4,5:1 en texto pequeño y de 3:1 en titulares (`ds_validate.py`).
- **Textos que caben**: ajústalos al ancho o recórtalos. Revisa que la fuente tenga cada glifo: hay fuentes condensadas sin `→ ′ ✓`.
- **Movimiento con intención**:
  - easing de salida para las entradas e in-out para los desplazamientos, nunca lineal salvo en mecanismos;
  - pequeño rebote (*overshoot*) solo en golpes;
  - la cámara se mueve hacia lo que importa y se para cuando el contenido habla.
- **Personas**: los textos no tapan caras (zonas libres del compilador). Los planos de entrevista cortan en palabra.

## Ritmo

- **Planos dentro de `ritmo.plano_s` del DS.** Con música, los cortes y las entradas de texto caen en el beat o en una subdivisión.
- **El gancho llega en el primer segundo.** La duración total está dentro de `estructura.duracion_s`.
- **Nada espera**: los tiempos muertos se aceleran (*speed ramp*) o se quitan, y se dice si se aceleró algo que el espectador va a medir.

## Audio

- **Niveles**: −14 LUFS integrados y −1 dBTP de pico (`audio` del DS); voz a −16 LUFS antes de mezclar.
- **Música**: 6–12 dB por debajo de la voz; sin voz, `sin_voz_db`.
- **SFX**:
  - un efecto por acción visible, del kit del DS, y ninguno sin evento en pantalla;
  - un golpe empieza 0–2 fotogramas antes que la imagen.
- **Cortes de audio**: fundidos cortos (`fade_corte_f`), sin clics.
- **Si no lo has escuchado, dilo.** Las medidas (LUFS, pico, espectro) no sustituyen a la escucha.

## Contenido

- **Cada afirmación tiene su `hecho`** en el guion, con fuente. Las cifras llevan contexto (p50, máquina, fecha).
- **Nada de comparaciones que el dato no sostiene**, ni cifras viejas (STALE) presentadas como actuales.
- **Sin marcas de terceros** salvo material con licencia del usuario.
- **Sin datos personales** en las grabaciones: rutas de casa, correos, tokens, notificaciones.
- **Subtítulos o texto suficiente** para entenderlo sin sonido; la mayoría lo ve en silencio.

## Verificación (antes de enseñar)

1. **Hoja de fotogramas en los tiempos clave**: gancho, cada escena, la firma, el cierre. Busca texto que se sale, glifos que faltan, solapes, caras tapadas y contraste.
2. **`verify.py`**: cortes en palabra, keyframes en rango y textos frente a caras.
3. **`ebur128`** sobre la mezcla final: LUFS integrados y pico verdadero.
4. **Duración, resolución, fps y tamaño** del archivo frente a la plataforma (< 30 MB para el móvil, ≤ 10 MB para el README en cuentas gratuitas).
5. **Agente `critico`**: veredicto y los 5 arreglos más importantes.
6. **Informe**: qué se comprobó, qué no y por qué.
