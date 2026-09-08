# Desarrollo técnico por delante de la puerta clínica

- Fecha de apertura: 7 de septiembre de 2026
- Motivo: no se dispone todavía de farmacéuticos anotadores

## Regla que gobierna este documento

> Fase 5+ implementation may proceed as preparatory engineering.
> Formal phase acceptance remains gated by clinical validation.

Se adelanta ingeniería para que, cuando entren los farmacéuticos, su trabajo sea
anotar, validar y decidir, no esperar a que se programe. **Nada de lo que se
construya aquí cierra un gate ni declara validación clínica.**

Gate 4 continúa **BLOCKED** y la Fase 5 **no** se declara PASS.

## Cuatro niveles de madurez

`pharma_validator_api.maturity` los define en código, no sólo en prosa, y una
suite comprueba que ninguna capacidad se declare validada:

| Nivel | Significado |
|---|---|
| `implementada` | Existe el código |
| `tecnicamente_verificada` | Sus pruebas pasan sobre datos reales o fixtures |
| `clinicamente_validada` | Farmacéuticos han validado el resultado. **Ninguna capacidad está aquí** |
| `lista_para_produccion` | Validada y operable. **Ninguna capacidad está aquí** |

`Settings.clinically_validated` es una propiedad que devuelve `False` y no un
ajuste: encender una bandera de entorno no puede afirmar validación clínica.

## Banderas de funcionalidad

Por defecto conservadoras. `enable_llm_prefill` seguirá apagada hasta que D-015
fije umbrales sobre métricas reales; encenderla antes presentaría como propuesta
algo cuya tasa de acierto nadie ha medido.

| Bandera | Defecto | Desbloquea |
|---|---|---|
| `enable_review_queue` | `true` | Infraestructura de trabajo, sin criterio clínico |
| `enable_llm_prefill` | `false` | D-014 + D-015 |
| `enable_second_review` | `false` | GOLD-002 |
| `enable_export` | `false` | Formato del proveedor |
| `enable_cima_link` | `false` | D-027 |
| `enable_auto_revalidation` | `false` | Criterio de relevancia clínica |

## Cola de revisión (DEV-502) — `tecnicamente_verificada`

Estados: `pendiente`, `asignado`, `en_revision`, `completado`,
`requiere_segunda_revision`, `bloqueado`. Un trabajo completado no se reabre en
silencio: vuelve por segunda revisión explícita.

**Prevención de colisiones.** `version` implementa bloqueo optimista y la
comprobación se hace dentro del `UPDATE`, no antes en Python: comprobar y luego
escribir deja una ventana por la que se cuela el segundo revisor. Quien llama
puede declarar `expected_version`, la versión que vio en pantalla, de modo que
decidir sobre un estado ya superado se rechace en lugar de pisar el trabajo
ajeno. Ambos casos responden **409**, no 500: que otro llegara antes es un
resultado previsible del flujo y la interfaz debe poder ofrecer recargar.

Una asignación caduca a los 30 minutos, de modo que un revisor que cierre el
navegador no retenga una ficha indefinidamente.

**El orden de la cola es técnico**: prioridad declarada y antigüedad, con
desempate estable. No expresa urgencia clínica, porque decidir que un
medicamento importa más que otro es un juicio farmacéutico.

Verificado en vivo sobre `real.db`: ciclo completo encolar → asignar → revisar →
completar, con 409 en asignación concurrente y en versión desactualizada.

## Medición de tiempos (DEV-508/DEV-509) — `tecnicamente_verificada`

`time_measurement` ya calculaba con descuento de inactividad por encima de 60 s.
Lo que faltaba era persistirlo: `review_session` guarda los agregados y
`field_focus_interval` los tramos crudos. Se conservan ambos a propósito: si el
umbral se revisara, recalcular exige los intervalos originales, y un agregado no
puede deshacerse.

El agregado lo calcula el servidor llamando al módulo puro, nunca la interfaz:
el descuento de inactividad debe aplicarse en un único sitio.

`is_synthetic` marca las sesiones de piloto técnico o pruebas. La métrica
rectora las excluye por defecto, de modo que una medición de ingeniería no pueda
sumarse a una cifra presentada como ahorro farmacéutico.

**Propósito declarado:** medir el ahorro de tiempo del sistema. No es un
instrumento de evaluación de personas; las consultas agregan por ficha y campo.

## Doble validación (DEV-510) — `tecnicamente_verificada`

