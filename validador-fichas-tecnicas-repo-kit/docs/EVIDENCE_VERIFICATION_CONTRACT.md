# Contrato de verificación literal de evidencia

- Issue: DEV-405
- Fase: 4
- Estado: implementado
- Módulo: `pharma_validator_api.evidence_verification`
- Base normativa: especificación v2, 8.1 (regla de oro del extractor) y 9

## Alcance

El módulo dictamina si una propuesta del extractor puede persistirse. Es puro y determinista: no persiste, no consulta la base de datos, no llama al modelo y no decide la política de pre-relleno de un campo, que recibe como entrada.

No requiere GPU y no depende de D-013. Es la barrera que hace verificable la puerta de salida de Fase 4: cero propuestas persistidas con evidencia literal inválida.

## Regla de oro

Ninguna propuesta sin cita. Si el extractor no puede señalar el fragmento exacto del que sale el valor, no propone nada. La verificación es automática y previa a persistir; no depende de la buena voluntad del modelo.

Una propuesta rechazada **nunca se corrige, se recorta ni se reescribe**. Se devuelve un diagnóstico y la propuesta se descarta como incidencia.

## Cadena canónica

La cita se verifica contra el texto de la sección **tal cual se almacenó** en la versión inmutable. No se desescapan entidades HTML, no se normalizan espacios y no se extrae texto del marcado.

Esto es coherente con `docs/GOLD_SET_ANNOTATION_CONTRACT.md` y no es un detalle menor: los artefactos del corpus conservan `&#237;`, `&#xa0;` y etiquetas. Verificar contra una proyección legible admitiría como válida una cita que no existe literalmente en la versión, que es exactamente lo que la regla de oro impide.

Un intervalo puede partir una entidad o una etiqueta. Si los desplazamientos reproducen exactamente el texto citado, la cita es válida: expandirla hasta un límite "limpio" cambiaría el literal.

## Verificación

Se admite una propuesta con valor solo si:

1. la política del campo no es `oculto`;
2. la política no es protegida con opción preseleccionada;
3. la sección citada pertenece a la versión documental;
4. la sección tiene texto verificable;
5. los desplazamientos delimitan un intervalo dentro de la sección;
6. la subcadena en ese intervalo es **exactamente igual** al texto citado;
7. la cita mide entre 10 y 400 caracteres, según 8.2;
8. el estado y la política son coherentes con lo que se propone.

`no_encontrado` se admite sin cita, pero solo si no aporta valor ni opciones: declarar ausencia es legítimo; declarar ausencia con valor no lo es.

## Diagnósticos

| Estado | Significado |
|---|---|
| `admitida` | la cita coincide literalmente; la propuesta puede persistirse |
| `rechazada_politica_oculta` | la política del campo es `oculto` |
| `rechazada_sin_evidencia` | propuesta con valor y sin cita |
| `rechazada_seccion_desconocida` | la sección citada no pertenece a la versión |
| `rechazada_seccion_sin_texto` | la sección existe pero no tiene texto verificable |
| `rechazada_offsets_invalidos` | intervalo ausente, vacío o fuera de la sección |
| `rechazada_texto_no_literal` | la subcadena no coincide con el texto citado |
| `rechazada_longitud_evidencia` | la cita mide menos de 10 o más de 400 caracteres |
| `rechazada_valor_sin_soporte` | el valor o las opciones contradicen estado o política |
| `rechazada_opciones_preseleccionadas` | un campo protegido llega con opción preseleccionada |

## Secciones de agrupación sin texto

Al validar contra el corpus real se observó que **1.464 de 13.907 secciones (10,5%) carecen de `contenido`**. Son cabeceras de agrupación —"4. DATOS CLÍNICOS", "5. PROPIEDADES FARMACOLÓGICAS", "6. DATOS FARMACÉUTICOS"— cuyo texto vive en las subsecciones.

Una cita contra ellas no es verificable. El módulo la rechaza con `rechazada_seccion_sin_texto`, distinto de un intervalo mal calculado: la incidencia que hay que investigar no es la misma, y confundirlas ocultaría un extractor que cita sistemáticamente cabeceras.

Esta observación es factual sobre el corpus capturado en DEV-208. No se repara el corpus ni se sintetiza contenido para esas secciones.

## Protección frente al sesgo de automatización

La verificación también hace cumplir las reglas de pre-relleno de la especificación 9, porque una propuesta que llega preseleccionada no debe llegar a persistirse aunque su cita sea válida:

- `oculto` no persiste ninguna propuesta;
- `solo_evidencia` admite cita pero nunca valor propuesto;
- `proponer_opciones` admite opciones sin ninguna preseleccionada, nunca un valor único;
- `proponer_valor` admite valor con cita verificada.

Ningún campo protegido puede quedar preseleccionado por la vía del extractor. La comprobación equivalente en la interfaz corresponde a Fase 5 y no la sustituye este módulo.

## Verificación realizada

- 19 pruebas específicas, incluidas cita inventada, cita desplazada un carácter, cita desescapada, cita que parte una entidad, sección desconocida, sección sin texto, longitudes límite y determinismo.
- Comprobación sobre una ficha real del corpus `cima-corpus-random-203`: cita válida admitida, cita inventada rechazada por `rechazada_texto_no_literal`, cita contra sección de agrupación rechazada por `rechazada_seccion_sin_texto`.
- Suite completa 112/112: 91 en `backend/` (819,99 s) y 21 en `tests/`. Ruff y mypy estricto sin incidencias en 23 ficheros.

## Límites

- No implementa el extractor, el cliente del servidor local ni la agrupación por sección: son DEV-401, DEV-402 y DEV-404.
- No persiste propuestas ni define su tabla; la persistencia llegará con el motor de extracción.
- No fija umbrales de confianza ni degradación por campo: es D-015 y depende de los resultados de DEV-408.
- No segmenta la ficha en secciones: consume secciones ya identificadas.
