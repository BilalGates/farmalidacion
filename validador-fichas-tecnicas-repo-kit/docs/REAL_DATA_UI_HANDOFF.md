# Vertical de visibilidad de datos reales

Rama `feat/real-data-visibility`. Documento de traspaso para el merge posterior.
No modifica `STATUS.md`, `BACKLOG.md`, `TRACEABILITY_MATRIX.md`,
`DEVELOPMENT_PLAN.md` ni `DECISION_REGISTER.md`, para no colisionar con el
trabajo paralelo de Fase 4.

## Hallazgo principal de la auditoría

Los importadores de Fase 3 estaban implementados y verificados, pero **ningún
script los ejecutaba contra una base de datos persistente**. Las únicas bases
existentes eran `data/local/validator.db` (sólo `alembic_version`, vacía) y
`data/local/demo.db` (5 registros del conjunto DEMO). Por eso la aplicación no
podía mostrar datos reales: no era un problema de interfaz, era que la carga
nunca se había ejecutado.

No se ha reconstruido la ingesta: se orquestan los importadores existentes.

## Qué se ha implementado

1. **Script de carga** que ejecuta los importadores ya existentes contra una
   base de datos real, en el orden de dependencia correcto.
2. **API de consulta read-only** bajo `/insights`, sin tocar los endpoints ni
   los servicios existentes.
3. **Interfaz**: panel de inicio con cifras reales, pantallas de Fuentes,
   Importaciones, listado de registros reales y ficha con procedencia.
4. **Separación explícita REAL / DEMO** en modelo, API e interfaz.

## Resultado de la carga real

`python scripts/ingest_master_files.py --database-url sqlite:///./data/local/real.db`
(~25 min, los libros suman más de 50 MB):

| Métrica | Valor |
|---|---|
| Registros totales | 43 381 |
| Especialidades | 29 850 |
| Principios activos | 7 189 |
| Medicamentos | 6 342 |
| Valores con procedencia | 2 169 251 |
| Campos de catálogo | 353 |
| Lotes de importación | 4, todos `completed` |
| Filas en cuarentena | 275 (especialidades, padre ausente o ambiguo) |
| Diagnósticos | 13 |

## Endpoints

Todos son `GET` y de sólo lectura. Prefijo `/insights`.

| Endpoint | Devuelve |
|---|---|
| `/insights/dashboard` | Métricas del sistema, estado por etapa, fecha de última importación, indicador `empty`. |
| `/insights/sources` | Documentos de origen con versión, hash, registros, lotes e incidencias. |
| `/insights/sources/{id}` | Lo anterior más las hojas importadas y los lotes. |
| `/insights/imports` | Lotes ejecutados con contadores por lote. |
| `/insights/imports/{id}` | Lo anterior más hojas e incidencias. |
| `/insights/records` | Listado paginado. Parámetros: `origin` (`real` por defecto, o `demo`), `q`, `entity_type`, `limit`, `offset`. |
| `/insights/records/{id}` | Ficha por bloques, con la procedencia de cada valor y las fuentes disponibles del registro. |

## Modelo utilizado

Se reutiliza el modelo físico existente sin cambios y **sin ninguna migración
nueva**:

- `TargetRecord`, `BlockInstance`, `FieldValue`, `ValueProvenance` — registros y valores.
- `SourceDocument`, `SourceDocumentVersion`, `SourceFragment`, `DocumentRecordLink` — origen y procedencia.
- `ImportBatch`, `ImportDiagnostic`, `QuarantinedSourceRow`, `ImportedSourceSheet` — importaciones.
- `CatalogFieldDefinition`, `ValidationDecisionRecord` — catálogo y decisiones.

### Cómo se distingue REAL de DEMO

Por el `source_type` del documento de origen enlazado al registro: el conjunto
de demostración usa `demo_showcase` y los maestros `master_excel`. No se añadió
ninguna columna. Un registro sin enlace documental se considera REAL, porque
clasificarlo como DEMO lo ocultaría del listado sin explicación.

Los importadores **no escriben `ExternalIdentifier`** (sólo lo hacen los
fixtures), por lo que el identificador visible del listado se toma de los campos
`*_IDEXTERNO` del propio maestro.

## Limitaciones

1. **No existe vinculación Maestro ↔ CIMA.** El modelo no almacena ninguna
   correspondencia verificada, así que la ficha muestra «Vinculación con CIMA
   pendiente» en lugar de insinuar una asociación. Para resolverlo haría falta
   decidir con qué clave se asocia un registro de maestro a un `nregistro` de
   CIMA, y esa decisión no corresponde a esta vertical.
