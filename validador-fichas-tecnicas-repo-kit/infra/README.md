# Infraestructura local

DEV-105 proporciona imágenes reproducibles y `compose.yaml` para el scaffold técnico.

```text
docker compose --profile demo up --build --detach --wait
docker compose --profile demo ps
docker compose --profile demo down
```

- Backend: <http://localhost:8000/health>
- Frontend: <http://localhost:5173/>

El backend aplica Alembic antes de arrancar y guarda la base DEMO, con sus fixtures, en el volumen nombrado `demo-data`. Para eliminar ese volumen recreable: `docker compose --profile demo down --volumes`.

Para los tres maestros reales ya importados en `data/local/real.db`, use
`docker compose --profile real up --build --detach --wait`. El perfil REAL monta
`data/local` del host y no comparte la base DEMO. Ambos perfiles usan los mismos
puertos, por lo que se arranca uno cada vez.

Los originales de referencia, secretos, bases locales y artefactos generados están excluidos del contexto de build.
