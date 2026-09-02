# Revisión de Gate 3

- Fecha: 2 de septiembre de 2026
- Resultado: **PASS**
- Alcance: DEV-301 a DEV-308

## Criterios y evidencia

| Criterio | Evidencia | Resultado |
|---|---|---|
| Todos los ficheros en alcance se perfilan y se importan o excluyen mediante decisión documentada | DEV-002 perfiló 7/7 Excel. DEV-302 importó el catálogo; DEV-303 principio activo; DEV-304 medicamento; DEV-305 especialidad. Interacciones se excluyen del piloto por ADR-0003/DEV-306. El estudio de esfuerzo y el fixture de omeprazol son evidencia, no maestros productivos, según SOURCE_INVENTORY | PASS |
| Cada valor importado conoce procedencia y lote | DEV-301 separa lote, versión, hash, diagnóstico y cuarentena. DEV-303 conserva 35.945 valores/procedencias; DEV-304 509.496; DEV-305 1.623.810, todos con versión, fragmento y rol master_baseline | PASS |
| Los 184 posibles huérfanos quedan reproducidos y clasificados | DEV-305 conserva 275 filas completas en cuarentena, correspondientes a 184 claves, con motivo MISSING_PARENT. DEV-308 reproduce el mismo agregado | PASS |
| La segunda ejecución del mismo lote no duplica datos | Pruebas reales de DEV-302 a DEV-305 mantienen un único lote y los mismos recuentos; diagnósticos y cuarentenas también son idempotentes | PASS |
| No se normaliza ni corrige sin regla registrada | Importadores conservan literal/tipo/posición y rechazan conciliación aproximada. DEV-307 compara estado y literal exactos y no selecciona con prioridades pendientes. DEV-308 solo informa | PASS |

## Clasificación de fuentes

| Fuente | Tratamiento en Fase 3 |
|---|---|
| Catalogo_campos_clinicos_medicamentos.xlsx | Importada: 353/353 definiciones; incidencias y overrides trazables |
| PrincipioActivoCargaMaster-22062026.xlsx | Importada idempotentemente |
| Medicamento-cargaMaster25062026.xlsx | Importada idempotentemente |
| Especialidades-CargaMaster190626.xlsx | Importada; huérfanos conservados en cuarentena |
| Interacciones-cargaMaster250626.xlsx | Excluida del piloto por ADR-0003; línea INT-001..005 separada |
| Estudio carga maestros con IA.xlsx | Evidencia de fuentes, alcance y esfuerzo; no es maestro productivo |
| OMEPRAZOL 20 MGrelleno.xlsx | Fixture de referencia ya importado y comparado en Fase 0B; no es maestro productivo |

## Validación transversal

El gate completo ejecutado tras DEV-308 terminó con código 0: 93 pruebas Python, una prueba frontend, Ruff, mypy sobre 22 módulos, ESLint, build Vite, configuración Compose, 8/8 hashes de referencia y Alembic upgrade/downgrade.

El informe de calidad DEV-308 produjo dos corridas idénticas byte a byte, de 0,462 s y 0,336 s, con hash 4009cac62bb27974ee3ff15a6b863a03cbb090816e220cb2aee66da128745d48.

## Límites y riesgos conservados

- Los 275 huérfanos no se reparan; siguen en cuarentena.
- Los duplicados y las 106 claves candidatas observadas no se convierten en errores ni claves naturales.
- Las 353 prioridades concretas continúan pendientes de validación humana; el motor no elige implícitamente.
- Las hojas vacías describen la versión recibida, no cardinalidad de dominio cero.
- Interacciones continúan fuera del piloto hasta resolver INT-001..005.
- PROVIDER-001/002 y el contrato de exportación permanecen pendientes para sus fases límite.

## Decisión de avance

Gate 3 queda cerrado como PASS y Fase 3 se considera completada. Fase 4 no se inicia automáticamente.

Antes de entrar en Fase 4 deben cumplirse sus prerrequisitos explícitos: confirmar hardware GPU mediante D-013 y definir/anotar el conjunto oro. DEV-401 tampoco debe iniciarse hasta registrar esa preparación de entrada.
