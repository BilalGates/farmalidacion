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
