---
name: depurar
description: Método para corregir un fallo — reproducir, aislar la causa raíz, escribir el test que falla, arreglar con el cambio mínimo y comprobar que no vuelve. Cárgala ante cualquier bug, error de CI, test rojo o comportamiento inesperado.
---

# depurar

## 1. Reproducir

- Consigue el fallo **tú**, con un comando o unos pasos exactos. Sin reproducción no hay arreglo, hay una apuesta.
- Copia el mensaje de error literal y la traza. Lee la traza de abajo arriba hasta el primer fichero del proyecto.
- En CI: `gh run view --log-failed` y reproduce el mismo comando en local.

## 2. Aislar

- Pregunta qué cambió: `git log -p` del fichero, `git bisect` si el fallo es nuevo y hay un commit bueno conocido.
- Reduce: el caso mínimo que sigue fallando.
- Comprueba hipótesis una a una con evidencia (log, test, consulta), no leyendo y suponiendo.
- Distingue **síntoma** de **causa**: un `null` que revienta aquí suele venir de otro sitio.

## 3. Blindar

- Escribe el test que reproduce el fallo y **míralo fallar**.
- Arregla con el cambio mínimo en la causa, no en el síntoma.
- Mira el test pasar. Ejecuta el resto de la suite del módulo.
- Busca el mismo patrón en otros sitios (pide a Luisito): un bug rara vez está solo.

## 4. Entregar

```markdown
**Síntoma:** …
**Causa raíz:** fichero:línea — por qué
**Arreglo:** …
**Test:** nombre — falla antes, pasa después
**Mismo patrón en:** … (arreglado / anotado)
```

## Trampas

- No silencies el error (`try/catch` vacío, `?? []`, `eslint-disable`, `@ts-ignore`) para que "pase".
- No arregles tres cosas a la vez: no sabrás cuál lo resolvió.
- Si tras dos hipótesis fallidas sigues sin causa, para y resume lo descartado antes de seguir.
