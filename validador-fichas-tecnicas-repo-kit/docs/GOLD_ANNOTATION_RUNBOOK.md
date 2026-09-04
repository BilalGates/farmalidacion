# Runbook de anotación del conjunto oro

- Destinatarios: los dos farmacéuticos anotadores (GOLD-002)
- Issue: DEV-407
- Contrato normativo: `docs/GOLD_SET_ANNOTATION_CONTRACT.md`
- Estado: listo para ejecutarse en cuanto se identifiquen los dos anotadores

Este runbook es operativo. Cuando las dos personas estén designadas, pueden empezar sin desarrollo adicional. Ante cualquier discrepancia entre este documento y el contrato, **manda el contrato**.

## 0. Qué se está haciendo y por qué importa

Se construye la **verdad de referencia** contra la que se medirá el extractor. Todo lo que la Fase 4 concluya sobre precisión, cobertura y seguridad de pre-relleno se apoya en estas anotaciones.

Dos consecuencias prácticas:

- **La independencia entre los dos anotadores es el activo principal.** La tasa de acuerdo entre ambos es el techo interpretativo de los resultados: a ningún campo se le puede exigir al modelo más concordancia que la que muestran dos personas. Si un anotador ve el trabajo del otro, ese techo deja de significar nada.
- **Se transcribe y se localiza; no se interpreta.** El anotador registra lo que la ficha dice, no lo que debería decir. No se corrige un error de la ficha, no se completa una laguna con conocimiento propio y no se homogeneiza la redacción.

No se anota ningún dato de paciente y no se emite ninguna recomendación clínica.

## 1. Arranque del entorno

Todo funciona **sin internet**: el corpus ya está descargado. No hace falta GPU.

```bash
cd validador-fichas-tecnicas-repo-kit/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Comprobación de que el entorno responde:

```bash
python -m pytest tests/test_gold_annotations.py tests/test_gold_completeness.py -q
```

### Materializar las entradas de anotación

Sólo se hace **una vez**, y ya está hecho. El resultado vive en `data/local/gold-set-407/`:

```bash
PYTHONPATH=src python ../scripts/materialize_gold_set.py \
  --corpus ../data/local/cima-corpus-random-203 \
  --output-dir ../data/local/gold-set-407
```

Produce:

- `gold-selection.json` — las 20 fichas del conjunto oro;
- `gold-sections.json` — el contenido literal de sus secciones (552 citables).

El script **no sobrescribe** un directorio existente. Si ya existe, no se vuelve a ejecutar: reejecutarlo no aporta nada porque la selección es determinista.

## 1 bis. Alta de los dos anotadores (GOLD-002)

Antes de anotar, las dos personas deben estar **dadas de alta**. No hay registro
nuevo que crear: se reutiliza la lista de revisores que ya existe (DEV-501).

En `.env` (o `.env.example` como plantilla):

```
APP_REVIEWERS=["ana.ruiz:Ana Ruiz","luis.gil:Luis Gil"]
```

Formato `identificador:Nombre visible`. El identificador es el que se escribe en
`annotator_id` de cada línea del JSONL, y debe coincidir exactamente.

A partir de ese momento, `check_gold.py` comprueba la identidad de los
anotadores automáticamente:

- un `annotator_id` que no esté en la lista es **error estructural**;
- dos anotaciones firmadas por la misma persona **no** son doble anotación.

Sin esa comprobación, un identificador mal escrito crearía un tercer anotador
fantasma y la doble anotación quedaría rota sin que nada lo señalase.

Para comprobar la lista sin tocar el `.env`:

```bash
PYTHONPATH=src python ../scripts/check_gold.py \
  --selection ../data/local/gold-set-407/gold-selection.json \
  --sections  ../data/local/gold-set-407/gold-sections.json \
  --reviewers "ana.ruiz:Ana Ruiz" "luis.gil:Luis Gil"
