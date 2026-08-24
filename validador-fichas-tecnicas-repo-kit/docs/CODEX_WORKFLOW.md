# Flujo de trabajo con Codex, agentes y skill

## 1. Componentes

### `AGENTS.md`

Contiene las reglas persistentes del repositorio. Codex lo lee antes de trabajar. Las instrucciones más cercanas a un subdirectorio pueden ampliar o sustituir las reglas generales mediante `AGENTS.md` o `AGENTS.override.md`. Mantener el archivo raíz breve y mover reglas específicas a cada módulo cuando el código exista.

### Skill `pharma-validator-companion`

Está incluida en `.agents/skills/pharma-validator-companion/`. Puede invocarse explícitamente con `$pharma-validator-companion`; también puede activarse cuando la tarea coincide con su descripción. Obliga a leer el contexto, comprobar decisiones, aplicar las restricciones clínicas, actualizar ADRs y dejar evidencia de pruebas.

### Agentes integrados de Codex

- `default`: orquestación general.
- `worker`: implementación acotada.
- `explorer`: exploración del repositorio en lectura.

### Agentes personalizados del proyecto

- `domain_modeler`: relaciones, cardinalidades y decisiones de dominio.
- `data_profiler`: perfilado de Excel, claves, integridad y round-trip.
- `backend_architect`: diseño de API, persistencia, migraciones y trabajos por lotes.
- `frontend_ux_reviewer`: revisión de teclado, accesibilidad, sesgo de automatización y rendimiento.
- `llm_evaluator`: evaluación del extractor, esquemas, evidencia y métricas.
- `qa_reviewer`: riesgos de corrección, regresión y cobertura.
- `security_auditor`: límites de datos, trazabilidad, despliegue interno y dependencias.

## 2. Regla de orquestación

El hilo principal mantiene requisitos, decisiones y resultado final. Los subagentes reciben tareas delimitadas y devuelven resúmenes, no volcados completos.

Usar agentes paralelos para:

- explorar ficheros o código;
- revisar una decisión desde perspectivas distintas;
- ejecutar o analizar pruebas;
- revisar seguridad, datos o UX;
- comparar alternativas sin editar.

Evitar agentes paralelos escribiendo en los mismos módulos. Para dos cambios independientes, usar ramas o worktrees distintos.

## 3. Ciclo de una incidencia

### Paso 1 — Preparación

- Leer la issue y los documentos aplicables.
- Invocar `$pharma-validator-companion`.
- Identificar requisitos, ADRs y decisiones pendientes.
- Declarar qué queda fuera de la incidencia.

### Paso 2 — Exploración paralela

Ejemplo:

```text
Delega el análisis en paralelo. Usa domain_modeler para revisar el impacto de dominio, data_profiler para comprobar los ficheros de referencia y qa_reviewer para proponer pruebas y fallos límite. No editéis código. Espera a los tres y consolida sus conclusiones con referencias a archivos.
```

### Paso 3 — Plan de ejecución

El agente principal produce:

- objetivo;
- archivos esperados;
- migraciones;
- riesgos;
- pruebas;
- documentación afectada;
- criterio de rollback.

Si aparece una decisión no cerrada, se crea un ADR antes de implementar el comportamiento definitivo. Se permite un spike aislado si su salida es evidencia para decidir y no código de producción.

### Paso 4 — Implementación

- Un único agente escritor.
- Cambio pequeño y coherente.
- Pruebas junto al comportamiento.
- Nada de refactors colaterales sin justificación.
- Si el alcance crece, dividir la issue.

### Paso 5 — Verificación paralela

Ejemplo:

```text
Revisa esta rama con agentes en paralelo. Usa qa_reviewer para corrección y pruebas, security_auditor para seguridad y procedencia, y el agente especializado del módulo afectado. No cambies código. Devuelve hallazgos ordenados por severidad con archivo, símbolo, reproducción y corrección segura.
```

### Paso 6 — Cierre

La respuesta final de Codex debe incluir:

1. objetivo completado;
2. decisiones tomadas o pendientes;
3. archivos modificados;
4. migraciones;
5. comandos de prueba y resultado exacto;
6. riesgos residuales;
7. documentos actualizados;
8. siguiente issue recomendada.

## 4. Worktrees

Usar worktrees para tareas independientes, por ejemplo:

- perfilador de Excel;
- scaffold backend;
- scaffold frontend;
- investigación de CIMA.

No usar dos worktrees para cambiar simultáneamente el mismo esquema o migración. El agente principal integra los resultados uno por uno y vuelve a ejecutar la batería completa.

## 5. Prompts reutilizables

### Explorar sin modificar

```text
Usa $pharma-validator-companion. Explora este problema en modo lectura. Relaciona tus hallazgos con la especificación, decisiones y ficheros reales. No propongas una implementación hasta identificar cardinalidades, procedencias, riesgos de pérdida y pruebas de aceptación.
```

### Crear un ADR

```text
Usa $pharma-validator-companion y redacta un ADR para la decisión D-XXX. Presenta contexto, restricciones, al menos dos alternativas reales, recomendación, consecuencias, migración, pruebas de validación y preguntas que todavía requieren aprobación humana. No marques el ADR como aceptado.
```

### Implementar una issue

```text
Usa $pharma-validator-companion. Implementa únicamente la issue XXX en una rama dedicada. Antes de editar, resume requisitos y ADRs aplicables, delega la exploración necesaria, presenta un plan corto y define pruebas. Después ejecuta las comprobaciones, corrige los fallos y actualiza STATUS, BACKLOG y TRACEABILITY.
```

### Revisar una PR

```text
Revisa esta PR con agentes paralelos de QA, seguridad y dominio. Prioriza pérdida de datos, cardinalidades, procedencia, versiones, políticas de pre-relleno, exportación y pruebas. Omite comentarios puramente estéticos. Espera a todos y consolida hallazgos por severidad.
```

## 6. Comprobación de configuración

Después de copiar el kit al repositorio:

```bash
codex --ask-for-approval never "Resume las instrucciones activas y enumera los agentes y skills disponibles para este repositorio."
```

Si falta alguna instrucción, revisar la ubicación de `AGENTS.md`, `.codex/agents/` y `.agents/skills/`, y reiniciar la sesión de Codex.
