# Contrato de `GET /records` (listado paginado)

Destinado a la sesión que trabaja el frontend. **Ningún archivo de frontend se
ha modificado desde el backend**; este documento describe el cambio para que se
implemente sin conflictos de merge.

## Qué cambia y por qué

Antes, `GET /records` devolvía **todos** los registros en una respuesta. Eso
funcionaba con el conjunto DEMO (cinco registros). Con los maestros reales
importados son 7.189, y la petición tardaba horas: el resumen de cada registro
recorre sus ocurrencias, valores, decisiones y conflictos.

El listado ahora está **paginado y limitado por defecto**. Un cliente que no
envíe parámetros recibe como mucho 50 filas, no las 7.189.

## Petición

`GET /records`

| Parámetro | Tipo | Por defecto | Notas |
|---|---|---|---|
| `q` | string | — | Búsqueda literal, sin normalizar acentos |
| `estado` | string | — | Filtra por `review_state` |
| `limit` | int | `50` | Rango `1..200`. Fuera de rango → **422** |
| `offset` | int | `0` | `>= 0`. Negativo → **422** |

Valores de `estado`: `pendiente`, `en_revision`, `requiere_revision`,
`validado`.

## Respuesta

La forma del cuerpo **no cambia**: sigue siendo `{items, total}`, y cada
elemento de `items` conserva exactamente los mismos campos que antes.

```json
{
  "items": [
    {
      "id": "25c93bda-…",
      "entity_type": "active_ingredient",
      "display_name": "omeprazol magnésico",
      "active_ingredient": null,
      "primary_identifier": null,
      "block_count": 1,
      "field_count": 5,
      "pending_count": 5,
      "resolved_count": 0,
      "conflict_count": 0,
      "review_state": "pendiente",
      "last_reviewed_at": null
    }
  ],
  "total": 8
}
```

## Comportamiento que conviene conocer

1. **`items` trae como mucho `limit` filas.** Un frontend que asumiera la lista
   completa mostrará sólo la primera página. Es el único cambio que obliga a
   tocar la pantalla.

2. **`total` significa cosas distintas según el filtro:**
   - Sin filtros, o con `q`: es el total real de coincidencias. Sirve para
     calcular el número de páginas (`ceil(total / limit)`).
   - **Con `estado`:** es el número de coincidencias *halladas hasta donde se ha
     recorrido*, y puede quedarse corto. `estado` se deriva del resumen y no es
     una columna, así que dar un total exacto obligaría a resumir el maestro
     entero, que es justamente lo que se evita. No lo uses para paginar con
     `estado` activo; pagina hasta que `items` venga vacío.

3. **`limit` tiene un techo de 200** a propósito: sin él, un cliente podría
   reintroducir el recorrido completo.

4. **El orden es estable** (por `id`), así que recorrer con `offset` no repite
   ni se salta filas.

## Sugerencia de uso desde el frontend

```ts
const params = new URLSearchParams({
  limit: String(limit),
  offset: String(page * limit),
});
if (q) params.set('q', q);
if (estado) params.set('estado', estado);

const res = await fetch(`${API_BASE}/records?${params}`);
const { items, total } = await res.json();
```

Para el selector de estado, prefiere «cargar más» a una paginación numerada:
`total` no es fiable en ese caso (punto 2).

## Sin cambios

- `GET /records/{id}` — la ficha de un registro no cambia.
- `GET /records/reviewers` — sin cambios.
- `POST /records/values/{field_value_id}/decisions` — sin cambios.

## Cómo levantar datos reales para probar

El conjunto DEMO tiene cinco registros y no ejercita la paginación. Para tener
7.189 registros reales (35.945 valores) en menos de un minuto — medido en 37 s
desde una base vacía:

```text
python -m alembic -c backend/alembic.ini upgrade head
python scripts/ingest_masters.py --only catalog --only active_ingredients
```

Los maestros de medicamentos y especialidades tardan mucho más y no hacen falta
para probar la pantalla; el motivo está en `docs/MASTER_INGESTION_THROUGHPUT.md`.

## Comprobado contra datos reales

Sobre los maestros importados (7.189 registros, 35.945 valores):

- `GET /records?q=omeprazol&limit=1` → 200, y la ficha del registro devuelto
  responde en **0,18 s**, conservando la procedencia por campo
  (`provenance_role: master_baseline`) y el estado `pendiente`.
- `GET /records/no-existe` → **404** con error controlado.
- La búsqueda ignora mayúsculas también en letras acentuadas: `MAGNÉSICO`
  encuentra `magnésico`. Lo que **no** hace es normalizar acentos: `magnesico`
  (sin tilde) no encuentra `magnésico`, y es deliberado — buscar es literal, y
  normalizar cambiaría lo que el usuario escribió por lo que se supone que quiso
  decir.
