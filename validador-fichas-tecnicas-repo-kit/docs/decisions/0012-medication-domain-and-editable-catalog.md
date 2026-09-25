# ADR-0012 — Dominio del medicamento y catálogo editable

- Estado: aceptado
- Fecha: 2026-09-22
- Decisiones relacionadas: D-029, D-030, D-031, D-032, D-033
- Responsables: producto, farmacia y tecnología

## Contexto

La revisión funcional realizada con un farmacéutico detectó que la aplicación
expone como una lista plana identidades que en el dominio forman una jerarquía.
También permite validar valores y editar ocurrencias de bloques, pero no mantener
de forma completa el registro canónico. Ambas limitaciones dificultan trabajar
con el catálogo completo, que es el propósito operativo del producto.

El Nomenclátor de prescripción distingue la descripción clínica de sustancia
activa (DCSA/VTM), la descripción clínica de producto (DCP/VMP), la descripción
clínica de producto con formato (DCPF/VMPP) y la presentación identificada por
Código Nacional. DCPF incorpora el contenido o tamaño del envase; un producto
puede contener varios principios activos. CIMA identifica además la autorización
y sus documentos mediante `nregistro`.

La aceptación farmacéutica deja de tratarse como trabajo previo al rediseño. Es
una capacidad operativa que el profesional ejecutará progresivamente sobre el
catálogo dentro del producto.

## Restricciones

- No fusionar marca, autorización, CN, DCPF, DCP y DCSA.
- Una presentación puede contener más de un principio activo.
- Los datos fuente y sus versiones permanecen inmutables.
- Una corrección humana crea estado canónico e historial; no reescribe la fuente.
- No inferir una relación por coincidencia de texto.
- No convertir una diferencia con CIMA en decisión clínica automática.
- No automatizar BOT PLUS Web con credenciales de una cuenta de usuario.
- Mantener la interfaz y sus mensajes en español.

## Opciones consideradas

### Opción A — Mantener registros planos y mejorar únicamente la tabla

Es barata, pero conserva la ambigüedad entre niveles, hace difícil navegar entre
presentaciones y no resuelve la edición completa.

### Opción B — Sustituir el modelo genérico por tablas farmacéuticas rígidas

Hace explícito el dominio, pero arriesga una migración destructiva y duplica la
capa probada de documentos, procedencia, bloques, decisiones y auditoría.

### Opción C — Añadir una capa tipada de identidad y mantenimiento

Conserva `TargetRecord` como sujeto canónico y añade identidades, relaciones y
proyecciones tipadas para producto comercial, autorización, presentación, DCPF,
DCP y DCSA. Los valores originales continúan en las estructuras actuales; el
estado canónico editable y su historial se superponen sin borrarlos.

## Decisión

Se adopta la opción C.

La navegación principal seguirá esta estructura contextual:

```text
producto comercial / autorización
└── presentación — CN
    └── DCPF — DCP más contenido del envase
        └── DCP — sustancia(s), dosis y forma
            └── una o varias DCSA / sustancias activas
```

La estructura expresa navegación y atribución, no obliga a que todas las
relaciones sean 1:N. Los vínculos se almacenan explícitamente y con procedencia.
`nregistro` continúa siendo la identidad regulatoria/documental de CIMA; el CN
identifica una presentación, no una marca completa.

El CN canónico de trabajo contiene seis dígitos. La representación original de
cada fuente se conserva literalmente, incluido un eventual séptimo dígito de
control. Las integraciones pueden validar o producir su representación completa
mediante una regla versionada, pero nunca descartar el original ni enlazar por
una normalización silenciosa.

La clasificación comercial (`original`, `generico`, `biosimilar`,
`sin_clasificar`) es independiente de condiciones como medicamento huérfano,
estupefaciente, psicotrópico, especial control médico o uso hospitalario. Estas
condiciones no son tipos mutuamente excluyentes.

La edición distingue:

1. afirmación de fuente inmutable;
2. estado canónico vigente;
3. revisión append-only con actor, motivo, instante, antes y después.

Crear, corregir, relacionar, clasificar, archivar y sustituir registros serán
operaciones de mantenimiento. Archivar o sustituir no elimina historia. Los
cambios emplean versión observada para evitar sobrescrituras concurrentes.

CIMA se presenta dentro del expediente con documento legible, búsqueda por
apartado y comparación campo a campo. Cada diferencia conserva versión,
apartado, fragmento y resultado (`coincide`, `difiere`, `falta_registro`,
`falta_cima`, `no_comparable` o `requiere_criterio`).

BOT PLUS se considera una fuente opcional para precios, financiación,
dispensación, interacciones y otras informaciones contratadas. D-033 permanece
pendiente de confirmar el producto de integración, su licencia, catálogo de
servicios, entorno de prueba, vigencias y contrato de uso. Tener acceso a BOT
PLUS Web no autoriza su automatización.

## Consecuencias

### Positivas

- La interfaz puede reflejar la forma de trabajo del farmacéutico.
- Una marca con múltiples presentaciones deja de aparecer como filas inconexas.
- La composición múltiple es una relación, no texto concatenado.
- Se habilita mantenimiento real sin sacrificar procedencia ni auditoría.
- CIMA y futuras fuentes se comparan sin convertirse en autoridad silenciosa.

### Negativas

- Requiere una migración aditiva y una proyección de compatibilidad temporal.
- La búsqueda debe indexar varias identidades y relaciones.
- Algunas relaciones importadas quedarán pendientes de conciliación.

### Riesgos

- Confundir DCSA con el principio activo específico de una presentación.
- Tratar el CN de seis dígitos como sustituto de su literal fuente.
- Presentar clasificaciones regulatorias como una única taxonomía excluyente.
- Permitir que una edición canónica oculte lo que decía la fuente.

## Validación

- Caso con dos CN de una misma marca y distinto DCPF.
- Caso con una DCP que contiene dos o más sustancias activas.
- Casos original, genérico, biosimilar, huérfano y especial control.
- Entrada de CN en seis y siete dígitos sin pérdida del literal.
- Edición concurrente rechazada sin escritura parcial.
- Reconstrucción completa del historial de una corrección.
- Comparación CIMA con evidencia literal y sin decisión automática.
- Prueba de usabilidad del listado sobre el volumen real.

## Migración y reversibilidad

La migración será aditiva. Primero se crean identidades y relaciones tipadas,
después se proyectan desde los registros existentes y se publica un informe de
ambigüedades. Las pantallas actuales se mantienen hasta que la nueva navegación
supere pruebas funcionales y de volumen. No se elimina ninguna tabla ni dato en
la primera entrega.

## Preguntas pendientes

- Contrato y disponibilidad de BOT PLUS Integración (D-033).
- Fuente autoritativa y regla exacta para cada condición especial.
- Regla aprobada de cálculo/validación del dígito de control del CN.
- Alcance exacto de las operaciones masivas de mantenimiento.

