# Registro de decisiones

Estados: `cerrada`, `propuesta`, `pendiente`, `bloqueada`, `descartada`. Una decisión solo está cerrada cuando existe evidencia de aprobación y, cuando afecta a arquitectura, un ADR aceptado.

| ID | Decisión | Estado | Debe cerrarse antes de | Recomendación inicial | Evidencia / ADR |
|---|---|---|---|---|---|
| D-001 | Unidad que revisa el farmacéutico | cerrada | Fase 0B | Expediente contextual; decisiones atribuidas al nivel destino correspondiente | ADR-0006 aceptado; aprobación humana 2026-08-25 |
| D-002 | Modelo canónico de documentos, registros y vínculos | cerrada | Fase 0B | Separar documento/versiones, registro destino y vínculo tipado | ADR-0006 aceptado; ADR-0001 sigue propuesto para el modelo completo |
| D-003 | Representación de bloques repetibles | cerrada | Fase 0B | Ocurrencias explícitas; prohibido concatenarlas | Aprobación humana 2026-08-24; ADR-0001 sigue propuesto para el modelo completo |
| D-004 | Claves naturales y reglas de identidad por bloque | cerrada | Fase 0B | PK canónica propia; referencia externa versionada | ADR-0005 aceptado; aprobación humana 2026-08-25 |
| D-005 | Significado de `S*` y `N*` | dependencia externa | Antes de reglas condicionales definitivas | Conservar literal; derivar solo `base_required`; modificador abierto | PROVIDER-001; no bloquea Fase 1 |
| D-006 | Relación `nregistro` / CN / medicamento / especialidad / principio activo | cerrada | Fase 0B | Identidades separadas y vínculos con rol, procedencia y vigencia; cardinalidad factual `nregistro`↔CN se verifica en Fase 2 | ADR-0006 aceptado; aprobación humana 2026-08-25 |
| D-007 | Estrategia para maestros actuales | cerrada | Fase 0B | Línea base con procedencia, consolidada con CIMA, FT y decisiones farmacéuticas | ADR-0002; aprobación humana 2026-08-24 |
| D-008 | Matriz de fuente y prioridad por campo | cerrada | Fase 3 | Línea base + prioridad configurable; conflicto visible y acción humana si falta regla | ADR-0007 aceptado; aprobación humana 2026-08-25 |
| D-009 | Alcance de interacciones | cerrada | Fase 0B | Línea separada de migración/conciliación, fuera del piloto de extracción FT | ADR-0003; aprobación humana 2026-08-24 |
| D-010 | Semántica de vacío, pendiente, no consta y no aplica | cerrada para modelo interno | Fase 0B | Estados separados; autoridad, comentarios, reversibilidad y doble validación definidos | ADR-0004 aceptado internamente; aprobación humana 2026-08-25; serialización en D-011 |
| D-011 | Contrato exacto de exportación | pendiente | Fase 6 | Obtener ejemplo aceptado y prueba en entorno proveedor | Por crear |
| D-012 | Separador decimal | pendiente | Fase 6 | Punto provisional y configurable | Especificación v2 |
| D-013 | Hardware GPU | cerrada | Fase 4 | Servidor interno con GPU de al menos 24 GB de VRAM; modelo/servidor exactos quedan en D-014 | Aprobación humana 2026-09-02; `docs/GPU_SIZING_ANALYSIS.md` |
| D-014 | Modelo/servidor de inferencia | pendiente | Fase 4 | Interfaz compatible OpenAI; elegir tras benchmark | Por crear |
| D-015 | Umbrales para `proponer_valor` y degradación | pendiente | Fase 4 | Definir por precisión, cobertura y tasa de corrección; depende de DEV-408 | Por crear; barrera de evidencia ya implementada en `docs/EVIDENCE_VERIFICATION_CONTRACT.md` |
| D-016 | Selección aleatoria o estratificada | cerrada | Fase 2 | Muestra aleatoria, semilla 203, sobre instantánea reproducible | Elección humana al continuar el 28-08-2026; informe real `bb80992258d07a5e49f1beef46e983f3f56a57e7d48ad20d5aef19e3bffa5fe7` |
| D-017 | Reglas ATC adicionales a `L04` | pendiente | Fase 6 | Decisión exclusiva de farmacia | Especificación v2 |
| D-018 | Autenticación real | cerrada para piloto | Fase 8 | No en piloto; reevaluar para auditoría formal | Especificación v2 |
| D-019 | Base de datos del piloto | cerrada | Fase 1 | SQLite con tipos portables y Alembic | Especificación v2 |
| D-020 | Estrategia de versiones de ficha técnica | cerrada | Fase 2 | Versiones content-addressed inmutables; `source_version` literal y opcional, nunca inferida | ADR-0001 aceptado; DEV-205/208; aceptación humana 31-08-2026 |
| D-021 | Campos `EX_DESCRIPCION` y `ME_DESCRIPCION` | cerrada | Fase 3 | `CHAR(100)` mediante overrides trazables | Especificación v2 |
| D-022 | Datos de paciente | cerrada | Siempre | Fuera de alcance | Especificación v2 |
| D-023 | Preselección en campos interpretables o clínicos | cerrada | Siempre | Prohibida | Especificación v2 |
| D-024 | Evidencia de propuestas de FT | cerrada | Fase 4 | Coincidencia literal obligatoria | Especificación v2 |
| D-025 | Idioma de interfaz | cerrada | Fase 5 | Español | Especificación v2 |
| D-026 | Límites canónicos internos ambiguos | cerrada | Fase 1 | Composición/DESCRIPCION 100; Links/DESCRIPCION 255; nunca truncar | Aprobación humana 2026-08-25; no equivale a contrato proveedor |
| GOLD-001 | Semilla del conjunto oro | cerrada | Fase 4 | Semilla reproducible `407` | Aprobación humana 2026-09-02; `docs/GOLD_SET_ANNOTATION_CONTRACT.md` |
| GOLD-002 | Anotadores farmacéuticos del conjunto oro | pendiente | Fase 4 | Dos anotadores independientes identificados | `docs/GOLD_SET_ANNOTATION_CONTRACT.md` |
| GOLD-003 | Cobertura por estrato ATC del conjunto oro | cerrada | Fase 4 | No estratificar por ATC el conjunto oro inicial: el inventario DEV-208 no contiene ATC; reevaluar solo con nueva evidencia | Aprobación humana 2026-09-02; `docs/GOLD_SET_ANNOTATION_CONTRACT.md` |

## Flujo de una decisión

1. El agente detecta una decisión que cambia comportamiento, datos o arquitectura.
2. La añade o actualiza aquí.
3. Crea un ADR con contexto, opciones, recomendación, consecuencias y plan de validación.
4. Los agentes de dominio, QA y seguridad revisan de forma independiente cuando corresponda.
5. El responsable humano acepta, modifica o descarta.
6. Codex actualiza plan, backlog, trazabilidad y código solo después de la decisión.