```

Los valores `mtorres` / `jlopez` que trae `.env.example` son **marcadores de
ejemplo, no personas**. Sustitúyelos antes de empezar.

## 2. Las 20 fichas del conjunto oro

Selección `gold-selection-v1`, semilla `407` (GOLD-001), sobre el universo de 500 de DEV-208.
`run_id`: `ac843f92c081045bd61ed80d6aef13c703f88275eeab433291ddb6ce9dd792cd`

**El orden de anotación es el ordinal.** Los dos anotadores siguen el mismo orden para que el progreso sea comparable en cualquier momento.

| # | nregistro | # | nregistro |
|---|---|---|---|
| 1 | 79062 | 11 | 82895 |
| 2 | 85814 | 12 | 68661 |
| 3 | 114961001 | 13 | 80282 |
| 4 | 86059 | 14 | 72152 |
| 5 | 85663 | 15 | 70934 |
| 6 | 58404 | 16 | 64551 |
| 7 | 72610 | 17 | 109551020 |
| 8 | 65723 | 18 | 75296 |
| 9 | 63280 | 19 | 67635 |
| 10 | 77610 | 20 | 84651 |

Esta lista no se cambia. Si una ficha resulta difícil, **no se sustituye por otra**: sustituirla rompería la reproducibilidad de la selección y sesgaría el conjunto hacia los casos fáciles. Se anota lo que se pueda y se deja constancia.

## 3. Qué campos se anotan

Los campos extraíbles del catálogo (DEV-302), que son los que el extractor intentará proponer. Los campos con política `oculto` **no se anotan**: no se piden al modelo, así que medirlos no aporta nada.

Para consultar el alcance exacto por apartado:

```bash
PYTHONPATH=src python -c "from pharma_validator_api.section_grouping import group_fields_by_section; help(group_fields_by_section)"
```

El alcance concreto de campos por ficha debe fijarse con el responsable funcional **antes de empezar** y pasarse luego a `check_gold.py --expected-units-per-document`. Sin ese número, el comprobador no puede detectar un campo que sencillamente nadie anotó.

## 4. La unidad de anotación

Cada anotación cubre exactamente una tupla:

```
(nregistro, versión documental, entidad, bloque, ordinal de ocurrencia, campo)
```

El **ordinal es obligatorio**. Un medicamento con tres vías de administración produce tres unidades, no una. Concatenar ocurrencias en un solo valor invalida la anotación.

La anotación pertenece a **una versión documental concreta**, nunca "a la ficha". La versión viaja en cada registro como `document_version_hash`.

## 5. Cómo se registra una anotación

Cada anotador escribe su propio fichero JSONL, una unidad por línea:

```
data/local/gold-set-407/annotations-<anotador>.jsonl
```

Formato de una línea (`gold-annotation-v1`):

```json
{"nregistro":"79062","document_version_hash":"8704a8e3...","block_type":"Posología","occurrence":1,"field_name":"DOSIS","annotator_id":"farmaceutico-1","annotated_at":"2026-09-10T09:15:00Z","state":"valued","literal_value":"20 mg","evidence":{"section_id":"4.2","start":1042,"end":1048,"literal_text":"20 mg"},"comment":null}
```

Campos obligatorios siempre: identidad completa de la unidad, `annotator_id`, `annotated_at` (ISO-8601 UTC) y `state`.

### El valor literal

`literal_value` se transcribe **exactamente** como aparece. No se corrigen mayúsculas, no se ajustan espacios, no se expanden abreviaturas y no se convierten unidades. Espacios y mayúsculas diferencian: `20 mg` y `20mg` son valores distintos y se compararán como distintos.

### La evidencia

Éste es el punto crítico del contrato.

La evidencia se cita como un intervalo `[start, end)` sobre el **contenido literal de la sección tal como está almacenado**, que es **HTML**, con sus entidades (`&#243;`, `&#xa0;`) y sus espacios originales. La cadena canónica es la que aparece en `gold-sections.json` bajo `content`.

Reglas:

- La verificación es **igualdad exacta** entre `literal_text` y la subcadena `content[start:end]`. No hay tolerancia.
- Leer el HTML renderizado como ayuda está permitido, pero **los desplazamientos que se guardan son siempre los de la cadena canónica**.
- Un intervalo puede empezar o terminar dentro de una entidad o de una etiqueta. **Eso no se corrige**: expandir el recorte hasta un límite "limpio" cambiaría el literal citado. Se confirma tal cual.
- La evidencia debe pertenecer a la ficha y versión que se está anotando. Evidencia de otro medicamento, o de otra versión, es inválida.

Para localizar desplazamientos sin contarlos a mano:

```bash
PYTHONPATH=src python - <<'PY'
import json
data = json.load(open('../data/local/gold-set-407/gold-sections.json', encoding='utf-8'))
NREG, SECCION, TEXTO = '79062', '4.2', '20 mg'
for s in data['sections']:
    if s['nregistro'] == NREG and s['section_id'] == SECCION:
        i = s['content'].find(TEXTO)
        print('start', i, 'end', i + len(TEXTO))
        print(repr(s['content'][i:i + len(TEXTO)]))
PY
```

Si el texto aparece varias veces, se elige la ocurrencia que corresponde al bloque anotado, no la primera por defecto.

## 6. Estados admitidos

Sólo estos cinco cierran una unidad. No se inventan estados nuevos.

| Estado | Cuándo se usa | Evidencia | Comentario |
|---|---|---|---|
| `valued` | La ficha contiene el dato y se puede localizar | **Obligatoria y exacta** | Opcional |
| `source_absent` | La sección o el fragmento no existe en esta versión | No aplica | Opcional |
| `source_blank` | La posición existe pero está vacía | **Localiza la posición** | Opcional |
| `no_consta` | Revisadas las fuentes obligatorias, el dato no aparece | No aplica | **Obligatorio** |
| `not_applicable` | El campo o bloque no corresponde semánticamente a este medicamento | No aplica | **Obligatorio** |

`pending` significa **trabajo sin terminar**. Bloquea el cierre del conjunto oro. No es una forma de "dejarlo en duda".

### La distinción que más se equivoca

`source_absent` / `source_blank` son **observaciones sobre el documento**: describen lo que hay o no hay en el texto.

`no_consta` / `not_applicable` son **decisiones humanas**: afirman algo sobre el medicamento tras revisar las fuentes. Por eso exigen comentario obligatorio.

**La ausencia y el vacío nunca se convierten automáticamente en `no_consta` ni en `not_applicable`.** Que una sección esté vacía no permite concluir que el dato no consta: puede estar en otro apartado. Esa conversión es siempre una decisión registrada, nunca una inferencia.

Si hay duda entre los cuatro, se deja `pending` y se lleva a la sesión de conciliación. Es preferible una unidad pendiente a una decisión inventada.

## 7. Comentarios

Obligatorio en `no_consta` y `not_applicable`: debe decir **qué se revisó** y por qué se concluyó eso. "No aparece" sin más no es suficiente; "revisados 4.1, 4.2 y 5.1, no se menciona" sí lo es.

Recomendable siempre que la unidad haya costado decidirla: el comentario es lo que hará útil la sesión de conciliación.

El resumen publicado no incluye texto clínico más allá de la evidencia estrictamente citada.

## 8. Guardado y verificación de progreso

El JSONL se guarda de forma incremental: una línea por unidad, según se anota. No se sobrescriben líneas anteriores.

Para comprobar en cualquier momento qué falta:

```bash
PYTHONPATH=src python ../scripts/check_gold.py \
  --selection ../data/local/gold-set-407/gold-selection.json \
  --sections  ../data/local/gold-set-407/gold-sections.json \
  --annotations ../data/local/gold-set-407/annotations-farmaceutico-1.jsonl
```

Informa de fichas esperadas y anotadas, unidades completadas y pendientes, evidencia ausente, errores estructurales, porcentaje de progreso y el veredicto **GOLD LISTO / NO LISTO**.

Sale con código 1 mientras no esté listo, así que sirve como puerta antes de evaluar.

**Sólo comprueba completitud y consistencia estructural.** No juzga si un valor es clínicamente correcto: eso no lo puede hacer una máquina, y por eso existe la doble anotación.

### Cuándo una ficha está terminada

Cuando todas sus unidades tienen un estado distinto de `pending`, y toda unidad `valued` tiene evidencia que reproduce exactamente sus desplazamientos. `check_gold.py` lo verifica.

## 9. Independencia entre los dos anotadores

Regla dura, sin excepciones mientras dure la campaña:

- **Cada anotador escribe únicamente su propio fichero.**
- **Ningún anotador abre, lee ni consulta el fichero del otro.**
- No se comentan casos concretos entre ambos: ni valores, ni evidencias, ni criterios sobre una ficha en curso.
- Las dudas **de método** (cómo se cita, qué estado aplica en general) se resuelven con el responsable funcional, nunca entre anotadores comparando su trabajo.
- No se anota "revisando" lo que hizo el otro. Eso no es una segunda anotación: es una revisión, y produce un acuerdo artificial que oculta la dificultad real del campo.

Si la independencia se rompe en alguna unidad, se deja constancia en el comentario. Una unidad contaminada declarada es recuperable; una silenciosa envenena la métrica.

