# Especificación funcional y técnica — v2
## Validador asistido de fichas técnicas para carga del catálogo de medicamentos

> **Para el agente de desarrollo:** este documento es la fuente de verdad del alcance.
> Antes de escribir código lee las secciones 3, 9 y 15: contienen las restricciones que no
> son negociables y los criterios con los que se aceptará el trabajo. Si algo aquí entra en
> conflicto con una decisión de implementación que te parezca mejor, plantéalo antes de
> desviarte. Trabaja por hitos (sección 16) y deja la aplicación ejecutable y probada al
> final de cada uno.
>
> **Versión 2.** Incorpora seis decisiones ya cerradas por el cliente, resumidas en la
> sección 18. Los cambios respecto a la v1 afectan sobre todo a escala (piloto de 500
> documentos), inferencia (modelo local obligatorio), autenticación (no la hay) y reglas de
> riesgo (por código ATC).

---

## 1. Contexto

Se va a cargar el catálogo de medicamentos de un servicio de farmacia hospitalaria en un
sistema nuevo de prescripción electrónica. El modelo destino exige **245 campos clínicos**
por registro, repartidos en cuatro entidades: Principio Activo, Medicamento, Especialidad y
una capa de maestros transversales.

La fuente documental es la **ficha técnica** (Resumen de las Características del Producto)
publicada por la AEMPS. Un análisis previo campo a campo concluyó que:

- 53 campos se pueden extraer de forma **directa** del documento,
- 17 requieren **interpretación** (el dato está, pero hay que traducirlo o decidirlo),
- 79 son **parciales** (solo aparecen en algunos medicamentos),
- 204 **no están** en el documento y se pueblan desde otras fuentes.

El esfuerzo humano estimado para validar todo esto a mano ronda las **1.800 horas de
farmacéutico**. Esta herramienta existe para reducir ese número, transformando la tarea de
*buscar y transcribir* en *leer y confirmar*.

**El catálogo de campos ya existe** como hoja de cálculo:
`Catalogo_campos_clinicos_medicamentos.xlsx`, hoja `Eval. solo Ficha Técnica`. Sus columnas
(Entidad, Bloque origen, Campo, Tipo, Obl., ¿Desde la FT?, Sección FT, Comentario) son
directamente la tabla de configuración descrita en la sección 6. **No reinventes este
catálogo: impórtalo.**

### 1.1 Fase actual: piloto de 500 fichas técnicas

El alcance de esta primera fase es **una muestra aleatoria de 500 fichas técnicas de CIMA**,
no el catálogo completo del centro. Esto tiene tres consecuencias que atraviesan todo el
documento:

1. **El dimensionado baja un orden de magnitud.** SQLite basta, un servidor modesto basta, y
   no hacen falta optimizaciones de escala. No sobredimensiones.
2. **La arquitectura debe seguir siendo válida al crecer.** El piloto es una fase, no un
   prototipo desechable. Nada de atajos que impidan pasar después a varios miles de
   registros: mantén las migraciones, los índices y la separación de capas.
3. **Hay que distinguir tres conjuntos de trabajo distintos**, y no confundirlos:

| Conjunto | Tamaño | Para qué |
|---|---|---|
| **Corpus** | 500 FT | Alimentar el extractor y hacer emerger casos raros |
| **Conjunto oro** | 20 FT | Anotado a mano; mide la precisión del extractor (hito 2) |
| **Conjunto de medida** | 50 FT | Comparación con y sin herramienta; mide el ahorro real (sección 17) |

> **Aviso importante.** Solo el conjunto de medida (50) requiere revisión humana completa.
> Si por inercia se planifica revisar los 500 a mano, el piloto consume del orden de 150
> horas de farmacéutico, que es más de lo que pretende ahorrar. **No es eso lo que se pide.**

### 1.2 Procedimiento de muestreo

Debe ser reproducible y quedar documentado:

- Semilla fija (`--seed`), guardada junto a la muestra. Dos ejecuciones con la misma semilla
  producen la misma lista.
- Se muestrea sobre medicamentos **autorizados y comercializados** (`estado.aut` presente,
  `comerc = true`). Los suspendidos o revocados no aportan al piloto.
- Se guarda la lista resultante en tabla, con su fecha y semilla, para poder repetir
  exactamente el experimento.
- **Informe de composición obligatorio:** distribución de la muestra por primer nivel ATC,
  por forma farmacéutica y por vía. Debe generarse automáticamente y presentarse antes de
  empezar a medir nada.

> **Nota metodológica que conviene leer antes de sacar conclusiones.** Una muestra aleatoria
> de CIMA no se parece al catálogo de un hospital: sobrerrepresenta genéricos orales, y de
> muchas moléculas aparecerán varios números de registro casi idénticos. Sirve bien para
> medir la precisión del extractor sobre el documento medio; sirve mal para estimar el ahorro
> de horas sobre *vuestro* catálogo. Por eso el informe de composición no es opcional: sin él
> no se sabe qué se ha medido. Si al verlo la distribución resulta poco representativa,
> considerad estratificar la muestra por primer nivel ATC. El sistema debe soportar ambos
> modos (`--modo aleatorio | estratificado`).

