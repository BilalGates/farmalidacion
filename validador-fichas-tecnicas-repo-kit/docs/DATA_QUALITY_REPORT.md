# Informe agregado de calidad de datos — DEV-308

## Objetivo y alcance

DEV-308 consolida, sin volver a perfilar celdas ni materializar filas, las evidencias agregadas de DEV-002 y DEV-009. Cubre los siete Excel y resume columnas, tipos, nulos, fórmulas, claves candidatas, duplicados, longitudes, catálogo y huérfanos.

No corrige, normaliza, trunca, deduplica ni concilia datos. Los originales siguen inmutables. Las relaciones detalladas de interacciones permanecen fuera de alcance conforme a ADR-0003.

## Entradas verificadas

- Perfil DEV-002: 1999097257b99fe5cc52ab903da873085dd9abe5deb7b0a1d327670f04875976.
- Integridad DEV-009: 987129be4c8d7b62517c0962e19279e01b00299c7c51490e179137b3040579e7.
- El generador valida manifiesto, hashes declarados, originales no modificados y hash estructural de integridad.
- Una salida existente se rechaza; la publicación se realiza desde un directorio temporal.

## Contrato de salida

El script scripts/generate_data_quality_report.py genera exclusivamente quality-report.json, columns-quality.csv, incidents.csv, summary.md y run-manifest.json.

No genera cells.csv, listados exhaustivos de valores ni serialización fila a fila.

## Ejecución real

El perfil de los siete libros terminó en 518,936 s con código 0. Dos informes independientes tardaron 0,462 s y 0,336 s. Ambos obtuvieron el hash 4009cac62bb27974ee3ff15a6b863a03cbb090816e220cb2aee66da128745d48 y todos sus artefactos fueron idénticos byte a byte.

## Resultados agregados

- 730 columnas y 9.301.670 valores materiales.
- 6.510.031 nulos, 52 fórmulas y cero errores de celda informados.
- 106 claves candidatas observadas; no se aceptan como claves naturales.
- 353 filas activas de catálogo y siete incidencias de catálogo.
- Seis grupos de duplicados que informan 34.315 filas; un duplicado no se clasifica automáticamente como error.
- 215 comparaciones de longitud: cuatro excesos y 24 valores exactamente al límite.
- 275 filas huérfanas de excipientes agrupadas en 184 claves fuente.
- 48 grupos de incidencias consolidados.

## Reproducción

    python scripts/profile_reference_files.py --raw-dir data/reference/raw --output <perfil>
    python scripts/analyze_integrity_incidents.py --raw-dir data/reference/raw --output <integridad>
    python scripts/generate_data_quality_report.py --profile <perfil> --integrity <integridad> --output <informe>

Los directorios usados son staging local y no se versionan.

## Límites y siguiente revisión

El informe demuestra reproducibilidad y visibilidad agregada, pero no repara fuentes ni cierra por sí solo Gate 3. El siguiente trabajo recomendado es la revisión formal de Gate 3, sin iniciar automáticamente Fase 4.