## 10. Comparación, discordancias y conciliación

Cuando ambos han terminado, se comparan los dos ficheros.

```bash
PYTHONPATH=src python ../scripts/check_gold.py \
  --selection ../data/local/gold-set-407/gold-selection.json \
  --sections  ../data/local/gold-set-407/gold-sections.json \
  --annotations ../data/local/gold-set-407/annotations-farmaceutico-1.jsonl \
                ../data/local/gold-set-407/annotations-farmaceutico-2.jsonl
```

La comparación es **exacta** sobre el par (estado, valor literal), con el criterio de DEV-307: espacios y mayúsculas diferencian, y `no_consta` / `not_applicable` no se colapsan entre sí ni con vacío.

### Cómo se tratan las discordancias

- **No se resuelven por mayoría, por antigüedad ni automáticamente.** Con dos anotadores no hay mayoría posible, y esa es exactamente la intención.
- Cada discordancia se registra como **desacuerdo abierto** en `gold-disagreements.csv`.
- Se concilian en una **sesión identificada**, con ambos anotadores presentes.
- La resolución **conserva las dos anotaciones originales**, más el actor, el instante y el motivo. Nunca se borra ni se sobrescribe la anotación descartada: es el registro de que el campo era ambiguo.
- Una unidad con desacuerdo sin conciliar **no entra en el cálculo de métricas** y se informa aparte.

Un campo con muchas discordancias no es un fracaso de los anotadores: es información valiosa. Significa que ese campo es intrínsecamente ambiguo, y probablemente **no debe pre-rellenarse automáticamente** por bueno que sea el modelo. Ese hallazgo alimenta D-015.

### Ejecutar la conciliación y el cierre

```bash
PYTHONPATH=src python ../scripts/run_gold_pipeline.py \
  --selection ../data/local/gold-set-407/gold-selection.json \
  --sections  ../data/local/gold-set-407/gold-sections.json \
  --annotations ../data/local/gold-set-407/annotations-farmaceutico-1.jsonl \
                ../data/local/gold-set-407/annotations-farmaceutico-2.jsonl \
  --output-dir ../data/local/gold-run-1
```

Se detiene si el conjunto oro no está cerrado, en lugar de producir métricas que parecerían válidas.

## 11. Artefactos generados

Bajo un directorio de ejecución que **nunca sobrescribe** uno existente:

| Artefacto | Contenido |
|---|---|
| `gold-selection.json` | Semilla, algoritmo, hash del universo, los 20 `nregistro`, hash de identidad |
| `gold-annotations.jsonl` | Una unidad por línea, con identidad, estado, valor, evidencia, anotador e instante |
| `gold-disagreements.csv` | Unidades en desacuerdo, ambas anotaciones y estado de conciliación |
| `run-manifest.json` | Hashes de entradas y salidas, versión de herramienta y recuentos |
| `summary.md` | Recuentos por estado, campo y anotador, y tasa de acuerdo |
| `gold-completeness.md` | Informe de completitud estructural |

Dos ejecuciones sobre las mismas anotaciones producen ficheros **idénticos byte a byte**.

## 12. Criterios de completitud del conjunto oro

El conjunto oro está cerrado cuando **todo** lo siguiente se cumple:

1. Las 20 fichas tienen anotaciones.
2. Exactamente dos anotadores han participado.
3. Ninguna unidad está en `pending`.
4. Toda unidad tiene anotación de **ambos** anotadores.
5. Toda unidad `valued` tiene evidencia que reproduce exactamente sus desplazamientos.
6. No queda ningún desacuerdo sin conciliar.
7. No hay errores estructurales.

`check_gold.py` verifica los siete y sólo entonces declara **GOLD LISTO**.

## 13. Errores frecuentes que invalidan trabajo

- Citar desplazamientos sobre el texto **renderizado** en vez del HTML almacenado. La verificación fallará.
- "Limpiar" un recorte que parte una entidad HTML. Cambia el literal y lo invalida.
- Concatenar dos ocurrencias de un bloque repetible en un solo valor.
- Marcar `no_consta` porque una sección está vacía, sin revisar el resto de fuentes obligatorias.
- Normalizar el valor al transcribirlo (unidades, mayúsculas, espacios).
- Consultar el fichero del otro anotador "sólo para comprobar".
- Sustituir una ficha difícil por otra.