---

## 2. Usuario y alcance

**Usuario único: farmacéutico validador.** No hay otros perfiles. No hay pacientes, no hay
prescriptores, no hay acceso externo. Entre 2 y 5 usuarios concurrentes como máximo.

**Utillaje interno.** La aplicación se despliega en la red del centro y su única salida son
los ficheros de carga del sistema destino.

**No se procesa ningún dato de paciente.** Ni uno. Toda la información que maneja la
herramienta procede de documentos públicos de la AEMPS. Esto elimina de raíz cualquier
requisito de protección de datos de salud, y debe seguir siendo cierto: si alguna
funcionalidad propuesta implica tocar datos de paciente, está fuera de alcance.

---

## 3. Lo que esta herramienta NO es

Exclusiones deliberadas. No deben implementarse aunque parezcan mejoras naturales:

1. **No es un asistente conversacional.** El modo de interacción principal es una pantalla
   de revisión campo a campo. El chat, si se implementa, es función secundaria dentro de esa
   pantalla (ver 10.5), nunca la puerta de entrada.
2. **No es una herramienta de apoyo a la decisión clínica.** No se abre a prescriptores, no
   responde preguntas sobre pacientes concretos, no recomienda tratamientos. Ampliar el
   alcance en esa dirección cambiaría el marco regulatorio aplicable; por eso el ámbito se
   mantiene explícitamente cerrado.
3. **No decide valores clínicos.** Ver sección 9. Es la restricción más importante del
   documento.
4. **No sustituye al sistema destino.** No prescribe, no gestiona stock, no dispensa.

---

## 4. Arquitectura

Aplicación web monolítica, desplegable en un único servidor interno.

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (SPA)                                          │
│  Pantalla de revisión · navegación por teclado           │
└───────────────────────┬──────────────────────────────────┘
                        │ REST/JSON
┌───────────────────────┴──────────────────────────────────┐
│  Backend                                                 │
│  ├── Ingesta CIMA      (muestreo, descarga, cacheo)      │
│  ├── Segmentador       (troceo por apartados 1–10)       │
│  ├── Extractor         (propuestas + evidencia citada)   │
│  ├── API de revisión   (propuestas, validaciones)        │
│  └── Exportador        (ficheros de carga)               │
└──────────┬───────────────────────────┬───────────────────┘
           │                           │
     ┌─────┴─────┐             ┌───────┴────────┐
     │  SQLite   │             │ Servidor LLM   │
     │           │             │ local (GPU)    │
     └───────────┘             └────────────────┘
```

**Stack** (cámbialo solo con una razón concreta, no por preferencia):

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic para migraciones.
- Base de datos: **SQLite**. Con 500 documentos no hay ninguna razón para PostgreSQL.
  Mantén las migraciones de Alembic desde el principio para que el salto sea trivial si más
  adelante hace falta.
- Frontend: React + TypeScript + Vite. Sin librería de componentes pesada: la interfaz es
  densa y muy específica, y las genéricas estorbarán más de lo que ayudan.
- Inferencia: servidor LLM local (ver 8.3).
- Tests: pytest en backend, Vitest en frontend.
- Todo dockerizado, con `docker compose up` funcionando desde el primer hito. El servicio de
  inferencia va en su propio contenedor con acceso a GPU.

---

## 5. Fuente de datos: CIMA (AEMPS)

API REST pública, sin autenticación, base `https://cima.aemps.es/cima/rest`.
Documentación oficial: `https://www.aemps.gob.es/apps/cima/docs/CIMA_REST_API.pdf`.

**Verifica los nombres exactos de parámetros contra esa documentación antes de
implementar**: este documento los resume, no los sustituye.

| Uso | Endpoint |
|---|---|
| Ficha de un medicamento | `GET /medicamento?nregistro=…` o `?cn=…` |
| Búsqueda paginada (muestreo) | `GET /medicamentos?...` |
| Listado de presentaciones | `GET /presentaciones?...` |
| **Texto de la FT por apartados** | `GET /docSegmentado/contenido/1?nregistro=…&seccion=…` |
| Cambios desde una fecha | `GET /registroCambios?fecha=…` |

El tipo de documento `1` es la ficha técnica. Apartados relevantes para la extracción:
**1, 2, 3, 4.1, 4.2, 4.3, 4.4, 5.1, 6.1, 6.3, 6.5, 6.6**.

Del objeto `medicamento` interesan además, como metadatos ya estructurados que **no hace
falta extraer del texto**: `nregistro`, `nombre`, `atcs`, `principiosActivos`, `excipientes`
(con `id`, `nombre`, `cantidad`, `unidad`, `orden`), `viasAdministracion`,
`formaFarmaceutica`, `presentaciones` (con `cn`), `estado`, `comerc`.

