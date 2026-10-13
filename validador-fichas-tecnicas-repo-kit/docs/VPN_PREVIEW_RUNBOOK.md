# Vista previa HTTPS temporal en la VPN

Estado comprobado el 7 de octubre de 2026: la web abre en
`https://10.212.134.116:5443/` desde el equipo anfitrión, la API responde a
`/api/auth/config`, una ruta protegida sin sesión devuelve 401 y el responsable
ha iniciado sesión por esta URL. Falta el acceso desde el equipo de la compañera.

## Alcance

- El puerto 5443 se publica únicamente en la IP Fortinet indicada por
  `VPN_BIND_IP` en `.env.entra-preview`, pero cualquier cliente de esa VPN puede
  intentar conectar mientras la publicación esté activa.
- Los datos siguen exigiendo sesión Entra, app role asignado, vínculo Object ID
  → revisor y revisor activo. La asignación de personas se administra en Entra.
- El certificado temporal sirve sólo para la IP actual y caduca el 6 de
  noviembre de 2026. Si la IP cambia, regenerar certificado y URI SPA.
- `data/local/vpn-tls/server.key` nunca debe salir del equipo anfitrión.
  Distribuir sólo `ca.crt` para confiar en el certificado; no omitir avisos TLS.

## Arranque y parada

Desde la raíz del kit, la publicación VPN se arranca con:

```powershell
docker compose -p pharma-validator-sources --env-file .env.entra-preview -f compose.yaml -f infra/compose.entra.preview.yaml -f infra/compose.entra.vpn.preview.yaml --profile preview --profile vpn up --no-build --detach --wait frontend-vpn vpn-gateway
```

Al terminar la prueba, detener sólo la puerta de entrada:

```powershell
docker compose -p pharma-validator-sources --env-file .env.entra-preview -f compose.yaml -f infra/compose.entra.preview.yaml -f infra/compose.entra.vpn.preview.yaml --profile preview --profile vpn stop vpn-gateway
```

La redirección SPA añadida a Farmalidación Web es
`https://10.212.134.116:5443/auth-redirect.html`. La URI de `localhost`
permanece para pruebas en el anfitrión.

## Retirar la confianza de prueba

La autoridad `Farmalidacion VPN piloto CA` se instaló sólo en
`Cert:\CurrentUser\Root` del anfitrión. Al terminar definitivamente la prueba,
puede retirarse con:

```powershell
certutil -user -delstore Root AEA649A2366C1A38D0E040430428416676D79371
```

Retirar también la confianza del equipo de la compañera si se le instaló.
Para un uso mantenido, TI debe proporcionar nombre estable, certificado
gestionado y una política de red que limite los orígenes autorizados.
