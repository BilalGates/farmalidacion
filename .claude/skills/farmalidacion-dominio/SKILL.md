---
name: farmalidacion-dominio
description: "Reglas de producto de Farmalidación: validación farmacéutica campo a campo, procedencia y versiones inmutables, políticas de prerrelleno, discrepancias y doble validación, exportación y separación REAL/DEMO. Cárgala siempre que un cambio toque datos, validación, importación o exportación."
---

# farmalidacion-dominio

La fuente de verdad son los documentos de `validador-fichas-tecnicas-repo-kit/docs/` (especificación v2, ADR aceptados, registro de decisiones). Esta skill resume lo que no se puede romper y dónde comprobarlo.

## Qué es y qué no es

Consolidación y validación de **datos maestros de medicamentos**. Nunca datos de pacientes, nunca recomendaciones clínicas, nunca apoyo a la decisión terapéutica.

## Reglas que bloquean una revisión

1. **Procedencia:** ninguna propuesta se guarda sin procedencia verificable; la evidencia literal de la ficha técnica coincide exactamente con la versión inmutable citada.
2. **Valores clínicos:** no se infieren, calculan, convierten, redondean ni normalizan sin una regla aceptada.
3. **Prerrelleno:** la política la decide el backend (`prefill_policy`); en `proponer_opciones` y `solo_evidencia` la interfaz **no preselecciona** nada.
4. **Bloques repetidos:** composiciones, indicaciones, vías, frecuencias, excipientes, enlaces, consejos, datos analíticos, poblaciones e interacciones se modelan como filas repetidas, nunca en un único valor.
5. **Datos de origen:** nunca se truncan, descartan ni coaccionan en silencio; se conserva el literal y se emite un diagnóstico (las filas apartadas van a cuarentena).
6. **Discrepancias:** ninguna se resuelve automáticamente; la decide un farmacéutico y los valores en conflicto conservan su procedencia. En la interfaz, solo se comparan valores marcados como discrepancia (`has_conflict`); el `literal_text` de la procedencia es un fragmento de evidencia, no el valor.
7. **Doble validación:** un registro con discrepancias de doble validación abiertas no se exporta. La segunda lectura es ciega.
8. **Historial:** cada decisión es un evento nuevo; no sustituye a la anterior.
9. **REAL y DEMO** no se mezclan nunca en la misma vista, consulta ni base.
10. **Permisos:** se comprueban en el servidor en cada operación (ADR 0015); la interfaz solo los refleja.

## Dónde mirar

| Tema | Código | Documentación |
|---|---|---|
| Estados de validación | `backend/src/pharma_validator_api/validation_states.py`, `frontend/src/domain/vocabulary.ts` | `docs/DECISION_REGISTER.md` |
| Prerrelleno | `prefill_policy.py` | especificación v2 |
| Procedencia y versiones | `document_versions.py`, `evidence_verification.py`, `provenance_conflicts.py` | `CIMA_DOCUMENT_VERSIONING.md`, `EVIDENCE_VERIFICATION_CONTRACT.md` |
| Doble validación | `double_review.py`, `second_review_*.py` | ADR correspondientes |
| Exportación | `export_engine.py`, `export_service.py` | `EXPORT_CONTRACT.md` |
| Importación y cuarentena | `master_ingestion.py`, `import_batches.py`, `quarantine_api.py` | `CATALOG_IMPORT_CONTRACT.md` |
| CIMA y Nomenclátor | `cima_*.py`, `nomenclator_*.py` | `CIMA_*`, ADR 0018 |

## Al cambiar algo de esto

- Test que ejecute la regla de verdad (skill `tests`), en especial los caminos que deben **rechazarse**.
- Si el cambio altera una decisión registrada: ADR nuevo y entrada en el registro, no un cambio silencioso.
- Aniol revisa antes que Dani (ver `.agents/proyecto.md`).
