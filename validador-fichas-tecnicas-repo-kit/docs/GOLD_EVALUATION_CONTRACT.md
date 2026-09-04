# Contrato de evaluación del extractor sobre el conjunto oro

- Issue: DEV-408
- Fase: 4
- Estado: motor implementado y probado con entradas sintéticas; **sin ejecución real**
- Versión: `gold-evaluation-v1`
- Implementación: `pharma_validator_api.gold_evaluation`

## Propósito

Convertir la doble anotación farmacéutica y las propuestas del extractor en las métricas que exige la puerta de salida de Fase 4, de forma reproducible y auditable.

Este contrato **no decide** política de pre-relleno (D-015) ni modelo (D-014). Produce la evidencia con la que esas decisiones se tomarán.

## Reglas que hacen honesta a la métrica

Tres reglas gobiernan el cálculo. Ninguna es negociable, porque cada una impide un modo concreto de producir un número que parece una métrica y no lo es.

### 1. El desacuerdo humano no puntúa

Una unidad donde los dos anotadores discrepan y no se ha conciliado **queda fuera del cálculo** y se informa aparte. Medir contra una verdad en disputa no mide al modelo: mide la ambigüedad del campo.

Igual tratamiento reciben las unidades en `pending` y las que sólo tiene un anotador: una anotación única no es doble anotación y no es verdad de referencia.

Las exclusiones **siempre se publican** junto con las métricas. Ocultarlas inflaría la exactitud aparente sin que se note.

### 2. La evidencia manda sobre el valor

Una propuesta cuya cita no fue admitida por el verificador literal (DEV-405) se clasifica como **evidencia inválida**, con independencia de si el valor coincide con el oro.

Un valor correcto por azar con cita inventada es un fallo, no un acierto. Sin cita válida no hay trazabilidad, y sin trazabilidad la propuesta no puede persistirse: contarla como acierto describiría un sistema que no existe.

### 3. La coincidencia normalizada nunca sustituye a la literal

La comparación principal es **exacta**: espacios y mayúsculas diferencian, con el mismo criterio de DEV-307.

La coincidencia tras normalizar (NFKC, plegado de mayúsculas, colapso de espacios) se calcula y se informa **aparte**, como diagnóstico para saber cuánto del error es de puro formato. Nunca se usa para admitir un valor.

## Clasificación de resultados

Cada unidad puntuada cae en **exactamente una** categoría, de modo que los recuentos siempre suman:

| Categoría | Significado |
|---|---|
| `correcta` | Coincidencia literal exacta con el oro |
| `parcial` | Coincide salvo formato. Acierto degradado, no acierto |
| `incorrecta` | Propuso un valor distinto |
| `no_localizada` | No propuso nada donde el oro tiene valor |
| `evidencia_invalida` | Propuso con cita no admitida por el verificador |
| `no_parseable` | La respuesta del modelo no pudo interpretarse |
| `alucinacion` | Propuso un valor donde el oro dice que no lo hay |

La separación entre `incorrecta` y `alucinacion` es deliberada: transcribir mal un dato que existe y **inventar** un dato que no existe son fallos de naturaleza distinta y de gravedad distinta.

## Métricas calculadas

Por campo y en global:

| Métrica | Definición |
|---|---|
| Exactitud | `correcta / soporte` |
| Precisión | `correcta / propuestas` (correcta + parcial + incorrecta + alucinación) |
| Recall | `correcta / soporte` |
| F1 | Media armónica de precisión y recall |
| Cobertura | Fracción donde el extractor propuso algo |
| Tasa de evidencia válida | Propuestas con cita admitida sobre propuestas totales |
| Alucinaciones | Recuento absoluto |
| Coincidencia normalizada | Recuento de aciertos sólo tras normalizar |
| Requiere revisión humana | `(soporte - correcta) / soporte` |
| Latencia media / throughput | Cuando se aportan tiempos por unidad |

**El global se publica pero no decide.** La política es siempre por campo: una exactitud global alta puede ocultar un campo crítico que falla sistemáticamente.

## Atribución

Toda evaluación exige un modelo atribuido. `evaluate(..., model=...)` falla sin él, y `InferenceResponse` rechaza construirse sin declarar el modelo que la produjo. Una métrica no atribuible no puede compararse en DEV-408.

Para cada ejecución debe registrarse: modelo, versión, cuantización, parámetros, versión de prompt y de esquema, hardware, fecha, duración, número de casos, errores y outputs.

## Ejecución

```bash
cd backend
PYTHONPATH=src python ../scripts/run_gold_pipeline.py \
  --selection ../data/local/gold-set-407/gold-selection.json \
  --sections  ../data/local/gold-set-407/gold-sections.json \
  --annotations ../data/local/gold-set-407/annotations-farmaceutico-1.jsonl \
                ../data/local/gold-set-407/annotations-farmaceutico-2.jsonl \
  --proposals ../data/local/extraction-run-1/proposals.json \
  --model "<modelo aceptado en D-014>" \
  --output-dir ../data/local/gold-run-1
```

El orquestador **se detiene si el conjunto oro no está cerrado**, en lugar de producir métricas parciales. Sin `--proposals` ejecuta hasta consolidar el conjunto oro y se detiene indicando que falta el extractor.

## Estado

El motor está implementado y verificado con **entradas sintéticas** (13 pruebas). No se ha ejecutado ninguna evaluación real: faltan el conjunto oro anotado (GOLD-002) y un modelo aceptado (D-014).

Ninguna métrica de este proyecto ha sido publicada todavía. Cualquier cifra que apareciese antes de esas dos condiciones sería inventada.
