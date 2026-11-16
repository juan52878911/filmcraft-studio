# Crítica de originalidad

Se hace dos veces:
1. sobre los fotogramas fijos, antes de aprobar la biblia;
2. sobre el video, antes de entregarlo, en la misma pasada de la verificación.

La hace el agente `critico-juicio` (con el modelo más capaz disponible) con ojos frescos; es el único crítico con IA y juzga también historia y copy. Recibe:
- `ejes.json` de `cine puntuar … --comparaciones <carpeta>`: lo ya medido y los techos (`para_ia.techos.originalidad`);
- los fotogramas;
- `biblia.json`;
- la hoja de referencias;
- las fichas de las referencias **con la capa 2 rellena** y la salida de `--comparar` (abajo).

Antes de lanzarla, comprueba que las fichas están completas: `python3 $S/referencias.py --validar "$W/referencias"` tiene que salir con 0. Sin la regla, el «dónde no» y el «no copiar» de cada referencia, el crítico no tiene contra qué medir el punto 1.

No le pases tu opinión: si le das la hipótesis, la confirma. Si el modelo del agente no está disponible, lánzalo con `model: opus`; si no hay subagentes, haz la crítica tú en un paso aparte, releyendo solo los fotogramas, la biblia y las referencias. Para criterios de composición y tipografía, puede apoyarse en la skill `frontend-design` si está instalada.

## Medir antes de opinar

```bash
python3 $S/referencias.py --comparar REFERENCIA FOTOGRAMA --json --out "$W/preproduccion/comparaciones/<ref>__<fotograma>.json"
```

Compara las fichas métrica a métrica contra su tolerancia, en dos grupos, y da un veredicto:

| Veredicto | Estilo | Composición | Qué hacer |
|---|---|---|---|
| `reproduce el estilo con composición propia` | ≥ 75 % dentro **y el color dentro** | notan o focos distintos | Es lo que se busca frente a una referencia |
| `clon probable` | dentro | misma figura de notan y mismos focos, o la misma imagen | Cambia la maqueta: es la composición de la referencia |
| `misma maqueta con otro estilo` | fuera | igual | También es copia: se calcó el layout y se cambió la piel |
| `estilo distinto` | fuera | distinta | Bien frente a una anti-referencia; frente a una referencia, `ajustar` dice qué mover y hacia dónde |

Cómo decide:

- **El color es condición necesaria del estilo**, no un voto más: `color.paleta` (ΔE por área), `color.tono_principal` y `color.paleta_tonos` (los tonos color a color, sin ponderar por área, para que cuente un acento) tienen que estar dentro de tolerancia. Con la paleta girada no hay «reproduce el estilo» aunque coincida todo lo demás; `color` en la salida dice cuál falla y `ajustar` lo pone primero.
- **Misma composición** es la figura del notan a menos de 0,20 y los focos a menos de 0,08 (también con la maqueta espejada), o que `derivado` reconozca **la misma imagen**: espejada, girada 90/180/270°, recortada hasta el 60 % por eje o con bandas negras. `derivado` dice la transformación, el recorte y la correlación; una misma imagen que conserva los tonos es clon aunque el recorte haya movido las demás métricas.
- La salida trae `filosofia_ref`: la regla generadora, lo que distingue, el «dónde no» y el «no copiar» de la referencia. Si falta, lleva un `aviso`: rellena la capa 2 antes de criticar.

Medido en la ronda 3 (pares sintéticos y 12 imágenes reales): 1 falso clon en 132 pares de la misma paleta con otra maqueta; 0 de 24 pares con la paleta girada 120° pasan por «reproduce el estilo»; 20 de 20 derivados geométricos y 20 de 20 cambios de brillo, saturación, contraste, grano y desenfoque salen clon; 21 de 21 pares sin relación salen distintos. Límites: una sola forma sobre fondo liso no basta para afirmar un recorte; un giro de tono de 40° en una imagen de muchos tonos puede pasar por el mismo estilo.

