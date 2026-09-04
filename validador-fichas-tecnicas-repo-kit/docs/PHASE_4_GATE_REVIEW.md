# Revisión formal de la puerta de salida de Fase 4

- Fecha de la revisión: 4 de septiembre de 2026
- Fase: 4 — Extractor local y evaluación
- Veredicto global: **BLOCKED**
- Motivo del bloqueo: GOLD-002 y D-014 son decisiones humanas pendientes. Sin conjunto oro anotado no existe medición posible, y sin modelo aceptado no existe extracción real.

Este documento no cierra la Fase 4. Registra, criterio por criterio, qué está verificado y qué falta, para que el bloqueo restante quede reducido a acciones humanas concretas.

## 1. Estado de los prerrequisitos de entrada

El plan fija tres prerrequisitos antes de los trabajos de Fase 4.

| Prerrequisito | Estado | Evidencia |
|---|---|---|
| Hardware GPU confirmado | **PASS** | D-013 cerrada por aprobación humana del 2-09-2026: servidor interno con GPU de ≥24 GB de VRAM. `docs/GPU_SIZING_ANALYSIS.md` |
| Conjunto oro definido y anotado | **BLOCKED** | Definido y seleccionado (`run_id ac843f92c081045bd61ed80d6aef13c703f88275eeab433291ddb6ce9dd792cd`, 20 fichas). **No anotado**: no existe ninguna anotación real. GOLD-002 pendiente |
| Modelo de procedencia y versiones estable | **PASS** | D-020 cerrada; ADR-0001 aceptado; versiones inmutables content-addressed verificadas en Fase 2 |

La Fase 4 **no está formalmente abierta**, porque su segundo prerrequisito no se cumple.

## 2. Criterios de la puerta de salida

El plan enumera cinco criterios de salida. Se revisan uno a uno.

### C1 — Cero propuestas persistidas con evidencia literal inválida

**Estado: PASS (por construcción), pendiente de confirmación sobre ejecución real.**

La barrera existe y no es puenteable:

- `pharma_validator_api.evidence_verification` verifica por igualdad exacta sobre el texto canónico, sin desescapar ni normalizar. Contrato en `docs/EVIDENCE_VERIFICATION_CONTRACT.md`.
- `run_extraction` en `pharma_validator_api.extractor` somete **toda** propuesta al verificador antes de admitirla; un adaptador devuelve candidatas, nunca decisiones.
- Cita inventada, desplazada o desescapada se rechazan con diagnóstico; nunca se corrigen ni se recortan.
- 19 pruebas específicas de verificación más validación sobre ficha real del corpus.

Lo que **no** puede afirmarse todavía: que en una ejecución real sobre las 20 fichas el recuento sea efectivamente cero. Eso exige la ejecución, que depende de D-014. El criterio se declara PASS en su parte estructural y queda pendiente de confirmación empírica.

### C2 — Resultados publicados sobre las 20 fichas oro

**Estado: BLOCKED.**

- La **selección** de las 20 fichas está hecha, es reproducible y su `run_id` es estable: `ac843f92c081045bd61ed80d6aef13c703f88275eeab433291ddb6ce9dd792cd`. Verificado sobre el corpus real de 500 (13 pruebas).
- Las entradas de anotación están materializadas: `scripts/materialize_gold_set.py` produce `gold-selection.json` y `gold-sections.json` (552 secciones citables, 58 secciones sin contenido en las 20 fichas).
- La **anotación** no existe. Cero unidades anotadas por cero anotadores.
- Sin conjunto oro no hay verdad de referencia, y sin verdad de referencia no hay resultados que publicar.

Bloqueo humano: **GOLD-002** (identificar dos farmacéuticos) y la campaña de anotación.

### C3 — Cada campo tiene política justificada por resultados o por restricción funcional

**Estado: BLOCKED (parcialmente mitigado).**

