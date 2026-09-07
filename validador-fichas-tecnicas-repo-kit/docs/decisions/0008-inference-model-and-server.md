# ADR-0008 — Modelo y servidor de inferencia local

- Estado: **propuesto** — pendiente de aceptación humana
- Fecha: 2026-09-04
- Decisiones relacionadas: D-014 (esta), D-013 (cerrada), D-015 (dependiente)
- Responsables: tecnología (propone), producto (acepta)

> Este ADR **no cierra D-014**. Presenta la comparación y una recomendación argumentada para que una persona decida. Ningún camino de código elige modelo por omisión: `BackendConfig` exige `model` explícito y falla sin él.

## Contexto

La Fase 4 necesita un extractor local ejecutándose para poder medirse. Todo lo demás está construido: interfaz `ExtractorLLM` (DEV-401), esquema guiado (DEV-403), agrupación por sección (DEV-404), verificación literal (DEV-405), lotes reanudables (DEV-406) y el transporte agnóstico al modelo (`inference_backend`). Falta declarar **qué modelo** y **qué runtime**.

D-013 está cerrada: servidor interno con GPU de **al menos 24 GB de VRAM**, sin salida a internet.

El plan exige comparar **al menos dos tamaños de modelo** sobre el conjunto oro. Por tanto D-014 no elige un modelo: elige el **conjunto de candidatos a comparar** y el runtime que los servirá.

## Restricciones

- **Sin internet.** Excluye toda API externa. Pesos descargados una vez y servidos en la red del centro.
- **API compatible con OpenAI-chat**, tras `ExtractorLLM`, para que el motor sea sustituible.
- **Salida guiada por esquema obligatoria.** No se confía en pedir JSON por prompt; reparar JSON malformado equivaldría a inventar contenido y el contrato de evidencia lo prohíbe.
- **Español biomédico**: fichas técnicas de la AEMPS, con terminología farmacológica densa y HTML con entidades.
- **Reproducibilidad**: `temperature=0`, semilla fija. Una métrica que no se puede repetir no es evidencia.
- **Contexto suficiente**: las secciones de FT son largas. Se agrupa por apartado, no por campo.
- **Licencia** que permita uso interno en un centro sanitario.
- Volumen del piloto: 500 documentos × ~15 llamadas ≈ 7.500 peticiones. El conjunto oro son sólo 20 fichas.

## Criterio rector

La especificación es explícita y conviene repetirlo: **el rendimiento no es el problema; la precisión sí.** Con 7.500 peticiones y unos segundos por petición, cualquier candidato razonable procesa el corpus en una noche. Optimizar por velocidad no compra nada que el piloto necesite.

Lo que sí importa: **calidad de evidencia literal en español** y **ausencia de alucinaciones**.

## Opciones consideradas

Se reducen a tres candidatos realistas para 24 GB. Se descartan de entrada los modelos de 70B (no entran sin doble GPU, y D-013 condiciona esa compra a que el hito 2 demuestre que hace falta) y las API externas (violan la restricción de red).

### Opción A — Qwen2.5-14B-Instruct sobre vLLM

| Atributo | Valor |
|---|---|
| Tamaño | 14B |
| Cuantización | Ninguna (BF16) o AWQ 4-bit si hiciera falta margen |
| VRAM esperada | ~28 GB en BF16 → **requiere AWQ/GPTQ 4-bit (~10 GB) en 24 GB** |
| RAM esperada | 16–32 GB |
| Contexto | 32K nativo |
| Structured output | Guided decoding nativo (`xgrammar`/`outlines`), JSON Schema estricto |
| Rendimiento | Alto; batching continuo |
| Despliegue | Medio: contenedor oficial, más piezas que Ollama |
| Offline | Sí, pesos locales |
| Reproducibilidad | Buena con `seed` + `temperature=0` |
| Licencia | Apache 2.0 |
| Español biomédico | Fuerte multilingüe; buen rendimiento documentado en español |
| Riesgos | En 24 GB obliga a cuantizar, lo que **confunde tamaño con cuantización** en la comparación |

**Ventajas:** mejor relación calidad/tamaño de la terna; guided decoding maduro; licencia permisiva.
**Inconvenientes:** en 24 GB no cabe sin cuantizar, y eso contamina la variable que DEV-408 quiere medir.

### Opción B — Qwen2.5-7B-Instruct sobre vLLM

| Atributo | Valor |
|---|---|
| Tamaño | 7B |
| Cuantización | Ninguna (BF16) |
| VRAM esperada | ~15 GB BF16, holgado en 24 GB |
| RAM esperada | 16 GB |
| Contexto | 32K nativo |
| Structured output | Guided decoding nativo, JSON Schema estricto |
| Rendimiento | Muy alto |
| Despliegue | Medio |
| Offline | Sí |
| Reproducibilidad | Buena |
| Licencia | Apache 2.0 |
| Español biomédico | Correcto; menor capacidad de razonamiento largo que 14B |
| Riesgos | Puede quedarse corto en campos que exigen localizar en secciones extensas |

