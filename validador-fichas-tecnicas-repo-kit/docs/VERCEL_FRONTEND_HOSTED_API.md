# Frontend en Vercel y API alojada

## Publicación de demostración

Los dos proyectos Vercel existentes pueden servir una vista pública con datos
**sintéticos**. Si la API se ejecuta en Vercel con SQLite, `main.py` crea su
esquema en `/tmp`, carga los fixtures incluidos en el paquete y permite el
origen `https://farmalidacion-beta.vercel.app`. El frontend debe compilarse con
`VITE_API_BASE_URL=https://farmalidacion-q7pt.vercel.app`.

La base de `/tmp` es temporal y distinta en cada instancia. Cambios hechos en
la demostración pueden perderse o no verse en otra petición. El modo de
identidad `pilot` es declarado, sin autenticación corporativa. No se publica
ningún dato REAL ni se presenta este despliegue como piloto operativo. Para
trabajo compartido con persistencia y acceso corporativo se necesita la
topología de la sección siguiente.

## Estado

El frontend puede publicarse como sitio estático en Vercel. La API no puede
usar allí la base SQLite local del piloto: las Functions tienen sistema de
ficheros de solo lectura y `/tmp` es temporal. Los logs del proyecto API
registraron `sqlite3.OperationalError: unable to open database file`; otra
petición registró un fallo al importar `vc_handler` del runtime Python.

El frontend tampoco puede llamar al backend de quien visita la web mediante
`localhost`: esa dirección apunta al ordenador del visitante. Un valor de
`VITE_API_BASE_URL` que apunte al mismo dominio del frontend tampoco identifica
una API.

## Topología necesaria

```text
Navegador del compañero
        │ HTTPS
        ▼
Frontend estático en Vercel
        │ HTTPS + token Entra + CORS
        ▼
API FastAPI en un servicio cloud accesible
        │
        ▼
Almacenamiento persistente de la aplicación
```

La API debe ejecutarse fuera de Vercel Functions, en un servicio que pueda
ejecutar la imagen `infra/backend.Dockerfile` y conservar la base y los
artefactos entre reinicios. La base SQLite REAL actual no está en el
repositorio; el proyecto también contiene bases de vista previa de alrededor
de 2 GB, demasiado grandes para incluirlas en una Function. No se debe apuntar
una Function a `./data/local/real.db` ni a `/tmp`.

## Configuración de los dos servicios

En el backend alojado:

- `APP_AUTH_MODE=entra`; no publicar con `pilot`, que solo usa una identidad
  declarada y no autentica cuentas.
- Configurar `APP_CORS_ALLOW_ORIGINS` con el origen HTTPS exacto de Vercel, por
  ejemplo `["https://farmalidacion-beta.vercel.app"]`.
- Configurar las variables `APP_ENTRA_*`, las capacidades de roles y los
  vínculos de revisores según `ENTRA_ID_INTEGRATION_PLAN.md`.
- `APP_DATABASE_URL` debe señalar al almacén persistente elegido. Las
  migraciones deben ejecutarse antes de servir tráfico.
- Comprobar `/health`, `/ready`, `/auth/config` y una ruta protegida sin token;
  esta última debe devolver `401` o `403`.

En el proyecto **frontend** de Vercel:

- `VITE_API_BASE_URL` debe ser el origen HTTPS público de la API, no el dominio
  del frontend ni una dirección localhost. Se integra en el bundle, así que
  cualquier cambio requiere un redeploy.
- Registrar en la aplicación SPA de Entra el redirect exacto
  `https://farmalidacion-beta.vercel.app/auth-redirect.html` y autorizar ese
  origen para la API.
- Volver a probar inicio de sesión y una consulta protegida con una cuenta
  corporativa autorizada.

## Acceso limitado a la VPN corporativa

El repositorio también conserva una vista previa en `infra/compose.entra.vpn.preview.yaml`.
Esa opción sirve frontend y API juntos tras un gateway HTTPS de la VPN. No es
un backend público para Vercel: depende de que cada compañero alcance la IP de
VPN, confíe en el certificado y tenga paso por el firewall. `STATUS.md` registra
que el certificado de prueba solo estaba instalado en el equipo local y que
una compañera no pudo conectar; la comprobación del firewall quedó pendiente.

