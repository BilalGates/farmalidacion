# Revisión del maestro de medicamentos incorporado el 28-09-2026

El commit `0fafe34` sustituyó
`Catalogo_campos_clinicos_medicamentos/base/Medicamento-cargaMaster25062026.xlsx`.
Se comparó la versión anterior del propio Git con la versión actual, sin editar
ningún libro.

| Versión | Bytes | SHA-256 |
|---|---:|---|
| Anterior | 3.545.660 | `4b87aeac96ea220126c090d755fa5bfbaabe7aec304cfccb2e15537bd96cbf1b` |
| Actual | 3.574.767 | `9ecb56cc1cd590c4e49d63c7ce7993df059372af341407acd197a818cd1a50dc` |

Se compararon por coordenada las celdas OOXML presentes en las siete hojas,
incluyendo tipo (`t`), valor literal (`v` o texto inline) y fórmula (`f`). La
parte `xl/sharedStrings.xml` es byte a byte idéntica entre ambas versiones, por
lo que los índices de cadenas compartidas tienen el mismo significado.

| Hoja OOXML | Celdas en cada versión | Diferencias de tipo, valor o fórmula |
|---|---:|---:|
| sheet1 | 215.137 | 0 |
| sheet2 | 33.701 | 0 |
| sheet3 | 98.838 | 0 |
| sheet4 | 9 | 0 |
| sheet5 | 28.623 | 0 |
| sheet6 | 27 | 0 |
| sheet7 | 133.294 | 0 |
| **Total** | **509.629** | **0** |

Ambos ZIP contienen 26 partes. Cambiaron XML de hojas, estilos, tema, metadatos
y partes de configuración, aunque no el contenido de las celdas comparadas.
Esta evidencia admite la versión actual como entrada del importador y conserva
el hash previo como referencia histórica. No afirma equivalencia visual de
formatos ni igualdad byte a byte. La prueba de importación real sigue siendo el
control de cardinalidades, vínculos y diagnósticos.
