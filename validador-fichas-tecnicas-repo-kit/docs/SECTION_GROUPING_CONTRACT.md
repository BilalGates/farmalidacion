# Contrato de agrupación por apartado

- Issue: DEV-404
- Fase: 4
- Estado: implementado
- Módulo: `pharma_validator_api.section_grouping`
- Base normativa: especificación v2, 6 y 8

## Alcance

Agrupa los campos extraíbles del catálogo en una petición por apartado de la ficha técnica. Es puro: no llama al modelo, no persiste y no reinterpreta el catálogo.

Lee `ft_section_literal` tal como lo importó DEV-302 y solo reconoce las formas que el catálogo realmente contiene. No infiere el apartado de un campo que no lo declara.

## Por qué agrupar

La especificación 8 lo exige: reunir todos los campos que dependen de un apartado y resolverlos en una sola petición. Una llamada por campo convierte un proceso de horas en uno de días.

Medido sobre el catálogo real de 353 definiciones: **129 campos extraíbles se resuelven en 14 llamadas** por documento. La especificación estimaba ~150 campos en ~12 apartados; los datos confirman el orden de magnitud.

Los 14 apartados citados son: 1, 2, 3, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 6.1, 6.3, 6.5 y 6.6.

## Formas reconocidas

| Literal | Interpretación |
|---|---|
| `4.2` | un apartado |
| `4.2 / 6.6` | dos apartados; el campo se pide en ambos |
| `6.6 / 4.2` | los mismos dos; el orden del literal no es significativo |
| `-`, `–`, `—`, vacío, ausente | el catálogo no declara apartado |
| cualquier otra cosa | diagnóstico, nunca una suposición |

Un campo citado en varios apartados genera una entrada en cada uno: la evidencia puede estar en cualquiera de ellos y descartar apartados silenciosamente perdería la cita.

El nivel superior de un apartado nunca es `0`. La hoja del catálogo contiene, **fuera del rango de las 353 definiciones**, una tabla de resumen con ratios como `0.375` o `0.333333`. Son estadísticas legítimas en su contexto, no secciones; aceptarlas como apartado convertiría una celda mal leída en una petición contra una sección inexistente. Las 353 definiciones reales no contienen ningún valor numérico en esa columna.

## Diagnósticos, no descartes

Ningún campo desaparece en silencio. Sobre el catálogo real se producen 245 diagnósticos:

| Motivo | Casos |
|---|---|
| el catálogo no declara apartado de ficha técnica | 208 |
| el campo se repite dentro del mismo apartado | 37 |

Los 208 sin apartado son del mismo orden que los 204 campos que DEV-006 clasificó como no procedentes de la ficha técnica, pero **no son la misma cifra y no se ha comprobado que sean el mismo conjunto**: una cosa es el veredicto de procedencia y otra que la celda `Sección FT` esté rellena. La diferencia de cuatro queda como observación, no como equivalencia. En todo caso no son un fallo de la agrupación, sino la constatación de que la mayor parte del catálogo no se extrae de la FT.

Un campo con política `oculto` no se pide y no genera diagnóstico: la especificación 6 mapea `no_disponible` a `oculto` y ese campo no aparece en esta pantalla.

## Campos repetidos

El catálogo conserva identidades `(bloque, campo)` repetidas —DEV-302 documentó cinco pares y prohíbe fusionarlos—. Una petición no puede llevar el mismo nombre dos veces, porque la respuesta del modelo no sería atribuible a una de las dos definiciones.

La repetición se informa como diagnóstico y el campo se solicita una sola vez. **No se deduplica el catálogo ni se fusionan las definiciones**: la repetición queda sin resolver y visible, en lugar de desaparecer.

Este caso lo detectó la validación contra el catálogo real, no las pruebas sintéticas: la agrupación fallaba con un error de construcción al encontrar el primer nombre repetido.

## Verificación realizada

- 17 pruebas: literal simple y múltiple, orden no significativo, marcas de ausencia, literal no reconocido, apartado inexistente en la versión, apartado parcialmente disponible, política oculta, orden numérico y no lexicográfico, reducción de llamadas, campo repetido y determinismo.
- Validación sobre el catálogo real: 353 definiciones, 129 campos extraíbles, 14 llamadas, 245 diagnósticos.
- Ruff y mypy estricto sin incidencias en 26 ficheros.
- 70 pruebas acumuladas en las cuatro piezas de Fase 4 sin GPU.

## Límites

- No consulta la base de datos: recibe las definiciones ya importadas.
- No mapea `veredicto` a `politica_prefill`: la política llega decidida.
- No construye el prompt de 8.2 ni llama al modelo.
- No decide qué hacer con los 208 campos sin apartado: quedan fuera de la extracción por decisión del catálogo, no de este módulo.
