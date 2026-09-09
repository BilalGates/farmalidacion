# Contrato del chat contextual citado

DEV-705 añade una consulta documental opcional dentro de la pantalla de
revisión. No es un asistente clínico: recupera texto literal de la ficha técnica
CIMA tipo 1 vinculada al registro activo y nunca propone tratamientos,
interpreta el contenido ni escribe campos.

## Contrato de lectura

- `POST /records/{record_id}/chat` acepta únicamente `question`, entre 1 y 500
  caracteres. Los campos adicionales se rechazan.
- Se consulta la versión más reciente de cada documento CIMA tipo 1 enlazado al
  registro y sólo sus artefactos con rol `section`.
- Una petición explícita de apartado devuelve el cuerpo literal completo de ese
  apartado. Las demás consultas hacen una búsqueda léxica determinista y
  devuelven hasta cinco fragmentos literales.
- El estado `answered` siempre incluye al menos una cita con versión documental,
  apartado y texto literal. `not_found` y `not_available` no fabrican respuesta.
- La operación no llama a un modelo generativo y no crea ni modifica registros,
  decisiones, bloques o procedencias. La elección de modelo sigue pendiente en
  D-014 y no es necesaria para este alcance.

## Interfaz y límites

El panel es colapsable y vive en la zona de evidencia de la revisión, por lo que
hereda el registro activo. Muestra de forma permanente que sólo localiza texto,
no escribe campos y no ofrece recomendaciones. Cada resultado presenta sus
citas inmediatamente debajo del mensaje.

No se admiten datos de pacientes ni preguntas orientadas a decidir un caso
clínico. El sistema no normaliza, resume ni completa el texto recuperado.
