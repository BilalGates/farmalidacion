# Contrato de importación del maestro de medicamento

- Issue: DEV-304
- Fase: 3
- Estado: implementado
- Fuente: `Medicamento-cargaMaster25062026.xlsx`
- SHA-256: `4b87aeac96ea220126c090d755fa5bfbaabe7aec304cfccb2e15537bd96cbf1b`

## Alcance reproducible

El importador exige y registra las hojas `General`, `Composicion`, `Indicacion`, `Frecuencia`, `Via`, `Prescripcion` y `Links` en ese orden. Cada hoja conserva ordinal, cabecera con tipos OOXML reales, filas y valores materiales.

| Hoja | Filas de datos | Valores materiales |
|---|---:|---:|
| General | 6.342 | 215.079 |
| Composicion | 4.211 | 33.688 |
| Indicacion | 19.766 | 98.830 |
| Frecuencia | 0 | 0 |
| Via | 5.723 | 28.615 |
| Prescripcion | 0 | 0 |
| Links | 22.214 | 133.284 |
| **Total** | **58.256** | **509.496** |

`Frecuencia` y `Prescripcion` generan `EMPTY_SOURCE_SHEET` informativo. La ausencia de filas describe esta versión y no decide la cardinalidad del dominio.

## Representación canónica

Cada fila de `General` crea un `target_record` de tipo `medication`, una ocurrencia `medication_general` y sus valores con procedencia. Cada fila hija crea una ocurrencia explícita del bloque correspondiente sobre su medicamento padre.

El vínculo padre se acepta solo cuando `MED_IDEXTERNO` coincide literalmente con una única fila general de esta versión. Una referencia ausente o ambigua se conserva en cuarentena; nunca se resuelve por texto, ATC, forma farmacéutica o similitud.

Cada valor conserva tipo OOXML y literal, y apunta a un fragmento de la versión exacta con hoja, fila y payload completo. Los vacíos materiales usan estado `empty`, distinto de `no_consta` y `no_aplica`.

## Bloques repetibles y duplicados

`Composicion`, `Indicacion`, `Via` y `Links` se importan fila a fila con ordinal por medicamento y hoja. No se concatenan ni deduplican ocurrencias.

La hoja `Links` contiene dos cabeceras literales `DESCRIPCION`. Ambas celdas se conservan con su columna en el payload y como dos valores de la misma ocurrencia; no se renombra ni descarta ninguna. Los duplicados de fila observados en DEV-002 tampoco se califican automáticamente como error.

## Relación con principio activo

Cada fila de `Composicion` intenta resolver `PA_IDEXTERNO` contra el `IDEXTERNO` literal de los registros importados por DEV-303. Solo una coincidencia exacta y única crea `composition_active_ingredient`.

En la versión actual se crean 4.211 vínculos y no aparecen referencias ausentes o ambiguas. El vínculo conserva el fragmento de la fila de composición y no fusiona identidades canónicas.

## Idempotencia, rendimiento y no pérdida

El lote usa localizador, versión literal opcional, SHA-256 e importador `medication_master` versión `1.0.0`. Las inserciones se agrupan en lotes técnicos de 500 ocurrencias sin reducir detalle ni cambiar orden semántico.

Dos ejecuciones producen un lote, 6.342 medicamentos, 58.256 ocurrencias, 509.496 valores, 509.496 procedencias y 4.211 vínculos. Hay dos diagnósticos informativos y cero cuarentenas. La prueba real, incluida la carga previa de DEV-303, terminó en 208,47 segundos.

No se convierten tipos, truncan textos, corrigen valores ni aplican contratos de exportación. El original permanece fuera de Git e inalterado. DEV-304 no añade una migración: reutiliza el núcleo canónico y el registro genérico de hojas ya reversible.

## Fuera de alcance

DEV-304 no importa especialidades, no consolida CIMA, no decide prioridades, no interpreta valores clínicos, no completa hojas vacías y no inicia el motor general de conflictos.
