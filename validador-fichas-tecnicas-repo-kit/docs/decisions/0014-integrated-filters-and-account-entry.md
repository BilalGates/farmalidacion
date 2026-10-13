# ADR-0014 — Filtros integrados y entrada de identidad

Fecha: 2026-10-05. Estado: aceptado para la interfaz por petición explícita del
responsable. La autenticación corporativa continúa pendiente en D-018.

## Contexto

Las capturas del responsable muestran nombres y revisión superpuestos, acciones
redundantes y filtros con distintas disposiciones. Solicita abrir por nombre,
mover apariencia a Equipo, filtros en columna y transiciones, además de sesiones
y permisos reales en vez de selección libre de identidad.

## Decisión de interfaz

- Seis columnas con `colgroup`, nombre completo como botón accesible y sin
  columna de apertura. Sin elipsis ni truncamiento. Se conservan modal,
  anterior/siguiente, foco de retorno y borradores.
- Revisión separa estado, responsable con nombre visible y operación. El ID
  identifica asignaciones y actúa como fallback si falta el nombre.
- Tema y densidad independientes en Equipo. Cabecera y expediente no permiten
  seleccionar otra persona directamente.
- Catálogo, Cola e Incidencias comparten filtros en una columna y controles de
  formulario. Abrir pliega temporalmente navegación; cerrar o salir restaura la
  preferencia manual sin sobrescribirla. En tamaños estrechos el panel aparece
  antes del contenido.
- Transiciones de 160–200 ms en navegación, controles, filtros, pestañas y
  expediente. `prefers-reduced-motion` elimina animaciones.
- Segunda lectura del modal se monta al primer acceso y después se conserva
  para mantener su formulario. No consulta al abrir catálogo.

## Identidad y límite pendiente

Entra ID es la dirección corporativa previa de `ENTRA_ID_INTEGRATION_PLAN.md`.
No existen tokens validados, sesiones ni permisos administrativos en el servidor
actual. Un selector recordado no equivale a autenticación ni control de acceso.

Hasta recibir configuración se concentra la identificación declarada en Equipo:
elegir persona, confirmar y finalizar identificación. Se etiqueta como piloto y
se explica la ausencia de autenticación. No aporta una garantía nueva. No se
crean contraseñas locales ni se reescriben firmas históricas por inferencia.

Activar acceso verificado requiere tenant, registros SPA/API, scope, audiencia,
redirecciones y matriz de permisos. La pregunta de proveedor y configuración
queda pendiente de respuesta del responsable.

## Alternativas e impacto

Se sustituye la excepción horizontal del catálogo y sus siete anchuras en la
CSS activa. CSS sola no coordinaría icono y `aria-expanded`; un contexto comunica
el estado efectivo. Sin migración de datos. El rol clínico no implica autoridad
administrativa. Entra debe aislar borradores por principal y resolver primeras
firmas declaradas antes de admitir doble lectura corporativa.

## Verificación

Pruebas de apertura por nombre y foco de retorno, asignación propia, preferencias,
plegado temporal e identificación declarada. Revisión geométrica con nombres
reales largos en ambos temas y densidades. Usabilidad farmacéutica y acceso
real con dos cuentas corporativas siguen pendientes.
