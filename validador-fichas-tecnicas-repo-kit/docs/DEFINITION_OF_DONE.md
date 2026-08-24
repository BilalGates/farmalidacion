# Definición de terminado

Una issue no está terminada solo porque el código compila. Debe cumplir los puntos aplicables.

## Requisitos y alcance

- La issue tiene objetivo y criterios de aceptación verificables.
- El cambio respeta la especificación y los ADRs aceptados.
- Las decisiones nuevas están registradas; no se han ocultado como detalles de implementación.
- No se ha ampliado el alcance a datos de paciente ni decisión clínica.

## Datos

- Se preservan claves, cardinalidades, procedencia y versiones.
- No existe truncamiento, coerción, deduplicación ni descarte silencioso.
- Los importadores son idempotentes o documentan explícitamente por qué no pueden serlo.
- Los errores se convierten en diagnósticos accionables.
- Las migraciones aplican y revierten cuando sea razonable.

## Extractor y seguridad clínica

- Toda propuesta persistida tiene procedencia verificable.
- La evidencia textual coincide literalmente con una versión inmutable.
- `proponer_opciones` y `solo_evidencia` no tienen preselección.
- No se realizan inferencias, conversiones o cálculos clínicos no autorizados.

## Interfaz

- El flujo afectado funciona con teclado cuando corresponda.
- El foco es visible y no se pierde trabajo al recargar.
- Estados como pendiente, no consta y no aplica no se confunden.
- Se han comprobado rendimiento y accesibilidad aplicables.

## Exportación y auditoría

- Solo se exportan estados permitidos.
- Los bloqueos por doble validación se respetan.
- Los tipos y longitudes se validan sin truncar.
- La exportación es reproducible y deja informe.
- La auditoría permite reconstruir el cambio.

## Calidad técnica

- Pruebas unitarias, integración y regresión relevantes añadidas.
- Lint, typecheck y tests pasan.
- Se han revisado rutas de error y casos límite.
- No se añaden dependencias sin justificación.
- Docker y fixtures siguen funcionando.

## Documentación

- `STATUS.md` actualizado.
- Backlog y trazabilidad actualizados.
- ADR actualizado cuando cambia una decisión.
- README o documentación operativa actualizada si cambia el uso.

## Revisión

- Al menos un revisor independiente comprueba los riesgos principales.
- Los hallazgos críticos o altos se resuelven o se aceptan explícitamente.
- La respuesta de cierre incluye comandos ejecutados y resultados reales.
