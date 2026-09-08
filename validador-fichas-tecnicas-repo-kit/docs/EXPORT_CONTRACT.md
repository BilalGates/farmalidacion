# Contrato de exportación

- Issues: DEV-601, DEV-602, DEV-603, DEV-604, DEV-605, DEV-610
- Fase: 6
- Estado: infraestructura implementada y verificada técnicamente; **contrato del proveedor pendiente (D-011)** y **prueba de carga pendiente (DEV-610, externa)**
- Módulos: `pharma_validator_api.export_engine` (puro), `export_service` (persistencia), `export_manifest`, `export_api`
- Base normativa: especificación 12; D-010 (semántica de estados); D-011 (contrato exacto); D-026 (límites canónicos ≠ contrato de proveedor)

## Qué está cerrado y qué no

El **mecanismo** está completo: leer el modelo canónico, validar contra un
contrato declarado, serializar en tres formatos, excluir lo que no cumple,
archivar la ejecución y poder repetirla byte a byte.

El **contrato concreto del proveedor** no lo está, y no puede estarlo desde el
desarrollo. D-011 sigue pendiente y exige un ejemplo aceptado. Por eso el perfil
es un dato y no una constante del módulo: cuando exista ese ejemplo se añadirá
un perfil, no se reescribirá el motor.

Ningún perfil declara `provider_accepted = True`. Que un fichero se genere
correctamente no significa que el destinatario lo acepte.

## Separación deliberada

| Capa | Responsabilidad | Qué NO hace |
|---|---|---|
| `export_engine` | Serializa filas según un perfil | No toca la base, no conoce el reloj, no fija el formato del proveedor |
| `export_service` | Traduce el modelo canónico a filas y archiva | No decide cómo se escribe una celda |
| `export_manifest` | Describe y verifica lo entregado | No repara un contenido que no cuadra |
| `export_api` | Contrato HTTP | No contiene reglas de negocio |

Ninguna estructura del ORM se serializa directamente: `export_service` es la
capa de transformación explícita entre ambas.

## Reglas que no se negocian

**Sólo se exporta lo validado.** Un campo sin decisión registrada excluye su
ficha. Entregarlo daría por validado un dato que nadie revisó. Estados
exportables: `confirmado`, `corregido`, `no_consta`, `no_aplica`. Quedan fuera
`pendiente`, `revision_pendiente` y `descartado`.

**Nada se trunca.** Un valor que excede su límite declarado produce incidencia y
excluye la fila. Recortarlo entregaría un dato distinto del validado sin que
nadie lo supiera.

**Los estados lógicos no se aplanan.** `no_consta`, `no_aplica`, nulo y vacío
significan cosas distintas (D-010). Cómo se escribe cada uno lo fija el perfil.
Si el perfil no lo declara, el registro se excluye: fail-closed.

**Un registro con cualquier problema bloqueante queda fuera entero.** Media
ficha es peor que ninguna, porque parece completa.

**Nada se corrige en silencio.** La salida del validador son motivos, no
correcciones.

## Reproducibilidad

Misma versión de datos + mismo perfil ⇒ mismos bytes ⇒ mismo `sha256`.

Lo que lo sostiene:

- **El reloj no entra en el contenido.** La fecha vive en `export_run` y en el
  manifiesto. Dos ejecuciones separadas por una hora producen el mismo hash.
- **El orden es explícito.** Filas por `target_record.id`; ocurrencias por
  `ordinal`, desempatando por `id`; campos por nombre. Sin orden declarado, dos
  ejecuciones idénticas darían ficheros distintos y el hash no significaría nada.
- **La versión del perfil se deriva de su configuración**, no se declara a mano.
  Cambiar una columna y olvidar subir el número dejaría dos exports
  incomparables declarando la misma versión.

## Informe de exclusiones

Cada exclusión registra ficha, campo, severidad, regla, motivo y estado
observado.

| Severidad | Significado |
|---|---|
| `bloqueante` | Impide entregar la ficha |
| `advertencia` | Se entrega, pero hay algo que declarar |
| `no_aplicable` | Ocurrencia marcada fuera de alcance por un revisor; no es un error |

Reglas actuales: `campo_sin_validar`, `estado_no_exportable`,
`estado_logico_no_serializable`, `ocurrencia_no_aplicable`,
`campo_obligatorio_ausente`, `excede_limite`, `contrato_incumplido`.

## Archivado

`export_run` guarda identificador, fecha, actor, perfil y su versión, formato,
estado, recuentos de entregadas y excluidas, hash, tamaño, ruta del artefacto y
la configuración completa serializada.

El fichero va a disco (`export_artifact_dir`), no a la base: un export de
decenas de miles de fichas no cabe razonablemente en una fila. `content_hash`
permite comprobar que el artefacto en disco es el que se declaró.

## Procedimiento para DEV-610 (prueba con proveedor)

Todo lo necesario está listo. Cuando se disponga del ejemplo aceptado:

1. Obtener del proveedor un fichero de ejemplo aceptado y su especificación de
   columnas, tipos, longitudes y serialización de estados. **Esto cierra D-011.**
2. Declarar un `ExportProfile` con esas columnas y su `state_rendering`. No
   requiere tocar el motor.
3. Ejecutar `POST /exports` con ese perfil sobre un subconjunto validado.
4. Revisar `/exports/{id}/exclusions`. Ninguna exclusión bloqueante debe quedar
   sin explicación aceptada por el proveedor.
5. Comprobar el artefacto contra su manifiesto (`export_manifest.verify`).
6. Entregar el fichero al entorno del proveedor y registrar el resultado.
7. Sólo entonces marcar el perfil `provider_accepted = True`, y sólo ese perfil.

Hasta el paso 7, DEV-610 permanece **PENDIENTE EXTERNO**. No puede simularse:
una prueba de carga que no ocurrió no se marca como hecha.

## Decisiones pendientes

| Decisión | Qué bloquea | Quién decide |
|---|---|---|
| D-011 | Contrato exacto: columnas, longitudes, serialización de `no_consta` / `no_aplica` | Proveedor + farmacia |
| DEV-610 | Aceptación real del fichero en el entorno del proveedor | Proveedor |
