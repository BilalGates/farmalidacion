# Auditoría exacta Maestro ↔ CIMA

- Fecha: 7 de septiembre de 2026
- Herramienta: `python scripts/analyze_master_cima_links.py`
- Alcance: los 29.850 CN distintos del maestro completo frente a los metadatos
  del corpus CIMA local reproducible de 500 documentos
- Regla: igualdad literal exacta; sin normalización, fuzzy matching ni escritura

## Resultados

| Medida | Resultado |
|---|---:|
| Documentos / `nregistro` CIMA | 500 |
| CN distintos en la muestra CIMA | 902 |
| CN maestro con match exacto único | 706 |
| CN maestro sin match en esta muestra | 29.144 |
| CN maestro con varios candidatos `nregistro` | 0 |
| CN CIMA sin match en maestro | 196 |
| `nregistro` con varios CN | 186 |
| Cobertura del maestro por la muestra | 2,3652 % |
| Cobertura de CN de la muestra CIMA en maestro | 78,2705 % |
| Incidencias estructurales del corpus | 0 |

La baja cobertura del maestro es esperable: se contrasta una muestra de 500
documentos, no el inventario CIMA completo. No debe interpretarse como 29.144
fallos de CIMA.

Ejemplos reproducibles de match único: CN `600136` ↔ `nregistro 66602`; CN
`600140` ↔ `62764`; CN `602421` y `602422` ↔ `68424`. El último par demuestra
que un `nregistro` puede agrupar varios CN sin que cada CN tenga varios
candidatos.

Ejemplos de `nregistro` con varios CN: `08463003` tiene `672137` y `766696`;
`1201443001` tiene 37 CN en la muestra. Ejemplos CIMA sin CN maestro: `600061`,
`600749`, `602805`. La herramienta publica diez ejemplos ordenados de cada
categoría y tiene una prueba que preserva ceros a la izquierda.

## Conclusión

Existe evidencia suficiente para diseñar posteriormente un vínculo explícito
presentación/CN ↔ autorización/`nregistro`, pero no para persistirlo todavía:
la muestra no cubre el catálogo y falta decidir vigencia, bajas y tratamiento
de CN CIMA ausentes del maestro. D-006 sigue gobernando identidades separadas.
