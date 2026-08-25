# Evidencia DEV-007 — Importación canónica temporal de omeprazol

## Resultado

El spike reversible representa las 22 hojas de `OMEPRAZOL 20 MGrelleno.xlsx` en una instantánea canónica temporal sin modificar el original. Conserva 616 filas materialmente pobladas como ocurrencias técnicas provisionales y 2.674 valores materiales.

El SHA-256 verificado del original es `5d11b447e5c3d9eed73b03e45d9cfe69c8cec54d89729e23a2bf95ae1564192b`.

## Representación conservada

Cada instantánea separa:

- `documento_fuente` y su `documento_fuente_version` inmutable;
- hoja, orden original y rol conceptual explícito;
- ocurrencia material con fila y ordinal originales;
- valor con coordenada, columna, tipo observado, literal original y fórmula, cuando existe;
- fragmento de procedencia estable para cada valor.

Las ocurrencias se identifican mediante coordenadas de fuente y se declaran `technical_provisional_not_natural_key`. El spike no deduce claves naturales, identidades farmacéuticas ni equivalencias entre entidades. Tampoco concatena, normaliza, deduplica o descarta valores.

## Conciliación

| Evidencia | Resultado |
|---|---:|
| Hojas representadas | 22/22 |
| Filas materiales | 616 |
| Valores materiales | 2.674 |
| Fórmulas | 0 |
| Recuentos por hoja frente a DEV-002 | coincidentes |
| Suite unitaria completa | 12/12 OK |

Dos corridas independientes generaron archivos `canonical-snapshot.json` idénticos byte a byte y el mismo hash canónico:

`5e8564dcd726380aec23f031f6060e4450d2c0fa09f559589e9c6d32caebdb5f`

Duraciones observadas de las corridas: 1,651 s y 2,206 s.

Los artefactos se escriben bajo `artifacts/`, excluido de Git, y pueden regenerarse con:

```powershell
python scripts/import_omeprazole_fixture.py --output artifacts/dev007-run-1
python scripts/import_omeprazole_fixture.py --output artifacts/dev007-run-2
```

## Límites y decisiones abiertas

- Esta instantánea no es una migración ni un esquema físico definitivo.
- Una fila material de la plantilla no se declara automáticamente instancia farmacéutica de negocio.
- La presencia estructural de las dos hojas de interacciones preserva el fixture, pero no integra el maestro de interacciones en el piloto.
- DEV-007 demuestra importabilidad y conservación; no demuestra todavía el round-trip.
- DEV-008 debe exportar y comparar las 22 hojas conforme al contrato semántico, sin normalizaciones implícitas.
- ADR-0001 permanece propuesto hasta completar esa evidencia y recibir la validación correspondiente.
