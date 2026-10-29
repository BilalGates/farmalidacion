---
name: revision-codigo
description: Revisar un diff o un módulo — corrección primero, luego seguridad, reglas del proyecto, mantenibilidad y estilo. Hallazgos con ubicación, escenario de fallo y arreglo. Cárgala para cualquier revisión de código.
---

# revision-codigo

## Preparar

- `git diff <base>...HEAD --stat` y luego el diff. Lee también lo que llama al código cambiado y lo que este llama.
- Lee el encargo: revisa contra lo que se pretendía, no contra lo que tú habrías hecho.

## Orden de revisión

1. **Corrección.** ¿Hace lo que dice? Casos límite, nulos, errores no tratados, condiciones de carrera, off-by-one, async sin `await`, efectos dobles.
2. **Seguridad y reglas de producto.** Ver skills `seguridad-web` y `farmalidacion-dominio`.
3. **Datos.** Consultas sin test que las ejecute, N+1, transacciones que faltan, migraciones irreversibles.
4. **Reglas del proyecto** (`.agents/proyecto.md`): tamaño de fichero, `any`, convenciones de carpetas, capa de datos, UI.
5. **Mantenibilidad.** Duplicación evidente, nombres engañosos, complejidad innecesaria, código muerto.
6. **Estilo** solo si el linter no lo cubre y afecta a la lectura.

## Cada hallazgo

```
[gravedad] fichero:línea — qué está mal
Escenario: entrada/estado concreto → resultado incorrecto
Arreglo:   cambio mínimo
```

Sin escenario concreto, es una sospecha: márcala así o no la incluyas.

## No

- No pidas reescrituras fuera del alcance del cambio; anótalas aparte.
- No mezcles preferencias personales con defectos.
- No repitas lo que ya marca una herramienta automática.
