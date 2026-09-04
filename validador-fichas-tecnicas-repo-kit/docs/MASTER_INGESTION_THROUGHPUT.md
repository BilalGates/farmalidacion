# Rendimiento de la ingesta de maestros

## Resumen

La ingesta de los maestros pequeños es rápida y está verificada de extremo a
extremo. La del maestro de **especialidades no es viable de una sola pasada**
con el ritmo actual: se midió en unos 9 s por cada 500 ocurrencias, lo que
proyecta decenas de horas para las 29.850 filas generales más las de
excipientes.

Esto es **comportamiento preexistente**, no una regresión introducida por los
índices ni por el orquestador: se ha comprobado midiendo ambas variantes.

## Lo que sí está verificado

Sobre SQLite migrada a `head`, con los ficheros reales:

| Maestro | Resultado |
|---|---|
| Catálogo | 353 definiciones |
| Principios activos | 7.189 ocurrencias, 35.945 valores, 0 cuarentena |

Los dos juntos, desde una base vacía y recién migrada: **37 s**.

Segunda pasada: reutiliza los lotes, y los recuentos de
`catalog_field_definition`, `target_record`, `block_instance`, `field_value` e
`import_batch` no varían.

## Lo que no se ha completado

**La ingesta de medicamentos y especialidades en una sola ejecución.** Se lanzó
y se abandonó tras unas 18 horas con la base en 1,4 GB y el maestro de
especialidades aún sin terminar. No hay, por tanto, ninguna cifra propia que
contrastar contra las del Gate 3 (509.496 valores de medicamento; 1.623.810 de
especialidad; 275 filas en cuarentena por 184 claves huérfanas). Esas cifras
siguen respaldadas por la evidencia de DEV-304/DEV-305, no por esta sesión.

## Descarte de los índices como causa

La sospecha inicial era que los once índices de `f19a4c7b6d82` encarecían la
escritura. **Se midió y es falso.**

Importando el maestro de principios activos (35.945 valores) sobre dos bases
idénticas salvo por el esquema:

| Esquema | Tiempo |
|---|---|
| Sin índices (`d51f7a2c9e04`) | 28,9 s |
| Con índices (`head`) | 29,6 s |

Sobrecoste: **×1,02**. Un 2 % es el precio de mantener once índices en
escritura, y compra pasar de horas a ~1 s en lectura.

Instrumentando además los volcados del importador de especialidades con un
presupuesto de 240 s:

| Esquema | Volcados completados |
|---|---|
| Sin índices | 23 |
| Con índices | 26 |

Con índices avanza **algo más**, no menos. La lentitud es del importador, no del
esquema.

## Dónde está el coste

El importador vuelca por lotes (`BULK_OCCURRENCES = 500`) usando `insert()` de
Core, que no acumula identidad ORM: la estrategia de escritura es correcta. El
coste está en el trabajo por fila del maestro más grande (7,9 MB, 22 hojas, con
payload literal y hash por fila conservados como evidencia), no en un defecto
evidente de una sola línea.

Optimizarlo **no se ha intentado** en esta sesión: tocaría un importador que ya
pasó el Gate 3 con su evidencia publicada, y hacerlo sin un contraste completo
disponible arriesgaría precisamente lo que ese gate garantiza.

## Recomendación

1. Para trabajar con la API sobre datos reales basta con catálogo y principios
   activos: 7.189 registros son suficientes para ejercitar listado, búsqueda,
   ficha y decisiones.

   ```text
   python scripts/ingest_masters.py --only catalog --only active_ingredients
   ```

2. Si se necesita el conjunto completo, conviene lanzarlo por maestro y dejarlo
   correr, en lugar de esperar una única ejecución:

   ```text
   python scripts/ingest_masters.py --only medications
   python scripts/ingest_masters.py --only specialties
   ```

   El orquestador es idempotente, así que reanudar no duplica lo ya importado.

3. Antes de optimizar el importador de especialidades hace falta un perfil por
   fase (parseo, construcción de buffers, volcado) sobre una muestra acotada del
   fichero. Sin esa medición, cualquier cambio sería una conjetura sobre código
   ya verificado.
