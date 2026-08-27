# Contrato verificado de la API CIMA

- Issue: DEV-201
- Fecha de verificación: 27 de agosto de 2026
- Fuente normativa consultada: [CIMA REST API v1.23](https://cima.aemps.es/cima/resources/docs/CIMA_REST_API.pdf)
- Catálogo oficial de publicación: [Datos abiertos de la AEMPS](https://sede.aemps.gob.es/datos-abiertos/)
- Estado: contrato documental verificado; cliente no implementado

## Alcance y límites

Este documento fija la superficie mínima que podrá usar DEV-202. No autoriza
descargas masivas, no define todavía persistencia ni completa las decisiones de
versionado de DEV-205.

Base oficial:

```text
https://cima.aemps.es/cima/rest/[METODO]
```

La documentación declara respuestas JSON codificadas en UTF-8 salvo los
formatos alternativos del contenido segmentado. No documenta autenticación.

## Endpoints mínimos de Fase 2

| Operación | Método y ruta | Parámetros documentados | Uso previsto |
|---|---|---|---|
| Buscar medicamentos | `GET /medicamentos` | `pagina`; `nombre`, `laboratorio`, `practiv1`, `practiv2`, `idpractiv1`, `idpractiv2`, `cn`, `atc`, `nregistro`, `npactiv`, `triangulo`, `huerfano`, `biosimilar`, `sust`, `vmp`, `comerc`, `autorizados`, `receta`, `estupefaciente`, `psicotropo`, `estuopsico` | muestreo y resolución inicial |
| Obtener medicamento | `GET /medicamento` | exactamente `cn` o `nregistro` según la búsqueda | metadatos estructurados y relación nregistro/presentaciones |
| Buscar presentaciones | `GET /presentaciones` | `pagina`; `cn`, `nregistro`, `vmp`, `vmpp`, `idpractiv1`, `comerc`, `estupefaciente`, `psicotropo`, `estuopsico` | contraste de CN por nregistro |
| Secciones disponibles | `GET /docSegmentado/secciones/{tipoDoc}` | `nregistro`; `tipoDoc=1` ficha técnica, `2` prospecto | inventario de secciones sin contenido |
| Contenido segmentado | `GET /docSegmentado/contenido/{tipoDoc}` | `nregistro` y `seccion` opcional; sin sección devuelve todas | adquisición literal por sección |
| Registro de cambios | `GET` o `POST /registroCambios` | `fecha` obligatoria en `dd/mm/yyyy`; `nregistro` repetible | detección incremental |
| Maestras | `GET /maestras` | `maestra`; opcionales `nombre`, `Id`, `codigo`, `estupefaciente`, `psicotropo`, `estuopsico`, `enuso` | catálogos estructurados cuando el mapeo esté aprobado |

El PDF también enumera `GET /presentacion/{codNacional}`, VMP/VMPP,
problemas de suministro, notas y materiales. No forman parte del cliente mínimo
de DEV-202 y no se incorporarán por conveniencia.

## Respuestas que deben conservarse sin pérdida

### Paginación

Los métodos paginados aceptan `pagina`. Una respuesta viva de
`/medicamentos` y otra de `/presentaciones` mostraron:

- `totalFilas`;
- `pagina`;
- `tamanioPagina`;
- `resultados`.

La documentación no fija página inicial, tamaño máximo, orden ni estabilidad
entre peticiones. DEV-202 debe tratarlos como comportamiento por verificar y
detectar repeticiones o cambios durante una captura.

### Medicamento

El objeto documentado incluye, entre otros:

- `nregistro`, `nombre`, `estado`, `comerc` y condiciones;
- `docs[]` con `tipo`, `url`, `secc`, `urlHtml` y `fecha`;
- `atcs[]`;
- `principiosActivos[]` con identidad, cantidad, unidad y orden;
- `excipientes[]` con identidad, cantidad, unidad y orden;
- `viasAdministracion[]`;
- `presentaciones[]` con `cn`, estado y comercialización;
- formas farmacéuticas y `dosis`.

Las listas y sus campos `orden` se conservarán tal como llegan. `pactivos`
y `dosis` son textos derivados o concatenados por CIMA y no sustituyen las
listas estructuradas.

### Documentos y secciones

El tipo documental `1` es ficha técnica y `2` prospecto. Las secciones
contienen `seccion`, `titulo`, `orden` y `contenido`.

`Accept` documentado para contenido:

- `application/json`: estructura JSON con número, título y contenido;
- `text/html`: contenido HTML sin cabeceras ni menú;
- `text/plain`: texto plano.

El valor literal adquirido, el `Content-Type` real, la URL, parámetros,
cabeceras relevantes, fecha de captura y hash deberán conservarse. No se
convertirá HTML a texto como sustitución silenciosa del original.

### Fechas y cambios

El PDF describe las fechas devueltas como Unix Epoch y añade `GMT+2:00`.
Esa formulación es ambigua porque Epoch es absoluto. DEV-202 debe conservar el
entero original y documentar cualquier conversión; no se asumirá zona horaria.

`registroCambios` devuelve `nregistro`, `fecha`,
`tipoCambio` (1 nuevo, 2 baja, 3 modificado) y `cambios[]`. Los códigos
documentados incluyen `estado`, `comerc`, `prosp`, `ft`,
`psum`, `notasSeguridad`, `matinf` y `otros`.

## Observaciones puntuales reproducidas

El 27 de agosto de 2026 se hicieron solicitudes pequeñas, sin persistir corpus:

- el ejemplo oficial `GET /medicamento?nregistro=51347` respondió 200,
  JSON UTF-8, con dos presentaciones y listas estructuradas;
- `GET /presentaciones?nregistro=51347&pagina=1` respondió con el
  envoltorio paginado y dos resultados;
- `GET /docSegmentado/secciones/1?nregistro=51347` devolvió 32 secciones;
- `GET /registroCambios` con fecha y nregistro respondió una lista.

La comprobación de `docSegmentado/contenido` quedó bloqueada después de dos
intentos: PowerShell no materializó la respuesta y Python recibió un cuerpo que
no pudo interpretar como JSON pese a `Accept: application/json`. No se probó
una tercera estrategia. DEV-202 debe capturar de forma controlada estado,
cabeceras y primeros bytes antes de decidir el parser.

## Incógnitas que el contrato oficial no cierra

- límites de ritmo, cuotas, `429` y cabecera `Retry-After`;
- timeouts, disponibilidad y política de reintentos;
- códigos y cuerpos de error para parámetros inválidos o inexistentes;
- `ETag`, `Last-Modified` y soporte de peticiones condicionales;
- tamaño, base y estabilidad de la paginación;
- orden garantizado de resultados y listas sin `orden`;
- comportamiento real de `Accept` en contenido segmentado;
- zona horaria efectiva de fechas Epoch;
- semántica de campos nuevos no presentes en v1.23.

Estas incógnitas no se rellenarán con supuestos. DEV-202 deberá usar parsers
tolerantes a campos adicionales, conservar respuestas originales y fallar de
forma visible ante formas incompatibles.

## Política interna, no contrato AEMPS

La especificación del proyecto propone aproximadamente cinco peticiones por
segundo, caché agresiva, timeout y reintentos exponenciales. Es una política
conservadora del proyecto: la documentación oficial v1.23 no publica una cuota.
DEV-202 podrá implementarla de forma configurable y respetuosa, sin presentarla
como garantía del proveedor.

## Criterio de entrada para DEV-202

Antes de persistir datos, DEV-202 debe probar con fixtures HTTP:

1. respuesta 200 documentada;
2. contenido segmentado para cada `Content-Type`;
3. campos adicionales y opcionales;
4. página vacía y página repetida;
5. timeout, error transitorio y límite de ritmo;
6. reintento idempotente y caché;
7. preservación byte a byte de la respuesta original.
