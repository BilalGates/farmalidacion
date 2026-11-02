# Diseño: Novedades CIMA accionables — fase 1

- Estado: **diseño cerrado** (Steve, 2026-10-30). Decisiones del usuario recogidas en ADR-0019 (aceptado) y D-040.
- Ámbito: estado, comercialización, bajas y altas. Ficha técnica queda para fase 2 (§12).
- Se apoya en: DEV-703 (`maintenance_change_event`, `maintenance_change_event_target`), D-027/ADR-0011 (vínculo CIMA solo por CN literal exacto y único en ambos lados), D-031/ADR-0012 (archivar en vez de borrar; revisiones append-only), ADR-0015 (permisos por operación), D-023 (sin preselección), regla de procedencia y de no normalizar.

## 0. Hallazgo que condiciona el diseño (leer primero)

Los Excel maestros **no tienen ninguna columna de estado de autorización ni de comercialización CIMA**. Comprobado en la cabecera importada (`imported_source_sheet.header_payload`, `real-preview.db`):

| Maestro | Hoja | Columnas relacionadas | Qué son |
|---|---|---|---|
| Especialidades | `General` | `CODIGO_NACIONAL`, `ACTIVO` (CHAR(1)), `DISPONIBLE_*`, `PERMITE_COMPRAR` | `ACTIVO` está catalogado en `catalog_field_definition` como *"Identificador interno o de vuestros maestros: fuera del alcance de una ficha técnica"*. `DISPONIBLE_*` es disponibilidad hospitalaria, no comercialización AEMPS. |
| Medicamentos | `General` | `ACTIVO` | Igual: flag interno. |
| Principios activos | `General` | `ACTIVO` | Igual. |

Resolución (ADR-0019, aceptado):

1. **Baja (`tipoCambio=2`) o revocación (`estado.rev` presente en la respuesta CIMA capturada)** → acción `proponer_activo_n` con `proposed_value="N"` para `ACTIVO` (Especialidades `General`, del registro enlazado por CN exacto), `rule_id="ADR-0019:baja-revocacion-activo:v1"`. Es propuesta: no se aplica sola ni se preselecciona.
2. **Cualquier otro cambio de estado o comercialización** → "Revisar en CIMA" sin valor propuesto (`diagnostic_code=sin_correspondencia`).
3. Además, la baja mantiene "Revisar si se archiva" sobre `medication_catalog_identity.active` (D-031), que no toca el Excel.

## 1. Decisión

Se añade una capa **derivada, determinista e idempotente** de *acciones de mantenimiento* encima de los eventos inmutables ya guardados: cada evento con destino en el catálogo genera 0..N acciones (`maintenance_action`), cada una con valor del maestro, valor CIMA y puntero a una **respuesta CIMA capturada como versión inmutable**. Las decisiones humanas van en una tabla append-only aparte (`maintenance_action_decision`). Nada modifica el catálogo salvo la aceptación explícita de "archivar", que reutiliza el camino de edición existente.

Alternativa descartada: añadir columnas de estado/acción a `maintenance_change_event`. El evento es inmutable (listener `_reject_historical_mutation`) y representa el aviso de CIMA, no la valoración; mezclarlo rompería la idempotencia y el historial.

## 2. Datos

### 2.1 Respuestas CIMA como versión inmutable

Valores de estado/comercialización salen de dos endpoints ya implementados en `cima_client.py`, con caché (`ResponseCache`, clave por URL+accept):

| Valor | Endpoint | Método | Puntero JSON |
|---|---|---|---|
| Estado del registro | `medicamento?nregistro=` | `CimaClient.medication(nregistro=…)` | `/estado/aut`, `/estado/susp`, `/estado/rev` (epoch ms, literales) |
| Comercialización del registro | idem | idem | `/comerc` |
| Estado y comercialización por CN | `presentacion?cn=` | `CimaClient.presentation(cn=…)` | `/estado/*`, `/comerc` |
| Presentaciones de un alta | `presentaciones?nregistro=` | `CimaClient.presentations(nregistro=…)` | `/resultados/i/cn`, `/resultados/i/nombre` |

