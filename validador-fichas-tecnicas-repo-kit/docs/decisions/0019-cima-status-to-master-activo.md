# ADR-0019 — Correspondencia de bajas y revocaciones CIMA con `ACTIVO` del maestro

- Estado: aceptado (decisión del responsable de farmacia, 2026-10-30)
- Fecha: 2026-10-30
- Decisiones relacionadas: D-040, D-027, D-031, D-023
- Responsables: producto / farmacia / tecnología

## Contexto

Las novedades CIMA (DEV-703) avisan de cambios de estado, comercialización y
bajas, pero los Excel maestros no tienen columnas de estado de autorización ni
de comercialización de CIMA. La única columna relacionada es `ACTIVO`
(CHAR(1), hoja `General` de Especialidades, Medicamentos y Principios activos),
catalogada como identificador interno. Sin una regla aceptada, ningún valor CIMA
puede proponerse para el maestro.

## Decisión

1. Regla `ADR-0019:baja-revocacion-activo:v1`: si la novedad es una **baja**
   (`tipoCambio=2`) o la respuesta CIMA capturada tiene **revocación**
   (`estado.rev` presente), se propone `ACTIVO = "N"` para el registro del
   catálogo enlazado por CN exacto (D-027).
2. Es solo una **propuesta**: no se aplica sin la decisión de un farmacéutico,
   no se preselecciona en la interfaz (D-023) y cita la respuesta CIMA inmutable
   de la que sale.
3. Cualquier otro estado (suspensión, autorización, cambios de comercialización)
   no tiene correspondencia: se muestra como «Revisar en CIMA» **sin valor
   propuesto**.
4. Las altas copian `nombre` de CIMA a las columnas de descripción del maestro
   (`DESCRIPCION_PRESCRIPCION`, `DESCRIPCION_GESTION`) como literal con
   procedencia citada, sin normalizar; aceptar un alta crea un **borrador** en el
   catálogo pendiente de validar, que el farmacéutico completa antes de
   exportarlo.
5. Las acciones pendientes no bloquean la exportación ni añaden avisos al Excel.

## Consecuencias

- `maintenance_action.proposed_value` solo puede tener valor con `rule_id`
  igual a esta regla (o a otra regla aceptada posterior).
- Cambiar la regla exige un ADR nuevo y una nueva `derivation_version`; las
  acciones ya creadas no se reescriben.
- Reabrir una acción aceptada **no deshace** lo aplicado (archivo, `ACTIVO = N`
  o borrador de alta): solo la devuelve a pendiente. Revertir exige otra
  revisión append-only (desarchivar, nueva revisión del campo).
- Si el maestro ya dice `N`, aceptar `ACTIVO = N` registra la decisión sin
  escribir ninguna revisión.
- Diseño: `docs/design/novedades-cima-accionables.md`.
