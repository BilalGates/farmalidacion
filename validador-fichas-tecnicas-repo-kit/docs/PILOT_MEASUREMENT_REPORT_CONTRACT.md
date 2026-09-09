# Contrato del informe del conjunto de medida

DEV-511 requiere resultados humanos reales sobre 50 fichas; este contrato no
los sustituye. Define cómo consolidarlos de forma reproducible cuando existan.

Cada línea JSONL identifica ficha, entidad, modo (`manual` o `asistida`),
minutos observados, estados finales, propuestas corregidas y comparaciones de
doble revisión. No admite recuentos negativos, estados distintos de
`confirmado`, `corregido` y `no_consta`, ni numeradores superiores a sus
denominadores.

`scripts/build_pilot_report.py` produce:

- minutos medios por registro, entidad y modo;
- reparto de estados;
- tasa de propuestas corregidas;
- tasa de discrepancias en doble validación;
- completitud de las dos observaciones para cada una de las 50 fichas.

Una tasa sin denominador es `null`, nunca cero. El informe sólo marca `ready`
si existen exactamente las 50 fichas esperadas y cada una tiene observación
manual y asistida. Las observaciones sintéticas se rechazan. Un informe
incompleto sale con código 2 y no constituye evidencia de ahorro.
