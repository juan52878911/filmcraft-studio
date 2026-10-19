# Audio y mezcla en FilmCraft

Las reglas de corte, efectos de sonido y entrega están parafraseadas de video-use (MIT). La cadena de voz y los niveles salen de los reels del AWS SBG EAN. Atribución en `../NOTICE.md`.

## Principios

- **El audio manda.** Los cortes candidatos salen de límites de palabra y silencios; la imagen se decide después.
- **No puedes oír.** Mide (LUFS, pico real, RMS por tramo) y reporta cifras. No digas "suena bien".
- **Pon fundidos cortos en cada corte** (2–4 f a 60 fps) para evitar chasquidos.
- **Menos efectos de sonido, mejor colocados.** Cada uno va ligado a algo visible (un corte, una caída, un golpe). Unos 8 en 20 s se sienten diseñados; 20 suenan a plantilla.
- **Golpe en el fotograma.** Si un efecto tiene ataque (silencio o subida antes del transitorio), adelántalo esa cantidad para que el transitorio caiga en el fotograma del evento.

## Voces bajas o lejanas (charlas en aulas)

Problema típico: el micrófono del móvil está lejos, la voz llega a −34/−37 LUFS y la sala tiene eco.

### A. Dentro de FilmCraft (ajustable por clip)

Efectos de audio sobre el clip de diálogo, en este orden:

| Efecto | Parámetros orientativos | Para qué |
|---|---|---|
| `highpass` | cutoff ≈ 90 Hz | Quitar retumbe y golpes de mesa |
| `denoise` | amount 40–60 | Aire acondicionado, ruido de sala |
| `dereverb` | amount moderado | Eco del aula; demasiado deja la voz metálica |
| `parametric_eq` | −3 dB en ~280 Hz (barro), +1 dB en ~1,2 kHz, +3,5 dB en ~3 kHz (presencia), +1,5 dB en ~6,5 kHz | Inteligibilidad |
| `single_band_compressor` | ratio ≈ 3:1, ataque ~5 ms, release ~80 ms | Igualar sílabas |
| `speech_enhance` | mix al gusto | Alternativa con modelo a la cadena manual; compara |
| `clip.audioGain` / `essentialSound.autoMatch` | objetivo −16 LUFS por clip de diálogo | Nivelar hablantes entre sí |

También existe el panel **Essential Sound**: marca los clips como `dialogue` (`essentialSound.setType`) y usa `repair.noise` o los presets de claridad.

### B. Preprocesado con ffmpeg (probado en los reels SBG)

Cuando hace falta mucha ganancia es más predecible procesar la fuente una vez y montar con la versión `_voz`. La cadena está en `scripts/procesar_voz.sh CRUDO SALIDA` (highpass 90, afftdn, EQ, dynaudnorm, compresor 3:1, loudnorm −16, limitador). El video se copia sin recodificar, así que se puede cambiar la fuente del clip sin tocar el montaje.

Verifica midiendo la loudness integrada del tramo usado, antes y después.

## Música y ducking

- Baja la música 12–15 dB bajo la voz. En los reels SBG el bed va a −18 dB bajo diálogo y a −6/−8 dB en tarjetas y cierre. Usa keyframes de `volume.level` en el clip de música o `essentialSound.generateDucking`.
- Saca la música con una rampa antes de un remate o tarjeta final, en vez de dejar morir su cola bajo la llamada a la acción.
- El gusto musical lo decide el usuario. Ofrece dos bases contrastadas.
- Si generas una base a medida, hazla al menos tan larga como el reel. Si la regeneras, sustituye el clip por uno nuevo en su propia pista.

## Efectos de sonido (paquete SBG)

Están en `design-systems/sbg-brutalista-s5/assets/sfx/` del plugin (transiciones/ y varios/; sintetizados, libres de derechos) y van a −7 dB. Las bases musicales se generan con `scripts/music_bed.py`.

| Evento | Efecto |
|---|---|
| Barrido de matte | `whoosh-corto` |
| Barrido largo o match cut | `whoosh-largo` |
| Persiana | `swipe` |
| Glitch | `glitch-rafaga` + `estatica` |
| Zoom-crash | `sub-drop` |
| Flash blanco | `flash-blanco` |
| Pop-up de texto | `pop` |
| Eco de texto | `blip` |
| Bloques en escalera | `tecla-maquina` |
| Inicio | `impacto` |
| Cierre | `riser-2s` → `impacto` |
| Fotos stop-motion | `obturador` |
| Celebración | `stinger-cian` |

Reparte en dos pistas ("Hits" para colas largas, "SFX" para golpes cortos) para que no se pisen: en FilmCraft un clip que se solapa en la misma pista recorta al anterior.

## Entrega

- Mezcla final a −14 LUFS integrados con pico real ≤ −1 dBTP (Reels, Shorts, YouTube). Para emisión, −23/−24 LUFS. Para pódcast, −16 a −19.
- `file.exportMedia` acepta `loudnessLufs` para normalizar al exportar.
- Mide por tramos: diálogo, solo música, tarjeta final. Una tarjeta final 15 dB por debajo del diálogo, o efectos más fuertes que la voz, son un error.

```bash
ffmpeg -nostats -i out.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "I:|Peak:"
```

## Trampas de FilmCraft con audio

- El importador de FCPXML puede soltar el diálogo en las pistas de efectos de sonido y perder los keyframes de volumen (ducking). Muévelo con `timeline.move` usando `linked: false` y reescribe los keyframes de `volume.level`.
- Los fundidos de audio se hacen con keyframes de `volume.level`: −60 dB en el borde y el nivel objetivo a N fotogramas.
