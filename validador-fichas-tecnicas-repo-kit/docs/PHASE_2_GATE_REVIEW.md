# Revisión de Gate 2

- Fecha: 31 de agosto de 2026
- Resultado: **PASS**
- Alcance: DEV-201 a DEV-208

## Criterios y evidencia

| Criterio | Evidencia | Resultado |
|---|---|---|
| Muestreo reproducible | Inventario de 16.093 candidatos; muestra aleatoria de 500, semilla 203 | PASS |
| Caché y límite de ritmo | Cliente configurable; caché ZIP inmutable compatible con Windows; pruebas HTTP offline | PASS |
| Versiones inmutables | DEV-205; paquetes content-addressed; bloqueo de mutación y reconstrucción SHA-256 | PASS |
| Informe de composición | 109 filas; ID `bb80992258d07a5e49f1beef46e983f3f56a57e7d48ad20d5aef19e3bffa5fe7` | PASS |
| Corpus descargado operativo sin red | 500 documentos, 1.000 artefactos y 115.583.103 bytes; segunda carga 0 con sockets bloqueados | PASS |

## Decisiones cerradas

- D-016: muestra aleatoria con semilla 203 sobre la instantánea documentada.
- D-020: versiones content-addressed e inmutables; `source_version` literal y
  opcional, nunca inferida. La aceptación no determina vigencia regulatoria.

## Límites conservados

- El corpus y la caché permanecen en `data/local/`, fuera de Git.
- No se procesan datos de pacientes ni se generan decisiones clínicas.
- No se implementa todavía consolidación de maestros, extracción, interfaz ni exportación.
- Fase 3 queda autorizada, pero DEV-301 no se inicia automáticamente.
