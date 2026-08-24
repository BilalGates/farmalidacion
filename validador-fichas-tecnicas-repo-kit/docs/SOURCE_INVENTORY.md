# Inventario y lectura de los ficheros de partida

## 1. Control de versión

Los hashes de esta tabla corresponden a los ficheros recibidos el 24 de agosto de 2026. Los originales deben mantenerse fuera de Git en `data/reference/raw/`.

| Fichero | SHA-256 | Papel |
|---|---|---|
| `ESPEC_validador_fichas_tecnicas.md` | `d951f0a23787a0355fc9f9f7e1e0c4d2e40441f7f5ef249492b4742fb29173a4` | Especificación funcional y técnica v2 |
| `Catalogo_campos_clinicos_medicamentos.xlsx` | `a10160ebe5c7fe0b5d2a35a12d4597c982bacdafe04cb0f8d98c437183d19eac` | Catálogo de configuración inicial |
| `Estudio carga maestros con IA.xlsx` | `f3522d062e93c3bdb4366e7974edb6e3591427a375fcc7cef3ac29d70468f45e` | Estudio de fuentes, alcance y esfuerzo |
| `PrincipioActivoCargaMaster-22062026.xlsx` | `89e6806b4cba7d6724533bfdc29ea834056223872385f08c080b72b965448e6c` | Maestro de principios activos |
| `Medicamento-cargaMaster25062026.xlsx` | `4b87aeac96ea220126c090d755fa5bfbaabe7aec304cfccb2e15537bd96cbf1b` | Maestro de medicamentos y bloques relacionados |
| `Especialidades-CargaMaster190626.xlsx` | `2117c3e33c05158dd10f81ce07424dd1ea2d0f36747faea3ad9c630b2d4ab37b` | Maestro de especialidades y excipientes |
| `Interacciones-cargaMaster250626.xlsx` | `f72d368f7590c1c41a886055f58b131305cb24c383cfa80f3028656fe351037f` | Maestro masivo de interacciones |
| `OMEPRAZOL 20 MGrelleno.xlsx` | `5d11b447e5c3d9eed73b03e45d9cfe69c8cec54d89729e23a2bf95ae1564192b` | Caso completo de referencia y prueba de ida y vuelta |

## 2. Fotografía estructural

### Catálogo de campos

- Hoja principal con 390 filas físicas y 10 columnas.
- El análisis funcional previo identificó 353 definiciones utilizables: 245 clínicas y 108 técnicas o de clave.
- Hay nombres técnicos repetidos en distintos contextos; el nombre de campo por sí solo no es una clave suficiente.
- Deben preservarse las variantes de obligatoriedad `S`, `N`, `S*` y `N*` hasta aclarar el significado del asterisco.
- El catálogo necesita subbloque, rol, cardinalidad y nombre exacto de exportación.

### Principio activo

- Hoja `General`: 7.190 filas físicas, incluida cabecera, y 101 columnas.
- Hojas `Frecuencia`, `Via`, `ConsejosAdministracion` y `DatosAnaliticos` contienen solo cabecera en el fichero recibido.
- El fichero actúa principalmente como línea base de claves y datos generales.

### Medicamento

- `General`: 6.343 filas físicas.
- `Composicion`: 4.212.
- `Indicacion`: 19.767.
- `Via`: 5.724.
- `Links`: 22.215.
- `Frecuencia` y `Prescripcion` contienen solo cabecera en el maestro general.
- La cardinalidad real confirma que un medicamento puede tener múltiples composiciones, indicaciones, vías y enlaces.

### Especialidades

- `General`: 29.851 filas físicas.
- `Excipientes`: 18.621.
- La relación especialidad-excipiente es repetible.
- El análisis previo detectó 184 identificadores paternos de excipientes sin correspondencia en la hoja general; debe reproducirse y clasificarse como incidencia de integridad.

### Interacciones

- `General`: 436.149 filas físicas.
- `AplicaA`: 436.149 filas físicas.
- Por volumen y naturaleza, no debe reconstruirse desde 500 fichas técnicas. La recomendación inicial es tratarlo como migración y conciliación separada.

### Omeprazol de referencia

- 22 hojas.
- Incluye bloques de principio activo, medicamento, especialidad y transversales.
- Demuestra que frecuencias, vías, consejos, datos analíticos, composiciones, indicaciones, excipientes, enlaces e interacciones son repetibles.
- Algunas hojas presentan miles de filas físicas por formato o fórmulas heredadas; el importador debe distinguir filas materialmente pobladas de rango usado aparente.
- Debe convertirse en fixture de aceptación y no editarse manualmente durante la prueba.

## 3. Consecuencias para el diseño

- No existe una relación simple uno-a-uno entre ficha técnica y registro de destino.
- No basta con una restricción única por `registro_id + campo_id`.
- El origen de un dato puede ser CIMA estructurado, ficha técnica, maestro actual o decisión farmacéutica.
- Los importadores deben conservar los valores originales, registrar diagnósticos y evitar coerciones silenciosas.
- La exportación debe reconstruir filas por bloque y no solo una fila ancha por medicamento.

## 4. Pruebas mínimas sobre estos ficheros

1. Verificación de hashes.
2. Perfilado reproducible de hojas, filas, columnas, tipos, nulos y duplicados.
3. Informe de integridad referencial entre hojas.
4. Detección de nombres de campo ambiguos y claves naturales.
5. Importación del omeprazol a un modelo canónico.
6. Exportación de vuelta y comparación semántica hoja por hoja.
7. Informe explícito de cualquier pérdida, normalización o diferencia de orden.