Cada respuesta usada como procedencia se persiste con un helper nuevo en `document_versions.py`:

```python
def persist_cima_api_response(
    session: Session, *, endpoint: Literal["medicamento", "presentacion", "presentaciones"],
    key: str,                 # nregistro o CN literal
    response: CimaResponse,   # body, content_sha256, fetched_at, url, cabeceras
    commit: bool = False,
) -> PersistedDocumentVersion
```

- `SourceDocument(source_type=f"cima_api_{endpoint}", name=key)`; `SourceDocumentVersion` por `content_hash` (si el hash ya existe, se devuelve la versión existente: idempotente); `SourceDocumentArtifact` con el cuerpo literal y cabeceras. Reutiliza `_validate_artifacts`/`_package_hash`; no se crea tabla nueva.
- La caché del cliente evita repetir peticiones dentro de la pasada; la versión persistida es la que se cita. **Si CIMA no responde, no se crea la acción con valor**: se crea con `diagnostic_code="cima_no_disponible"` y `cima_version_id NULL`, y la UI la muestra como "Pendiente de consultar CIMA" (no accionable hasta reintento).

### 2.2 Tablas nuevas (migración aditiva)

Fichero: `backend/migrations/versions/c1d2e3f4a5b6_add_maintenance_actions.py`, `down_revision = "b0c1d2e3f4a5"` (head actual; Rahul lo confirma con `alembic heads`). Tipos portables (String/Text/Integer/DateTime(timezone=True)), sin enums nativos ni JSONB.

**`maintenance_action`** (derivada; insert-only, nunca se actualiza)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | String(36) PK | `uuid5(NAMESPACE_URL, f"maintenance-action:v1:{event_id}:{kind}:{target_record_id or '-'}:{national_code or '-'}:{master_field or '-'}")` → idempotencia |
| `event_id` | FK `maintenance_change_event.id`, index | |
| `kind` | String(40) | `revisar_estado`, `revisar_comercializacion`, `proponer_activo_n`, `revisar_archivo`, `proponer_alta` |
| `area` | String(40) | `estado`, `comerc`, `baja`, `alta` |
| `data_origin` | String(10) NOT NULL | `REAL`/`DEMO` (ver §6) |
| `target_record_id` | FK `target_record.id`, NULL, index | NULL solo en `proponer_alta` |
| `identity_id` | FK `medication_catalog_identity.id`, NULL, index | identidad de presentación ligada al target |
| `national_code` | Text NULL | CN literal del enlace exacto |
| `master_workbook` | String(40) NULL | `especialidades` |
| `master_sheet` | String(80) NULL | `General` |
| `master_field_name` | String(80) NULL | p. ej. `ACTIVO` (contexto) |
| `master_field_value_id` | FK `field_value.id` NULL | literal del maestro citado |
| `master_value_literal` | Text NULL | copia literal, sin normalizar |
| `cima_version_id` | FK `source_document_version.id` NULL | respuesta CIMA inmutable |
| `cima_pointer` | Text NULL | puntero JSON (RFC 6901) dentro del artefacto |
| `cima_value_literal` | Text NULL | literal tal como viene (JSON serializado si es objeto) |
| `proposed_value` | Text NULL | solo con `rule_id` aceptado; `N` en `proponer_activo_n` |
| `rule_id` | String(80) NULL | `ADR-0019:baja-revocacion-activo:v1` o `ADR-0019:alta-nombre-descripcion:v1` |
| `proposal_json` | Text NULL | solo `proponer_alta` (§4.4) |
| `diagnostic_code` | String(60) NULL | `sin_columna_destino`, `cima_no_disponible`, `cn_no_unico`, `sin_correspondencia`… |
| `derivation_version` | String(20) | `"novedades-v1"` |
| `created_at` | DateTime tz | |

Restricciones e índices: `UniqueConstraint(event_id, kind, target_record_id, national_code, master_field_name)` (además del id determinista); `Index(data_origin, kind)`; `Index(target_record_id)`; `Index(identity_id)`. Listener `before_update`/`before_delete` → `ImmutableHistoryError` como en los modelos vecinos.

