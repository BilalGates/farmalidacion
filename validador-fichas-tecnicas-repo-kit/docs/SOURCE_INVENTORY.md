# Inventario y lectura de los ficheros de partida

## 1. Control de versión

Los hashes de esta tabla corresponden a los ficheros recibidos el 24 de agosto de 2026. Los originales deben mantenerse fuera de Git en `data/reference/raw/`.

Ubicación operativa indicada por el responsable el 23 de septiembre de 2026 para
los tres maestros activos: `../Catalogo_campos_clinicos_medicamentos/base/`
(respecto a la raíz del repositorio). Se verificaron allí los tres SHA-256 de
esta tabla; el directorio está fuera de Git. El maestro de interacciones se
incorporará más adelante y no forma parte de esta ubicación actual.

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

## 3. Contrato real por hoja (cabeceras del snapshot activo)

Se inspeccionó solo la fila de cabeceras con los mismos parsers XML de los
importadores; no se escribieron los libros. Los tres importadores enumeran cada
hoja, conservan sus cabeceras y cargan cada celda material como valor literal con
procedencia a la fila Excel. Las hojas sin filas de datos también se registran.

| Libro | Hoja | Columnas | Función estructural / clave observada | Estado en el snapshot |
|---|---|---:|---|---|
| Especialidades | `General` | 120 | Registro de especialidad; `BN_IDEXTERNO`, `CODIGO_NACIONAL`, referencia `ME_IDEXTERNO`; `PVL`/`PVP` | Con datos |
| Especialidades | `Excipientes` | 9 | Ocurrencia repetible; `BN_IDEXTERNO` enlaza con la especialidad y `EX_IDEXTERNO` identifica excipiente | Con datos; hay huérfanos documentados |
| Medicamentos | `General` | 58 | Registro de medicamento; `MED_IDEXTERNO`, `ID_MEDICAMENTO`; incluye `MED_DCP` y `MED_ATC` | Con datos |
| Medicamentos | `Composicion` | 13 | Ocurrencia repetible de composición; referencias `MED_IDEXTERNO` y `PA_IDEXTERNO` | Con datos |
| Medicamentos | `Indicacion` | 8 | Ocurrencia repetible; referencias medicamento e indicación | Con datos |
| Medicamentos | `Frecuencia` | 9 | Ocurrencia repetible; referencias medicamento y frecuencia | Solo cabecera |
| Medicamentos | `Via` | 8 | Ocurrencia repetible; referencias medicamento y vía | Con datos |
| Medicamentos | `Prescripcion` | 27 | Ocurrencia de prescripción por `GRUPO_POBLACIONAL`, con frecuencia, vía, dosis, unidad y observaciones | Solo cabecera |
| Medicamentos | `Links` | 10 | Enlaces y presentación; columna `DESCRIPCION` duplicada en D y F | Con datos; el nombre de campo no es único |
| Principios activos | `General` | 101 | Registro de principio activo; `IDEXTERNO`, `ID_PRINCIPIO_ACTIVO`, `ATC`; incluye límites de dosis por población | Con datos |
| Principios activos | `Frecuencia` | 9 | Ocurrencia repetible; referencias `PA_IDEXTERNO` y frecuencia | Solo cabecera |
| Principios activos | `Via` | 9 | Ocurrencia repetible; referencias `PA_IDEXTERNO` y vía | Solo cabecera |
| Principios activos | `ConsejosAdministracion` | 19 | Ocurrencia de consejo por vía, forma farmacéutica y población | Solo cabecera |
| Principios activos | `DatosAnaliticos` | 19 | Ocurrencia de dato analítico; incluye corte, gravedad y poblaciones | Solo cabecera |

La carga conserva ambas columnas `DESCRIPCION` de `Links` como valores
independientes. `field_value.source_column_index` preserva el ordinal Excel y la
revisión etiqueta cabeceras repetidas con su letra (por ejemplo, `columna D` y
`columna F`), sin renombrar el campo fuente ni inferir su significado. La nueva
migración rellena esa coordenada en valores ya importados cuando puede
reconstruirla desde su identificador estable y el fragmento original.

El perfil confirma además 4.211 relaciones de composición inequívocas y deja
sin crear el puente especialidad→medicamento cuando no existe una única
coincidencia. En la hoja `Excipientes`, 275 filas quedan en cuarentena por padre
ausente (184 identificadores distintos). Estos resultados pertenecen al
importador y no autorizan a corregir los libros de origen.

## 4. Consecuencias para el diseño

- No existe una relación simple uno-a-uno entre ficha técnica y registro de destino.
- No basta con una restricción única por `registro_id + campo_id`.
- El origen de un dato puede ser CIMA estructurado, ficha técnica, maestro actual o decisión farmacéutica.
- Los importadores deben conservar los valores originales, registrar diagnósticos y evitar coerciones silenciosas.
- La exportación debe reconstruir filas por bloque y no solo una fila ancha por medicamento.

## 5. Pruebas mínimas sobre estos ficheros

1. Verificación de hashes.
2. Perfilado reproducible de hojas, filas, columnas, tipos, nulos y duplicados.
3. Informe de integridad referencial entre hojas.
4. Detección de nombres de campo ambiguos y claves naturales.
5. Importación del omeprazol a un modelo canónico.
6. Exportación de vuelta y comparación semántica hoja por hoja.
7. Informe explícito de cualquier pérdida, normalización o diferencia de orden.
