# Contrato de anotación del conjunto oro

- Issue: DEV-407
- Fase: 4 (prerrequisito de entrada)
- Estado: contrato definido; herramienta no implementada
- Algoritmo de selección: `gold-selection-v1`
- Formato de anotación: `gold-annotation-v1`

## Propósito y no-propósito

Este contrato fija cómo se selecciona, anota y verifica el conjunto oro de 20 fichas técnicas que mide el extractor en la Fase 4. La anotación es la verdad de referencia contra la que se calculan precisión, cobertura, evidencia válida, falsos positivos y falsos negativos por campo.

El conjunto oro **no** es un maestro consolidado, no alimenta la exportación, no resuelve conflictos de procedencia y no sustituye la validación farmacéutica del piloto. Una anotación es una observación humana sobre una versión documental concreta, no una decisión de dominio reutilizable.

No se anota ningún dato de paciente y no se emite ninguna recomendación clínica. El anotador transcribe y localiza lo que la ficha dice; no interpreta lo que debería decir.

## Selección reproducible de las 20 fichas

El conjunto oro se extrae del corpus ya capturado en DEV-208, no de una nueva descarga:

- inventario `cima-inventory-20260828`, instantánea `72e9b05fd60a524fa9115c09fee9f29e98779a8c5c95565fe6d0bee4395c27cb`;
- corpus `cima-corpus-random-203`, manifiesto `34d2216d09150bb07615fada4adc4ea45f7a35cbb7b96c011fa689d6d6759fb3`;
- universo elegible: los 500 `nregistro` de la muestra aleatoria con semilla 203, cuyo SHA-256 es `ebeb1f8c3823c5cd206bf3044f9f9adef194ed93d23048806268309b9fee8929`.

La selección de 20 reutiliza el modo aleatorio de `cima-sampling-v1` (DEV-203) sobre ese universo, ordenando primero por `nregistro` y aplicando `random.Random(seed).sample`. GOLD-001 fija la semilla del conjunto oro en `407` por decisión humana.

No se estratifica por ATC. GOLD-003 cierra esta decisión para el conjunto oro inicial porque las 16.093 filas del inventario carecen de ATC según DEV-208 y elegir estratos por otra vía exigiría inferir un dato ausente. Solo nueva evidencia versionada permitiría reevaluarlo.

La ejecución se identifica por SHA-256 de versión del algoritmo, modo, semilla, tamaño 20 y hash del universo de entrada. Repetir la misma ejecución produce exactamente los mismos 20 `nregistro`; una diferencia detiene el proceso con conflicto en lugar de reescribir la selección.

## Unidad de anotación

La unidad es la tupla `(nregistro, versión documental, entidad, bloque, ordinal de ocurrencia, campo)`.

El ordinal es obligatorio y explícito. Los bloques repetibles —composiciones, indicaciones, vías, frecuencias, excipientes, enlaces, consejos, datos analíticos, poblaciones— se anotan como ocurrencias numeradas. Concatenar varias ocurrencias en un valor invalida la anotación; una ficha con tres vías produce tres unidades, no una.

Cada anotación se ancla a una `source_document_version` concreta por `content_hash`. Una anotación nunca es válida "para la ficha"; lo es para la versión que se anotó. Si la versión cambia, la anotación anterior se conserva y la nueva se anota aparte.

## Evidencia literal

La evidencia es el punto crítico del contrato, porque la puerta de salida de Fase 4 exige cero propuestas persistidas con evidencia literal inválida y esa comprobación se calibra aquí.

Los artefactos de ficha técnica del corpus son listas de secciones con `seccion`, `titulo`, `contenido` y `orden`, donde `contenido` es **HTML**, no texto plano. Por tanto se fija:

- la cadena canónica de evidencia es el valor literal de `contenido` de la sección citada, **tal cual se almacenó**, sin desescapar entidades, sin normalizar espacios y sin extraer texto;
- la evidencia se cita como un intervalo de desplazamientos `[inicio, fin)` en unidades de punto de código sobre esa cadena canónica, más el texto literal recortado;
- la verificación es igualdad exacta entre el texto citado y la subcadena de la versión inmutable en ese intervalo;
- la evidencia se materializa como `SourceFragment` con `locator_type` propio del conjunto oro y `locator` que identifica sección y desplazamientos, con `literal_text` conservado.

Anotar sobre una proyección legible del HTML está permitido como ayuda de lectura, pero los desplazamientos que se persisten son siempre los de la cadena canónica. Ninguna herramienta puede guardar una evidencia cuyos desplazamientos no reproduzcan exactamente el texto citado.

