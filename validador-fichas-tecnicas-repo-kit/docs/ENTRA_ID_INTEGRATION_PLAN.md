# Identidad verificada con Microsoft Entra ID

## Estado

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

## Pruebas de aceptación

Token ausente, firma inválida, tenant incorrecto, audiencia incorrecta, token
caducado, scope o rol ausente y `reviewer_id` suplantado deben fallar. Dos cuentas
Entra distintas deben poder completar una doble revisión; la misma cuenta no.
Se probará renovación de claves y pérdida temporal de Entra sin aceptar tokens
no verificables. Una prueba de extremo a extremo usará el tenant de pruebas y
usuarios reales designados, sin grabar tokens en fixtures.

La integración se activará después de recibir los datos del administrador y
resolver el mapeo de roles. Hasta entonces, D-018 continúa como limitación
explícita del piloto.