`double_review` compara dos revisiones independientes campo a campo y clasifica
cada caso: acuerdo, discrepancia de estado, discrepancia de valor, pendiente de
primera o de segunda revisión.

Tres reglas que sostienen el resto:

- **Ninguna discrepancia se resuelve automáticamente.** Elegir por antigüedad,
  rol u orden de llegada sería inventar criterio clínico.
- **Un campo con una sola decisión no es acuerdo**, es incompleto. Confundirlos
  daría por validado lo que solo ha visto una persona.
- **Conciliar exige justificación**, y no puede aplicarse sobre un acuerdo:
  reescribirlo borraría que dos lecturas coincidieron.

Mismo estado con distinto valor cuenta como discrepancia: dos personas que
confirman cosas distintas no han confirmado lo mismo.

## Piloto técnico sintético — `scripts/technical_pilot.py`

Ejercita cola, medición y doble validación sobre registros reales con revisores
**ficticios** (`test_reviewer_a` / `test_reviewer_b`). Ejecutado sobre 50
registros de `real.db`:

| Medida | Resultado |
|---|---:|
| Registros procesados | 50 |
| Colisiones rechazadas | 50 |
| `synthetic_seconds_per_field` | 7,0 |
| `real_seconds_per_field` | `null` |
| Discrepancias sin conciliar | 1 |

El `null` es el resultado importante: la medición sintética no contamina la
métrica real. **No es evidencia de ahorro farmacéutico** y su salida se declara
`synthetic / engineering only`. Los datos del piloto se borraron tras la
ejecución; `real.db` conserva 43.381 registros y 2.169.251 valores.

## Motor de exportación (DEV-601/602/603/605) — `tecnicamente_verificada`

Separación exigida por el encargo: `ExportProfile` describe **cómo** se
serializa (delimitador, codificación, separador decimal, orden de columnas,
escritura de estados lógicos) y `export` aplica ese perfil. **El motor no fija
el formato del proveedor**: D-011 sigue pendiente, y D-026 advierte de que los
límites canónicos internos no equivalen a un contrato de proveedor. Por eso el
perfil es un dato, no una constante: cuando exista un ejemplo aceptado se
añadirá un perfil, no se reescribirá el motor. `provider_accepted` es `false`
en todo perfil existente.

Tres reglas que no se negocian:

- **Nada se trunca en silencio.** Un valor que excede su límite declarado
  produce incidencia y, en modo estricto, detiene la exportación. Entregar un
  fichero con un valor recortado sería peor que no entregarlo, porque parece
  completo.
- **Los estados lógicos no se aplanan a vacío.** `no_consta` y `no_aplica`
  significan cosas distintas entre sí y distintas de «vacío»; cómo se escriben
  lo decide el perfil. Un estado que el perfil no declara produce incidencia,
  no una celda vacía indistinguible de un dato ausente.
- **Reproducible byte a byte** (DEV-605). El XLSX se escribe a mano, sin
  dependencias externas, porque las bibliotecas habituales incrustan marcas de
  tiempo que romperían el checksum.

`export_manifest` acompaña cada entrega con perfil, columnas, codificación,
recuento de filas, `sha256`, tamaño e incidencias. `verify` detecta un solo byte
alterado o un fichero truncado, y no intenta repararlo. El manifiesto describe
la exportación; **no la certifica clínicamente**.

Comprobado sobre `real.db`: 200 registros completos exportados a CSV y XLSX, 0
incidencias, checksum estable entre ejecuciones y manifiesto verificado. Los
acentos se emiten en UTF-8 correcto.

## Lo que sigue bloqueado por personas

| Bloqueo | Decide | Estado |
|---|---|---|
| GOLD-002 | Responsable funcional / farmacia | Dos farmacéuticos reales |
| GOLD-004 | Responsable funcional | Congelar alcance de campos/unidades |
| D-014 | Responsable con criterio técnico | Aceptar modelo/runtime |
| D-015 | Responsable funcional / farmacia | Umbrales tras métricas reales |
| D-027 | Arquitectura / farmacia | Mapeo de identificadores externos |

## Límite de este entorno

Esta máquina no tiene GPU ni `torch`/vLLM instalados: el smoke real del
extractor contra un runtime de inferencia (bloque A/B) no puede ejecutarse aquí.
Es una limitación de hardware, no un bloqueo clínico, y se resuelve en el
servidor de D-013.
