# Vertical funcional de revisión — spike de producto

## Naturaleza de este trabajo

Esta vertical es un **spike de producto demostrable**, no el cierre de la Fase 5.
Se construyó para materializar visualmente cómo funcionará Farmalidación ante
dirección, sin alterar el plan de desarrollo ni relajar ninguna restricción.

No abre la Fase 5 ni cierra DEV-502, DEV-503, DEV-504, DEV-505 ni DEV-509. La
puerta de entrada de la Fase 5 sigue sin cumplirse, porque la Fase 4 no está
abierta: el conjunto oro sigue sin anotar (GOLD-002) y D-014/D-015 continúan
pendientes.

## Recorrido implementado

```text
Inicio → Fichas técnicas → buscar/filtrar → abrir ficha
      → consultar valores, fuentes y procedencia
      → identificar discrepancias
      → decidir y firmar → guardar
      → volver al listado con el estado actualizado
```

## Implementado y verificado

| Capacidad | Dónde vive | Prueba |
|---|---|---|
| Listado con estado agregado, búsqueda y filtro | `records.list_records` | `test_list_supports_search_and_state_filter` |
| Detalle por bloques con ocurrencias separadas | `records.read_record` | `test_repeated_occurrences_are_not_collapsed` |
| Valor, fuente y procedencia por campo | `records._read_field_value` | `test_conflicting_sources_are_reported_without_being_resolved` |
| Detección de discrepancias entre fuentes | `review.evaluate_field_conflict` | idem |
| Decisión firmada y persistida | `review.record_decision` | `test_decision_is_persisted_and_changes_the_list_state` |
| Persistencia entre reinicios | `ValidationDecisionRecord` | `test_decision_survives_a_restart` |
| Historial append-only | modelo + evento SQLAlchemy | `test_history_is_append_only_and_keeps_the_previous_decision`, `test_stored_decision_cannot_be_mutated` |
| Interfaz de listado, ficha y revisión | `frontend/src/screens/` | `frontend/src/App.test.tsx` |

## Barreras que la capa HTTP no puede saltarse

La vertical **no reimplementa** ninguna regla clínica. `review.py` traduce entre
la base de datos y los módulos puros ya verificados, y los errores de esas
barreras se propagan literalmente hasta la pantalla:

- `reviewer_identity` — sin revisor de la lista no se firma nada;
- `validation_states` — legitimidad de la decisión y de la transición;
- `provenance_conflicts` — evaluación de discrepancias entre fuentes.

Cada una tiene su prueba de extremo a extremo en `test_review_vertical.py`.

## Simulado o provisional

- **Datos DEMO.** `data/examples/showcase-demo.json` contiene cinco registros de
  demostración generados por `scripts/generate_showcase_fixture.py`. Los nombres
  de campo y bloque proceden del catálogo real de 353 definiciones; **los valores
  no proceden de los maestros ni de CIMA**. Cada registro declara el sistema
  fuente `demo_showcase` y la interfaz muestra un aviso permanente. Los ficheros
  originales de referencia no se han modificado.
- **Sin matriz de prioridad por campo.** `evaluate_field_conflict` invoca el
  motor de ADR-0007 con `rule=None` deliberadamente. Toda discrepancia real
  queda en `unresolved_pending_priority`: ninguna se resuelve automáticamente y
  la interfaz nunca aparenta que se haya tomado una decisión farmacéutica.
- **Sin políticas de pre-relleno.** La vertical no consume todavía
  `prefill_policy`. Hasta que lo haga, la pantalla **no precarga ningún valor** y
  el desplegable de decisión arranca vacío: es el comportamiento seguro, y
  cumple por defecto la prohibición de preselección en campos protegidos (D-023).
- **Una sola firma por decisión.** La doble validación de 11.1 no está
  implementada; `reviewer_identity.require_distinct` existe pero esta vertical no
  la invoca.
- **Módulos anunciados.** Validaciones, Fuentes, Importaciones, Auditoría y
  Configuración aparecen en la navegación como «Pronto» con una nota que declara
  qué hacen hoy, qué falta y de qué decisión dependen. Representarlos no los
  implementa ni cierra su dependencia.

## Pendiente (fases posteriores)

Integración CIMA en la interfaz, extracción LLM, resolución clínica de
discrepancias, doble validación definitiva, exportación, reglas completas de
`no_consta`/`no_aplica` por campo, significado de `S*`/`N*`, navegación completa
por teclado y precarga con objetivo de 100 ms.

## Decisiones abiertas que esta vertical NO cierra

| Decisión | Estado | Cómo la representa la vertical |
|---|---|---|
| D-005 `S*`/`N*` | dependencia externa (PROVIDER-001) | no se deriva obligatoriedad; `field_required` llega del cliente y por defecto es falso |
| D-011 contrato de exportación | pendiente | no existe exportación; el módulo se anuncia como pendiente |
| D-012 separador decimal | pendiente | los valores se muestran literales, sin reformatear |
| D-014 modelo de inferencia | pendiente | no hay extracción; se anuncia como posterior |
| D-015 umbrales de `proponer_valor` | pendiente | no hay propuestas automáticas |
| D-017 reglas ATC de riesgo | pendiente | no hay doble validación activa |
| Prioridad por campo (bajo ADR-0007) | pendiente de aprobación humana | discrepancias visibles y sin resolver |

## Cómo ejecutar la demo

```text
docker compose up --build --detach --wait
```

Compose activa `APP_LOAD_SHOWCASE_FIXTURE` y una lista de revisores de ejemplo.
La interfaz queda en `http://127.0.0.1:5173` y la API en `http://127.0.0.1:8000`.

Para desarrollo local sin contenedores, el backend necesita
`APP_LOAD_SHOWCASE_FIXTURE=true`, `APP_REVIEWERS` y
`APP_CORS_ALLOW_ORIGINS=["http://localhost:5173"]`.

## Regenerar el conjunto DEMO

```text
python scripts/generate_showcase_fixture.py
```

El generador es determinista: dos ejecuciones producen el mismo fichero.
