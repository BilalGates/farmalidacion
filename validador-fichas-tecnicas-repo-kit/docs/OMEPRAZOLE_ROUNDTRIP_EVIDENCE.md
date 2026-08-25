# Evidencia DEV-008 — Round-trip semántico de omeprazol

## Resultado

El spike reconstruye `OMEPRAZOL 20 MGrelleno.xlsx` desde DEV-007 usando la versión original verificada exclusivamente como plantilla estructural inmutable. Elimina los contenidos materiales de cada celda procesada, los restaura desde el snapshot canónico y después compara origen y salida independientemente.

| Evidencia | Resultado |
|---|---:|
| Hojas | 22/22 |
| Valores materiales | 2.674/2.674 |
| Estructuras de hoja iguales | 22/22 |
| Diferencias | 0 |
| Normalizaciones aplicadas | 0 |
| Suite completa | 14/14 OK |

Se comparan nombres, ordinales y visibilidad; sistema de fechas; coordenada, tipo, literal, fórmula, atributos, estilo e identidad de cadena compartida de cada celda material; estructura sin payload material; conjunto de partes; y bytes de las partes auxiliares. Una prueba negativa altera una celda y confirma que se produce un `defect`.

## Reproducibilidad

Dos ejecuciones finalizaron en 8,165 s y 7,373 s. Los XLSX reconstruidos y los informes JSON fueron idénticos.

- Hash reproducible: `7d474de536f4e168636c286aabd4ab3339715dde04c3164900c58c5204926adf`.
- SHA-256 reconstruido: `9ec597794fecd3db3ef6b4488184a9780a26dd8f949c66f9b475b1b257d1095d`.
- SHA-256 original antes/después: `5d11b447e5c3d9eed73b03e45d9cfe69c8cec54d89729e23a2bf95ae1564192b`.

Los artefactos regenerables permanecen bajo `artifacts/`, fuera de Git.

## Límites

- Es un spike reversible, no el exportador definitivo del proveedor.
- La plantilla conserva estilos, merges, comentarios, rich text, dimensiones y celdas no materiales; el comparador verifica que las partes auxiliares no cambian.
- No se infieren claves naturales, identidades farmacéuticas ni relaciones de negocio.
- Las hojas de interacciones se preservan sin integrar su maestro en el piloto FT.
- El fixture contiene cero fórmulas; no se generaliza evidencia real sobre fórmulas complejas.
- ADR-0001 permanece propuesto y la puerta 0B requiere aceptación humana y decisiones abiertas resueltas.
