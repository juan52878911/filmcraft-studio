# Motor imagen → video

`S` y `W` vienen del SKILL.md de `director-video`. Convierte una imagen fija (un fotograma aprobado de la biblia, un poster, una foto, una referencia propia) en un plano animado **coherente con su composición**. El movimiento no se inventa: sale de la ficha de la imagen (`ref_metricas.py`), que dice dónde está el foco, qué líneas mandan, cuánta profundidad hay y si hay texto.

```bash
python3 $S/ref_metricas.py IMG --ficha "$W/escenas/img.ficha.json" --hoja "$W/escenas/img.hoja.png"   # mira la hoja
python3 $S/imagen_a_video.py IMG --plan [--ficha "$W/escenas/img.ficha.json"]   # modo sugerido y por qué; ruta de cámara; texto protegido; capa 2
python3 $S/imagen_a_video.py IMG --modo revelado --dur 4 --fps 30 --fotogramas 0.5,2,3.5 --out "$W/escenas/img.mp4"   # PNG para revisar
python3 $S/imagen_a_video.py IMG --modo revelado --dur 4 --fps 30 --lienzo 1080x1920 --out "$W/escenas/img.mp4"
```

Sale un MP4 H.264 sin audio al lienzo pedido (`--lienzo`, cubre y recorta al centro; sin él, el tamaño de la imagen hasta `--max`). Sin `--modo` usa `video.sugerido.modo` de la ficha. Imprime JSON con fotogramas, duración, plan y tiempos. Entra en FilmCraft como cualquier fuente de motor `codigo` (`analyze_media.py --sin-vision`).

## Qué modo usar

| Modo | Qué hace | Úsalo cuando la ficha dice | No lo uses si |
|---|---|---|---|
| `kenburns` | La cámara va del plano general a los puntos fuertes en orden de saliencia (`--orden inverso`: de los focos al general). Spline suave, ≥ 1,5 s por parada, sin salirse del cuadro. No para en adornos (focos con menos del 8 % del peso o a menos del 8 % del borde), **no corta un titular** en ningún fotograma y **el último encuadre contiene el texto entero**. La velocidad punta se limita a 0,30 anchos de ventana por segundo: si no da tiempo, quita paradas | 2 o más `puntos_fuertes` separados; imagen con resolución de sobra (acerca hasta 1,5×) | La imagen mide menos que el lienzo: el acercamiento la ablanda. El texto ocupa casi todo el cuadro: el zoom se queda en 1,0–1,1 (lo dice `plan.paradas`); usa `revelado` |
| `parallax` | 2.5D: lo cercano se desplaza más que lo lejano y la cámara empuja hacia el foco. Eje según `video.sugerido.paralaje_eje` (paralelo al horizonte) | `profundidad.pista` atmosférica o foco selectivo; foto o ilustración con planos | Simetría alta (rompe el eje: usa `--amp 0` y solo `--zoom`) |
| `capas` | Separa 3 capas por forma y profundidad, rellena el fondo y las hace entrar escalonadas, de atrás hacia delante; después derivan | Pieza gráfica (`pieza_grafica`), formas separables sobre un fondo dominante | Foto o ilustración continua: la ficha ya no lo ofrece. Si lo fuerzas, las capas solo derivan (sin entrada, sin costuras oscuras) y el plan trae un `aviso` |
| `ciclo` | Bucle sin costura: órbita de paralaje, respiración y grano periódicos. El fotograma N es el 0 | Fondos, tarjetas de espera, `ritmo` fuerte, stickers y loops de redes | Necesitas un arranque o un final: un ciclo no tiene |
| `revelado` | La imagen se construye por valores desde el foco: color dominante → masas del notan → imagen completa | Notan marcado (`contraste_global` > 0,2), posters, piezas con texto: no deforma nada | Clave muy alta o muy baja con poca masa: el notan casi no se ve |

Parámetros que importan: `--amp` (paralaje, fracción del ancho; 0,012 por defecto, más de 0,03 delata el proxy), `--zoom` (empuje total, 0,06), `--grano auto|0..1` (auto usa el grano medido: una imagen limpia sigue limpia), `--motor rigido|malla` (auto: rígido si hay texto o formas planas de borde duro, para que nada se deforme; malla continua para fotos).

## Profundidad

- **Sin modelos** (por defecto): un proxy hecho de posición, nitidez, saliencia y croma, promediado por segmento de color para que cada forma se mueva entera. Sirve para paralajes pequeños. No es geometría.
- **Mapa propio**: `--profundidad mapa.png` (blanco = cerca). Puede venir de Blender (pase Z), de un modelo o estar pintado a mano.
- **Depth Anything**: `--profundidad auto` lo usa si `torch` y `transformers` están instalados y el modelo ya está en la caché (no descarga nada); `--profundidad modelo.onnx` lo ejecuta con `onnxruntime`. Instalar o descargar necesita permiso. La ruta ONNX no está probada en esta máquina: revisa el primer fotograma.