- Las políticas por **restricción funcional** están cerradas y son verificables: D-023 prohíbe la preselección en campos interpretables o clínicos, y `pharma_validator_api.prefill_policy` la implementa. Ningún campo `proponer_opciones` o `solo_evidencia` puede aparecer preseleccionado.
- Las políticas **justificadas por resultados** no pueden fijarse: dependen de métricas que no existen. D-015 (umbrales) está pendiente por esa razón, y su ADR de esqueleto documenta exactamente qué datos faltan.

Fijar umbrales ahora sería inventar la evidencia que deberían resumir.

### C4 — Los fallos del extractor no bloquean la revisión manual con evidencia

**Estado: PASS.**

- `NullExtractor` no propone ningún valor y deja el resto de la Fase 4 ejecutable sin GPU, materializando la degradación elegante.
- Un fallo del extractor produce incidencia y no interrumpe el lote: `ExtractorError` está documentado con esa semántica.
- Campo no solicitado, duplicado o ausente producen incidencia, nunca una suposición.
- La vertical de revisión demostrable funciona con evidencia sin depender del extractor.
- Cubierto por 12 pruebas de `test_extractor.py`.

### C5 — El corpus se procesa de forma reanudable

**Estado: PASS (estructural), pendiente de ejecución real.**

- `pharma_validator_api.extraction_batches` planifica de forma reanudable: un lote interrumpido reanuda sólo lo que falta.
- La configuración (prompt, esquema, modelo) forma parte de la identidad del trabajo: cambiarla supera el trabajo anterior sin borrarlo, lo que permitirá a DEV-408 comparar dos tamaños sobre el mismo corpus sin pisar la primera ejecución.
- 17 pruebas. Contrato en `docs/EXTRACTION_BATCH_CONTRACT.md`.

Falta la confirmación sobre una ejecución real, que depende de D-014.

## 3. Trabajos de Fase 4, uno a uno

| Trabajo | Issue | Estado | Evidencia |
|---|---|---|---|
| Interfaz `ExtractorLLM` desacoplada | DEV-401 | **PASS** | 12 pruebas; `docs/EXTRACTOR_INTERFACE_CONTRACT.md` |
| Servidor local compatible con OpenAI chat | DEV-402 | **BLOCKED** | Contrato de transporte agnóstico implementado (`inference_backend`, 11 pruebas). El cliente real exige modelo aceptado: D-014 |
| Salida guiada por esquema | DEV-403 | **PASS** | 22 pruebas; `docs/GUIDED_SCHEMA_CONTRACT.md`. La traducción a GBNF depende del runtime de D-014 |
| Llamadas agrupadas por sección | DEV-404 | **PASS** | 17 pruebas; validado sobre catálogo real (353 definiciones, 129 campos extraíbles, 14 llamadas) |
| Verificación literal antes de persistir | DEV-405 | **PASS** | 19 pruebas; `docs/EVIDENCE_VERIFICATION_CONTRACT.md` |
| Reanudación de lotes y versionado | DEV-406 | **PASS** | 17 pruebas; `docs/EXTRACTION_BATCH_CONTRACT.md` |
| Herramienta de anotación del conjunto oro | DEV-407 | **BLOCKED** | Selección, herramienta, completitud y pipeline listos. Falta la anotación humana: GOLD-002 |
| Comparación de al menos dos tamaños de modelo | DEV-408 | **BLOCKED** | Motor de evaluación implementado (`gold_evaluation`, 13 pruebas). Faltan gold y modelos: GOLD-002 + D-014 |
| Métricas por campo, política, entidad y sección | DEV-408 | **BLOCKED** | Calculadas por `gold_evaluation`; sin datos que alimentarlas |
| Degradación configurable a `solo_evidencia` | DEV-409 | **BLOCKED** | Mecanismo disponible en `prefill_policy`; los umbrales son D-015 |

## 4. Criterios transversales no negociables

Se revisan porque su incumplimiento invalidaría el gate con independencia de las métricas.

