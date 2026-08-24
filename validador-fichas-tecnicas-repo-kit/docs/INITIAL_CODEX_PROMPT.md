# Primer encargo para Codex

Copiar el siguiente texto en una sesión nueva abierta en la raíz del repositorio.

```text
Usa $pharma-validator-companion y actúa como agente principal del proyecto.

Objetivo de esta sesión: completar el arranque de la Fase 0A y preparar la Fase 0B. No escribas todavía código de producto, migraciones definitivas ni interfaz.

1. Lee AGENTS.md, docs/PROJECT_CONTEXT.md, docs/DEVELOPMENT_PLAN.md, docs/DECISION_REGISTER.md, docs/SOURCE_INVENTORY.md y la especificación v2.
2. Resume las instrucciones activas y señala cualquier conflicto documental.
3. Comprueba que están disponibles los agentes personalizados y la skill del proyecto.
4. Verifica los ficheros de `data/reference/raw/` con el script existente. Si faltan, informa de ello sin inventar resultados.
5. Delega en paralelo y en modo lectura:
   - a domain_modeler: revisar D-001, D-002, D-003, D-006, D-010 y ADR-0001;
   - a data_profiler: diseñar el perfilado reproducible de todos los Excel y la prueba de ida y vuelta de omeprazol;
   - a qa_reviewer: proponer criterios de aceptación y pruebas de no pérdida;
   - a security_auditor: revisar límites, procedencia, versiones y riesgos del flujo de agentes.
6. Espera a todos y consolida un único informe.
7. Propón el primer lote de issues, pequeñas y ordenadas, para completar la Fase 0B. Cada issue debe incluir objetivo, entregables, dependencias y criterio de aceptación.
8. Actualiza solo documentación de planificación si es necesario. No marques decisiones como aceptadas y no cambies la especificación original.
9. Finaliza indicando:
   - decisiones que requieren validación humana;
   - primer issue que recomiendas ejecutar;
   - riesgos que impedirían comenzar a programar el modelo canónico.
```
