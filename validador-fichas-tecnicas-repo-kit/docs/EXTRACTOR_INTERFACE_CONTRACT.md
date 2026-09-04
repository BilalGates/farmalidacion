# Contrato de la interfaz `ExtractorLLM`

- Issue: DEV-401
- Fase: 4
- Estado: implementado
- Módulo: `pharma_validator_api.extractor`
- Base normativa: especificación v2, 8 (motor de extracción), 8.1, 8.3 y 8.4

## Alcance

Define la interfaz sustituible entre el sistema y el motor de inferencia local, la petición agrupada por sección y la ejecución que verifica cada propuesta antes de admitirla.

No abre sockets, no elige modelo, no depende de hardware y no persiste. El adaptador real contra el servidor OpenAI-compatible es DEV-402 y sí requiere D-013.

## Lo que es sustituible y lo que no

La especificación exige que el código hable con el modelo a través de una interfaz con implementaciones intercambiables por configuración, para no acoplarse a un motor concreto. Eso es `ExtractorLLM`: quien la implemente decide cómo obtiene sus propuestas.

Lo que **no** es sustituible es la admisión. `run_extraction` verifica toda propuesta con el verificador literal de DEV-405 antes de considerarla admitida. Una implementación no puede declararse a sí misma válida: devuelve candidatas, no decisiones. Esta separación es deliberada, porque la regla de oro de 8.1 dejaría de ser una garantía por construcción si el adaptador pudiera saltársela.

## Agrupación por sección

`SectionRequest` reúne todos los campos que dependen de un apartado y se resuelve en una sola llamada, como exige la especificación 8: con ~150 campos extraíbles y ~12 apartados relevantes, agrupar reduce de unas 150 llamadas por documento a unas 15. Es la diferencia entre un proceso de horas y uno de días.

La sección debe pertenecer a la versión documental solicitada, y los campos de una petición deben ser únicos. Ambas condiciones se validan al construir la petición, no al ejecutarla.

## Identidad del extractor

Toda propuesta admitida queda atribuida a una `ExtractorIdentity` con versión de extractor y modelo. Sin esa atribución, un resultado de DEV-408 no es imputable a un modelo concreto y la comparación entre dos tamaños deja de ser interpretable, que es justamente lo que el hito 2 debe medir.

## Incidencias

`run_extraction` no interrumpe el lote ante un extractor que se comporta mal. Registra incidencias y sigue:

| Situación | Tratamiento |
|---|---|
| El extractor falla | incidencia; la sección devuelve cero propuestas admitidas |
| Propone un campo no solicitado | incidencia; la propuesta se descarta |
| Propone el mismo campo dos veces | incidencia; solo se evalúa la primera |
| No devuelve un campo solicitado | incidencia; no se inventa ausencia |
| Propone con cita inválida | rechazo verificado, con su diagnóstico |

Un fallo del extractor no bloquea la revisión manual con evidencia, según la puerta de salida de Fase 4.

## Degradación y `NullExtractor`

`NullExtractor` no propone ningún valor: devuelve `no_encontrado` para cada campo. Hace ejecutable el resto de la Fase 4 sin GPU y materializa la degradación elegante de 8.4.

Su existencia no es un atajo de pruebas. La especificación es explícita: la mayor parte del ahorro de tiempo no viene de que el sistema acierte el valor, sino de que coloca el apartado correcto de la ficha junto al campo correcto. El sistema debe ser útil con un extractor mediocre, y mejor con uno bueno. `NullExtractor` es el caso límite que lo demuestra.

## Verificación realizada

- 12 pruebas, entre ellas: propuesta honesta admitida con identidad atribuible; cita inventada rechazada; campo protegido con opción preseleccionada rechazado; fallo del extractor que no bloquea la revisión; campo no solicitado, duplicado y ausente como incidencias; determinismo.
- Prueba específica de que una implementación no puede puentear la verificación afirmando su propia validez.
- Ruff y mypy estricto sin incidencias en 24 ficheros.

## Límites

- No implementa el cliente del servidor local ni la decodificación guiada por esquema: son DEV-402 y DEV-403.
- No persiste propuestas ni define su tabla.
- No reanuda lotes: es DEV-406.
- No fija umbrales de confianza ni política por campo: es D-015, pendiente de DEV-408.
- No segmenta la ficha en secciones: consume secciones ya identificadas.

## Transporte hacia el servidor de inferencia (DEV-402) — 4 de septiembre de 2026

`pharma_validator_api.inference_backend` define **cómo se habla** con un servidor
compatible con la API de chat de OpenAI, no **con qué modelo** se habla. La
separación es deliberada: D-014 sigue pendiente de aceptación humana, y fijar el
modelo en el código convertiría en decisión de ingeniería una decisión que el
registro reserva a una persona.

Por eso `BackendConfig` exige `model` explícito y **falla sin él**. No existe
valor por defecto, ni endpoint por defecto, ni cuantización por defecto.

Garantías del transporte:

- **Reproducibilidad por defecto.** `temperature=0.0` y semilla fija. Una
  evaluación que no se puede repetir no es evidencia; el muestreo creativo debe
  pedirse explícitamente.
- **Salida guiada estricta.** Se solicita `response_format` de tipo
  `json_schema` con `strict`. Es la barrera que evita tener que "reparar" JSON,
  y reparar una respuesta malformada sería inventar contenido.
- **Los fallos se clasifican.** `timeout`, `transport` y `server_error` son
  transitorios y se reintentan con espera creciente. `invalid_json`,
  `schema_violation` y `empty_response` **no se reintentan**: con temperatura 0
  y semilla fija, repetir produce exactamente el mismo error y sólo gasta
  tiempo de GPU.
- **La atribución no se pierde.** Si el servidor responde con un modelo distinto
  del solicitado, la llamada falla. Publicar métricas de un modelo bajo el
  nombre de otro invalidaría toda la comparación de DEV-408.

Módulo puro: el envío HTTP se inyecta como función, de modo que el contrato se
prueba sin levantar un servidor. 11 pruebas.

**No cierra DEV-402.** El cliente HTTP real y la traducción del esquema a GBNF
—si el runtime elegido lo requiere— dependen de qué se acepte en D-014.
