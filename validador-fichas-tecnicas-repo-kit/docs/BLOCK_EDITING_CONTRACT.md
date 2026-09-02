# Contrato de edición de bloques repetibles

- Issue: DEV-507
- Fase: 5
- Estado: implementado en el núcleo de decisión; la interfaz de edición no existe todavía
- Módulo: `pharma_validator_api.block_editing`
- Base normativa: plan de Fase 5; DEV-011/ADR-0004; reglas no negociables de `AGENTS.md`

## Alcance

Implementa crear, eliminar, ordenar, fusionar, marcar no aplicable y revertir sobre las ocurrencias de un bloque repetible. Es puro: transforma una lista de ocurrencias en otra y describe qué cambió. No persiste, no escribe auditoría y no renderiza.

Cada operación devuelve un `BlockEdit` con la operación, el resultado, las ocurrencias afectadas y el motivo. La auditoría de la especificación 11 consumirá esa descripción en lugar de reconstruirla a posteriori.

## Por qué cada operación es delicada

La regla no negociable del proyecto es modelar los bloques repetidos como ocurrencias explícitas y no colapsarlos. Las cinco operaciones que pide el plan de Fase 5 son, precisamente, las que pueden violarla. Por eso cada una lleva su salvaguarda:

| Operación | Salvaguarda |
|---|---|
| crear | no puede declarar procedencia de origen |
| eliminar | una ocurrencia importada exige comentario |
| reordenar | debe cubrir exactamente las existentes |
| fusionar | exige comentario y falla ante valores en conflicto |
| marcar no aplicable | conserva los valores intactos; exige comentario |
| revertir | reversible y auditada; exige comentario |

## Crear no fabrica procedencia

Una ocurrencia añadida por un revisor no puede declarar `origin_provenance`. Si pudiera, una fila inventada resultaría indistinguible de una importada del maestro, y la procedencia dejaría de significar nada.

## Eliminar distingue el origen

Una ocurrencia importada representa una fila real de la fuente. Borrarla en silencio sería descartar un dato de origen, así que exige comentario y el mensaje sugiere marcarla `no_aplicable`, que suele ser la operación correcta.

Una ocurrencia que añadió el propio revisor se retira sin fricción: no había nada de la fuente que preservar.

## Reordenar no es una vía para borrar

La secuencia solicitada debe incluir todas las ocurrencias y ninguna más. Omitir una la eliminaría de hecho, esquivando la salvaguarda de eliminación. Los ordinales se reasignan consecutivos desde 1 tras cada operación.

## Fusionar: la operación más peligrosa

Fusionar colapsa dos filas en una y contradice directamente la regla de ocurrencias explícitas. Además de comentario obligatorio, **falla si las dos ocurrencias afirman valores distintos para el mismo campo**.

Elegir uno de los dos sería decidir un dato clínico en nombre del revisor sin dejar constancia de qué se descartó. El conflicto debe resolverse antes, de forma visible.

Sí se permite fusionar ocurrencias **complementarias**: cuando una aporta un campo que la otra tiene ausente, no hay contradicción y ningún valor se pierde. La comprobación es simétrica: fusionar A sobre B y B sobre A dan el mismo resultado. Un campo ausente en ambas sigue ausente y no se inventa.

## Marcar no aplicable conserva los valores

DEV-011 lo dice explícitamente: un bloque puede marcarse `not_applicable` lógicamente **sin alterar ocurrencias**, y es reversible y auditado. La marca no borra ni vacía los valores: la ocurrencia sigue ahí con su contenido, señalada como no aplicable.

Marcar y revertir exigen comentario, porque ambas son decisiones humanas sobre la pertinencia de un dato.

## Un error corregido durante la implementación

La primera versión de la fusión comparaba el valor de origen contra el de destino sin comprobar si el de **origen** era ausente. Un campo ausente en la ocurrencia de origen frente a un valor en la de destino se tomaba como conflicto, cuando en realidad es el caso complementario que la fusión debe permitir.

El fallo lo detectó una prueba antes de que existiera interfaz. Se añadió además la prueba de simetría que faltaba, porque la comprobación original solo miraba el ausente en un sentido.

## Verificación realizada

- 22 pruebas: creación con renumeración, procedencia fabricada rechazada, identificador duplicado, eliminación de fila importada con y sin comentario, eliminación de fila añadida por el revisor, reordenación completa y su uso indebido para descartar, fusión con comentario, con conflicto, complementaria, simétrica y con ausentes en ambas, marca no aplicable que conserva valores, reversión, ordinal inválido, campo repetido y determinismo.
- Ruff y mypy estricto sin incidencias en 32 ficheros.

## Límites

- No persiste las ocurrencias ni escribe la auditoría append-only: es DEV-609.
- No implementa la interfaz de edición ni su navegación por teclado.
- No decide qué bloques son repetibles: lo determina el modelo canónico.
- No resuelve conflictos de procedencia entre fuentes: eso es DEV-307.