## Bloqueo para completar la publicación REAL

El repositorio no identifica todavía un servicio cloud para alojar la API, su
almacenamiento persistente ni una URL pública de API. Este equipo tampoco tiene
`az` o `vercel` CLI autenticados. Hasta provisionar esa API y obtener su URL,
no existe un valor correcto para `VITE_API_BASE_URL` y no se puede completar ni
verificar la conexión desde Vercel.

## Preparación del servidor REAL (2026-10-14)

`infra/compose.hosted.yaml` define sólo la API y una puerta HTTPS con Caddy. La
API exige Entra, monta una base SQLite persistente, desactiva ambos fixtures y
rechaza arrancar si falta la base, contiene DEMO o tiene menos registros que el
umbral configurado. El frontend continúa en Vercel. No ejecutar este perfil con
la base DEMO ni publicar una base real con el modo `pilot`.

La copia local elegida para el traslado es `data/local/real-preview.db`: tiene
43.381 registros REAL, cero DEMO, cuatro lotes completos y ninguna sesión de
revisión de prueba. Los cuatro maestros Excel comparados con los hashes de
ingesta coinciden salvo `Medicamento-cargaMaster25062026.xlsx`: el archivo ZIP
cambió, pero las siete hojas conservan exactamente las mismas filas, valores y
fórmulas que la versión importada. La base supera `PRAGMA quick_check`.

Preparar una instantánea separada, sin modificar la base original:

```powershell
python scripts/prepare_hosted_snapshot.py data/local/real-preview.db data/hosted/real.db
$env:HOSTED_MIN_REAL_RECORDS = '43381'
python scripts/check_hosted_database.py data/hosted/real.db
```

La instantánea preparada el 14 de octubre tiene SHA-256
`22c3c86ee4bb0922d5b2c7f8b50ee9e2e27e30d7c04ec2223803c482127bfdfd`.
Comprobar esta huella de nuevo en el servidor antes de arrancar. Una instantánea
nueva puede tener otra huella y debe documentarse como nueva entrega.

`data/hosted/` está ignorado por Git y excluido del contexto de Docker. Subir
`real.db` al servidor por un canal de transferencia autenticado; nunca al
repositorio ni a Vercel. En el servidor, clonar el repositorio, crear
`data/hosted/`, instalar allí el fichero con propietario UID/GID `10001:10001`
y limitar acceso al directorio y a las copias de seguridad. No sobrescribir una
base que ya contenga decisiones de los revisores: para actualizaciones se
requiere un procedimiento de migración y respaldo.

El servidor necesita DNS público para la API, puertos 80/443, Docker Compose y
almacenamiento persistente con margen para la base, sus copias y los artefactos.
Copiar `infra/hosted.env.example` a `.env.hosted` fuera de Git y sustituir sus
marcadores con la configuración Entra aprobada. El dominio en `API_DOMAIN`
debe resolver a ese servidor. Desde la raíz del proyecto en el servidor:

```sh
docker compose --env-file .env.hosted -f infra/compose.hosted.yaml config --quiet
docker compose --env-file .env.hosted -f infra/compose.hosted.yaml up -d --build
```

Antes de cambiar Vercel, comprobar HTTPS y certificado, `/health` y `/ready`
con 200, `/database-info` con 43.381 REAL y cero DEMO, y una ruta de registros
sin token con 401/403. Registrar el redirect SPA
`https://farmalidacion-beta.vercel.app/auth-redirect.html`, asignar app roles a
las cuentas autorizadas y verificar una lectura autenticada. Sólo entonces
configurar `VITE_API_BASE_URL=https://<API_DOMAIN>` en el proyecto **frontend**
de Vercel, redesplegar y comprobar el catálogo desde un navegador externo con
una cuenta corporativa. El proyecto API DEMO de Vercel queda separado.
