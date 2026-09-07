# Protección de artefactos humanos antes de GOLD

## Reproducibles

Los maestros originales, sus hashes, los importadores, las migraciones y el
corpus CIMA inmutable permiten reconstruir `real.db`, la selección GOLD y
`gold-sections.json`. No sustituyen una copia operativa, pero una pérdida no
elimina decisiones humanas.

## No reproducibles

Antes de que empiece GOLD deben protegerse y versionarse fuera del único disco
de trabajo:

- `annotations-<revisor>.jsonl` de cada farmacéutico;
- artefactos de conciliación y `gold-disagreements.csv`;
- gold final, manifiestos y hashes de cada ejecución;
- decisiones farmacéuticas persistidas en `validation_decision_record`;
- comentarios, revisiones, mediciones de tiempo y futura auditoría append-only;
- configuración exacta de revisores, modelo, prompt, esquema y hardware usada
  en cada benchmark.

La copia debe mantener separación por anotador durante la campaña, control de
acceso, historial inmutable o versionado, verificación de hash y una prueba de
restauración. No se inicia trabajo humano real hasta que el responsable de
operación haya declarado destino, periodicidad, retención y responsable de
restauración. Este documento define el perímetro; no implementa una plataforma
de backup.
