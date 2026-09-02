# Contrato del esquema de salida guiada

- Issue: DEV-403
- Fase: 4
- Estado: implementado
- Módulo: `pharma_validator_api.guided_schema`
- Versión de esquema: `guided-extraction-v1`
- Base normativa: especificación v2, 8.2 (formato de salida), 8.3 y 12.3

## Alcance

Construye el esquema JSON que gobierna la decodificación del modelo y valida la respuesta contra él. No llama al modelo, no verifica la evidencia y no persiste.

La especificación 8.3 es explícita: hay que usar decodificación guiada por esquema —guided decoding en vLLM, gramáticas GBNF en llama.cpp— y **no confiar en pedir JSON en el prompt y luego parsear**, porque con modelos locales pequeños eso falla lo bastante a menudo como para envenenar el proceso por lotes.

## El esquema es cerrado

`additionalProperties` es falso en la raíz y en cada resultado, y `required` cubre las ocho claves de 8.2. El motor no puede emitir claves no previstas ni omitir la cita.

`minItems` y `maxItems` se fijan al número de campos solicitados, y el enum de `campo` se restringe a esos nombres: la respuesta no puede traer campos ajenos a la petición ni dejar huecos. La longitud de `evidencia_texto` se acota a 10–400 caracteres, el mismo rango que exige 8.2 y que verifica DEV-405.

## La sección la aporta la petición, no el modelo

`parse_response` recibe el apartado citado como argumento. El esquema no le pide al modelo que repita la sección, porque hacerlo le permitiría declarar una distinta de la que se le dio y citar contra un texto que no se le mostró.

Esta decisión corrigió un fallo real durante la implementación: una primera versión leía la sección de la respuesta, con lo que toda propuesta con cita habría quedado sin sección y DEV-405 la habría rechazado por un motivo equivocado, ocultando la causa.

## Validación de tipos sin reparar

Los valores se validan contra `tipo_dato` del catálogo, derivando la restricción de `CHAR(n)`, `DECIMAL(p,s)` y `BIT`. La regla de 12.3 se aplica literalmente: si `CHAR(100)` recibe 112 caracteres, **falla con un error legible; no se trunca en silencio**.

En coherencia con las reglas no negociables, tampoco se redondea un decimal con exceso de escala, ni se convierte un `BIT` que no sea `0` o `1`, ni se relaja a texto libre un tipo no reconocido. Una respuesta malformada es un error explícito, nunca una propuesta parcialmente reconstruida: repararla introduciría un valor que el modelo no emitió.

## Relación con DEV-401 y DEV-405

Las tres piezas se encadenan y ninguna sustituye a otra:

| Issue | Responsabilidad |
|---|---|
| DEV-403 | la respuesta está **bien formada** y sus valores respetan el tipo declarado |
| DEV-401 | la petición se **agrupa por sección** y el resultado se atribuye a un modelo |
| DEV-405 | la cita **existe literalmente** en la versión inmutable |

Una propuesta bien formada puede seguir teniendo una cita inventada. Por eso el esquema no exime de la verificación literal, que se aplica después sobre cada propuesta.

## Verificación realizada

- 22 pruebas: esquema cerrado, recuento de resultados fijado, longitud de evidencia acotada, sección tomada de la petición e ignorada si el modelo la envía, campo desconocido, duplicado o ausente rechazados, estado inválido, `CHAR` que excede, `DECIMAL` con exceso de escala o precisión, `BIT` inválido, booleano no aceptado como desplazamiento y determinismo.
- Ruff y mypy estricto sin incidencias en 25 ficheros.
- 53 pruebas acumuladas en las tres piezas de Fase 4 sin GPU (DEV-401, DEV-403, DEV-405).

## Límites

- No implementa el cliente del servidor local ni traduce el esquema a GBNF: es DEV-402.
- No construye el prompt de 8.2 ni agrupa las llamadas: la agrupación es DEV-401 y DEV-404.
- No valida longitudes sobre el corpus completo: el informe de longitudes máximas de 12.3 es trabajo de exportación en Fase 6.
- No fija umbrales de `confianza`: es D-015, pendiente de DEV-408.
