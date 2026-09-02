# Contrato de reglas de pre-relleno

- Issue: DEV-510
- Fase: 5
- Estado: implementado en el núcleo de decisión; la pantalla que lo consume no existe todavía
- Módulo: `pharma_validator_api.prefill_policy`
- Base normativa: especificación v2, 9 («Reglas de pre-relleno — CRÍTICO»), 9.2 y 9.3

## Por qué existe

La especificación dedica su sección más enfática a esto: un farmacéutico que revisa 300 registros en una mañana acepta lo que la pantalla le propone. Es sesgo de automatización y está documentado. Si la herramienta rellena un campo que requiere criterio clínico, el resultado es **un dato que nadie decidió realmente, con la apariencia de haber sido validado**.

El módulo convierte esa advertencia en una decisión ejecutable y comprobable. La pantalla consume estas decisiones en lugar de reimplementarlas, de modo que la regla se pueda probar sin renderizar nada y no dependa de que cada componente de interfaz la recuerde.

## Las cuatro políticas

| Política | Presentación | Casilla |
|---|---|---|
| `proponer_valor` | valor extraído ya escrito, junto a su evidencia | precargada |
| `proponer_opciones` | evidencia y candidatos normalizados | ninguno marcado |
| `solo_evidencia` | lo que dice el documento y un aviso | vacía |
| `oculto` | no aparece en esta pantalla | no visible |

En `solo_evidencia` la evidencia **sí** se muestra: es lo que permite juzgar sin decidir por nadie. Lo que no se muestra es un número sugerido.

## El ejemplo canónico

La ficha técnica de omeprazol declara una posología de 20–40 mg/día. El campo `ADUDOMAXDIA` pide un **techo de alerta**, que no es lo mismo. La pantalla muestra la evidencia del apartado 4.2, la casilla vacía y el aviso de que la ficha no declara dosis máxima y el valor es criterio farmacéutico.

Y nada más. El número lo escribe una persona, y queda registrado quién.

## La política es una regla, no una recomendación

`plan_field_presentation` no confía en que quien llama respete la política. Si recibe un valor propuesto para un campo protegido, **lo descarta** en lugar de mostrarlo. Un fallo en la capa que llama no puede convertirse en un valor preseleccionado en pantalla.

`assert_no_protected_preselection` comprueba una pantalla completa y detecta incluso un plan construido a mano que intente saltarse la regla. Es la prueba automática de políticas de pre-relleno que exige la puerta de salida de Fase 5.

## Confirmación en bloque

La especificación 9.3 la permite solo para campos `proponer_valor` y solo si su evidencia está visible en pantalla en ese momento. Nunca para `proponer_opciones` ni `solo_evidencia`, ni desde una vista de listado donde la evidencia no se esté mostrando.

`assert_bulk_confirmation_allowed` valida ambas condiciones antes de aplicar la confirmación: la visibilidad de la evidencia es un argumento explícito, no una suposición. Un campo `proponer_valor` **sin** evidencia tampoco admite bloque.

## Relación con la Fase 4

DEV-405 impide que se persista una propuesta cuya cita no exista literalmente. Este módulo impide que una propuesta, aun siendo válida, se presente como decisión tomada en un campo que requiere criterio humano.

Son barreras distintas contra riesgos distintos: una protege la veracidad de la cita, la otra la autoría de la decisión. Ninguna sustituye a la otra.

## Verificación realizada

- 13 pruebas: las cuatro políticas, el ejemplo canónico `ADUDOMAXDIA`, valor descartado en campo protegido, comprobación sobre pantalla completa, plan manipulado detectado, confirmación en bloque permitida y denegada por política y por evidencia no visible, y determinismo.
- Ruff y mypy estricto sin incidencias en 28 ficheros.

## Límites

- No implementa la pantalla de tres zonas, la navegación por teclado ni el guardado incremental: son DEV-503, DEV-504 y DEV-505.
- No mide `segundos_empleados` (DEV-508) ni gestiona la cola de trabajo (DEV-502).
- No registra quién decide: la identificación de usuario es DEV-501, y la especificación 10.1 advierte de que sin autenticación la firma es declarada, no demostrada.
- No decide la política de cada campo: la trae el catálogo, mapeada desde `veredicto` según la especificación 6.
