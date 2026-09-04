# ADR-0009 — Umbrales de `proponer_valor` y degradación a `solo_evidencia`

- Estado: **propuesto (esqueleto)** — pendiente de datos y de aceptación humana
- Fecha: 2026-09-04
- Decisiones relacionadas: D-015 (esta), D-014 (dependencia), D-023 (cerrada), GOLD-002 (dependencia)
- Responsables: farmacia (acepta), tecnología (calcula y propone)

> Este ADR **no fija ningún umbral**. Define cómo se calcularán y con qué datos, para que la decisión, cuando llegue, se tome sobre evidencia y no sobre intuición. Fijar un número ahora sería inventar la evidencia que ese número debería resumir.

## Contexto

Cada campo del catálogo tiene una política de interfaz: `proponer_valor`, `proponer_opciones`, `solo_evidencia` u `oculto`. La puerta de salida de Fase 4 exige que **cada campo tenga política justificada por resultados o por restricción funcional**.

Las políticas por restricción funcional ya están cerradas: D-023 prohíbe la preselección en campos interpretables o de criterio clínico, y `prefill_policy` lo implementa. Ese grupo **no depende de esta decisión**.

Lo que falta es el otro grupo: campos donde la política debería decidirse por lo bien que el extractor los resuelve. Eso exige métricas que hoy no existen.

## Por qué el umbral no puede fijarse todavía

Faltan tres insumos, y ninguno es opcional:

1. **El conjunto oro anotado** (GOLD-002 + campaña). Sin verdad de referencia no hay métrica.
2. **La tasa de acuerdo entre anotadores por campo.** Es el techo interpretativo: a ningún campo puede exigírsele al modelo más concordancia que la que muestran dos farmacéuticos entre sí. Un umbral del 95 % en un campo donde dos personas coinciden el 80 % de las veces es incoherente.
3. **Los resultados del extractor** (D-014 + DEV-408).

## Métricas que alimentarán los umbrales

Calculadas por `pharma_validator_api.gold_evaluation`, **por campo**, nunca sólo en global:

| Métrica | Definición operativa | Papel en la decisión |
|---|---|---|
| Exactitud literal | Coincidencia exacta con el oro (espacios y mayúsculas diferencian) | Criterio principal |
| Precisión | De lo propuesto, qué fracción acertó | Gobierna el riesgo de pre-rellenar mal |
| Recall | De lo que existía, qué fracción localizó | Gobierna cuánto trabajo ahorra |
| F1 | Media armónica | Resumen, nunca criterio único |
| Cobertura | Fracción donde propuso algo | Un campo con cobertura baja no ahorra tiempo aunque acierte |
| Tasa de evidencia válida | Propuestas con cita admitida por el verificador literal | **Veto**: sin evidencia no hay pre-relleno |
| Alucinaciones | Valor propuesto donde el oro dice que no lo hay | **Veto**: pesa más que la exactitud |
| Coincidencia normalizada | Coincide salvo formato | Diagnóstico: distingue error real de error de formato |
| Requiere revisión humana | Fracción que una persona debe corregir | Mide el ahorro real |
| Acuerdo entre anotadores | Concordancia humana en ese campo | **Techo**: acota lo exigible |

### Cómo se calculan

- Una unidad con **desacuerdo humano sin conciliar no puntúa**, y las exclusiones se informan siempre.
- La comparación es **exacta**; la normalizada se informa aparte y nunca sustituye a la literal.
- Una propuesta con evidencia no admitida cuenta como **evidencia inválida** aunque el valor coincida: un acierto por azar con cita inventada es un fallo.
- Los intervalos de confianza importan: con 20 fichas, un campo puede tener muy pocas unidades. **Un campo con soporte insuficiente no recibe umbral; se queda en `solo_evidencia` por falta de evidencia, no por mal resultado.**

## Campos que probablemente necesiten umbrales distintos

No se propone un umbral único. Ejes que justifican tratamiento diferenciado:

- **Riesgo clínico.** Un error en dosis o contraindicación no cuesta lo mismo que en un enlace. Los prefijos ATC de riesgo (`L04`, D-017) merecen criterio más estricto.
- **Cardinalidad.** Los bloques repetibles (composiciones, vías, excipientes) fallan de forma distinta: puede acertarse el valor y errarse la ocurrencia.
- **Tipo de dato.** `CHAR` largo, `DECIMAL` y `BIT` tienen modos de fallo distintos.
- **Longitud de la sección de origen.** Localizar en un apartado extenso es más difícil.
- **Acuerdo humano observado.** Campo ambiguo entre personas ⇒ no pre-rellenar.

## Cómo se usarán los umbrales

Tres bandas, cuya frontera es lo que falta decidir:

| Banda | Efecto en la interfaz | Condición cualitativa |
|---|---|---|
| **A — pre-relleno** | `proponer_valor` con valor propuesto | Exactitud alta, evidencia válida ~total, alucinaciones ~cero, acuerdo humano alto, soporte suficiente |
| **B — confirmación** | `proponer_opciones` o valor sin preseleccionar | Resultados buenos pero no suficientes para asumir el valor sin mirar |
| **C — sin pre-relleno** | `solo_evidencia` | Resultados pobres, evidencia inestable, alucinaciones presentes, acuerdo humano bajo o soporte insuficiente |

Reglas que se proponen como **no negociables**, con independencia del número que se elija:

1. **Cualquier alucinación observada en un campo lo excluye de la banda A** para el piloto. La asimetría es deliberada: un campo vacío cuesta tiempo; un campo con un valor plausible e inventado cuesta seguridad.
2. **Tasa de evidencia válida por debajo del 100 % excluye de A.** El contrato ya impide persistir sin cita válida; la política no puede ser más laxa que la barrera.
3. **Ningún campo protegido por D-023 entra en A**, por buenos que sean sus números. Esa decisión está cerrada y no se reabre con métricas.
4. **El umbral nunca supera el acuerdo humano** observado en ese campo.
5. **Soporte insuficiente ⇒ banda C**, no banda A por defecto optimista.

## Decisión propuesta

Ninguna todavía. El procedimiento propuesto es:

1. Cerrar el conjunto oro (GOLD-002 + campaña + conciliación).
2. Aceptar D-014 y ejecutar DEV-408 con las configuraciones acordadas.
3. Publicar métricas por campo junto con la tasa de acuerdo humano.
4. Clasificar cada campo en A/B/C aplicando las cinco reglas anteriores.
5. Traer a farmacia la clasificación propuesta **con la evidencia al lado**, para aceptación campo a campo de los que caigan en A.

La banda A es la única que exige aprobación explícita de farmacia, porque es la única donde el sistema propone un valor que una persona podría confirmar sin mirar.

## Consecuencias

### Positivas

- La política queda justificada por evidencia y es auditable.
- Un campo que degrada a `solo_evidencia` sigue aportando valor: la evidencia junto al campo ya ahorra la búsqueda.

### Negativas

- Con 20 fichas, varios campos tendrán soporte insuficiente y quedarán en C sin haber "fallado". Es el precio de no inventar confianza.

### Riesgos

- **Sobreajuste al conjunto oro.** Mitigación: el conjunto de medida de 50 fichas de la Fase 5 sirve de control.
- **Optimismo por métrica global.** Mitigación: la decisión es siempre por campo; el global se publica pero no decide.

## Validación

`prefill_policy` ya tiene pruebas automáticas de que ningún campo protegido aparece preseleccionado. Al fijar umbrales se añadirán pruebas que verifiquen que la clasificación resultante respeta las cinco reglas.

## Migración y reversibilidad

Los umbrales son configuración, no código. Un campo puede moverse de banda sin migración de datos. Mover un campo **hacia** A exige nueva aprobación de farmacia; moverlo hacia C no.

## Preguntas pendientes

- ¿Acepta farmacia la regla "cualquier alucinación excluye de pre-relleno"?
- ¿Qué soporte mínimo por campo se considera suficiente?
- ¿Se aplica criterio más estricto a los ATC de riesgo desde el piloto?
- ¿La aceptación de la banda A es campo a campo o por bloques?