**`maintenance_action_decision`** (append-only)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | String(36) PK | |
| `action_id` | FK `maintenance_action.id`, index | |
| `sequence` | Integer | 1..N, `UniqueConstraint(action_id, sequence)` (control de concurrencia: el cliente envía `expected_sequence`) |
| `decision` | String(30) | `aceptada`, `descartada`, `enviada_revision`, `reabierta` |
| `reason` | Text | obligatorio y no vacío en `descartada` y `reabierta`; opcional en el resto |
| `applied_revision_id` | FK `medication_catalog_revision.id` NULL | cuando aceptar archiva o crea el borrador de alta |
| `applied_field_revision_id` | FK `field_maintenance_revision.id` NULL | cuando aceptar `proponer_activo_n` escribe `ACTIVO` |
| `actor_id` | String(80) | del principal autenticado (ADR 0015) |
| `actor_assurance` | String(20) | como `catalog_cima_review_decision` |
| `recorded_at` | DateTime tz | |

Estado vigente = última decisión; sin decisiones = `pendiente`. `enviada_revision` es un estado intermedio (sigue contando como "por atender" en la cola de Revisión, no en la bandeja). Cada decisión emite además `audit_event` vía `audit_store.record_event` (tipo `maintenance_action.decision`).

Downgrade: `drop_table` de ambas (en orden inverso). Ningún dato existente se toca.

## 3. Mapeo área → campos (fase 1)

| Área CIMA / tipo | Acción | Valor CIMA (procedencia) | Valor maestro mostrado | Valor propuesto |
|---|---|---|---|---|
| `estado` (modificación, sin revocación) | `revisar_estado` por CN enlazado | `presentacion?cn` `/estado` | Especialidades `General.ACTIVO` del target (contexto) | ninguno; `diagnostic_code=sin_correspondencia` |
| `comerc` | `revisar_comercializacion` por CN | `presentacion?cn` `/comerc` | idem | ninguno; `sin_correspondencia` |
| `tipoCambio=2` (baja) o `estado.rev` presente | `proponer_activo_n` por target/CN | `medicamento?nregistro` / `presentacion?cn` `/estado` (o respuesta vacía/404 citada como tal) | Especialidades `General.ACTIVO` | `N` (`rule_id` ADR-0019) |
| `tipoCambio=2` (baja) | `revisar_archivo` por target | idem | `medication_catalog_identity.active` | ninguno preseleccionado; aceptar = archivar con justificación |
| `tipoCambio=1` (alta) sin target | `proponer_alta` por CN de CIMA | `presentaciones?nregistro` + `medicamento?nregistro` | — | fila del maestro (§4.4) |
| `prosp`, `psum`, `notasSeguridad`, `matinf`, `otros` | ninguna en fase 1 | — | — | el evento sigue visible en histórico |
| `ft` | sin cambios (comportamiento actual de `_mark_pending`) | — | — | fase 2 |

Si un evento trae `estado` y `comerc`, se generan ambas acciones. Si el estado capturado tiene revocación, se genera `proponer_activo_n` en lugar de `revisar_estado`. Si un nregistro enlaza a varios CN del catálogo, una acción por CN (y por target). Reglas de enlace sin cambios: CN literal exacto, único en ambos inventarios (`_catalog_targets_by_registration`); si no es único, el evento cae en "sin registro en el catálogo" con `diagnostic_code=cn_no_unico` visible en la sección secundaria (D-040: **se guardan todos** los avisos sin registro).

## 4. Backend

### 4.1 Módulo nuevo `maintenance_actions.py`

```python
@dataclass(frozen=True)
class ActionDraft: ...          # campos de maintenance_action salvo id/created_at

def derive_actions(session, *, event: MaintenanceChangeEvent,
                   targets: Sequence[MaintenanceChangeEventTarget],
                   client: MaintenanceClient) -> list[ActionDraft]
def persist_actions(session, drafts: Sequence[ActionDraft]) -> int   # inserta solo ids nuevos
def backfill_actions(session, *, client, batch_size: int = 200,
                     on_progress: Callable[[int], None] | None = None) -> BackfillResult
def current_state(session, action_ids) -> dict[str, ActionState]
def decide(session, *, action_id, decision, reason, expected_sequence, principal) -> ActionDecisionRead
```

