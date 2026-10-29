---
name: commits
description: Agrupar cambios en commits atómicos por unidad funcional y redactar mensajes con la convención de Farmalidación (castellano, verbo en infinitivo, sin prefijo de tipo). La usa Larry; cárgala también para revisar si un historial es revisable.
---

# commits

## Agrupar por unidad funcional

- Implementación + tipos + tests + docs inseparables → **un** commit.
- Corrección independiente → su propio `fix`.
- Refactor sin cambio de comportamiento → separado de la funcionalidad.
- Docs generales → `docs`; herramientas, configuración, dependencias → `chore`.
- Tamaño no manda: treinta ficheros coherentes = un commit; tres arreglos sin relación = tres.
- Orden por dependencia: esquema/contratos → servicios → interfaz → tests → docs.

## Heurística rápida por ruta

| Ruta | Tipo probable |
|---|---|
| `src/**` nuevo comportamiento | `feat` |
| `src/**` corrige | `fix` |
| solo mueve/extrae | `refactor` |
| `**/__tests__/**`, `*.test.*`, `e2e/**` solos | `test` |
| `docs/**`, `*.md` solos | `docs` |
| `scripts/**`, config, `.github/**`, `.agents/**`, lockfile | `chore` |

El alcance sale de la carpeta de dominio (`src/modules/<x>` → `(x)`).

## Mensaje (convención de Farmalidación)

El tipo de la tabla anterior sirve para **agrupar**; no se escribe en el mensaje.

```
Explicar las discrepancias con lo que dice cada fuente

Por qué hacía falta y qué decisión se tomó, en castellano y en prosa.
Qué se verificó (tests, capturas) y lo que quedó pendiente.

Co-Authored-By: …   (si el perfil lo indica)
```

- Asunto: verbo en infinitivo con mayúscula (`Aplicar`, `Corregir`, `Retirar`, `Unificar`…), describe el resultado y no los ficheros, ≤ 72 caracteres, sin punto final.
- Cuerpo: el porqué y la verificación. Si el cambio rompe algo existente, dilo explícitamente.
- Prohibido: `wip`, `cambios varios`, `Actualizar archivos`, verbos vagos sin objeto (`Mejorar`, `Ajustar`).

## Seguridad

- Rutas concretas en `git add`; nunca `-A`, `.` ni globs amplios.
- Revisar `git diff --cached --stat` por commit: sin secretos, sin artefactos generados, sin restos de otro grupo.
- Nunca `--no-verify`, `amend`, `rebase`, `push`, `reset --hard`.
