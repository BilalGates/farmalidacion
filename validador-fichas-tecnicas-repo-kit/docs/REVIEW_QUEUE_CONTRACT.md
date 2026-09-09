# Contrato de la cola de revisión

DEV-502 organiza trabajo técnico y evita que dos revisores modifiquen por
accidente la misma ficha. La prioridad es declarada; la cola no infiere
urgencia ni relevancia clínica.

## Clasificación y filtros

Cada entrada conserva explícitamente su conjunto (`oro`, `medida` o `corpus`)
y si requiere doble validación. La API no deduce estas propiedades desde el
medicamento. El listado admite filtros combinables por entidad, bloque, estado,
conjunto, marca de doble validación y persona asignada.

Las filas existentes migran de forma conservadora a `corpus` y sin doble
validación. Una clasificación distinta debe declararse al encolar.

## Asignación

La asignación individual y por lote respeta la caducidad de 30 minutos y las
reglas del dominio. Cada elemento de un lote incluye la versión observada. Si
una versión está obsoleta, una entrada no existe o una asignación vigente
pertenece a otra persona, se rechaza el lote completo y no se conserva ninguna
asignación parcial. Un lote no puede repetir registros y se limita a 100.

La doble validación sigue permitiendo dos lecturas mediante su flujo explícito;
esta marca sólo clasifica la cola y no permite apropiarse del trabajo vigente
de otra persona.