- `derive_actions` es pura salvo las llamadas CIMA (inyectables con el `Protocol` existente; ampliar `MaintenanceClient` con `presentations(nregistro=…)` si falta).
- `decide("aceptada")` sobre `revisar_archivo`: en la **misma transacción** llama a la función de servicio que hoy usa `PUT /catalog/identities/{id}` con `active=False` (extraerla de `catalog_api.change_identity` a `catalog_store` si no está separada) y guarda `applied_revision_id`. Sobre `proponer_activo_n` aceptar escribe `ACTIVO="N"` en el `field_value` citado con el servicio del mantenimiento existente (`POST /records/values/{field_value_id}/maintenance`, append-only en `field_maintenance_revision`), citando la acción como procedencia, y guarda `applied_field_revision_id`. Sobre `revisar_estado`/`revisar_comercializacion` aceptar significa "revisado, conforme" y no escribe catálogo. Sobre `proponer_alta` aceptar crea una identidad **borrador pendiente de validar** con el servicio de `POST /catalog/identities` (CN y descripciones con procedencia, resto vacío) y la encola en Revisión (conjunto general); el farmacéutico la completa antes de exportarla.
- Conflicto de `expected_sequence` → 409 con mensaje en castellano.

### 4.2 Integración en la pasada diaria (`maintenance_job.run_one_day`)

- Hoy solo se guardan eventos con target (`relevant_changes`). Cambio (D-040): guardar **todos** los avisos, con o sin target. Los que no tienen target no refrescan ficha técnica ni generan acciones salvo `proponer_alta` (`change_type == 1`); van a la vista secundaria.
- Tras `process_change_report`, por cada evento nuevo: `persist_actions(derive_actions(...))`. Reutiliza el `client` y su caché.

### 4.3 Backfill idempotente

- CLI: `python -m pharma_validator_api.cli.maintenance_actions backfill [--origin REAL|DEMO] [--limit N]` (seguir el patrón de `cli/` existente) y endpoint `POST /maintenance/actions/backfill` (lanza en segundo plano con `maintenance_lock`, como `/maintenance/run`).
- Recorre eventos con targets en orden `(occurred_at_epoch, id)`, por lotes, commit por lote; los ids deterministas hacen que relanzar no duplique. Agrupa por CN/nregistro para pedir cada respuesta CIMA una sola vez por pasada.
- Escala: ~7 k eventos y ~8,4 k enlaces en `real-preview.db` → del orden de 8 k peticiones `presentacion` (con el rate limit del cliente). Debe poder interrumpirse y reanudarse; progreso en `maintenance_run` con `requested_date="backfill-v1"`.
- **Ojo:** el backfill toma el valor CIMA **actual**, no el del día del aviso. La acción cita la respuesta capturada (fecha visible), así que la procedencia es verdadera, pero la UI debe decir "valor en CIMA a fecha X", no "valor tras la novedad".

### 4.4 Propuesta de alta

`proposal_json` = `{ "workbook": "especialidades", "sheet": "General", "columns": [ {"name": <cabecera exacta en orden>, "value": <literal|null>, "provenance": {...}|null, "diagnostic": "sin_fuente"|null}, … ] }`.

- El orden y nombres de columnas se toman de la **cabecera importada** (`imported_source_sheet.header_payload` de la última importación de Especialidades `General`), no de una lista escrita a mano: así coincide exactamente con el Excel al que se exporta (`master_workbook_export.py`).
- Se rellenan `CODIGO_NACIONAL` = `cn` literal de `presentaciones?nregistro`, y `DESCRIPCION_PRESCRIPCION` y `DESCRIPCION_GESTION` = `nombre` literal de esa presentación (`rule_id=ADR-0019:alta-nombre-descripcion:v1`; procedencia: versión y puntero). Sin truncar: si el literal supera la longitud declarada se conserva y se emite `diagnostic="excede_longitud"`. **Todo lo demás `null` con `diagnostic="sin_fuente"`**, incluidos `ME_*`.
- Una propuesta por CN de CIMA del nregistro dado de alta; `data_origin` = origen de la base que ejecuta la pasada (§6).