**Ventajas:** entra sin cuantizar, lo que lo convierte en el **término limpio de comparación** frente al 14B cuantizado; rápido; sobra VRAM para contexto largo.
**Inconvenientes:** menor techo de calidad.

### Opción C — Llama-3.1-8B-Instruct sobre llama.cpp / Ollama

| Atributo | Valor |
|---|---|
| Tamaño | 8B |
| Cuantización | GGUF Q5_K_M o Q8_0 |
| VRAM esperada | ~7–9 GB |
| RAM esperada | 16 GB |
| Contexto | 128K nominal (práctico bastante menor) |
| Structured output | Gramáticas GBNF; conversión desde JSON Schema, menos directa que vLLM |
| Rendimiento | Medio; batching pobre frente a vLLM |
| Despliegue | **El más simple**: un binario o `ollama run` |
| Offline | Sí |
| Reproducibilidad | Buena con semilla; el ecosistema GGUF varía entre versiones |
| Licencia | Llama 3.1 Community License (no OSI; restricciones de uso) |
| Español biomédico | Aceptable, por detrás de Qwen2.5 en español |
| Riesgos | Licencia con condiciones; GBNF añade una traducción propia que puede introducir defectos |

**Ventajas:** despliegue trivial; útil como control de referencia barato.
**Inconvenientes:** salida guiada menos directa; licencia menos limpia para un centro sanitario; español algo más débil.

## Decisión propuesta

**Comparar B (Qwen2.5-7B BF16) frente a A (Qwen2.5-14B AWQ 4-bit), ambos sobre vLLM.** Mantener C como control opcional sólo si sobra tiempo.

Razones concretas:

1. **Cumple el requisito de comparar dos tamaños** con la misma familia de modelo y el mismo runtime, de modo que la única variable relevante sea el tamaño (más la cuantización, que se declara explícitamente como variable acompañante y se documenta como tal).
2. **vLLM ofrece guided decoding contra JSON Schema directamente**, sin la traducción intermedia a GBNF. Menos capas entre el esquema de DEV-403 y la decodificación significa menos sitios donde un defecto pueda parecer un fallo del modelo.
3. **Apache 2.0** evita cualquier discusión de licencia en un entorno sanitario.
4. **Qwen2.5 rinde mejor en español** que Llama-3.1 a tamaño comparable, y el corpus es íntegramente español técnico.

Sobre la contaminación tamaño/cuantización: es inevitable en 24 GB y **debe declararse en el informe**, no disimularse. Si los resultados quedan próximos, la lectura honesta es "no hay diferencia demostrada", no "el grande gana". D-013 ya previó que 48 GB eliminaría esta confusión; ampliar sólo se justifica si el hito 2 lo demuestra necesario.

## Consecuencias

### Positivas

- Comparación interpretable con una sola familia y un solo runtime.
- Salida guiada estricta sin traducción intermedia.
- Sin ataduras de licencia.

### Negativas

- vLLM es más exigente de operar que Ollama.
- El 14B sólo entra cuantizado en 24 GB.

### Riesgos

- Que ninguno de los dos alcance el listón por campo. **Mitigación:** el sistema ya degrada a `solo_evidencia`; la Fase 4 no exige que el modelo acierte, exige saber en qué campos acierta.
- Que la cuantización, y no el tamaño, explique la diferencia. **Mitigación:** declararlo en el informe y, si es determinante, pedir 48 GB con evidencia.

## Validación

Ejecutar DEV-408 sobre el conjunto oro anotado con ambas configuraciones y registrar, para cada ejecución: modelo, versión, cuantización, parámetros, versión de prompt y esquema, hardware, fecha, duración, número de casos, errores y outputs. Las métricas las calcula `pharma_validator_api.gold_evaluation`.

## Migración y reversibilidad

Coste de cambio **bajo por diseño**: el modelo se declara en `BackendConfig`; nada más en el código lo conoce. Cambiar de candidato es cambiar configuración y reejecutar. `extraction_batches` marca el trabajo previo como superado sin borrarlo, de modo que una segunda ejecución no destruye la primera.

## Preguntas pendientes

- ¿Se acepta la terna, o farmacia prefiere incluir un modelo específicamente biomédico?
- ¿Se asume la confusión tamaño/cuantización en 24 GB, o se amplía a 48 GB antes de medir?
- ¿Se ejecuta C como control, o se descarta?