- Frente a una **anti-referencia**, el veredicto bueno es `estilo distinto`.
- `ajustar` lista las métricas de estilo más alejadas, con el sentido (subir, bajar) y la palanca. Úsalo para el arreglo, no para perseguir cada cifra.
- Compara también los fotogramas propios **entre sí**: si gancho y firma salen `clon probable`, hay una plantilla repetida (punto 3).
- Las medidas no ven el significado: que el estilo coincida no dice que la regla esté entendida. El veredicto final es del crítico; estas cifras son su evidencia. `cine puntuar --comparaciones` las lee: «clon probable» o «misma maqueta» es bloqueante y deja la originalidad en 2 como mucho; «estilo distinto» frente a una referencia que se quería reproducir, en 3.
- **El crítico cita la capa 2.** En el punto 1 copia la `regla_generadora` y el `donde_no` de `filosofia_ref` y dice, con fotograma, si el video los cumple; si algo de `no_copiar` aparece en un fotograma, es un arreglo de los cinco primeros. Una crítica que no cita la regla de la referencia no vale.

## Lista (cada punto con evidencia: fotograma, segundo o archivo)

1. **Filosofía, no filtro.** ¿Se puede decir la regla del estilo y dónde NO actúa? Si el efecto va igual en todo, es un clon de la referencia. Evidencia obligatoria: la `regla_generadora` y el `donde_no` de la ficha de la referencia (`filosofia_ref`), citados, frente al fotograma.
2. **Metáfora con producto.** Cada variable visual (color, temperatura, textura, movimiento) significa algo del producto. Si una no significa nada, sobra.
3. **Una maqueta por idea.** No hay plantilla repetida (forma + titular + párrafo + comando). Cada idea tiene su composición: lo que se multiplica, lo que gira, lo que encaja.
4. **Escala con intención.** Cifras y formas *a sangre*, recortadas por el borde, con una forma dominante por plano. Nada pequeño y centrado sobre un fondo vacío.
5. **Poco texto.** Un titular, un dato y el comando o CTA. Ningún rótulo de plantilla («Feature 1», «Rápido. Seguro. Simple.»).
6. **Ritmo.** Los cortes caen en el beat. Hay una o dos transiciones firma y ninguna de catálogo. Hay pausas donde hay un resultado.
7. **Evolución.** El efecto evoluciona por partes (región, letra, capa) y en el tiempo. El cierre no es una tarjeta de logo estática: cierra la metáfora (termina congelado y solo el cursor queda caliente).
8. **Formas con significado.** Cada forma o pictograma representa algo del producto. No hay decoración suelta.
9. **Paleta con familia.** Una familia de tono más un acento. Meter tonos ajenos a la metáfora da un arcoíris genérico; en Chispa pasó con el azul y el menta.
10. **Producto real.** Se ve la grabación o el dato real con una cámara con intención: zoom al resultado, pausa y el resto fuera de foco. Nunca una UI inventada.
11. **El sonido también firma.** El momento firma se oye: filtro, campana, golpe o silencio.
12. **Fuera de la media de 2026.** Evita las señales de lo genérico de `skills/promo-codigo/references/aprendido.md` del plugin:
    - fondo claro plano con 2D y poco texto;
    - gradiente morado e Inter;
    - *dithering* de componente listo;
    - música «tech corporate»;
    - curvas por defecto.

## Salida del agente

`juicio.json` (formato en `agents/critico-juicio.md`):
- `veredicto_estilo`: `distinto`, `correcto pero genérico` o `clon`;
- `puntuaciones.originalidad` (con el techo de las medidas), `regla_referencia` citada de la ficha;
- hasta 5 arreglos ordenados por impacto, cada uno con el punto de la lista que incumple, la evidencia y el cambio concreto.

`cine nota --ejes ejes.json --juicio juicio.json` los junta con los arreglos medidos y da los 5 definitivos. Aplica los arreglos, rehaz solo lo afectado y enseña al usuario el antes y el después. Anota en la biblia (`criticas`) qué se cambió y por qué.