### 4.5 API (`maintenance_api.py`, router `/maintenance`)

| Método y ruta | Capacidad (access_policy) | Qué hace |
|---|---|---|
| `GET /maintenance/actions?state=pendiente&kind=&group_by=kind&limit&offset&origin=` | `sources.read` | Bandeja "Por atender": contadores por `kind` y página de acciones con estado vigente |
| `GET /maintenance/actions/history?…` | `sources.read` | Acciones decididas, con última decisión |
| `GET /maintenance/actions/unlinked?page&limit` | `sources.read` | Eventos sin target (secundaria), con `diagnostic_code` |
| `GET /maintenance/actions/{action_id}` | `sources.read` | Detalle: valores, procedencia (versión, puntero, fecha de captura, URL), decisiones |
| `GET /catalog/identities/{identity_id}/maintenance-actions` | `catalog.read` | Acciones del expediente |
| `POST /maintenance/actions/{action_id}/decisions` | `review.write`, `actor_field="actor_id"` | Body `{actor_id, decision, reason, expected_sequence}`; el servidor ignora el actor del body si no coincide con el principal (patrón existente) |
| `POST /maintenance/actions/send-to-review` | `review.write`, `actor_id` | Body `{actor_id, action_ids[]}` (máx. 200): por cada target distinto llama a `review_queue_store.enqueue` (si ya hay entrada, no la duplica) y registra `enviada_revision` por acción. Respuesta: encoladas / ya en cola / rechazadas con motivo |
| `POST /maintenance/actions/backfill` | `sources.manage` | Lanza el backfill |
| `GET /catalog/identities?maintenance=pending` | `catalog.read` | Nuevo parámetro de filtro (§5.3) |

`review_set` para lo enviado: el conjunto general (`corpus`, valor por defecto de `enqueue`), por D-040. No se añade valor nuevo.

Registrar todas las rutas en `access_policy.POLICIES`; un test existente comprueba que no hay rutas sin política (si no lo hay, añadirlo).

## 5. Interfaz

Textos en castellano, de tú; skill `farmalidacion-ui` antes de tocar estilos; hoja nueva solo en `screens/maintenance.css` (o la que ya use la pantalla), nada en `styles.css`/`studio.css`.

### 5.1 `MaintenanceScreen.tsx` (Novedades CIMA)

- Pestañas: **Por atender** (por defecto) · **Histórico** · **Sin registro en el catálogo**.
- Cifras de cabecera: solo acciones pendientes con target (por tipo). Los avisos sin target y el total de eventos no aparecen en las cifras principales.
- Por atender: grupos plegables por acción ("Desactivar en el maestro (ACTIVO=N)", "Revisar estado en CIMA", "Revisar comercialización en CIMA", "Revisar si se archiva", "Proponer alta"), con contador. Cada fila: nombre/CN del catálogo (enlace al expediente), fecha del aviso, valor del maestro, valor en CIMA con "consultado el …" y enlace a la procedencia, el valor propuesto con la regla citada (ADR-0019) o, si es null, "Sin valor propuesto: no hay correspondencia aceptada". Ningún control preseleccionado.
- Selección múltiple por grupo + "Enviar a Revisión" (lote) y acciones por fila "Marcar revisada", "Archivar" (solo `revisar_archivo`), "Descartar" (pide justificación obligatoria).
- Proponer alta: tabla con las columnas exactas del maestro; vacías con "sin fuente". "Crear borrador" crea la identidad pendiente de validar.
- Histórico: la tabla actual de eventos más el estado de sus acciones.

### 5.2 Expediente (`CatalogIdentityScreen.tsx`)

- Bloque "Novedades CIMA sin atender" encima de `CatalogCimaComparisonPanel` y `NomenclatorComparisonPanel`, alimentado por `GET /catalog/identities/{id}/maintenance-actions`; mismas acciones por fila. No altera los paneles de comparación existentes; solo se coloca junto a ellos para que el farmacéutico vea el apoyo CIMA/Nomenclátor al decidir.
- Contador en la cabecera del expediente si hay pendientes.