## Revisión final para decisión — 7 de septiembre de 2026

La propuesta se actualiza, sin aceptarla, porque Qwen3 sustituye razonablemente
a Qwen2.5 para una comparación nueva. Recomendación A: comparar
`Qwen/Qwen3-8B` BF16 y `Qwen/Qwen3-14B-AWQ` 4-bit sobre la misma versión fijada
de vLLM. Alternativa B: conservar Qwen2.5-7B/14B si el centro ya tiene esos
pesos validados y prioriza continuidad sobre capacidad más reciente. Se
descarta Ministral-8B como candidato principal por su licencia de investigación,
que exige revisión/licencia adicional para uso interno no estrictamente de
investigación.

| Criterio | Recomendación A | Alternativa B |
|---|---|---|
| Modelos | Qwen3 8B / 14B | Qwen2.5 7B / 14B |
| Cuantización | 8B BF16; 14B AWQ 4-bit | igual patrón |
| Runtime | vLLM, versión e imagen fijadas | vLLM fijado |
| VRAM estimada | ~17 GB / ~10–12 GB más KV cache | ~15 GB / ~10 GB |
| RAM operativa | 32 GB recomendados | 16–32 GB |
| Contexto | 32.768 nativo; no activar YaRN salvo necesidad medida | 32K |
| Structured output | JSON Schema mediante Chat Completions de vLLM | igual |
| Español | familia multilingüe; español incluido | multilingüe anterior |
| Biomédico | hipótesis sin validar; decide DEV-408 | hipótesis sin validar |
| Offline/licencia | pesos locales, Apache-2.0 | pesos locales, Apache-2.0 |
| Reproducibilidad | revisión de pesos, contenedor, prompt, esquema y parámetros fijados | igual |
| Throughput/latencia | suficiente para piloto; se mide, no se presupone | suficiente |
| Riesgo principal | modo de razonamiento y cuantización pueden alterar salida literal | menor novedad, menor techo esperado |

Parámetros a congelar antes del benchmark: `temperature=0`, `top_p=1`, semilla
0, `max_tokens=1024`, modo no pensante explícito para Qwen3, revisión exacta de
pesos, cuantización, versión de vLLM, prompt y esquema. No se comparará un 8B en
modo no pensante con un 14B en modo pensante.

Fuentes primarias consultadas: [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B),
[Qwen3-14B-AWQ](https://huggingface.co/Qwen/Qwen3-14B-AWQ),
[Qwen3 multilingüe](https://qwenlm.github.io/blog/qwen3/),
[structured outputs de vLLM](https://docs.vllm.ai/en/latest/features/structured_outputs/)
y [servidor OpenAI-compatible](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html).
Las cifras de VRAM son estimaciones de ingeniería y deben confirmarse en el
servidor de D-013; no son especificaciones publicadas por el fabricante.

Decisión humana reducida a: aceptar Recomendación A, o escoger Alternativa B por
continuidad operativa. D-014 permanece **pendiente**.

## Anexo — Estado de la integración (4 de septiembre de 2026)

Revisión de qué queda por hacer el día que se acepte una opción.

La integración **ya está construida y probada**, salvo una pieza. La cadena
completa existe y encaja:

```
build_schema (DEV-403) → inference_backend (transporte) → parse_response (DEV-403)
                       → run_extraction → verify_extraction (DEV-405)
```

`pharma_validator_api.llm_extractor.LocalServerExtractor` implementa
`ExtractorLLM` y une esas piezas. Verificado con 9 pruebas, sin red y sin GPU:
una respuesta bien formada produce una propuesta admitida; **una cita inventada
la rechaza el verificador literal aunque la haya emitido el adaptador**; un
servidor caído se convierte en incidencia y no bloquea la revisión manual; una
respuesta malformada no se repara; la petición exige salida guiada estricta con
`temperature` 0.

El envío HTTP OpenAI-compatible ya existe en `http_inference_sender` y está
probado offline con transporte simulado. Clasifica timeout/transporte/408/429/5xx
como transitorios y no reintenta un 4xx de contrato. Falta desplegarlo contra el
runtime y pesos que acepte D-014, y registrar una ejecución real.

Coste restante de cerrar DEV-402 una vez aceptada una opción: configuración y
smoke contra el servidor real, más captura del manifiesto de hardware/modelo.

Si se aceptase la opción C (llama.cpp), habría además que traducir el esquema
JSON a GBNF; con las opciones A y B ese trabajo no existe, porque vLLM consume
el JSON Schema directamente. Es una razón práctica más a favor de vLLM, y no
estaba cuantificada en la comparación original.

Ninguna parte del código elige modelo: `BackendConfig` exige `model` explícito y
falla sin él, y hay una prueba que lo fija.
