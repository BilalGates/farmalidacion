# Mapa estructural de campos de los maestros farmacéuticos

## Alcance

Este mapa conecta cabeceras observadas con conceptos del catálogo sin cambiar
los Excel ni declarar equivalencias clínicas no aprobadas. Resume los tres
libros de `Catalogo_campos_clinicos_medicamentos/base`. Las referencias y
cardinalidades observadas se detallan en
`EXTERNAL_IDENTIFIER_AUDIT.md`, `TARGET_RECORD_RELATIONSHIP_EVIDENCE.md` y
`CARDINALITY_KEY_EVIDENCE.md`.

## Mapeo con evidencia estructural

| Nivel/concepto | Libro y hoja | Campos observados | Evidencia segura | Estado y límite |
|---|---|---|---|---|
| Presentación / CN | `Especialidades` · `General` | `CODIGO_NACIONAL`, `BN_IDEXTERNO`, `ID_ESPECIALIDAD`, `ME_IDEXTERNO` | El CN aparece en el registro de especialidad y es único en las 29.850 filas de esta versión. `ME_IDEXTERNO` referencia el nivel Medicamento. | El CN identifica la presentación en el modelo aprobado. No demuestra que `BN_IDEXTERNO` sea producto comercial ni autorización CIMA. |
| Medicamento / DCP candidato | `Medicamentos` · `General` | `MED_IDEXTERNO`, `ID_MEDICAMENTO`, `MED_DCP`, `MED_ATC`, `FF_ID_FORMA_FARMACEUTICA` | `MED_IDEXTERNO` identifica el nivel Medicamento y recibe referencias desde Especialidades. Composición enlaza filas repetibles a principios activos. | El nivel se proyecta como DCP según ADR-0012. La semántica precisa de los campos descriptivos debe respetar su cabecera y conservar el literal. |
| Composición | `Medicamentos` · `Composicion` | `MED_IDEXTERNO`, `PA_IDEXTERNO`, `PA_ID_PRINCIPIO_ACTIVO`, `PA_DESCRIPCION`, `CANTIDAD`, `UN_ID_UNIDAD` | Cada ocurrencia enlaza medicamento y principio activo por identificadores literales; `CANTIDAD` y unidad permanecen en la misma ocurrencia. Se observan hasta 22 composiciones por medicamento en este snapshot. | Puede sostener relaciones DCP→principio activo específico. No concatenar componentes ni convertir esta fila en un código DCSA. |
| Principio activo específico | `Principios activos` · `General` | `IDEXTERNO`, `ID_PRINCIPIO_ACTIVO`, `DESCRIPCION`, `ATC` | `IDEXTERNO` es único en las 7.189 filas del snapshot; `PA_IDEXTERNO` es la referencia desde Composición. | Representa el principio activo específico del maestro. No equivale automáticamente a una DCSA/VTM. |
| Excipiente | `Especialidades` · `Excipientes` | `BN_IDEXTERNO`, `EX_IDEXTERNO`, `EX_ID_EXCIPIENTE`, `EX_DESCRIPCION`, `CANTIDAD` | La hoja mantiene ocurrencias repetibles y referencia a la especialidad mediante `BN_IDEXTERNO`. | No confundir el prefijo `EX_` ni el campo de descripción con un principio activo. Filas sin padre permanecen en cuarentena. |
| Indicación, frecuencia, vía y prescripción | Hojas homónimas de `Medicamentos` y `Principios activos` | identificador padre (`MED_IDEXTERNO` o `PA_IDEXTERNO`) más identificadores del bloque | Los importadores conservan hojas y ocurrencias por separado; varias hojas de este snapshot solo contienen cabecera. | La hoja vacía no significa que el concepto no exista. No fabricar filas para completar la jerarquía. |

## Niveles sin campo fuente explícito identificado

- **Producto comercial y autorización CIMA:** los maestros observados no
  contienen `nregistro`. Las claves `BN_IDEXTERNO`, `ME_IDEXTERNO` y
  `CODIGO_NACIONAL` mantienen ámbitos distintos. La asociación con autorización
  requiere evidencia CIMA versionada.
- **DCPF/VMPP:** no se observó una cabecera identificada explícitamente como
  DCPF/VMPP. El enlace Especialidad→Medicamento no basta para saltar a DCPF.
  Las dos columnas `DESCRIPCION` de `Medicamentos/Links` (D y F) quedan
  diferenciadas por posición, pero su función no se deduce del nombre.
- **DCSA/VTM:** no se observó un identificador DCSA separado. La composición
  del maestro puede contener varios principios activos específicos, pero no
  determina por sí sola una agrupación DCSA.

## Reglas para actualizar este mapa

1. Conservar libro, hoja, cabecera, posición de columna y literal fuente.
2. Etiquetar cada relación como observada, aprobada por ADR o pendiente de
   validación funcional; no convertir unicidad de un snapshot en regla histórica.
3. Añadir una equivalencia nueva solo con definición del emisor o acuerdo
   farmacéutico registrado.
4. Verificar las 14 hojas y los bloques repetibles al comparar una versión
   futura. Una hoja vacía se conserva en el inventario.
