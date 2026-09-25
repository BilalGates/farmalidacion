# Glosario operativo del catálogo de medicamentos

## Propósito

Este vocabulario evita que «medicamento», «marca», «especialidad» y
«presentación» se usen como sinónimos en API, interfaz o documentación. Es el
contrato lingüístico de CAT-001 y aplica junto a ADR-0012.

## Términos

| Término de interfaz | Significado en el producto | Identificadores habituales | No equivale a |
|---|---|---|---|
| Producto comercial | Nombre comercial bajo el que se agrupa el contexto de navegación | nombre; vínculos a autorizaciones | CN, DCPF o DCP |
| Autorización CIMA | Identidad regulatoria y documental de un medicamento autorizado | `nregistro` | presentación o envase |
| Presentación | Unidad comercial concreta identificable en el catálogo | CN; vínculo a autorización y DCPF | marca completa |
| Código Nacional (CN) | Identificador de una presentación; se muestran seis dígitos de trabajo | seis dígitos canónicos; literal fuente opcional de siete | `nregistro`, DCPF o identificador interno |
| DCPF | Descripción clínica del producto con formato; añade contenido/tamaño de envase al producto clínico | código DCPF/VMPP | nombre comercial o CN |
| DCP | Descripción clínica del producto: sustancia(s), dosis y forma farmacéutica | código DCP/VMP | envase concreto |
| DCSA | Descripción clínica de sustancia activa; puede representar una sustancia o combinación normalizada | código DCSA/VTM | fila literal de composición sin verificar |
| Principio activo específico | Sustancia concreta que participa en la composición observada de una presentación/producto | código de principio activo y fuente | necesariamente una DCSA completa |
| Composición | Relación ordenada entre producto y uno o varios principios activos, con cantidad/unidad cuando proceda | vínculo tipado y ocurrencias | texto concatenado |
| Ficha técnica | Documento oficial versionado asociado a la autorización | versión CIMA, apartado y hash | estado canónico editable |
| Estado canónico | Valor vigente mantenido por la organización | revisión y versión del registro | valor original de una fuente |

## Reglas de lenguaje de interfaz

- Mostrar «Presentación» cuando exista CN; no «Marca (CN)».
- Mostrar siempre el nivel junto al identificador: `CN 654789`, `DCPF …`,
  `DCP …`, `DCSA …` o `nregistro …`.
- «Medicamento» puede usarse en textos generales, pero no como etiqueta de una
  entidad cuando el nivel sea necesario para actuar.
- «Huérfano» describe una condición regulatoria del medicamento, no un registro
  sin padre. Las incidencias referenciales se denominan «sin relación padre».
- «Especial control» no se presenta como sinónimo genérico de droga; la pantalla
  muestra la condición catalogada concreta y su fuente.
- Un dato sin clasificación se muestra como «Sin clasificar», nunca como
  original por defecto.

## Código Nacional

La pantalla admite búsqueda por seis o siete dígitos. Hasta aprobar la regla de
control, el sistema sólo puede:

1. comprobar que la entrada sea numérica y tenga la longitud esperada;
2. extraer los seis primeros dígitos como término de búsqueda cuando se aportan
   siete;
3. conservar el literal completo y declarar que el control no fue validado;
4. impedir que esta representación provisional cree o fusione identidades.

La vinculación histórica `exact_national_code_v1` no cambia retroactivamente.
CAT-002 publicará una nueva regla si la evidencia autoriza equivalencias.

## Clasificaciones

### Clase comercial, de valor único y versionada

- `original`
- `generico`
- `biosimilar`
- `sin_clasificar`

### Condiciones, de cardinalidad múltiple

- `huerfano`
- `estupefaciente`
- `psicotropico`
- `especial_control_medico`
- `uso_hospitalario`
- otras condiciones aceptadas posteriormente

Cada clasificación o condición conserva fuente, versión, vigencia y estado de
revisión. La lista no determina consejo clínico ni prioridad de revisión.

## Casos de aceptación de CAT-001

Los datos sintéticos versionados en
`data/examples/medication-domain-acceptance.json` fijan únicamente estructura:

1. una autorización y producto comercial con dos presentaciones/CN;
2. DCPF distintos por contenido de envase;
3. DCP relacionado con más de un principio activo;
4. búsqueda equivalente por literal de seis y siete dígitos sin perder ninguno;
5. clase comercial y condiciones coexistiendo sin sobrescribirse.

Los nombres y códigos sintéticos no se usarán para validar reglas clínicas ni
se mezclarán con datos REAL.

