# Registro de decisiones

Estados: `cerrada`, `propuesta`, `pendiente`, `bloqueada`, `descartada`. Una decisión solo está cerrada cuando existe evidencia de aprobación y, cuando afecta a arquitectura, un ADR aceptado.

| ID | Decisión | Estado | Debe cerrarse antes de | Recomendación inicial | Evidencia / ADR |
|---|---|---|---|---|---|
| D-001 | Unidad que revisa el farmacéutico | pendiente | Fase 0B | Revisar un registro destino con acceso a todas sus fuentes vinculadas | ADR-0001 |
| D-002 | Modelo canónico de documentos, registros y vínculos | propuesta | Fase 0B | Separar documento/versiones, registro destino y vínculo N:M | ADR-0001 |
| D-003 | Representación de bloques repetibles | cerrada | Fase 0B | Ocurrencias explícitas; prohibido concatenarlas | Aprobación humana 2026-08-24; ADR-0001 sigue propuesto para el modelo completo |
| D-004 | Claves naturales y reglas de identidad por bloque | propuesta | Fase 0B | Identidad canónica propia y claves de fuente versionadas; validar por round-trip y con proveedor | ADR-0005; DEV-004 |
| D-005 | Significado de `S*` y `N*` | pendiente | Fase 0B | Conservar literal hasta respuesta del proveedor | Por crear |
| D-006 | Relación `nregistro` / CN / medicamento / especialidad / principio activo | pendiente | Fase 0B | Vínculos explícitos con rol y vigencia | ADR-0001 |
| D-007 | Estrategia para maestros actuales | cerrada | Fase 0B | Línea base con procedencia, consolidada con CIMA, FT y decisiones farmacéuticas | ADR-0002; aprobación humana 2026-08-24 |
| D-008 | Matriz de fuente y prioridad por campo | pendiente | Fase 3 | Configurable; conflicto visible, sin reemplazo silencioso | Por crear |
| D-009 | Alcance de interacciones | cerrada | Fase 0B | Línea separada de migración/conciliación, fuera del piloto de extracción FT | ADR-0003; aprobación humana 2026-08-24 |
| D-010 | Semántica de vacío, pendiente, no consta y no aplica | propuesta | Fase 0B | Estados separados del valor; semántica y exportación por validar | ADR-0004 |
| D-011 | Contrato exacto de exportación | pendiente | Fase 6 | Obtener ejemplo aceptado y prueba en entorno proveedor | Por crear |
| D-012 | Separador decimal | pendiente | Fase 6 | Punto provisional y configurable | Especificación v2 |
| D-013 | Hardware GPU | pendiente | Fase 4 | Medir dos tamaños compatibles con el hardware real | Especificación v2 |
| D-014 | Modelo/servidor de inferencia | pendiente | Fase 4 | Interfaz compatible OpenAI; elegir tras benchmark | Por crear |
| D-015 | Umbrales para `proponer_valor` y degradación | pendiente | Fase 4 | Definir por precisión, cobertura y tasa de corrección | Por crear |
| D-016 | Selección aleatoria o estratificada | pendiente | Fase 2 | Decidir tras informe de composición | Especificación v2 |
| D-017 | Reglas ATC adicionales a `L04` | pendiente | Fase 6 | Decisión exclusiva de farmacia | Especificación v2 |
| D-018 | Autenticación real | cerrada para piloto | Fase 8 | No en piloto; reevaluar para auditoría formal | Especificación v2 |
| D-019 | Base de datos del piloto | cerrada | Fase 1 | SQLite con tipos portables y Alembic | Especificación v2 |
| D-020 | Estrategia de versiones de ficha técnica | propuesta | Fase 2 | Versiones inmutables, nunca sobrescritura | ADR-0001 |
| D-021 | Campos `EX_DESCRIPCION` y `ME_DESCRIPCION` | cerrada | Fase 3 | `CHAR(100)` mediante overrides trazables | Especificación v2 |
| D-022 | Datos de paciente | cerrada | Siempre | Fuera de alcance | Especificación v2 |
| D-023 | Preselección en campos interpretables o clínicos | cerrada | Siempre | Prohibida | Especificación v2 |
| D-024 | Evidencia de propuestas de FT | cerrada | Fase 4 | Coincidencia literal obligatoria | Especificación v2 |
| D-025 | Idioma de interfaz | cerrada | Fase 5 | Español | Especificación v2 |

## Flujo de una decisión

1. El agente detecta una decisión que cambia comportamiento, datos o arquitectura.
2. La añade o actualiza aquí.
3. Crea un ADR con contexto, opciones, recomendación, consecuencias y plan de validación.
4. Los agentes de dominio, QA y seguridad revisan de forma independiente cuando corresponda.
5. El responsable humano acepta, modifica o descarta.
6. Codex actualiza plan, backlog, trazabilidad y código solo después de la decisión.
