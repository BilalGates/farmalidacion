# Contrato de procesamiento reanudable por lotes

- Issue: DEV-406
- Fase: 4
- Estado: implementado
- Módulo: `pharma_validator_api.extraction_batches`
- Versión del planificador: `extraction-batch-v1`
- Base normativa: plan de desarrollo, Fase 4 («reanudación de lotes, control de versiones de prompt/modelo y observabilidad»; «el corpus se procesa de forma reanudable»)

## Alcance

Decide qué unidades de una extracción quedan pendientes y cuáles se conservan de una ejecución anterior. Es un planificador puro: no abre sockets, no llama al modelo y no persiste. Quien ejecute el plan aporta el estado ya completado.

El volumen del piloto son 500 documentos por unas 15 llamadas: unas 7.500 peticiones, una noche de proceso. Reiniciar desde cero por una interrupción es inaceptable, y por eso la reanudación es puerta de salida de Fase 4 y no una comodidad.

## Unidad de trabajo

La unidad reanudable es una llamada: versión documental, apartado y conjunto de campos solicitados. Su clave es el SHA-256 de esa identidad.

El orden de los campos no cambia la clave —se ordenan antes de calcularla—, pero **el conjunto sí**: pedir `POSOLOGIA` sola y pedir `POSOLOGIA` junto a `VIA` son unidades distintas, porque la respuesta del modelo depende de qué se le preguntó en la misma llamada.

## La configuración forma parte de la identidad

La huella de configuración cubre versión del planificador, versión del extractor, modelo, versión de prompt y versión de esquema. Un cambio en cualquiera de ellos produce propuestas distintas.

Una unidad completada **solo se reutiliza si se resolvió con la misma huella**. Al cambiar de modelo, de prompt o de esquema, el trabajo anterior no se invalida ni se borra: se marca como *superado* y la unidad se vuelve a planificar. Esto es lo que permite que DEV-408 compare dos tamaños de modelo sobre el mismo corpus sin que la segunda ejecución pise los resultados de la primera.

## Estados y decisiones

| Situación | Decisión |
|---|---|
| unidad no vista antes | pendiente |
| completada con la misma huella | reutilizada, no se repite |
| completada con otra huella | superada y replanificada |
| incidencia con la misma huella | reintentada por defecto |
| incidencia con reintento desactivado | reutilizada tal cual |
| estado de otro lote o agrupación anterior | ignorado y no tocado |

El reintento de incidencias es configurable porque una incidencia puede ser transitoria —un fallo del servidor local— o estable —una sección sin texto verificable—. Reintentar siempre desperdiciaría la noche de proceso; no reintentar nunca ocultaría un fallo pasajero. La decisión es de quien opera el lote, no del planificador.

## Orden de proceso

Las unidades pendientes se ordenan por versión documental y apartado en orden numérico, no por el hash de la clave. Un lote de 7.500 peticiones debe ser legible mientras avanza: con orden por hash, el avance parece aleatorio y no se puede estimar cuánto queda.

El orden numérico se comparte con DEV-404 (`section_sort_key`), de modo que la agrupación y la planificación presenten los apartados igual: `4.2` antes que `5.1`, y `2` antes que `10`.

## Errores de uso frente a fallos de unidad

Se distinguen dos cosas que no deben confundirse:

- **Fallo de unidad**: el extractor no responde o la propuesta se rechaza. Es esperable, se registra y no interrumpe el lote.
- **Error de uso**: dos peticiones producen la misma unidad, o el estado trae una clave repetida. Indica una agrupación mal construida o un estado corrupto, y se detiene de forma explícita en lugar de continuar con un plan ambiguo.

## Verificación realizada

- 17 pruebas: reanudación parcial de un lote interrumpido, reutilización con la misma configuración, supersesión al cambiar modelo, prompt o esquema, reintento de incidencias configurable, estado ajeno ignorado, clave sensible al conjunto de campos e insensible a su orden, huella estable, errores de uso y determinismo.
- Ruff y mypy estricto sin incidencias en 27 ficheros.

## Límites

- No persiste el estado ni define su tabla: recibe las unidades completadas.
- No ejecuta las peticiones: eso es DEV-402 con el adaptador real.
- No mide observabilidad más allá de los recuentos del plan.
- No decide si una incidencia es transitoria o estable: expone la opción de reintento.
