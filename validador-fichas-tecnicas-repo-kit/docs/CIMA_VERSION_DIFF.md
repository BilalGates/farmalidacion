# Contrato de diff entre versiones CIMA

- Issue: DEV-206
- Fase: 2
- Versión: `cima-version-diff-v1`
- Estado: implementado y verificado offline

## Alcance

El comparador recibe dos identificadores de versión explícitos del mismo
documento. El llamador decide cuál se presenta como anterior y cuál como nueva;
esa dirección no implica vigencia regulatoria ni cierra D-020.

DEV-206 no consulta `registroCambios`, no descarga documentos, no modifica
validaciones y no crea tareas `revision_pendiente`. Prepara evidencia legible
para esos flujos posteriores.

## Correspondencia y clasificación

Los artefactos se emparejan exclusivamente mediante `artifact_role + ordinal`.
No se deduce equivalencia por título, contenido, posición aproximada o
similitud. Cada ocurrencia queda clasificada como `added`, `removed`, `modified`
o `unchanged`.

Un cambio de localizador, URL, estado HTTP, tipo, cabeceras o fecha se informa
como metadato modificado aunque el cuerpo sea idéntico.

## Diff textual y contenido binario

Solo se intenta decodificar tipos `text/*`, JSON, XML y sufijos `+json`/`+xml`.
Se respeta el `charset` declarado y se usa UTF-8 únicamente cuando el tipo
textual no declara otro. Una codificación desconocida o bytes incompatibles no
se reparan ni sustituyen.

Cuando ambos cuerpos son texto decodificable se genera un diff unificado
completo, sin truncamiento. Si alguno es binario o no decodificable, el informe
marca `binary_or_undecodable`, conserva hashes y no fabrica texto.

Antes de comparar se recalcula el SHA-256 de cada cuerpo persistido. Cualquier
discrepancia detiene el proceso.

## Salidas

El directorio contiene `version-diff.json`, con clasificación, hashes,
metadatos y texto completo, y `version-diff.md`, como resumen legible.

El identificador depende de la versión del algoritmo y de la pareja ordenada
anterior/nueva. Las mismas entradas producen los mismos bytes. Un informe
existente distinto nunca se sobrescribe.

## Evidencia automatizada

Las pruebas offline cubren artefactos añadidos, eliminados, modificados e
idénticos; texto UTF-8; binario no decodificable; cambio solo de metadatos;
dirección inversa; repetición byte a byte; documentos distintos y corrupción.

## Pendientes

- D-020 está aceptada; ninguna versión se declara vigente ni se infiere su orden regulatorio.
- La consulta diaria de `registroCambios` pertenece a DEV-701.
- El marcado selectivo de validaciones requiere fases posteriores.
- Gate 2 quedó en PASS tras demostrar corpus descargado y operación offline en DEV-208.
