# ADR-0018 — Nomenclátor como fuente persistente y versionada

- Estado: propuesto (la parte técnica ya implementada es reversible; el enriquecimiento queda bloqueado)
- Fecha: 2026-10-26
- Decisiones relacionadas: D-034, D-035
- Responsables: producto / farmacia / tecnología

## Contexto

«Mi Nomenclátor» ya guardaba en el servidor cada copia de `dbo.nomenclatur`
(TSV de 73 columnas, nombre por SHA-256, un directorio por cuenta) y registraba
cada sincronización en `nomenclator_user_snapshot`, tabla append-only. La
interfaz, sin embargo, mezclaba «hay datos» con «el conector está abierto», no
mostraba el historial ni los cambios entre versiones y no permitía consultar el
contenido. La sincronización real del 2026-10 dejó 35.228 filas con fecha de
origen 2026-10-01.

## Restricciones

- La base SQL Server original no se modifica: sólo `SELECT` sobre `dbo.nomenclatur`, con `ApplicationIntent=ReadOnly`.
- No se procesan datos de pacientes ni se toman decisiones clínicas.
- No se reemplaza la identidad canónica ni se sobrescriben valores de CIMA o del maestro.
- No se deduplican filas sin una regla aceptada; un CN repetido invalida la copia entera.

## Opciones consideradas

### A. Sincronización incremental

Requiere una marca de cambio fiable en la fuente. `FECHA_ACTUALIZACIÓN` existe,
pero no hay evidencia de que se actualice en cada modificación ni de cómo se
reflejan las bajas. Se descarta mientras no haya esa evidencia.

### B. Instantánea completa versionada con comparación verificable (elegida)

Cada sincronización lee la tabla completa, se valida (73 columnas, CN de 6
dígitos únicos, UTF-8, hash) y sólo después se registra como versión vigente.
Las versiones anteriores se conservan. Los cambios se calculan comparando por CN
las 73 celdas literales de dos versiones.

### C. Cargar las filas en tablas relacionales

Facilita las consultas, pero implica una migración y un modelo de columnas que
todavía no está aprobado (D-034). Se pospone.

## Decisión propuesta

Opción B. El conector sólo hace falta para importar; toda consulta usa la copia
persistida. Las correspondencias con el catálogo se calculan **sólo** por
igualdad exacta de CN con presentaciones activas: una identidad = exacta; varias
= ambigua; ninguna = sin correspondencia. No se usan nombres ni similitud
textual, y nada se consolida.

## Consecuencias

### Positivas

- Se puede trabajar con el conector cerrado y el navegador reiniciado.
- Una importación fallida o interrumpida no modifica la versión vigente.
- Historial y cambios auditables por cuenta, aislados en el backend.

### Negativas

- Cada sincronización transfiere la tabla completa (unos 35.000 registros).
- Las consultas recorren la copia en memoria (caché de 4 versiones).

### Riesgos

- Si un fichero de versión desaparece del disco, la API responde 503 en lugar de usar otra versión sin avisar.

## Validación

`backend/tests/test_nomenclator_api.py` y `backend/tests/test_nomenclator_local_connector.py`:
versionado, cambios, fallo de importación, aislamiento, correspondencias,
volumen de 35.228 filas, origen no autorizado y cierre del conector.

## Migración y reversibilidad

No hay migración de esquema. Los endpoints nuevos son de lectura y pueden
retirarse sin afectar a los datos.

## Preguntas pendientes

- D-035: qué campos de Nomenclátor pueden mostrarse como enriquecimiento del catálogo (filtros, búsqueda) y con qué prioridad frente a CIMA y el maestro.
- D-034: clave de reconciliación más allá del CN (n.º de registro, DCP/DCSA) y su estabilidad entre versiones.