### 5.3 Filtro de catálogo

- En la `FilterBar` del catálogo: casilla "Con novedades CIMA sin atender" → `maintenance=pending`. En backend: `EXISTS` sobre `maintenance_action` con `identity_id = medication_catalog_identity.id` (o por `target_record_id`) cuya última decisión no exista o sea `reabierta`. Índice `maintenance_action(identity_id)` lo soporta.

Contratos TS en `frontend/src/api/` (o donde vivan los de mantenimiento): `MaintenanceAction`, `MaintenanceActionDecision`, `MaintenanceActionKind`, `MaintenanceActionState`, con los mismos nombres de campo que el backend.

## 6. Seguridad y trazabilidad

- **REAL/DEMO:** `data_origin` obligatorio en cada acción. Con target se calcula con `data_origin.origin_for_record`; sin target (altas) se toma del origen de la base/perfil que ejecuta la pasada. Toda consulta de acciones filtra por un único origen (mismo patrón que `apply_origin_filter`); la API rechaza mezclar. Test: fixture con acciones REAL y DEMO; ningún endpoint devuelve ambas.
- **Permisos:** solo capacidades existentes (`sources.read`, `catalog.read`, `review.write`, `sources.manage`); actor desde el principal (ADR 0015).
- **Procedencia:** acción con valor CIMA sin `cima_version_id` es imposible (CHECK lógico en `persist_actions` + test). El artefacto citado contiene literalmente `cima_value_literal` en `cima_pointer` (test que reconstruye con `reconstruct_artifact` y compara).
- **Sin normalizar:** `proposed_value` debe ser NULL si `rule_id` es NULL o no está en la lista cerrada de reglas aceptadas (las dos de ADR-0019; test de rechazo).
- **Sin automatismos:** ninguna acción cambia catálogo, `field_value` ni exportación sin decisión humana; las escrituras (archivar, `ACTIVO=N`, borrador de alta) ocurren solo al aceptar, con revisión append-only y procedencia.
- **Exportación:** las acciones pendientes no bloquean la exportación ni añaden aviso al Excel (D-040). Un borrador de alta sigue las reglas normales de validación antes de exportarse.

## 7. Orden de ejecución para Rahul

1. Leer ADR-0019 y D-040 (decisiones cerradas).
2. Migración `c1d2e3f4a5b6_add_maintenance_actions.py` + modelos en `models.py` con listeners de inmutabilidad.
3. `persist_cima_api_response` en `document_versions.py` + tests.
4. `maintenance_actions.py`: `derive_actions`, `persist_actions`, `decide`, `current_state` + tests unitarios.
5. Cambios en `maintenance_job.run_one_day` (guardar altas, derivar acciones) + test.
6. Backfill (CLI y endpoint con `maintenance_lock`) + test de idempotencia.
7. Endpoints de §4.5, políticas en `access_policy.py`, filtro `maintenance` en `catalog_api.list_identities`.
8. Frontend: tipos y cliente API → `MaintenanceScreen` (pestañas, bandeja, lote) → bloque en `CatalogIdentityScreen` → filtro en `FilterBar`.
9. Documentación: `docs/CIMA_NOVELTY_PANEL_CONTRACT.md` (acciones), `docs/STATUS.md`, backlog y trazabilidad.

## 8. Tests a escribir

