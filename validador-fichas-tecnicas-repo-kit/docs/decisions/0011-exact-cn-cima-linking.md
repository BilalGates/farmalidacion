# ADR-0011 — Vinculación exacta CN–CIMA

- Estado: aceptado por instrucción del responsable, 2026-09-09
- Decisiones relacionadas: D-006, D-027

## Decisión

Vincular una versión documental CIMA con un registro de especialidad únicamente
cuando `CODIGO_NACIONAL` coincide literalmente y el CN identifica exactamente
un registro maestro y un `nregistro` CIMA. No se normalizan ceros, no se usa
similitud y no se heredan decisiones entre registros.

El vínculo conserva la versión documental concreta y declara
`exact_national_code_v1` como regla. Los casos sin correspondencia o ambiguos
se informan y no se escriben. La ejecución es idempotente.

## Evidencia

La auditoría previa encontró 706 coincidencias exactas únicas y cero ambiguas
en el corpus piloto de 500 documentos. La materialización real reprodujo esos
706 enlaces, y la segunda ejecución creó cero enlaces.

## Consecuencias

La interfaz puede presentar evidencia CIMA en los 706 registros enlazados y el
mantenimiento copiará esos vínculos a cada versión posterior. Los restantes CN
seguirán sin CIMA hasta ampliar el corpus; ausencia de vínculo no implica que el
medicamento no exista en CIMA.
