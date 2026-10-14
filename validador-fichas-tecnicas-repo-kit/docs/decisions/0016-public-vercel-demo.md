# ADR-0016 — Demostración pública y desechable en Vercel

Estado: aceptada para demostración técnica por petición del responsable del 14-10-2026; no autoriza uso clínico ni almacenamiento de revisiones reales.

## Contexto

El frontend está publicado en Vercel y el equipo necesita abrirlo desde sus propios ordenadores. La API fallaba al abrir SQLite bajo el sistema de archivos de solo lectura de la Function. La base REAL está solo en el ordenador de desarrollo; no hay servidor persistente público configurado.

## Decisión

Cuando la API corre en Vercel con SQLite, crea una base de demostración en `/tmp` a partir del esquema ORM y tres fixtures sintéticos empaquetados. Su origen CORS es el frontend público. Se mantiene identidad declarada `pilot` solo para recorrer la demostración. El backend local y cualquier base externa configurada siguen sus rutas normales.

## Consecuencias

- No se publica el corpus REAL ni información clínica de pacientes.
- Cada instancia tiene una base temporal; las escrituras pueden perderse o divergir entre peticiones. No sirve para revisión compartida persistente.
- Una publicación operativa requerirá almacenamiento duradero, migraciones, Entra ID y una comprobación real con cuentas del equipo.

## Verificación

Arranque equivalente local bajo `VERCEL=1`: rutas de salud y configuración, registros DEMO exclusivamente y preflight CORS del frontend. Tras cada push, comprobar las dos URLs públicas y el arranque en frío de la API.
