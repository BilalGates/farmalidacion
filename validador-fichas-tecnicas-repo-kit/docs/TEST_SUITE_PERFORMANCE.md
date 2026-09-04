# Rendimiento y estratificación de la suite de pruebas

- Fecha del análisis: 4 de septiembre de 2026
- Motivo: la suite completa tardaba ~21 minutos, lo que desincentiva ejecutarla durante el desarrollo

## Medición de partida

```
python -m pytest -q          →  321 passed in 1285.98s (21:25)
```

## Dónde se consumía el tiempo

El coste está concentrado en **cuatro pruebas**, no repartido por la suite:

| Prueba | Duración |
|---|---|
| `test_specialty_importer.py::test_real_master_import_preserves_valid_rows_and_quarantines_orphans` | > 580 s |
| `test_medication_importer.py::test_real_master_import_is_lossless_linked_and_idempotent` | 259,8 s |
| `test_active_ingredient_importer.py::test_real_master_import_is_lossless_idempotent_and_provenanced` | 38,4 s |
| `test_catalog_importer.py::test_real_catalog_import_is_lossless_and_idempotent` | 6,9 s |

Las cuatro comparten el mismo patrón:

1. Migran una base SQLite nueva con Alembic (`command.upgrade(..., "head")`).
2. Leen uno o varios **ficheros Excel reales** de `data/reference/raw/`.
3. Importan el maestro completo fila a fila.
4. **Repiten la importación** para demostrar idempotencia, duplicando el coste.

El resto de la suite es rápida: 351 pruebas en 78 s, es decir ~0,2 s de media.

### Por qué estas pruebas son caras y deben seguir siéndolo

No son lentas por descuido. Son las pruebas que sostienen las puertas de salida de la Fase 3: ausencia de pérdida de filas, procedencia de cada valor, cuarentena de huérfanos e idempotencia del lote. Verifican esas propiedades **sobre los ficheros reales del cliente**, no sobre una miniatura.

Sustituir el Excel real por un fixture reducido habría bajado el tiempo, pero también habría dejado de comprobar lo único que hace creíble esa garantía. **No se ha hecho**, y no se recomienda.

## Cambio aplicado

Se han añadido marcadores de pytest. **Ninguna prueba se ha eliminado, simplificado ni debilitado**; sólo se pueden seleccionar subconjuntos.

```toml
[tool.pytest.ini_options]
testpaths = ['tests']
markers = [
    "slow: importa maestros Excel reales sobre una base migrada (minutos por prueba)",
    "reference: depende de los ficheros de referencia de data/reference/raw",
]
```

Las cuatro pruebas están marcadas `@pytest.mark.slow` y `@pytest.mark.reference`.

## Las dos suites

### A — Suite rápida, para iterar

```bash
cd backend
python -m pytest -q -m "not slow"
```

**351 pruebas en 78 s.** Cubre todo salvo las cuatro importaciones de maestros reales. Es la que conviene ejecutar al desarrollar.

### B — Suite integral, para gates y CI

```bash
cd backend
python -m pytest -q
```

**355 pruebas.** Es la que debe pasar antes de cerrar una fase, revisar una puerta o integrar en `main`. **Ninguna puerta de fase se declara con la suite rápida.**

Para ejecutar sólo la parte lenta:

```bash
python -m pytest -q -m "slow"
```

## Calidad estática

```bash
python -m ruff check .     # All checks passed!
python -m mypy src         # Success: no issues found in 38 source files
```

## Lo que se ha descartado deliberadamente

- **Reducir los Excel reales a fixtures pequeños.** Anularía la garantía que estas pruebas existen para dar.
- **Compartir una base migrada entre pruebas mediante fixture de sesión.** Es la optimización más tentadora y la más peligrosa aquí: estas pruebas verifican *idempotencia* y *cuarentena*, propiedades sensibles al estado previo. Compartir base introduciría acoplamiento entre pruebas y podría ocultar exactamente el defecto que buscan.
- **Cachear el resultado de la importación.** Convertiría la prueba en una comprobación de la caché.
- **Paralelizar con `pytest-xdist`.** Es viable y probablemente seguro, pero añade una dependencia y un modo de fallo nuevo para ganar tiempo en una suite que ya sólo se ejecuta en gates. Puede reconsiderarse si la parte lenta crece.

## Oportunidad pendiente, no aplicada

`test_specialty_importer` importa **tres** maestros (principios activos, medicamentos y especialidades) porque necesita las claves foráneas para clasificar huérfanos. Ahí sí existe I/O repetido real entre ficheros de prueba distintos.

Una fixture de sesión que construyese **una vez** una base con los dos maestros previos, y de la que cada prueba tomase una **copia** en disco, conservaría el aislamiento y evitaría reimportar. La copia es lo que preserva la propiedad de idempotencia.

No se ha aplicado porque toca el camino crítico de una puerta de fase ya cerrada (Gate 3) y el beneficio —minutos en una suite que sólo corre en CI— no justifica el riesgo ahora. Queda documentado como trabajo opcional con diseño ya pensado.
