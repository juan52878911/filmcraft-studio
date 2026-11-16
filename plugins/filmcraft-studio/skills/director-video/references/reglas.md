# Listón profesional y verificación

Un video se ve profesional cuando nada se nota: no hay texto ilegible, cortes a destiempo, saltos de volumen ni elementos que no pertenecen al estilo. Esta lista se repasa con la hoja de fotogramas y las medidas, no de memoria.

## Imagen

- **Un solo design system.** Toda tipografía, color, transición y grano sale del DS. Si una escena de IA o de pantalla desentona, se iguala con el grade del DS; si no se puede, se quita.
- **Jerarquía**: un elemento dominante por plano. Titular, dato o persona, nunca los tres a la vez.
- **Márgenes**: 5–8 % del ancho; nada importante en las franjas de interfaz de cada plataforma. En vertical, la franja inferior (y > 0,74) es para rótulos o se deja libre.
- **Tamaños mínimos a 1080 px de ancho**:
  - rótulos de 40 px o más;
  - pies y fuentes de 26 px o más, y siempre legibles en el móvil;
  - contraste de 4,5:1 en texto pequeño y de 3:1 en titulares (`cine validar-ds <id>`).
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

Todo lo que se puede contar lo cuenta el binario `cine` (`${CLAUDE_PLUGIN_ROOT}/bin/cine`); la IA solo juzga historia, copy, originalidad y los criterios marcados `juicio`. Cada vuelta `N` va en su carpeta (`W/verificacion/vN/`):

1. **Medir.**
   - Montaje en FilmCraft: `verify.py` (cortes en palabra, keyframes en rango, textos frente a caras, hojas, curva de loudness) → `verificacion.json`.
   - Video renderizado (promo, escena por código, entrega): `cine medir-video <video> --out vN/medidas-<entregable>.json` por entregable (formato, peso, LUFS, pico dBTP, curva, cortes, planos, negros y flashes).
   - Hoja de fotogramas en los tiempos clave: gancho, cada escena, la firma, el cierre. Es la evidencia del crítico, no tu opinión.
2. **Criterios.** `cine criterios --biblia biblia.json --medidas a.json,b.json [--verificacion verificacion.json --compiled compiled.json]` comprueba los de la biblia con cifra (lienzo, duración, fps, LUFS, dBTP, MB, `medida`). Sale con 1 si alguno no cumple.
3. **Puntuar.** `cine puntuar --ds <id> --biblia biblia.json [--compiled compiled.json --verificacion verificacion.json] [--medidas …] [--comparaciones <carpeta de referencias.py --comparar --json>] --out vN/ejes.json`: criterios, obligatorios, audio, imagen, ritmo y lectura de 1 a 5 con reglas fijas, bloqueantes, arreglos medidos, `sin_medir` y `para_ia` (techos y criterios de juicio).
4. **Juzgar.** Subagente `critico-juicio` con `vN/ejes.json` y la carpeta de trabajo (hojas, biblia, referencias), sin tus conclusiones; su JSON va a `vN/juicio.json`. Si no hay subagentes, juzga tú en un paso aparte releyendo solo lo que dice `agents/critico-juicio.md`.
5. **Nota.** `cine nota --ejes vN/ejes.json --juicio vN/juicio.json > vN/nota.json`: nota ponderada, veredicto (publicable / publicable con arreglos / no publicable) y los 5 arreglos, los medidos primero. Sale con 1 si es «no publicable»: no es un fallo del comando.
6. **Arreglar** los 5 y rehacer solo lo afectado. En la vuelta siguiente añade `--mejor <nota de la mejor versión> --bloq-anterior si|no` a `cine nota`:
   - `Mejora`: la nueva pasa a ser la mejor;
   - `Regresión` (también si aparece un bloqueante que la anterior no tenía): vuelve a la mejor versión y prueba otro arreglo;
   - `Empate`: para; no hay más que sacar con estos arreglos;
   - `pendiente de A/B` (`ab_necesario: true`, |Δ| < 0,30 sin bloqueante nuevo): `cine ab --nueva <hojas de vN> --anterior <hojas de vM> --out vN/ab` (en montaje, las hojas están en la carpeta de `verify.py --out`; la clave queda en `vN/clave-ab.txt`, fuera de lo que ve el crítico), `critico-juicio` en modo A/B sobre `vN/ab/` → `vN/ab.json`, y otra vez `cine nota … --mejor … --bloq-anterior … --ab vN/ab.json --clave vN/clave-ab.txt`. Solo entonces: el A/B no se pide si `ab_necesario` es false.
7. **Informe.** La tabla de criterios sale de `cine criterios … --md` (cumple, no cumple, sin comprobar, juicio, con evidencia); las filas `juicio` se completan con `criterios` de `juicio.json`. Añade qué se comprobó, qué no y por qué (`sin_medir`, el audio sin escuchar).