| Regla | Estado | Evidencia |
|---|---|---|
| Nunca se procesan datos de paciente | **PASS** | D-022; el corpus son fichas técnicas públicas de CIMA |
| Nunca se emite recomendación clínica | **PASS** | El extractor transcribe y localiza; no interpreta |
| Nunca se preselecciona `proponer_opciones` / `solo_evidencia` | **PASS** | D-023; `prefill_policy` con pruebas |
| Ninguna propuesta se persiste sin procedencia verificable | **PASS** | C1; `run_extraction` no admite sin verificar |
| No se infiere, convierte ni normaliza sin regla aprobada | **PASS** | El verificador exige igualdad exacta; la normalización sólo existe como métrica secundaria informada aparte |
| Los bloques repetibles se modelan como ocurrencias | **PASS** | La unidad de anotación incluye ordinal obligatorio; concatenar invalida |
| Versiones inmutables enlazadas a cada propuesta | **PASS** | D-020; anclaje por `content_hash` |
| Nada se trunca ni descarta en silencio | **PASS** | Toda anomalía produce diagnóstico |

## 5. Resumen del veredicto

| Criterio | Veredicto |
|---|---|
| C1 — Cero evidencia literal inválida persistida | PASS (estructural) |
| C2 — Resultados publicados sobre las 20 fichas oro | **BLOCKED** |
| C3 — Política justificada por campo | **BLOCKED** |
| C4 — Los fallos no bloquean la revisión manual | PASS |
| C5 — Corpus reanudable | PASS (estructural) |
| Prerrequisito — GPU | PASS |
| Prerrequisito — Conjunto oro anotado | **BLOCKED** |
| Prerrequisito — Procedencia y versiones | PASS |

**Gate 4: BLOCKED.** No se cierra la Fase 4 y no se abre la Fase 5.

## 6. Bloqueos humanos, con acción mínima que los desbloquea

| # | Bloqueo | Quién decide | Evidencia ya disponible | Acción que desbloquea |
|---|---|---|---|---|
| 1 | **GOLD-002**: identidad de los dos farmacéuticos anotadores | Responsable funcional / farmacia | Contrato de anotación, selección reproducible de 20 fichas, herramienta, comprobador de completitud, runbook operativo | Nombrar dos personas y registrarlas en `APP_REVIEWERS`. Los valores actuales del `.env.example` son marcadores, no personas |
| 2 | **Campaña de anotación** de las 20 fichas por ambos | Los dos farmacéuticos | Runbook `docs/GOLD_ANNOTATION_RUNBOOK.md`; entradas materializadas; `check_gold.py` mide progreso | Ejecutar la anotación independiente y la conciliación |
| 3 | **D-014**: modelo y servidor de inferencia | Responsable funcional con criterio técnico | ADR-0008 con 3 candidatos comparados y recomendación argumentada | Aceptar una opción del ADR |
| 4 | **D-015**: umbrales de `proponer_valor` y degradación | Responsable funcional / farmacia | ADR-0009 con el método de cálculo definido; faltan los datos | Aceptar tras publicar métricas del gold |

Los bloqueos 1 y 3 son independientes entre sí y pueden resolverse en paralelo. El 2 depende del 1; el 4 depende del 2 y del 3.

## 7. Qué está listo para ejecutarse el día que se desbloquee

Toda la cadena posterior está construida y probada con entradas sintéticas:

```
anotaciones → verificación → comparación/conciliación → gold final
            → extractor → evaluación → métricas → Gate 4
```

- `scripts/materialize_gold_set.py` — entradas de anotación (ejecutado, verificado).
- `scripts/check_gold.py` — completitud y consistencia estructural; código de salida 1 si no está listo.
- `scripts/generate_gold_annotations.py` — los cinco artefactos contractuales.
- `scripts/run_gold_pipeline.py` — orquesta la secuencia completa y se detiene si el gold no está cerrado.
- `pharma_validator_api.gold_evaluation` — métricas exigidas por el plan.
- `pharma_validator_api.inference_backend` — transporte agnóstico al modelo.

Ninguna de estas piezas elige modelo, inventa anotadores ni fija umbrales.
