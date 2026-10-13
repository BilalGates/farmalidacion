# Identidad verificada con Microsoft Entra ID

## Estado

**Aplazado por el responsable el 2026-10-06.** La integración técnica y la
vista de administración están preparadas, pero el modo Entra no se activa.
Para retomarlo hacen falta tenant ID, client IDs de SPA y API, origen y API
públicos HTTPS, redirect URI exacta, scope, app roles y sus capacidades,
asignaciones de usuarios y vínculos Object ID → identificador de revisor
revisados por el administrador. Después: configurar el despliegue, ejecutar
migraciones y probar inicio/cierre, permisos y doble revisión con dos cuentas
corporativas reales. No solicitar ni guardar contraseñas, client secrets o
tokens en el repositorio. El piloto sigue con identidad declarada.

Actualización 2026-10-05: el responsable solicita inicio/cierre de sesión y
permisos reales. Se han solicitado tenant, registros SPA/API, scope y roles.
Integración implementada y probada con tokens sintéticos, desactivada por defecto
(ADR-0015). La vista previa conserva identificación declarada en Equipo,
etiquetada como piloto. No se ha activado ni probado con cuentas corporativas.

Plan de integración preparado el 30-09-2026. El piloto actual usa identidad
declarada (D-018); no debe describirse como autenticado. La integración requiere
datos de registro y permisos del administrador de Entra ID antes de activarse.
Intune administra dispositivos, mientras Entra ID proporciona las cuentas y
autenticación: [Microsoft Intune core concepts](https://learn.microsoft.com/en-us/intune/fundamentals/manage-devices).

## Datos que debe entregar el administrador

1. Tenant ID del directorio corporativo y confirmación de aplicación de un solo
   tenant.
2. Client ID del registro SPA, URI de redirección para el origen real de la web
   y client ID del registro de la API.
3. Scope delegado que la SPA solicitará para la API y audiencia que recibirá
   el access token. No basta un token de Microsoft Graph ni un ID token.
4. Grupo o app role autorizado a revisar, y el rol farmacéutico para decisiones
   reservadas. Confirmar cómo se asignarán Elena Tomás y la segunda revisora.
5. Política de acceso condicional: si exige dispositivo Intune conforme, MFA u
   otras condiciones, y origen HTTPS autorizado.

No enviar client secrets, contraseñas ni tokens al repositorio. Los IDs y scopes
anteriores son identificadores de configuración, no credenciales.

## Contrato de implementación

- La SPA React usará MSAL con código de autorización y PKCE para solicitar un
  access token dirigido a la API. [Flujos MSAL](https://learn.microsoft.com/en-us/entra/identity-platform/msal-authentication-flows).
- FastAPI validará firma mediante claves publicadas por el tenant, `iss`, `tid`,
  `aud`, `exp`, `nbf`, versión de token, cliente autorizado y scope o app role.
  Un token válido para Graph u otro tenant será rechazado. [Validación de
  claims](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation).
- La identidad de auditoría se derivará de `tid` y `oid` validados por el
  servidor; el nombre visible será sólo descriptivo. Ningún `reviewer_id` del
  body o query podrá cambiar el actor de una escritura.
- Las rutas de lectura de datos reales, administración, revisión, mantenimiento
  y exportación tendrán autorización explícita. `/health` y `/ready` podrán
  seguir siendo endpoints operativos sin datos clínicos.
- La doble validación comparará identidades verificadas distintas. Se conservará
  la garantía `declarada` en eventos históricos; sólo eventos nuevos autenticados
  podrán recibir una garantía distinta, sin reescribir auditoría anterior.
- La activación será fail closed: configuración incompleta o JWKS inaccesible
  bloquea operaciones protegidas; DEMO local podrá conservar un modo de desarrollo
  explícito y aislado.

## Perímetro concreto preparado el 5 de octubre

- `frontend/src/api/client.ts`: token de la API; descargas mediante `fetch` y
  blob autenticados, nunca tokens en enlaces.
- `main.py`: proteger todos los routers, `/database-info`, documentos,
  auditoría y descarga; CORS admite `Authorization`.
- `reviewer_identity.py` y `records.py`: principal derivado del servidor.
  Rechazar actor suplantado en cuerpo, query y cabeceras, incluidas cargas y
  escrituras de conexiones/fuentes.
- `reviewer_api.py`: autoridad administrativa separada de rol farmacéutico.
- Cola y sesiones de medición: comprobar propietario, versión y capacidad.
- Borradores/caché: espacio por principal, retirar memoria al salir y conservar
  borradores del propietario sin transferirlos a otra cuenta.
- Historial: no cambiar garantía declarada ni vincular handles antiguos por
  nombre/correo. Primera lectura verificada o vínculo formal antes de segunda
  lectura corporativa.

| Capacidad propuesta | Operaciones |
|---|---|
| Consultar | Catálogo, fuentes, procedencia, historial |
| Revisar | Asignación propia y decisiones permitidas por rol clínico |
| Mantener catálogo | Datos de trabajo, relaciones y clasificaciones |
| Gestionar fuentes | Conexiones, carga y mantenimiento |
| Exportar | Generación y descarga |
| Administrar equipo | Altas, roles y activación |

El perímetro está implementado en `access_policy.py`, con prueba que compara
el manifiesto y todas las operaciones OpenAPI. La asignación corporativa de
capacidades está pendiente. Configuración
incompleta debe cerrar acceso protegido, sin volver al selector del piloto.
Ocultar un botón no es autorización: se prueba cada operación en servidor.

`GET /auth/access` ofrece a un administrador con `team.manage` una vista de los
roles y capacidades configurados y de los vínculos de cuenta aceptados. Indica
si el primer acceso ya selló el vínculo y si el revisor está activo. Un vínculo
configurado no demuestra por sí solo que el usuario tenga asignado un app role
en Entra; esa asignación debe verificarse en el tenant. El endpoint no expone
tokens, contraseñas ni secretos y no permite reasignar un vínculo histórico.

## Configuración implementada

`APP_AUTH_MODE=entra`, `APP_ENTRA_TENANT_ID`, `APP_ENTRA_API_CLIENT_ID`,
`APP_ENTRA_SPA_CLIENT_ID`, `APP_ENTRA_REQUIRED_SCOPE`, `APP_ENTRA_SPA_SCOPE`,
`APP_ENTRA_ROLE_CAPABILITIES` y `APP_ENTRA_REVIEWER_BINDINGS`. Estos dos últimos
son objetos JSON: app role -> lista de capacidades y object ID -> handle aceptado.
Guids deben estar en formato canónico. No se vincula por email ni nombre.

Capacidades admitidas: `catalog.read`, `catalog.maintain`, `sources.read`,
`sources.manage`, `review.read`, `review.write`, `review.reconcile`, `export.read`,
`export.create`, `audit.read`, `team.manage`. Se conceden únicamente las declaradas
para los app roles del access token; ser farmacéutico no concede administración.
Añadir capacidades de lectura necesarias a cada rol que debe consultar su área.
Un segundo lector exclusivo debe carecer de lectura ordinaria/auditoría: el
endpoint ciego y el historial ordinario son contratos distintos.

### Matriz de la vista previa local (2026-10-07)

Los valores de app role en el registro **Farmalidación API** deben coincidir
exactamente con los siguientes. La matriz está preparada en
`.env.entra-preview` (ignorado por Git); un rol sin usuario asignado en Entra no
concede acceso.

| App role | Capacidades de aplicación |
|---|---|
| `Reader` | `catalog.read`, `sources.read` |
| `Administrator` | Todas las 11 capacidades admitidas |
| `Pharmacist` | Lectura y mantenimiento de catálogo; lectura de fuentes; lectura, escritura y conciliación de revisiones; lectura y creación de exportaciones; auditoría |
| `DataScientist` | Lectura y mantenimiento de catálogo; lectura y gestión de fuentes; lectura de cola y exportaciones; auditoría |

`Administrator` gestiona operaciones de la aplicación, pero las firmas clínicas
siguen sujetas al rol de revisor local. `Pharmacist` y `DataScientist` son roles
corporativos distintos; no convierten por sí solos el rol clínico del revisor.
Las asignaciones de usuarios se hacen en **Aplicaciones empresariales →
Farmalidación API → Usuarios y grupos**, y requieren un vínculo Object ID →
revisor local aceptado individualmente.

Registrar exactamente `<origen>/auth-redirect.html` como redirect de SPA. El
puente MSAL v5 se sirve del mismo origen con `Cache-Control: no-store`, sin COOP.
[Guía oficial del puente MSAL](https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/redirect-bridge.md).
El registro API debe emitir access tokens v2 e incluir app roles asignados al
usuario. La API necesita salida HTTPS al JWKS oficial; una caída sin clave válida
bloquea acceso. No hay secretos en la SPA.

Para Compose REAL hay un override de ejemplo `infra/compose.entra.example.yaml`.
La activación y los valores efectivos no se aplican automáticamente. Ejecutar
migraciones antes de servir: el vínculo se sella en el primer acceso y no se
reasigna; desactivar la persona en Equipo o retirar configuración revoca acceso.
El override exige además `APP_CORS_ALLOW_ORIGINS` como lista JSON del origen HTTPS
del frontend y `VITE_API_BASE_URL` con la URL pública HTTPS de la API. Vite
integra esta última al compilar: cambiar sólo una variable del contenedor ya
construido no cambia la API a la que llama el navegador. Publicar ambos servicios
mediante el proxy corporativo y registrar exactamente la URL final del puente
`/auth-redirect.html`; los puertos de Compose se enlazan sólo a `127.0.0.1`.

## Pruebas de aceptación de la integración

Token ausente, firma inválida, tenant incorrecto, audiencia incorrecta, token
caducado, scope o rol ausente y `reviewer_id` suplantado deben fallar. Dos cuentas
Entra distintas deben poder completar una doble revisión; la misma cuenta no.
Se probará renovación de claves y pérdida temporal de Entra sin aceptar tokens
no verificables. Una prueba de extremo a extremo usará el tenant de pruebas y
usuarios reales designados, sin grabar tokens en fixtures.

La integración se activará después de recibir los datos del administrador y
resolver el mapeo de roles. Hasta entonces, D-018 continúa como limitación
explícita del piloto.
