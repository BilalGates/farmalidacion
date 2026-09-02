# Contrato de identificación del revisor

- Issue: DEV-501
- Fase: 5
- Estado: implementado en el núcleo de decisión; el selector de interfaz no existe todavía
- Módulo: `pharma_validator_api.reviewer_identity`
- Base normativa: especificación v2, 10.1 y 11.1; D-018

## Alcance

Resuelve quién firma una validación a partir de una lista configurable, y rechaza operar sin revisor seleccionado. Es puro: no persiste, no expone endpoints y no renderiza el selector.

## Identidad declarada, no demostrada

La especificación 10.1 es explícita: no hay LDAP ni contraseñas. Al abrir la aplicación se elige el nombre propio de una lista configurable, que se recuerda en el navegador. Es un selector, no un inicio de sesión.

La consecuencia que la especificación pide tener presente: **la firma de cada validación es declarada, no demostrada**. Identifica quién dijo ser, no quién era. Para utillaje interno en un equipo pequeño es razonable; no sostendría una auditoría formal.

El módulo lo hace explícito en el tipo: `Reviewer.assurance` vale siempre `declarada`. El campo existe para que una futura autenticación real —D-018, cerrada para el piloto y reevaluable en Fase 8— sea un cambio de valor y no una reinterpretación silenciosa de lo que significa la firma. Es lo que la especificación pide decidir a sabiendas ahora en vez de descubrirlo después.

## La lista es la autoridad

Los revisores se configuran mediante `APP_REVIEWERS`, con formato `identificador:Nombre`. No se crean revisores sobre la marcha: un nombre que no está en la configuración no puede firmar, porque entonces la lista dejaría de ser el registro de quién puede revisar.

Una lista vacía no firma nada. Es el comportamiento correcto para un despliegue sin configurar: mejor bloquear que aceptar cualquier nombre.

## Dos errores que no se confunden

| Situación | Significado |
|---|---|
| identificador ausente o vacío | la pantalla no pidió usuario |
| identificador desconocido | se intentó firmar con un nombre fuera de la lista |

Ambos impiden guardar, pero indican fallos distintos y llevan mensajes distintos. Colapsarlos en un único error genérico haría que un despliegue mal configurado y un intento de firma indebida se investigasen igual.

## Doble validación

La especificación 11.1 exige que los registros de alto riesgo se validen de forma independiente por **dos usuarios distintos**. `require_distinct` lo comprueba antes de que la segunda validación se registre, de modo que quien hizo la primera no pueda firmar también la segunda.

La comprobación vive aquí, junto a la resolución de identidad, y no en la pantalla: una segunda validación que llegue por cualquier vía queda igualmente sujeta a la regla.

## Verificación realizada

- 15 pruebas: construcción desde configuración, formato inválido, identificadores duplicados, revisor sin nombre, rechazo sin usuario seleccionado, revisor fuera de la lista, distinción entre ambos errores, nivel de garantía declarada, doble validación con dos revisores y su rechazo con el mismo, lista vacía, y lectura del formato real documentado en `.env.example`.
- Ruff y mypy estricto sin incidencias en 29 ficheros.

## Límites

- No implementa el selector de interfaz ni recuerda la elección en el navegador.
- No persiste la validación ni escribe auditoría: la tabla de solo inserción de la especificación 11 es DEV-609.
- No clasifica el riesgo ATC que activa la doble validación: es DEV-606.
- No gestiona la asignación de lotes para evitar colisiones: es DEV-502.
