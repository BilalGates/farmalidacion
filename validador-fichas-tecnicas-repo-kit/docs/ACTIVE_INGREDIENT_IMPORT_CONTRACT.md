# Contrato de importación del maestro de principio activo

- Issue: DEV-303
- Fase: 3
- Estado: implementado
- Fuente: `PrincipioActivoCargaMaster-22062026.xlsx`
- SHA-256: `89e6806b4cba7d6724533bfdc29ea834056223872385f08c080b72b965448e6c`

## Alcance reproducible

El importador exige y registra, en este orden, las hojas `General`, `Frecuencia`, `Via`, `ConsejosAdministracion` y `DatosAnaliticos`. Cada hoja conserva nombre, ordinal, fila de cabecera, cabecera literal con tipo de celda, número de filas de datos y número de valores materiales.

La versión recibida contiene:

| Hoja | Filas de datos | Valores materiales |
|---|---:|---:|
| General | 7.189 | 35.945 |
| Frecuencia | 0 | 0 |
| Via | 0 | 0 |
| ConsejosAdministracion | 0 | 0 |
| DatosAnaliticos | 0 | 0 |

Las cuatro hojas sin datos se registran como `EMPTY_SOURCE_SHEET` de severidad informativa. Este resultado describe únicamente la versión importada: no prueba que los bloques no existan, sean opcionales ni tengan cardinalidad 0 en el dominio.

## Representación canónica

Cada fila material de `General` produce:

- un `target_record` de tipo `active_ingredient` con PK canónica técnica;
- un vínculo con la versión exacta del libro;
- un `source_fragment` localizado por hoja y fila física, con payload literal;
- una `block_instance` explícita de tipo `active_ingredient_general`;
- un `field_value` por celda material;
- una `value_provenance` con rol `master_baseline` por valor.

El payload del fragmento conserva columna, cabecera, tipo OOXML observado, valor literal y fórmula. Los vacíos materiales permanecen como estado `empty`; nunca se convierten en `no_consta` o `no_aplica`.

Las hojas hijas, cuando contengan filas en una versión posterior, solo podrán vincularse mediante una coincidencia literal y única de `PA_IDEXTERNO` con el `IDEXTERNO` observado en `General`. Una referencia ausente o ambigua se conserva en cuarentena; no se resuelve por nombre, semejanza ni inferencia.

## Identidad y no pérdida

`IDEXTERNO` se conserva como valor fuente, pero no se convierte en PK ni clave natural canónica. Una fila general siempre mantiene su propia identidad técnica aunque el identificador esté vacío o repetido. Esas situaciones generan diagnóstico y nunca una fusión automática.

No se convierten números, recortan textos, deduplican filas, concatenan ocurrencias ni aplican límites de exportación. El libro original permanece fuera de Git e inalterado.

## Versionado e idempotencia

El lote se identifica por localizador, versión literal opcional, SHA-256 de bytes e importador `active_ingredient_master` versión `1.0.0`. La versión documental es content-addressed y queda separada de la identidad canónica.

Dos ejecuciones sobre la fuente actual producen exactamente:

- un lote y una versión documental;
- cinco registros de hoja;
- 7.189 registros destino, fragmentos, vínculos y ocurrencias;
- 35.945 valores y 35.945 vínculos de procedencia;
- cuatro diagnósticos informativos;
- cero filas en cuarentena.

La migración `c83e519ad264` añade el registro genérico por hoja y es reversible. El downgrade no modifica ningún Excel.

## Fuera de alcance

DEV-303 no importa medicamentos ni especialidades, no concilia identidades entre fuentes, no asigna prioridad autoritativa, no completa las hojas vacías y no implementa exportación.
