# Revisión formal de la puerta de Fase 0B

- Fecha: 2026-08-25
- Resultado: **no superada**
- Recomendación: detener avance a Fase 1.

| Criterio | Estado | Evidencia | Bloqueo restante |
|---|---|---|---|
| ADR canónico aceptado | bloqueado | ADR-0001; ADR-0006/0004 aceptados en sus alcances | ADR-0001 y ADR-0005/D-004 siguen propuestos |
| Catálogo sin colisiones ambiguas | bloqueado | DEV-006/009 | cinco identidades repetidas, dos conflictos de tipo y D-005 pendiente |
| Importación sin pérdida | cumplido | DEV-007: 22/22, 616 ocurrencias, 2.674 valores | ninguno en el fixture |
| Round-trip sin pérdida | cumplido como spike | DEV-008: 22/22, 2.674/2.674, cero diferencias | no es exportador final |
| Diferencias clasificadas | cumplido | contrato y reporte DEV-008 | cero diferencias observadas |
| Cero truncamientos/descartes | cumplido en spikes | DEV-007/008/009 | cuatro excesos requieren gobierno antes de exportar |
| Semántica interna de estados | cumplido | ADR-0004/D-010 | ninguno interno |
| Serialización externa | bloqueado | D-011 | contrato del proveedor |

## Decisiones necesarias

1. Aceptar, modificar o sustituir ADR-0001.
2. Resolver D-004/ADR-0005 sin convertir unicidad observada en clave natural.
3. Resolver D-005 con el proveedor sin reinterpretar `S*`/`N*`.
4. Resolver los conflictos `Composición/DESCRIPCION` (`CHAR(50)`/`CHAR(100)`) y `Links/DESCRIPCION` (`CHAR(100)`/`CHAR(255)`), además de identidades repetidas.
5. Obtener para D-011 la representación exacta de carga del proveedor.

No se autorizan migraciones definitivas, backend, frontend, exportador final ni integración CIMA/LLM. Cualquier excepción requiere decisión humana y ADR explícitos.