### 5.1 Reglas de ingesta

- **Cachea agresivamente.** El texto de una ficha técnica cambia pocas veces al año. Una vez
  descargado, no se vuelve a pedir.
- **Limita el ritmo** (máx. ~5 peticiones/segundo) y reintenta con espera exponencial. Es un
  servicio público gratuito; trátalo con cuidado. Con 500 documentos la descarga completa
  debería llevar minutos.
- **Registra siempre la fecha de revisión del texto** (apartado 10 de la FT) junto al
  contenido. Es la versión contra la que se valida (sección 11).
- La ficha técnica es **por número de registro**, no por código nacional. Un `nregistro`
  agrupa varias presentaciones. Modela esa relación explícitamente: es fuente habitual de
  errores.

---

## 6. Catálogo de campos (tabla de configuración)

Toda la lógica de qué se pide, de dónde sale y cómo se comporta la interfaz se gobierna desde
una tabla de configuración, **no desde código**. Añadir un campo debe ser insertar una fila.

```
campo_catalogo
  id                    PK
  entidad               enum: principio_activo | medicamento | especialidad | transversal
  bloque                text          -- ej. "Medicamento - Info prescripción"
  campo                 text          -- ej. "ADUDOMAXDIA"
  tipo_dato             text          -- ej. "DECIMAL(10,3)", "CHAR(100)", "BIT"
  longitud_max          int NULL      -- derivada de tipo_dato, para validación
  obligatorio           bool
  veredicto             enum: directo | interpretacion | parcial | no_disponible
  secciones_ft          text[]        -- ej. ["4.2","4.3"]
  politica_prefill      enum: proponer_valor | proponer_opciones | solo_evidencia | oculto
  descripcion           text
  orden                 int
```

**Seed inicial:** importar la hoja `Eval. solo Ficha Técnica` del Excel citado en 1. Mapeo de
`veredicto` a `politica_prefill`:

| Veredicto | Política de pre-relleno |
|---|---|
| `directo` | `proponer_valor` |
| `interpretacion` | `proponer_opciones` |
| `parcial` | `solo_evidencia` |
| `no_disponible` | `oculto` (no aparece en esta pantalla) |

### 6.1 Correcciones de tipo ya acordadas

Aplicar en la importación, sobrescribiendo lo que diga el Excel:

| Campo | Tipo en el Excel | Tipo a usar |
|---|---|---|
| `EX_DESCRIPCION` | `CHAR(20)` | **`CHAR(100)`** |
| `ME_DESCRIPCION` | `CHAR(20)` | **`CHAR(100)`** |

Estas ampliaciones están confirmadas con el proveedor del sistema destino. Déjalas como
overrides explícitos y comentados en el importador, no editando el Excel, para que la
trazabilidad del cambio quede en el código.

---

## 7. Modelo de datos

```
muestra                     -- trazabilidad del piloto
  id                PK
  semilla           int
  modo              enum: aleatorio | estratificado
  n_solicitado      int
  criterios         jsonb        -- filtros aplicados
  creada_en         timestamp

registro                    -- la unidad que se revisa
  id                PK
  muestra_id        FK
  entidad           enum
  clave_natural     text         -- nregistro, CN, o código de principio activo
  nregistro_ft      text
  descripcion       text
  atc               text         -- copiado de CIMA; alimenta las reglas de riesgo
  requiere_doble    bool         -- calculado (ver 11.1)
  estado            enum: pendiente | en_revision | completado | bloqueado
  conjunto          enum NULL: oro | medida | corpus

ficha_tecnica
  nregistro         PK
  nombre            text
  fecha_revision    date         -- apartado 10
  hash_contenido    text
  descargada_en     timestamp

seccion_ft
  id                PK
  nregistro         FK
  seccion           text         -- "4.2"
  texto             text
  orden             int

propuesta                   -- lo que sugiere el extractor
  id                PK
  registro_id       FK
  campo_id          FK
  valor_propuesto   text NULL    -- NULL cuando la política no permite proponer valor
  opciones          jsonb NULL   -- candidatos, ninguno preseleccionado
  evidencia_seccion text
  evidencia_texto   text         -- fragmento literal
  evidencia_ini     int          -- offset de carácter en seccion_ft.texto
  evidencia_fin     int
  confianza         float
  extractor_version text
  modelo            text         -- nombre y versión del modelo local
  creada_en         timestamp

validacion                  -- lo que decide la persona
  id                PK
  registro_id       FK
  campo_id          FK
  propuesta_id      FK NULL
  valor_final       text NULL
  estado            enum: confirmado | corregido | no_consta | pendiente | descartado
  usuario           text         -- nombre elegido en el selector de sesión (ver 10.1)
  es_segunda        bool         -- true si es la segunda validación independiente
  ft_fecha_revision date
  validada_en       timestamp
  segundos_empleados int         -- para medir el piloto
  comentario        text NULL
  UNIQUE (registro_id, campo_id, es_segunda)

auditoria                   -- append-only, sin UPDATE ni DELETE
  id, tabla, registro_id, campo_id, accion, valor_antes, valor_despues,
  usuario, timestamp
```

