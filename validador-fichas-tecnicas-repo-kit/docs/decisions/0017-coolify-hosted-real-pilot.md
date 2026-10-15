# ADR-0017 — Piloto REAL compartido en Coolify

Estado: plataforma aceptada por petición del responsable el 15-10-2026; activación pendiente de despliegue y comprobación de acceso corporativo.

## Decisión

Publicar frontend React y API FastAPI en el servidor existente de Coolify. La única ruta pública de la aplicación será el frontend HTTPS; nginx enviará `/api/` al backend en la red interna de Compose. La base SQLite REAL residirá en `/srv/farmalidacion/data/real.db`, fuera de Git y de las imágenes, con almacenamiento persistente y copia de seguridad independiente.

El backend arrancará sólo si la base contiene al menos 43.381 registros y cero registros DEMO. El modo Entra será obligatorio y fallará cerrado cuando falten registros, roles, vínculos o claves corporativas. No se migrarán datos de la demostración de Vercel ni se permitirá que su identidad declarada firme revisiones reales.

## Límites y operación

El servidor compartido tiene 2 CPU y 3,7 GB de RAM, con otros servicios en marcha. El volumen REAL debe verificarse después de transferirlo y antes de desplegar. No se borrarán aplicaciones, imágenes ni volúmenes ajenos para hacer espacio. La demo Vercel seguirá identificada como DEMO hasta que el acceso REAL esté verificado y se comunique la nueva URL al equipo.

La URI `https://<dominio>/auth-redirect.html` debe estar registrada en la SPA de Entra y deben comprobarse dos cuentas corporativas con sus roles. La existencia del servidor y una respuesta HTTP saludable no constituyen aceptación de la autenticación ni de los datos.
