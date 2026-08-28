# Contrato de corpus CIMA offline

- Issue: DEV-207
- Fase: 2
- Esquema: `1.0.0`
- Estado: verificado con fixture sintético

## Alcance

Un corpus offline es un directorio autocontenido con `manifest.json` y los
cuerpos originales declarados por ese manifiesto. La verificación y la carga no
usan el cliente HTTP ni intentan completar ficheros ausentes.

El corpus versionado `dev-207-synthetic-v1` contiene dos versiones sintéticas
del mismo documento y cuatro artefactos. Sirve exclusivamente para pruebas: sus
URLs usan `example.test`, su `source_version` declara `synthetic-dev-207-*` y no
constituye evidencia regulatoria ni clínica.

## Manifiesto e integridad

Cada versión declara `nregistro`, tipo documental, versión fuente literal y una
lista ordenable de artefactos. Cada artefacto conserva rol, ordinal,
localizador, ruta relativa, URL fuente, estado HTTP, cabeceras, fecha de captura
y SHA-256 del cuerpo.

La verificación rechaza:

- versiones de esquema o tipos de corpus desconocidos;
- rutas absolutas, ascendentes o exteriores al directorio;
- ocurrencias rol/ordinal duplicadas;
- un mismo fichero declarado más de una vez;
- cuerpos ausentes o con hash distinto;
- ficheros no declarados.

No se repara, decodifica, normaliza ni sustituye ningún cuerpo.

## Operación sin red

`verify_offline_corpus` lee y verifica exclusivamente el sistema de archivos.
`load_offline_corpus` transforma cada entrada en una respuesta cacheada y usa
el contrato inmutable de DEV-205. Una segunda carga idéntica es idempotente.

La prueba automatizada reemplaza la creación de sockets por un fallo inmediato
y, bajo ese bloqueo, verifica el corpus, persiste dos versiones, reconstruye
bytes y genera el diff textual de DEV-206.

## Límite de la evidencia

DEV-207 demuestra la operación técnica sin red y ofrece el formato para un
corpus descargado. No descarga ni incorpora las 500 fichas del piloto, no
verifica respuestas reales de CIMA y no resuelve D-016 ni D-020. Por ello Gate 2
continúa abierto hasta repetir este contrato con el corpus real autorizado.