Un intervalo puede empezar o terminar dentro de una entidad HTML o de una etiqueta, porque la cadena canónica conserva `&#243;`, `&#xa0;` y el marcado tal cual. Ese recorte no se corrige, no se expande hasta un límite "limpio" y no se reescribe: expandirlo cambiaría el literal citado. La herramienta advierte al anotador de que el intervalo parte una entidad o una etiqueta y le pide confirmar o reajustar la selección; lo que se persiste es siempre lo que el anotador confirmó, verificado por igualdad exacta.

Un valor sin evidencia localizable no se anota como valor. Se anota con el estado que corresponda según la tabla siguiente.

## Estados admitidos

Los estados de anotación son los ya validados en DEV-011 y no se inventan nuevos:

| Estado | Cuándo lo usa el anotador | Evidencia |
|---|---|---|
| `valued` | la ficha contiene el dato y puede localizarse | obligatoria y exacta |
| `source_absent` | la sección o el fragmento no existe en esta versión | no aplica |
| `source_blank` | la posición existe pero está vacía | localiza la posición |
| `no_consta` | revisadas las fuentes obligatorias configuradas, el dato no aparece | motivo obligatorio |
| `not_applicable` | el campo o bloque no corresponde semánticamente al medicamento | comentario obligatorio |

`pending` no es un estado de anotación terminada: una unidad en `pending` significa conjunto oro incompleto y bloquea su cierre.

Ausencia y vacío nunca se convierten automáticamente en `no_consta` ni en `not_applicable`. Esa conversión exige decisión humana registrada, en coherencia con la regla 1 de DEV-011.

## Doble anotación y desacuerdo

Cada unidad se anota de forma independiente por dos anotadores farmacéuticos, sin ver la anotación del otro. La comparación es exacta sobre el par (estado lógico, valor literal), con el mismo criterio del motor de DEV-307: espacios y mayúsculas diferencian, y `no_consta`/`not_applicable` no se colapsan entre sí ni con vacío.

Un desacuerdo no se resuelve por mayoría, por antigüedad ni automáticamente. Se registra como desacuerdo abierto, se concilia en una sesión identificada y la resolución conserva ambas anotaciones originales, el actor, el instante y el motivo. Una unidad con desacuerdo sin conciliar no entra en el cálculo de métricas y se informa aparte.

La tasa de acuerdo entre anotadores se publica junto con las métricas del extractor. Es el techo interpretativo de los resultados: ningún campo puede exigirse al modelo por encima de la concordancia humana observada en ese campo.

## Salidas

La herramienta produce, bajo un directorio de ejecución que no sobrescribe uno existente:

- `gold-selection.json`: semilla, algoritmo, hash del universo, los 20 `nregistro` con ordinal y hash de identidad de la ejecución;
- `gold-annotations.jsonl`: una unidad por línea, con identidad completa, estado, valor literal, evidencia citada, anotador, instante y comentario cuando es obligatorio;
- `gold-disagreements.csv`: unidades con desacuerdo, ambas anotaciones y estado de conciliación;
- `run-manifest.json`: hashes de entradas y salidas, versión de la herramienta y recuentos;
- `summary.md`: recuentos por estado, campo y anotador, y tasa de acuerdo.

Dos ejecuciones sobre las mismas anotaciones producen ficheros idénticos byte a byte. El resumen no incluye texto clínico más allá de la evidencia estrictamente citada.

## Aceptación de DEV-407

1. La selección de 20 es reproducible desde el universo de 500 y su hash de ejecución es estable.
2. Toda unidad `valued` tiene evidencia cuyos desplazamientos reproducen exactamente el texto citado sobre la versión inmutable.
3. Ninguna evidencia se valida contra texto desescapado o normalizado.
4. Los bloques repetibles conservan ocurrencias numeradas sin concatenación.
5. Ausencia, vacío, `no_consta` y `not_applicable` permanecen distinguibles.
6. Las unidades en `pending` bloquean el cierre del conjunto oro.
7. Los desacuerdos se conservan y no se resuelven automáticamente.
8. Dos ejecuciones producen salidas idénticas byte a byte.
9. No se descarga nada nuevo de CIMA ni se modifica el corpus existente.

## Dependencias y decisiones abiertas

- La selección depende del corpus de DEV-208 y del muestreo de DEV-203; no introduce fuente nueva.
- El alcance exacto de campos a anotar depende del catálogo importado en DEV-302 y se fija al abrir DEV-407 como implementación.
- GOLD-001: cerrada con semilla reproducible `407` por aprobación humana del 2 de septiembre de 2026.
- GOLD-002: identidad de los dos anotadores farmacéuticos y su disponibilidad, pendiente.
- GOLD-003: cerrada sin estratificación ATC para el conjunto oro inicial, porque DEV-208 no contiene ese atributo. No se infiere ATC; la decisión solo se revisará si aparece nueva evidencia versionada.
- D-013 no bloquea este contrato: seleccionar y anotar no requiere GPU.
