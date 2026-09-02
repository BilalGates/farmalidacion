# Contrato de medición de tiempo por campo

- Issue: DEV-508
- Fase: 5
- Estado: implementado en el núcleo de cálculo; la captura de foco en la interfaz no existe todavía
- Módulo: `pharma_validator_api.time_measurement`
- Base normativa: especificación v2, 7.2, 10.2 y 17

## Alcance

Calcula `segundos_empleados` por campo a partir de intervalos de foco ya observados. Es puro: no lee relojes, no depende de la interfaz y no persiste.

## Por qué importa

El piloto existe para medir. La especificación 7.2 lo dice sin rodeos: **sin este dato la comparación de la sección 17 no se puede hacer**. Y la sección 10.2 fija `segundos por campo validado` como la métrica que gobierna todas las decisiones de interfaz: cualquier elemento decorativo que no reduzca ese número sobra.

El piloto de medición compara un farmacéutico trabajando a mano contra otro con la herramienta. Ese dato sustituye a la estimación teórica de ahorro y es lo que debe decidir si se amplía al catálogo completo. Una medición mal hecha no es un detalle técnico: es una decisión de negocio tomada sobre una cifra falsa.

## El descuento de inactividad

7.2 exige descontar la inactividad por encima de **60 segundos**. Cada tramo de foco se cuenta entero hasta ese umbral; lo que exceda se descarta.

No es un refinamiento opcional. Un revisor que deja la pantalla abierta durante la comida convertiría un campo de 8 segundos en uno de 3.600 y arruinaría la media de la sesión. Una prueba lo comprueba directamente: con dos campos, uno honesto de 8 segundos y otro abandonado una hora, la media resultante es 34 segundos y no 1.804.

Un tramo de exactamente 60 segundos **no** se marca como recortado: el umbral es el límite de lo que cuenta, no el principio de lo que sobra.

## El tiempo descartado se informa

`discarded_seconds` y `was_capped` se devuelven junto al tiempo contado. Descartar en silencio impediría distinguir dos situaciones que no se parecen: un campo genuinamente difícil que consume varios minutos de trabajo real, y una pantalla olvidada abierta.

Si al analizar el piloto muchos campos aparecen recortados, eso es en sí un hallazgo sobre cómo se usó la herramienta, no ruido que convenga ocultar.

## Intervalos solapados

Dos intervalos de foco que se solapan son un error explícito, no una duración que convenga estimar: el foco no puede estar en dos sitios a la vez, así que un solapamiento indica captura defectuosa. Inventar una duración plausible produciría exactamente la cifra falsa que este contrato trata de evitar.

Los intervalos se ordenan antes de medir, de modo que el orden en que se registren no cambie el resultado.

## Campos sin foco

Un campo sin intervalos se mide con cero segundos y sigue contando como campo medido. Excluirlo haría que el denominador de `segundos por campo` dependiera de si alguien llegó a enfocarlo, y la media mejoraría sola al ignorar los campos que nadie tocó.

## Verificación realizada

- 15 pruebas: intervalo único, visitas múltiples acumuladas, descuento por encima del umbral, umbral exacto sin recorte, tiempo descartado informado, campo sin foco, orden irrelevante, solapamiento como error, intervalo invertido, agregación de sesión, sesión vacía sin media, campo medido dos veces y determinismo.
- Ruff y mypy estricto sin incidencias en 31 ficheros.

## Límites

- No captura los intervalos de foco: eso corresponde a la pantalla de revisión (DEV-503/504).
- No persiste `segundos_empleados` en la tabla `validacion`.
- No calcula la tasa de corrección de propuestas ni las discrepancias entre revisores: son parte del informe del piloto (DEV-511).
- No compara con ni sin herramienta: esa comparación es el piloto de la sección 17, que se ejecuta al terminar el hito 3.
