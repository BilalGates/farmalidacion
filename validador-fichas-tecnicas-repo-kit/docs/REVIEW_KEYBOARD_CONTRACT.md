# Contrato de navegación por teclado de la revisión

- Issue: DEV-504
- Fase: 5
- Estado: implementado y verificado técnicamente
- Módulo: `frontend/src/domain/shortcuts.ts`
- Base normativa: plan de Fase 5; especificación 8

## Por qué el mapa es un dato y no un `if`

La tabla que se muestra al revisor y el comportamiento real salen del mismo
array `SHORTCUTS`. Si el mapa viviera dentro del componente, añadir un atajo
significaría acordarse de documentarlo, y la ayuda en pantalla acabaría
describiendo algo distinto de lo que hace la aplicación.

## Mapa

| Atajo | Acción |
|---|---|
| Alt + ↓ | Campo siguiente |
| Alt + ↑ | Campo anterior |
| Alt + → | Ficha siguiente de la cola |
| Alt + ← | Ficha anterior de la cola |
| Alt + Enter | Abrir o cerrar la revisión del campo activo |
| Ctrl + Enter | Guardar la decisión del campo activo |
| Esc | Cerrar la edición sin guardar |
| Alt + E | Llevar el foco a la evidencia |
| Alt + C | Volver al campo desde la evidencia |
| Shift + ? | Mostrar u ocultar la ayuda |

## Restricciones que el mapa respeta

**No se pisan atajos del navegador.** Ctrl+T, Ctrl+W, Ctrl+L y F5 siguen
llegando al navegador. El modificador principal es Alt, que en la práctica
queda libre; Ctrl+Enter se usa para guardar por ser convención establecida.

**Nada de una sola tecla mientras se escribe.** Cada atajo declara
`worksWhileTyping`. Teclear «?» en un comentario no puede abrir la ayuda, y
escribir «c» en un valor no puede cambiar el foco.

**Un modificador de más no dispara nada.** Ctrl+Alt+Enter no coincide con
`guardar` ni con `editar`: si un modificador no está declarado, debe estar
ausente. Sin esta regla una combinación podría ejecutar dos acciones.

**Ningún atajo ejecuta una acción destructiva de forma inmediata.** El mapa no
contiene «descartar» ni «eliminar». Eliminar una ocurrencia de bloque exige
pasar por el editor y declarar el motivo.

**Guardar no puede saltarse una comprobación.** Ctrl+Enter atraviesa la misma
condición que habilita el botón. Un atajo que guardase una decisión incompleta
estaría firmando por un farmacéutico.

## Qué sigue abierto

Alt+→ y Alt+← están declarados y documentados, pero la navegación entre fichas
de la cola todavía no está conectada a la pantalla: el atajo se resuelve y no
tiene efecto. Se implementará junto con la integración de cola y revisión.