### 7.1 Sobre el estado `no_consta`

Es un estado de primera clase y **no es lo mismo que "vacío" ni que "pendiente"**. Significa
"he mirado la ficha técnica y el dato no está ahí". En el bloque de dosis máximas la mayoría
de celdas acabarán legítimamente en `no_consta`, y eso es un resultado correcto, no un
trabajo a medias. Marcarlo debe costar una sola tecla.

### 7.2 Sobre `segundos_empleados`

El piloto existe para medir. Registra el tiempo dedicado a cada campo desde que recibe el
foco hasta que se resuelve, descontando inactividad por encima de 60 segundos. Sin este dato
la comparación de la sección 17 no se puede hacer.

---

## 8. Motor de extracción

Por cada registro y cada campo con `politica_prefill != oculto`:

1. Recuperar el texto de las `secciones_ft` configuradas para ese campo.
2. Llamar al modelo local con salida estructurada.
3. Persistir la propuesta **solo si trae evidencia válida**.

**Agrupa las llamadas por sección.** No hagas una llamada por campo: reúne todos los campos
que dependen del apartado 4.2 y resuélvelos en una sola petición. Con ~150 campos extraíbles
y ~12 apartados relevantes, esto reduce de unas 150 llamadas por documento a unas 15, que es
la diferencia entre un proceso de horas y uno de días.

### 8.1 Regla de oro del extractor

> **Ninguna propuesta sin cita.** Si el extractor no puede señalar el fragmento exacto del
> documento del que sale el valor, no propone nada y devuelve `no_encontrado`.

Verificación automática obligatoria antes de persistir: `evidencia_texto` debe aparecer
**literalmente** en el texto de la sección indicada. Si no aparece, la propuesta se descarta y
se registra como incidencia. Esto elimina las citas inventadas por construcción, sin depender
de la buena voluntad del modelo — y con un modelo local pequeño esa garantía pasa de
conveniente a imprescindible.

### 8.2 Prompt del extractor (plantilla)

```
Eres un extractor de datos que trabaja sobre fichas técnicas de medicamentos
autorizadas por la AEMPS. Tu única función es localizar información y citarla.

DOCUMENTO — Medicamento: {nombre}, apartado {seccion}:
"""
{texto_seccion}
"""

CAMPOS A EXTRAER
{lista de campos con nombre, descripción y tipo de dato}

REGLAS
1. Solo puedes usar información contenida en el texto anterior. No aportes
   conocimiento propio sobre el medicamento.
2. `evidencia_texto` debe ser una copia LITERAL y contigua del documento,
   de entre 10 y 400 caracteres. Se verificará automáticamente.
3. Si el dato no está en el texto, devuelve estado "no_encontrado" y no
   inventes un valor aproximado ni lo deduzcas.
4. No conviertas unidades, no calcules, no redondees, no infieras.
5. Si el texto es ambiguo o admite varias lecturas, devuelve estado
   "ambiguo", la evidencia, y todas las lecturas posibles en `opciones`.

FORMATO DE SALIDA (JSON, sin texto adicional)
{
  "resultados": [
    {
      "campo": "<nombre del campo>",
      "estado": "encontrado" | "no_encontrado" | "ambiguo",
      "valor": <valor tipado o null>,
      "opciones": [<candidatos>] | null,
      "evidencia_texto": "<cita literal>" | null,
      "confianza": <0.0-1.0>
    }
  ]
}
```

### 8.3 Inferencia local

**No hay salida a internet.** Toda la inferencia se ejecuta dentro de la red del centro. El
código debe hablar con el modelo a través de una interfaz `ExtractorLLM` con implementaciones
intercambiables por configuración, para no acoplarse a un motor concreto.

**Servidor de inferencia.** Expón el modelo por una API compatible con el formato
OpenAI-chat, de modo que el cliente sea trivial y sustituible. Opciones razonables: vLLM
(mejor rendimiento por lotes), o llama.cpp / Ollama (más simple de operar). Para un piloto,
la simplicidad de operación pesa más que el rendimiento máximo.

**Salida estructurada por construcción.** Usa decodificación guiada por esquema JSON
(*guided decoding* en vLLM, gramáticas GBNF en llama.cpp). No confíes en pedir JSON en el
prompt y luego parsear: con modelos locales pequeños eso falla lo bastante a menudo como para
envenenar el proceso por lotes.

**Modelo.** Elegir un modelo instruido con buen rendimiento en español y capacidad de seguir
esquemas. Prueba al menos dos tamaños sobre el conjunto oro antes de fijar uno: la diferencia
de precisión entre un 7–8B y un 30B+ en tareas de extracción con cita puede ser grande, y es
exactamente lo que el hito 2 debe medir en vez de asumir.

**Dimensionado orientativo**, a confirmar midiendo:

| VRAM | Encaja cómodamente | Comentario |
|---|---|---|
| 24 GB | 7–14B sin cuantizar, ~30B cuantizado a 4 bits | Suficiente para el piloto |
| 48 GB | ~30B holgado | Margen para probar modelos mayores |
| 2 × 48 GB | 70B cuantizado | Solo si el hito 2 demuestra que hace falta |

Volumen del piloto: 500 documentos × ~15 llamadas ≈ **7.500 peticiones**. Con unos pocos
segundos por petición, el corpus completo se procesa en una noche incluso en la
configuración más modesta. **El rendimiento no es el problema; la precisión sí.** Dimensiona
para calidad, no para velocidad.

### 8.4 Degradación elegante — importante

Si el hito 2 demuestra que la precisión del modelo local es insuficiente para un tipo de
campo, **la respuesta correcta no es abandonar la herramienta**: es bajar ese campo a
`solo_evidencia` en la tabla de configuración.

Merece la pena entender por qué. La mayor parte del ahorro de tiempo no viene de que el
sistema acierte el valor, sino de que **coloca el apartado correcto de la ficha técnica al
lado del campo correcto**, evitando que la persona busque. Ese beneficio existe aunque el
extractor no proponga nada. Diseña el sistema para que sea útil con un extractor mediocre, y
mejor con uno bueno.

Consecuencia práctica: `politica_prefill` debe poder cambiarse por configuración y por campo,
sin desplegar código.

---

## 9. Reglas de pre-relleno — CRÍTICO

Esta sección es la razón de ser del diseño. Léela dos veces.

### 9.1 El problema

Un farmacéutico que revisa 300 registros en una mañana acepta lo que la pantalla le propone.
Es sesgo de automatización y está bien documentado. Si la herramienta propone un valor en un
campo que requiere criterio clínico, el resultado será un dato que nadie decidió realmente,
con la apariencia de haber sido validado.

### 9.2 Las reglas

**`proponer_valor`** (campos directos). La pantalla muestra el valor extraído, ya escrito en
la casilla, junto a su evidencia. Un clic confirma. Ejemplos: código ATC, forma farmacéutica,
cantidad de la composición, nombre.

**`proponer_opciones`** (campos de interpretación). La pantalla muestra la evidencia y una
lista de candidatos normalizados, **con ninguno preseleccionado**. La persona elige. Ejemplo:
la 4.2 dice "cada 8 horas" y se ofrecen los códigos de frecuencia compatibles, sin marcar.

**`solo_evidencia`** (campos parciales y todos los de criterio clínico). La pantalla muestra
lo que dice el documento y **la casilla queda vacía**. Ningún número sugerido, ninguna casilla
marcada por defecto.

> Ejemplo canónico, el bloque de dosis máximas. La ficha técnica de omeprazol declara una
> posología habitual de 20–40 mg/día. El campo `ADUDOMAXDIA` pide un **techo de alerta**, que
> no es lo mismo. La pantalla debe mostrar:
>
> ```
> ADUDOMAXDIA — Dosis máxima diaria, adulto            [        ]
> Evidencia (§4.2): "La dosis recomendada es de 20 mg una vez al día…"
> ⚠ La ficha técnica no declara dosis máxima. Este valor es criterio farmacéutico.
> ```
>
> Y nada más. El número lo escribe una persona, y queda registrado quién.

**`oculto`.** El campo no aparece en esta pantalla; se puebla desde otra fuente.

### 9.3 Confirmación en bloque

Se permite confirmar de una vez todos los campos `proponer_valor` de un bloque, siempre que
sus evidencias estén visibles en pantalla en ese momento. **Nunca** se permite confirmación en
bloque de campos `proponer_opciones` o `solo_evidencia`, ni desde una vista de listado donde
la evidencia no se esté mostrando.

---

## 10. Interfaz de revisión

### 10.1 Identificación de usuario (sin autenticación)

No hay LDAP ni contraseñas. Al abrir la aplicación se pide **elegir el nombre propio de una
lista configurable**, que se recuerda en el navegador. Es un selector, no un inicio de sesión.

> **Consecuencia que conviene tener presente.** Sin autenticación, la firma de cada
> validación es *declarada*, no *demostrada*: identifica quién dijo ser, no quién era. Para
> utillaje interno en un equipo pequeño es razonable, y no cambia nada del diseño. Pero si en
> algún momento estas validaciones tuvieran que sostener una auditoría formal, hará falta
> autenticación real. Merece la pena decidirlo a sabiendas ahora, no descubrirlo después.

La lista de usuarios se define por configuración. La aplicación debe rechazar guardar
validaciones sin usuario seleccionado.

### 10.2 Principio rector

La métrica que gobierna todas las decisiones de interfaz es **segundos por campo validado**.
Cualquier elemento decorativo que no reduzca ese número sobra.

### 10.3 Disposición

Tres zonas, a pantalla completa:

```
┌───────────────────────────────────────────────────────────────────────┐
│ OMEPRAZOL 20 mg cápsulas · nregistro 12345 · FT rev. 03/2024          │
│ Registro 47 de 500          ████████░░░░░░  42 %        👤 M. Torres  │
├──────────────────────────────┬────────────────────────────────────────┤
│  CAMPOS                      │  EVIDENCIA                             │
│                              │                                        │
│  ▸ Identificación      4/4 ✓ │  Ficha técnica · apartado 4.2          │
│  ▾ Posología           2/9   │                                        │
│    ATC        A02BC01    ✓   │  …Adultos: la dosis recomendada es     │
│  ▸ ADUDOMAXDIA  [      ]     │  de ██20 mg una vez al día██. En       │
│    ADUDOMAXTOMA [      ]     │  casos graves puede aumentarse…        │
│    FUNCRENA     ( ) Sí ( ) No│                                        │
│  ▸ Consejos            0/3   │  ⚠ No se declara dosis máxima.         │
│                              │     Valor de criterio farmacéutico.    │
├──────────────────────────────┴────────────────────────────────────────┤
│ ⏎ confirmar   N no consta   ⇥ siguiente   ⇧⇥ anterior   ? ayuda       │
└───────────────────────────────────────────────────────────────────────┘
```

- **Izquierda:** los campos del registro, agrupados por bloque, con contador de progreso. El
  campo activo va resaltado.
- **Derecha:** el fragmento de ficha técnica correspondiente al campo activo, **con la
  evidencia marcada dentro de su párrafo**, no aislada. El contexto alrededor es lo que
  permite juzgar si la cita es pertinente.
- **Abajo:** recordatorio permanente de atajos.

### 10.4 Navegación por teclado

Requisito, no adorno. La revisión completa debe poder hacerse sin tocar el ratón.

| Tecla | Acción |
|---|---|
| `Enter` | Confirmar el valor propuesto y avanzar |
| `Tab` / `Shift+Tab` | Siguiente / anterior campo |
| `N` | Marcar `no consta` y avanzar |
| `E` | Editar el valor |
| `C` | Añadir comentario |
| `1`…`9` | Elegir opción n en campos de opciones |
| `Ctrl+Enter` | Confirmar todos los campos directos del bloque |
| `Ctrl+S` | Guardar y salir |
| `?` | Ayuda de atajos |

El guardado es **automático e incremental**, campo a campo. Nadie debe poder perder una hora
de trabajo por cerrar una pestaña.

### 10.5 Cola de trabajo

Pantalla de entrada con la lista de registros pendientes, filtrable por entidad, bloque,
estado, conjunto (`oro` / `medida` / `corpus`) y marca de doble validación. Debe permitir
asignar lotes a un usuario para que dos farmacéuticos no revisen lo mismo por accidente —
salvo cuando la doble validación lo requiere expresamente.

### 10.6 Chat (hito 5, opcional)

Panel lateral colapsable dentro de la pantalla de revisión, con el contexto del medicamento
activo ya cargado. Sirve para preguntas puntuales sobre el documento: "¿menciona algo sobre
insuficiencia renal?", "enséñame el apartado 6.3 completo". **Toda respuesta debe citar
apartado y fragmento.** Desde el chat no se escribe en ningún campo.

---

## 11. Auditoría, riesgo y versionado

- Cada validación registra usuario, momento, valor final, propuesta de la que partía y
  **fecha de revisión de la ficha técnica** contra la que se validó.
- La tabla `auditoria` es de solo inserción. Ni `UPDATE` ni `DELETE`.
- Cuando CIMA notifique un cambio de ficha técnica (sección 13), todas las validaciones de
  ese `nregistro` cuya `ft_fecha_revision` sea anterior pasan a **`revision_pendiente`**. No
  se borran ni se invalidan: se marcan.
- La pantalla debe poder mostrar, para cualquier campo, quién lo validó, cuándo, contra qué
  versión y qué decía exactamente el documento en ese momento.

### 11.1 Doble validación por código ATC

Los registros de alto riesgo requieren validación independiente por **dos usuarios
distintos**. El criterio es el **código ATC**, que viene ya estructurado desde CIMA, así que
la clasificación es automática y no requiere etiquetado manual.

```
regla_riesgo
  id            PK
  atc_prefijo   text        -- "L04", "L01", "B01AB", …
  motivo        text        -- se muestra al usuario
  activa        bool
```

La regla es de **coincidencia por prefijo**: un registro con ATC `L04AB01` casa con la regla
`L04`. Si casa con cualquier regla activa, `requiere_doble = true`.

Semilla inicial acordada: **`L04`** (inmunosupresores). El cliente ampliará la lista; deja el
mantenimiento accesible desde la interfaz, sin desplegar código. Candidatos habituales para
esa conversación, a decidir por farmacia y no por el desarrollo: antineoplásicos, agentes
antitrombóticos, insulinas y antidiabéticos, opioides y electrolitos concentrados.

Comportamiento requerido:

- El sistema **impide** que la misma persona haga las dos validaciones.
- La segunda validación se hace **a ciegas**: el segundo revisor no ve lo que decidió el
  primero hasta haber emitido su propia respuesta.
- Al terminar, las discrepancias se listan en una pantalla de conciliación con ambos valores
  y ambas evidencias. Un registro con discrepancias sin resolver no se exporta.

---

## 12. Exportación

Un fichero por bloque, con las columnas en el orden del catálogo de campos.

### 12.1 Formato por defecto

Configurable, pero con estos valores de partida:

| Parámetro | Valor por defecto |
|---|---|
| Formato | CSV |
| Delimitador | `;` (punto y coma) |
| Codificación | UTF-8 **con BOM** |
| Fin de línea | CRLF |
| Cabecera | sí, con el nombre técnico del campo |
| Separador decimal | `.` (punto) |
| Formato de fecha | `AAAA-MM-DD` |
| Texto entrecomillado | solo cuando contiene delimitador, comillas o salto de línea |
| Nombre de fichero | `{entidad}_{bloque}_{AAAAMMDD-HHMM}.csv` |

Notas de criterio: el punto y coma con BOM es lo que hace que el fichero se abra bien en Excel
en configuración regional española sin que nadie tenga que tocar nada. El separador decimal
con punto es lo contrario de lo que hace Excel, pero es lo que suelen esperar los procesos de
carga; **confirmadlo con el proveedor y cambiadlo en configuración si hace falta.** Ofrece
también exportación a `.xlsx` para revisión visual, y `.txt` con delimitador de tabulador
como alternativa.

### 12.2 Reglas de exportación

- **Solo se exportan campos en estado `confirmado`, `corregido` o `no_consta`.** Lo
  `pendiente` no sale, y el informe lo enumera.
- Los registros con doble validación pendiente o con discrepancias sin conciliar **no se
  exportan**.
- Informe adjunto por exportación: total de campos, reparto por estado, campos obligatorios
  sin validar, registros en `revision_pendiente`, y discrepancias abiertas.
- Cada exportación se archiva con su marca de tiempo y es reproducible.

### 12.3 Validación de tipos y control de longitudes

Antes de exportar, todo valor se valida contra `tipo_dato`. Si `CHAR(100)` recibe 112
caracteres, **falla con un error legible; no se trunca en silencio**.

Añade además un **informe de longitudes máximas observadas** por campo, ejecutable sobre el
corpus completo en cualquier momento:

```
campo                 tipo declarado   máx. observado   estado
EX_DESCRIPCION        CHAR(100)        27               OK
DESCRIPCIONPRESCRIP   CHAR(100)        118              ⚠ EXCEDE
```

Es una comprobación barata que habría detectado sola el problema de los `CHAR(20)` antes de
que llegara a una reunión. Ejecútala al final del hito 1 y lleva el resultado al proveedor.

---

## 13. Mantenimiento continuo

Tarea programada diaria contra `GET /registroCambios?fecha=…`:

1. Detecta altas, bajas y modificaciones desde la última ejecución.
2. Si cambió la ficha técnica: vuelve a descargar las secciones, marca las validaciones
   afectadas como `revision_pendiente` y **guarda un diff legible** entre la versión anterior
   y la nueva del apartado afectado.
3. Si cambió el estado o la comercialización: actualiza los metadatos y avisa.
4. Panel de novedades donde el farmacéutico ve qué cambió, con el diff, y decide si su
   validación anterior sigue siendo válida — sin rehacer el trabajo desde cero.

Esto es lo que evita que la carga nazca caducando.

---

## 14. Requisitos no funcionales

- **Rendimiento de interfaz:** cambio de campo por debajo de 100 ms. La evidencia del
  siguiente campo se precarga. La fluidez es aquí un requisito funcional, porque de ella
  depende el ahorro de horas.
- **Extracción:** proceso por lotes en segundo plano, con reanudación tras fallo y registro de
  progreso. No bloquea la revisión.
- **Escala del piloto:** 500 fichas técnicas, ~150 campos extraíbles por registro, del orden
  de 10⁵ propuestas. SQLite lo absorbe sin esfuerzo. Indexa `(registro_id, campo_id)`.
- **Sin autenticación**, pero con identificación de usuario obligatoria (10.1).
- **Trazabilidad de versiones:** cada propuesta guarda `extractor_version` y `modelo`. Al
  cambiar el prompt o el modelo, sube la versión. Sin esto no se pueden comparar tandas.
- **Idioma:** interfaz íntegramente en español.
- **Accesibilidad:** contraste suficiente y foco de teclado siempre visible. Se trabaja con
  esta pantalla muchas horas seguidas.

---

## 15. Criterios de aceptación

1. Ningún campo con política `solo_evidencia` o `proponer_opciones` aparece con valor
   preseleccionado. **Test automático obligatorio.**
2. Toda propuesta persistida tiene evidencia cuyo texto aparece literalmente en la sección
   citada. **Test automático obligatorio.**