Backend (`backend/tests/`):
- `test_maintenance_actions_migration`: upgrade/downgrade limpios sobre una base con eventos existentes.
- `test_derive_actions_estado_comerc`: evento `estado`+`comerc` con un target → dos acciones con versión y puntero; `proposed_value` NULL, `diagnostic_code=sin_columna_destino`.
- `test_derive_actions_baja`: `tipoCambio=2` → `proponer_activo_n` (`N`, rule_id) y `revisar_archivo`.
- `test_derive_actions_revocacion`: `estado.rev` presente → `proponer_activo_n`; `estado.susp` → `revisar_estado` sin propuesta.
- `test_aceptar_activo_n_escribe_revision`: `ACTIVO` pasa a `N` vía `field_maintenance_revision`; descartar no escribe nada.
- `test_aceptar_alta_crea_borrador`: identidad pendiente de validar, encolada en `corpus`.
- `test_eventos_sin_target_se_guardan`.
- `test_derive_actions_alta_estructura`: columnas de `proposal_json` == cabecera importada (mismo orden); solo `CODIGO_NACIONAL` y las dos descripciones con valor y procedencia; un `nombre` largo no se trunca.
- `test_derive_actions_cima_unavailable`: sin respuesta → `cima_no_disponible`, sin valor.
- `test_backfill_idempotente`: dos ejecuciones → mismo número de filas; reanudar tras corte.
- `test_action_immutable`: update/delete → `ImmutableHistoryError`.
- `test_decision_descartar_requiere_motivo`, `test_decision_concurrencia_409`, `test_decision_audit_event`.
- `test_aceptar_archivo_crea_revision`: identidad `active=False`, revisión append-only, `applied_revision_id`.
- `test_aceptar_estado_no_escribe_catalogo`.
- `test_send_to_review_lote`: encola en `corpus` una vez por target; `enviada_revision` por acción; entradas existentes no se duplican.
- `test_origin_separation`: ningún endpoint mezcla REAL y DEMO.
- `test_access_policy_maintenance_actions`: cada ruta exige su capacidad; sin capacidad → 403.
- `test_catalog_filter_maintenance_pending`.
- `test_proposed_value_requires_rule`.

Frontend (Vitest):
- `MaintenanceScreen.test.tsx`: pestañas, cifras solo de pendientes con target, agrupación, lote, justificación obligatoria al descartar, sin preselección, texto "Sin valor propuesto".
- `CatalogIdentityScreen.test.tsx`: bloque de novedades visible con pendientes y ausente sin ellas.
- Filtro del catálogo envía `maintenance=pending`.

## 9. Verificación

Desde `validador-fichas-tecnicas-repo-kit/`: `cd backend && python -m pytest`; `cd frontend && npx vitest run && npm run lint && npm run build`; `python scripts/verify_project.py` (incluye migraciones). Manual: backfill sobre una copia de `real-preview.db`, relanzarlo y comprobar recuentos idénticos; capturas antes/después de Novedades y expediente en claro y oscuro.

## 10. Riesgos

| Riesgo | Mitigación | Reversión |
|---|---|---|
| Volumen de peticiones del backfill (~8 k) | caché, rate limit del cliente, lotes reanudables, una petición por CN | parar el job; filas creadas son válidas |
| Valor CIMA actual ≠ valor en la fecha del aviso | mostrar fecha de captura; nunca "valor tras la novedad" | — |
| Farmacia interpreta "Marcar revisada" como "actualizado en el maestro" | texto explícito; ADR-0019 para escritura real | — |
| Archivar por error | justificación obligatoria; desarchivar con otra revisión (D-031) | revisión inversa |
| Crecimiento al guardar todos los avisos (~58 k) | índices existentes; vista secundaria paginada; fuera de las cifras | — |
| Aceptar `ACTIVO=N` por error | justificación en historial; otra revisión lo revierte | revisión inversa |
| Migración | aditiva | `alembic downgrade -1` |

## 11. Decisiones

- **ADR-0019 (aceptado, 2026-10-30)** y **D-040**: reglas de §0, altas como borrador con `nombre` CIMA en descripción, todos los avisos guardados, envío a Revisión al conjunto general, sin bloqueo de exportación ni aviso en el Excel. Fichero: `docs/decisions/0019-cima-status-to-master-activo.md`.
- Pendiente al construir: ampliar `CIMA_NOVELTY_PANEL_CONTRACT.md` (DEV-703).

## 12. Fuera de alcance / fase 2

- Ficha técnica: marcar también campos **no validados** de apartados cambiados (hoy `_mark_pending` solo reabre los decididos) y generar acciones `revisar_ft` por apartado.
- Prospecto, notas de seguridad, materiales informativos, `psum`, `otros`.
- Bloqueo de exportación por acciones pendientes.

## 13. Preguntas abiertas

Ninguna: P-1..P-6 resueltas por el usuario el 2026-10-30 (ver §11).
