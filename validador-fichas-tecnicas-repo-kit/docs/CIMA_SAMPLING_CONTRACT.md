# Contrato de muestreo reproducible CIMA

- Issue: DEV-203
- Fase: 2
- Algoritmo: `cima-sampling-v1`
- Estado: implementado y verificado offline

## Alcance

El muestreo selecciona números de registro desde un inventario completo de
respuestas originales de `GET /medicamentos`. No descarga fichas técnicas, no
interpreta contenido clínico y no decide cuál de los dos modos se usará en el
piloto. D-016 permanece abierta hasta revisar el informe de DEV-204.

## Entrada y elegibilidad

Cada página se lee desde su cuerpo JSON original cacheado. El proceso exige:

- `pagina`, `totalFilas` y `resultados` con tipos compatibles;
- un único total declarado y exactamente ese número de filas observadas;
- ninguna página ni `nregistro` repetidos;
- `nregistro` no vacío y estructura ATC compatible.

Son elegibles solo los registros con `estado.aut` presente y `comerc = true`.
Los demás se contabilizan como excluidos, nunca se incorporan silenciosamente.
El inventario se identifica mediante SHA-256 de la lista ordenada de páginas y
hashes de sus cuerpos originales.

## Algoritmos

### Aleatorio

Ordena primero los candidatos elegibles por `nregistro` y aplica
`random.Random(seed).sample`. El orden previo elimina la dependencia del orden
en que se proporcionen los ficheros de página.

### Estratificado

Agrupa por primer nivel ATC y reparte el tamaño proporcionalmente mediante
restos mayores. Los empates se resuelven por código de estrato y la selección
dentro de cada estrato usa la misma semilla.

Si un medicamento no tiene ATC o contiene códigos de más de un primer nivel,
el modo estratificado falla de forma explícita. No se escoge un ATC por orden ni
se crea un estrato artificial sin una decisión humana.

## Identidad y persistencia

La ejecución se identifica por SHA-256 de:

- versión del algoritmo;
- modo;
- semilla;
- tamaño solicitado;
- hash del inventario fuente.

`sampling_run` conserva esos criterios, los recuentos elegible/excluido y la
fecha de creación. `sampling_item` conserva ordinal, `nregistro`, estrato y hash
de la respuesta fuente. Repetir exactamente una ejecución no duplica filas; si
los metadatos o ítems existentes difieren, se detiene con un conflicto.

La migración es reversible. El manifiesto JSON no incluye la fecha operativa,
por lo que las mismas entradas y criterios producen contenido idéntico. Un
manifiesto existente solo se reutiliza si coincide byte a byte; nunca se
sobrescribe con una ejecución diferente.

## Evidencia automatizada

- ambos modos producen la misma lista ante inventario, modo y semilla iguales;
- una muestra sintética de 600 elegibles reproduce exactamente los mismos 500;
- la asignación estratificada proporcional está comprobada;
- páginas incompletas, repetidas, `nregistro` duplicados y ATC ambiguo fallan;
- la persistencia es idempotente y su downgrade elimina ambas tablas;
- todas las pruebas usan respuestas HTTP locales y no necesitan red.

## Límites pendientes

- No se ha descargado ni seleccionado el corpus CIMA real de 500 documentos.
- D-016 debe elegir el modo después del informe de composición de DEV-204.
- El inventario real debe capturarse completo y permanecer disponible en la
  caché inmutable antes de ejecutar la selección del piloto.
- Forma farmacéutica y vía no participan en la selección de DEV-203; se
  incorporarán al informe de composición de DEV-204.
- Versiones documentales, secciones y detección de cambios pertenecen a
  DEV-205/206.
