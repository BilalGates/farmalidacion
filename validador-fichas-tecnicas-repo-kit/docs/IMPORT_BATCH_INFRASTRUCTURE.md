# Infraestructura común de importación

- Issue: DEV-301
- Fase: 3
- Estado: implementado
- Fecha: 31 de agosto de 2026

## Alcance

DEV-301 aporta infraestructura común para que los importadores posteriores registren lotes, hashes, diagnósticos y filas en cuarentena. No interpreta Excel, no mapea campos canónicos, no resuelve conflictos y no importa ningún maestro concreto.

## Identidad del lote

El identificador reproducible se calcula sobre:

- sistema de fuente;
- localizador literal de fuente;
- versión literal de fuente, o ausencia explícita;
- SHA-256 de los bytes exactos del fichero;
- nombre del importador;
- versión del importador.

Una repetición exacta reutiliza el lote. Un cambio en cualquiera de esos elementos crea otro lote. `source_version` es opcional, se conserva literalmente y nunca se deduce del nombre, contenido o fecha del fichero.

El lote puede enlazarse opcionalmente a `source_document_version`; esa relación no convierte el fichero en autoridad ni determina vigencia.

## Diagnósticos

Cada diagnóstico conserva lote, severidad, código, localizador, mensaje, detalles literales opcionales, recuento y fecha. La clave reproducible evita duplicar el mismo diagnóstico dentro de una reejecución del lote. No se usa para declarar que una fila duplicada sea errónea.

## Cuarentena

Cada fila en cuarentena conserva:

- lote y localizador de origen;
- código y explicación del motivo;
- payload literal entregado por el importador;
- SHA-256 de ese payload;
- fecha de registro.

La infraestructura no corrige, normaliza, trunca, fusiona ni elimina el payload. Los importadores concretos serán responsables de producir una serialización literal y reproducible de la fila y de clasificar el motivo sin resolverlo automáticamente.

## Estados

Los lotes se crean como `pending` y pueden finalizar como `completed` o `failed`. Un lote fallido conserva diagnósticos y cuarentena. DEV-301 no implementa reintentos ni una máquina de estados operativa; estos podrán añadirse cuando exista un importador concreto que demuestre la necesidad.

## Reversibilidad y límites

La migración `a4d2c8f71b30` crea solo las tres tablas comunes y su downgrade las elimina en orden de dependencias. No cambia las entidades canónicas existentes ni los Excel originales. La infraestructura no decide claves naturales, equivalencias, prioridades entre fuentes ni tratamiento de huérfanos.