2. **Faltan índices físicos** (ver abajo). El listado y la ficha tardan entre 2
   y 3 segundos sobre 43 381 registros por este motivo.
3. `source_version` llega vacío porque la carga se ejecutó sin `--source-version`;
   el campo existe y se muestra en cuanto se etiquete la entrega.
4. La pantalla de Importaciones es de consulta: no permite subir ficheros.
5. `processed_rows` es `None` para el importador de catálogo, que no registra
   hojas. Se muestra «—» en lugar de un cero que se leería como «no procesó nada».

## Pieza física que falta (no se ha creado la migración)

**El esquema no tiene ningún índice sobre claves ajenas.** En particular falta
uno sobre `field_value.block_instance_id`: con 2,17 millones de valores, cada
consulta de campos recorre la tabla entera (`SCAN field_value` en el plan de
ejecución).

Siguiendo la instrucción de no crear migraciones, **no se ha añadido**. Se ha
mitigado en el código: las consultas se reescribieron para recorrer esa tabla
una sola vez por petición en lugar de una vez por dato mostrado, y el filtro de
origen se pasó de `EXISTS` correlacionado a subconsulta de conjunto. El efecto:

| Endpoint | Antes | Después |
|---|---|---|
| `/insights/dashboard` | no terminaba | 0,4 s |
| `/insights/records` | 16,5 s | 2,1 s |
| `/insights/records/{id}` | 10,5 s | 2,4 s |

Índices recomendados cuando se decida abrir una migración:

```sql
CREATE INDEX ix_field_value_block_instance ON field_value (block_instance_id);
CREATE INDEX ix_block_instance_target_record ON block_instance (target_record_id);
CREATE INDEX ix_value_provenance_field_value ON value_provenance (field_value_id);
CREATE INDEX ix_document_record_link_target ON document_record_link (target_record_id);
```

Con ellos las tres pantallas deberían bajar de un segundo. La búsqueda por texto
seguiría siendo lineal: si se quiere búsqueda rápida por descripción hará falta
además un índice sobre `field_value(field_name, literal_value)` o una tabla de
búsqueda dedicada.

## Archivos

**Nuevos (backend)**
- `backend/src/pharma_validator_api/insights.py` — API de consulta.
- `backend/src/pharma_validator_api/data_origin.py` — separación REAL/DEMO.
- `backend/tests/test_insights_api.py` — 16 pruebas.
- `scripts/ingest_master_files.py` — orquestación de los importadores.

**Nuevos (frontend)**
- `src/screens/DashboardScreen.tsx`, `SourcesScreen.tsx`, `ImportsScreen.tsx`,
  `RealRecordListScreen.tsx`, `RealRecordDetailScreen.tsx`
- `src/components/AsyncState.tsx`, `src/components/OriginBadge.tsx`
- `src/api/useQuery.ts`, `src/domain/format.ts`
- `src/RealData.test.tsx` — 10 pruebas.

**Modificados**
- `backend/src/pharma_validator_api/main.py` — registra el router (2 líneas).
- `frontend/src/api/types.ts`, `client.ts` — tipos y funciones añadidos al final.
- `frontend/src/navigation.ts` — rutas `registros`, `fuentes`, `importaciones`.
- `frontend/src/App.tsx` — inicio pasa a ser el panel real; la vertical DEMO se
  mantiene íntegra en `#/fichas` bajo «Revisión (DEMO)».
- `frontend/src/styles.css` — estilos añadidos al final, con los tokens existentes.
- `frontend/src/App.test.tsx` — arranca en `#/fichas`, que es donde vive ahora la
  vertical DEMO que esas pruebas ejercitan. No se debilitó ninguna aserción.

No se ha tocado ningún archivo del extractor, GOLD, evaluación ni Fase 4.

## Verificación ejecutada

| Comprobación | Resultado |
|---|---|
| Backend, suite completa | 366 pasan, 1 omitida |
| `test_insights_api.py` | 16 pasan |
| Frontend | 17 pasan (10 nuevas) |
| Ruff | limpio |
| mypy | limpio |
| ESLint | limpio |
| `npm run build` | correcto |
| Recorrido completo sobre `real.db` | los 9 pasos del criterio de éxito |

## Cómo reproducirlo

```bash
python scripts/ingest_master_files.py --database-url sqlite:///./data/local/real.db
APP_DATABASE_URL=sqlite:///./data/local/real.db uvicorn pharma_validator_api.main:app
cd frontend && npm run dev
```

La carga tarda unos 25 minutos y es idempotente: repetirla no duplica datos,
reutiliza los lotes existentes.