## Coherencia con la composición

`video.traduccion` de la ficha lista, rasgo a rasgo, qué movimiento le corresponde. Reglas que aplica el script o que debes aplicar al elegir:

- **Foco principal**: la cámara termina ahí (o empieza, con `--orden inverso`); el revelado y el empuje nacen ahí. Si hay texto, manda el texto: el encuadre final se abre hasta contenerlo.
- **Horizonte o línea dominante**: el desplazamiento va paralelo a ella; nunca se inclina. Si el horizonte ya viene inclinado (hasta ±10°), el eje de paralaje sigue esa inclinación. En una pieza con texto no hay horizonte: una franja o la base de unas tarjetas no guían la cámara.
- **Patrón** (semitono, rayado): no se reescala ni se desenfoca; movimientos cortos.
- **Capa 2 de la ficha**: `--plan` devuelve `filosofia` y `criterio` (la regla generadora y el «dónde no»). Mandan sobre el modo sugerido: si la regla dice que algo no se mueve, no se mueve. Si la capa está vacía, el plan lo avisa: rellénala antes de animar (`skills/preproduccion/references/referencias.md`).
- **Simetría alta**: solo empuje axial.
- **Texto**: es rígido. El motor `rigido` mueve cada bloque entero; nunca uses `malla` sobre texto.
- **Espacio negativo**: ahí entran los rótulos animados del montaje.
- **Bordes duros**: arranques y frenos marcados, cortes. **Bordes suaves**: movimiento lento y fundidos.
- **Grano**: si la imagen tiene grano, tiene que moverse (`--grano auto`); un grano congelado delata la foto fija.
- **Ritmo**: la duración por parada o por capa cae en beats del guion (`--dur` = beats × 60 / BPM).

## Verificar

```bash
ffmpeg -v error -ss 3.9 -i plano.mp4 -frames:v 1 fin.png
python3 $S/referencias.py --comparar IMG fin.png      # el grupo «estilo» tiene que seguir dentro de tolerancia
```

`--comparar` reconoce el fotograma como la misma imagen aunque el plano la haya acercado o recortado (`derivado`), y exige que el color siga dentro de tolerancia.

Mira una hoja de 4 fotogramas antes de montar. Señales de fallo: bordes que ondulan (pasa a `--motor rigido` o baja `--amp`), dobles contornos en `capas` (la separación partió una forma: usa `revelado` o `kenburns`), letras que se tuercen. En una pieza gráfica con fondo de textura, `capas` deja a los 0,5 s una huella lisa donde irá cada forma (el relleno no reproduce la textura): revisa ese fotograma.

## Cuándo delegar

| Necesitas | Ve a |
|---|---|
| Que algo de la imagen cobre vida: agua, pelo, tela, humo, una persona que se gira, cámara que rodea el objeto | **IA generativa** de imagen a video (Kling, Veo, Runway, Wan/LTX). Solo con permiso y con las reglas del motor `ia` de `motores.md` |
| Cámara física con paralaje fuerte, luz que cambia, profundidad de campo real, texto extruido | **Blender** (`motor_blender.py`): la imagen como plano o proyectada sobre geometría sencilla; exporta el pase Z y úsalo aquí con `--profundidad` si solo quieres mejor paralaje |
| Tipografía que se anima letra a letra, cifras que cuentan, diagramas | Motor `codigo` (escena propia o **bloques**): redibuja la pieza en vez de mover una foto de ella |
| Solo dar vida a un fondo, un poster o un fotograma aprobado durante 2–6 s | Este script |

### Prompt para IA generativa

```bash
python3 $S/imagen_a_video.py IMG --prompt-ia --dur 4 [--ficha ficha.json]
```

No llama a ninguna API: escribe el prompt con lo medido (movimiento de cámara según horizonte —nunca en una pieza gráfica—, simetría y diagonales; clave de luz; paleta en hex; filo de los bordes; grano; texto rígido y sin cortar; patrón, duotono, desregistro y peso de la letra si los hay) y, si la ficha tiene la capa 2 rellena, añade la regla del estilo, el movimiento, la emoción, lo que la distingue y el «dónde no» (como prohibición). `filosofia.usada` dice qué campos entraron; si la capa está vacía, la primera nota lo avisa. Úsalo como primer fotograma = la imagen, 2–4 s, 2–3 tomas. Después compara el último fotograma con `--comparar`, pasa el plano por el grade del DS y anota en el informe el modelo, el prompt y la licencia.

## Tiempos de referencia (M4, 1920×960, 30 fps)

Ficha: 0,1–0,2 s. Preparación: 0,1–0,5 s. Render: `kenburns` ≈ 11 ms por fotograma; `revelado` ≈ 35 ms; `capas` ≈ 32 ms; `parallax` y `ciclo` ≈ 40–50 ms. Un plano de 4 s tarda entre 1,5 y 6 s.
