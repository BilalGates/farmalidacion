# Análisis de dimensionado de hardware de inferencia (D-013)

- Decisión: D-013 — Hardware GPU
- Fase: 4 (prerrequisito de entrada)
- Estado: decisión humana aceptada el 2 de septiembre de 2026
- Fuente base: especificación v2, sección de inferencia local

Este documento registra el criterio aceptado para D-013: la inferencia se ejecutará en un servidor interno con una GPU de al menos 24 GB de VRAM. La elección del modelo, runtime y servidor concretos sigue abierta bajo D-014 hasta disponer del benchmark.

## Restricciones no negociables

- **Sin salida a internet.** Toda la inferencia se ejecuta dentro de la red del centro. Esto excluye API externas y obliga a hardware propio o alojado en el centro.
- El modelo se expone por API compatible con OpenAI-chat tras la interfaz `ExtractorLLM`, de modo que el motor sea sustituible sin tocar el resto del código.
- La salida es guiada por esquema (guided decoding en vLLM, gramáticas GBNF en llama.cpp). No se confía en pedir JSON por prompt.
- La Fase 4 exige comparar **al menos dos tamaños de modelo** sobre el conjunto oro. El hardware debe permitir esa comparación, no solo ejecutar el modelo final.

## Dimensionado orientativo de la especificación

| VRAM | Encaja cómodamente | Comentario de la especificación |
|---|---|---|
| 24 GB | 7–14B sin cuantizar, ~30B cuantizado a 4 bits | Suficiente para el piloto |
| 48 GB | ~30B holgado | Margen para probar modelos mayores |
| 2 × 48 GB | 70B cuantizado | Solo si el hito 2 demuestra que hace falta |

La especificación marca estas cifras como orientativas y **a confirmar midiendo**. Ese es precisamente el trabajo del hito 2.

## Volumen y rendimiento

Volumen del piloto declarado en la especificación: 500 documentos × ~15 llamadas ≈ **7.500 peticiones**. Con unos pocos segundos por petición, el corpus completo se procesa en una noche incluso en la configuración más modesta.

La conclusión de la especificación es explícita y conviene no perderla de vista al comprar hardware: **el rendimiento no es el problema; la precisión sí.** Sobredimensionar por velocidad no compra nada que el piloto necesite; el criterio de compra es qué tamaños de modelo permite comparar.

El conjunto oro son 20 fichas, no 500. La medición del hito 2 es, por tanto, mucho más barata que la pasada completa del corpus: cabe repetirla varias veces por modelo sin coste de tiempo relevante.

## Lectura para la decisión

Lo que el análisis sí permite afirmar:

- 24 GB es el suelo que la especificación considera suficiente para el piloto, y ya permite comparar dos tamaños (por ejemplo 7–14B sin cuantizar frente a ~30B en 4 bits). Cumple el requisito del hito 2 sin margen de sobra.
- 48 GB no acelera la decisión, pero amplía el espacio de comparación y evita que la cuantización sea una variable confundida en la medida: en 24 GB, el modelo grande solo entra cuantizado, de modo que la comparación mezcla tamaño y cuantización.
- 2 × 48 GB no está justificado antes de tener resultados. La especificación lo condiciona a que el hito 2 demuestre que hace falta.

Lo que **no** puede decidirse midiendo antes de tener hardware: cuál es el tamaño mínimo que alcanza el listón por campo. Esa es la salida del hito 2, no su entrada. Por eso D-013 debe cerrarse con un criterio de suficiencia para *comparar*, no de suficiencia para *acertar*.

## Elección de motor

Para el piloto, la especificación prioriza simplicidad de operación sobre rendimiento máximo:

- **vLLM**: mejor rendimiento por lotes, guided decoding nativo. Más exigente de operar.
- **llama.cpp / Ollama**: más simples de operar, gramáticas GBNF para la salida guiada.

Ambos quedan tras `ExtractorLLM`, así que la elección es reversible y no bloquea DEV-401. No requiere ADR propio salvo que se aparte de estas opciones.

## Decisión aceptada y trabajo pendiente

1. Provisionar o confirmar el servidor interno con al menos 24 GB de VRAM; compra y reutilización son opciones operativas equivalentes si cumplen el límite de red.
2. Declarar bajo D-014 los dos modelos candidatos, el runtime y si la comparación incluye cuantización como variable separada.
3. Ejecutar DEV-408 sobre el mismo conjunto oro anotado y conservar configuración, versiones y resultados.

D-013 está cerrada. DEV-401, DEV-403, DEV-405 y el contrato de DEV-407 no requieren acceso inmediato a la GPU. DEV-402 y DEV-408 sí requieren el servidor interno disponible y D-014 solo puede cerrarse tras comparar los modelos previstos.
