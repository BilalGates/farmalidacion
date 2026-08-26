# Infraestructura local

DEV-105 proporciona imágenes reproducibles y `compose.yaml` para el scaffold técnico.

```text
docker compose up --build --detach --wait
docker compose ps
docker compose down
```

- Backend: <http://localhost:8000/health>
- Frontend: <http://localhost:5173/>

El backend aplica Alembic antes de arrancar y guarda SQLite en el volumen nombrado `app-data`. El volumen contiene solo el esquema hasta que DEV-107 defina el fixture canónico de demostración. Para eliminar también ese volumen recreable: `docker compose down --volumes`.

Los originales de referencia, secretos, bases locales y artefactos generados están excluidos del contexto de build.