3. Un farmacéutico puede validar un registro completo sin usar el ratón.
4. El estado `no_consta` se distingue de `pendiente` en base de datos, interfaz y exportación.
5. La exportación rechaza valores que no caben en el tipo destino, con error legible, y el
   informe de longitudes máximas se genera sobre el corpus completo.
6. La auditoría permite reconstruir, para cualquier campo, quién validó qué, cuándo y contra
   qué versión de qué documento.
7. Un registro con ATC que casa con una regla de riesgo activa exige dos validaciones de
   usuarios distintos, la segunda a ciegas, y no se exporta con discrepancias abiertas.
8. La muestra es reproducible: misma semilla, misma lista de 500 documentos.
9. `docker compose up` levanta el sistema completo, incluido el servidor de inferencia, con
   datos de ejemplo.
10. Todo funciona **sin acceso a internet** una vez descargado el corpus.

---

## 16. Plan de entrega por hitos

**Hito 1 — Muestreo, ingesta y catálogo.**
Muestreo reproducible de 500 FT con informe de composición. Cliente CIMA con cacheo y
limitación de ritmo. Segmentador por apartados. Importador del Excel a `campo_catalogo` con
los overrides de tipo de 6.1. Informe de longitudes máximas. Sin interfaz: se valida con
tests y línea de comandos.

**Hito 2 — Extractor local.**
Servidor de inferencia en contenedor, interfaz `ExtractorLLM`, decodificación guiada por
esquema, prompt de 8.2, verificación literal de evidencia, proceso por lotes.
**Puerta de salida:** anotar a mano el conjunto oro (20 FT), medir precisión y cobertura por
tipo de campo con al menos dos tamaños de modelo, y publicar los resultados. Los campos que no
alcancen el listón se bajan a `solo_evidencia` (8.4) y se sigue adelante. No se pasa al hito 3
sin esa medición hecha.

**Hito 3 — Pantalla de revisión.**
Selector de usuario, cola de trabajo, pantalla de tres zonas, navegación completa por teclado,
guardado incremental, políticas de pre-relleno, medición de `segundos_empleados`.
**Es el hito que justifica el proyecto**; si hay que recortar alcance, se recorta de los otros.

**Hito 4 — Exportación, riesgo y auditoría.**
Ficheros de carga con el formato de 12.1, validación de tipos, informes, reglas ATC, doble
validación a ciegas, pantalla de conciliación, consulta de auditoría.

**Hito 5 — Mantenimiento y extras.**
Tarea de `registroCambios`, panel de novedades con diff, y el chat contextual de 10.6.

El piloto de medición (sección 17) se ejecuta al terminar el hito 3.

---

## 17. Piloto de medición

Sobre el **conjunto de medida (50 fichas técnicas)**: un farmacéutico trabaja a mano y otro
con la herramienta, y se comparan minutos por registro y errores detectados en una revisión
posterior a ciegas. Dos semanas.

Se reportan, como mínimo:

- minutos por registro, con y sin herramienta, por entidad;
- reparto de resultados por estado (`confirmado` / `corregido` / `no_consta`);
- **tasa de corrección de las propuestas** — qué porcentaje de lo que propuso el extractor
  tuvo que cambiarse. Es la medida directa de si el sistema ayuda o entorpece;
- discrepancias entre revisores en los registros de doble validación.

Ese dato sustituye a la estimación teórica de ahorro y es lo que debe decidir si se amplía al
catálogo completo.

---

## 18. Decisiones cerradas

Las seis dudas de la versión 1 están resueltas y ya incorporadas al documento:

| # | Decisión | Dónde se refleja |
|---|---|---|
| 1 | Alcance: muestra aleatoria de 500 fichas técnicas | 1.1, 1.2, 14, 16 |
| 2 | Sin salida a internet: modelo local obligatorio | 8.3, 8.4, 15.10 |
| 3 | Sin autenticación; identificación por selector de usuario | 10.1, 14 |
| 4 | Salida flexible: CSV por defecto, también TXT y XLSX | 12.1 |
| 5 | Doble validación por código ATC, semilla `L04` | 11.1 |
| 6 | `EX_DESCRIPCION` y `ME_DESCRIPCION` ampliados a `CHAR(100)` | 6.1, 12.3 |

### 18.1 Lo que queda por decidir

Ninguna de estas bloquea el arranque, pero conviene cerrarlas antes de los hitos que se
indican:

1. **Ampliación de la lista de reglas ATC** más allá de `L04` — antes del hito 4. Decisión de
   farmacia, no de desarrollo.
2. **Separador decimal del fichero de carga** — confirmar con el proveedor antes del hito 4.
   Está por defecto en punto y es configurable.
3. **Hardware de GPU disponible** — antes del hito 2. Determina qué tamaños de modelo se
   pueden comparar.
4. **Modo de muestreo** (aleatorio puro o estratificado por ATC) — se decide al ver el informe
   de composición del hito 1.
