# ADR-0015 — Sesión Entra y permisos por operación

Estado: aceptado para implementación por la petición explícita del responsable
del 5 de octubre de 2026. Activación corporativa y asignación de permisos pendientes.
Amplía D-018; no certifica identidad en el modo piloto ni aceptación clínica.

## Contexto y decisión

El responsable pide iniciar/cerrar sesión y acceder sólo con cuentas autorizadas.
El plan previo ya propone Microsoft Entra ID. Se implementa esa integración
desactivada por defecto, sin inventar cuentas, roles corporativos ni contraseñas.

La SPA utiliza MSAL Browser, código y PKCE, puente de redirección empaquetado en
el mismo origen y tokens en cabecera. El servidor admite exclusivamente access
tokens v2 del tenant, audiencia y SPA configurados, con firma RS256, tiempos,
scope delegado y app roles asignados. Cada ruta y método tiene capacidad explícita.
Nueva ruta sin política se rechaza. Configuración incompleta devuelve 503; no
hay degradación silenciosa a piloto. Salud y configuración pública no sirven datos.

`/auth/me` decide identidad, rol clínico y capacidades efectivos. Cuerpo, query
y cabeceras de importación no pueden suplantar al actor autenticado. Cola conserva
versiones, propietario y lease; mediciones verifican propietario. La segunda
lectura deja de asumir rol farmacéutico. Roles clínicos y administración son
autoridades distintas, ambas comprobadas en el servidor.

Un vínculo explícito `(tid, oid) -> handle` conserva actores históricos. El
primer acceso verificado sella una fila con unicidad en ambos sentidos, fecha
y prohibición de edición/borrado por ORM; no existen endpoints de reasignación.
Configuración que contradiga un vínculo sellado se rechaza. Ni nombre ni correo
crean vínculos. Sólo la persona autenticada de la petición recibe la garantía
`verificada_entra`; las firmas anteriores permanecen intactas. Fuentes, conexiones
y cola no tienen columna de garantía; sus actores se comprueban sin reinterpretar
su historial ni ampliar silenciosamente esos modelos.

Al salir se retira el programa, se vacía la caché y se ignoran respuestas de la
sesión anterior. Los borradores se conservan en un espacio por sujeto; no se
heredan borradores del piloto ni de otra cuenta. Preferencias visuales siguen
siendo del navegador. Una cuenta con sólo exportación conserva navegación propia.

## Alternativas, límites y migración

Contraseñas locales añadirían una segunda autoridad y gestión de credenciales
no elegida por el responsable. Un selector etiquetado «login» no autenticaría.
Ocultar botones sin permisos en API permitiría operar por peticiones manuales.

La migración `a9b0c1d2e3f4` sólo añade vínculos vacíos; no vincula semillas ni
reescribe eventos. La aceptación de cada vínculo inicial es responsabilidad
del administrador que entrega la configuración. Retirarlo de configuración
revoca acceso, conservando la fila y el historial.

El endpoint ciego mantiene su contrato: no entrega primera lectura hasta emitir
la segunda. El acceso ordinario al historial sigue siendo una capacidad distinta;
un rol de segunda lectura exclusiva no debe incluir `catalog.read` ni `audit.read`.
No se afirma que esconder el historial ordinario en la UI garantice ceguera.

## Verificación y activación

Pruebas sintéticas con firma real y DB desechable: claims/firma incorrectos,
scope/roles/cuenta no asignada, suplantación, permisos, propietario, configuración
incompleta, caída de claves, rotación JWKS, vínculo inmutable y auditoría nueva.
Pruebas React: puerta antes de datos, denegación del servidor, salir, reintento
MSAL, carrera de tokens, borradores por sujeto y navegación por permisos.

Pendientes: tenant/registros, scope y redirects aceptados, matriz efectiva,
vínculos de personas reales y prueba E2E con cuentas designadas y políticas de
MFA/dispositivo. No se activa Entra sobre la vista previa ni producción en este corte.
