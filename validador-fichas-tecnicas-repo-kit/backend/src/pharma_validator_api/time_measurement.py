"""Medición de `segundos_empleados` por campo (DEV-508).

La especificación 7.2 es tajante: el piloto existe para medir. Se registra el
tiempo dedicado a cada campo desde que recibe el foco hasta que se resuelve,
**descontando inactividad por encima de 60 segundos**. Sin este dato la
comparación de la sección 17 no se puede hacer.

El descuento no es un detalle: un revisor que deja la pantalla abierta durante
la comida convertiría un campo de 8 segundos en uno de 3.600 y arruinaría la
media. Medir mal es peor que no medir, porque produce una cifra que parece un
resultado.

El módulo es puro: recibe intervalos de foco ya observados y calcula. No lee
relojes ni depende de la interfaz.
"""

from __future__ import annotations

from dataclasses import dataclass

# 7.2: inactividad por encima de este umbral no cuenta como trabajo.
INACTIVITY_THRESHOLD_SECONDS = 60


class TimeMeasurementError(RuntimeError):
    """Intervalos incoherentes; no se inventa una duración plausible."""


@dataclass(frozen=True)
class FocusInterval:
    """Tramo continuo con el campo enfocado, en segundos desde un origen común."""

    started_at: float
    ended_at: float

    def __post_init__(self) -> None:
        if self.ended_at < self.started_at:
            raise ValueError("Un intervalo no puede terminar antes de empezar.")

    @property
    def duration(self) -> float:
        return self.ended_at - self.started_at


@dataclass(frozen=True)
class FieldTiming:
    field_name: str
    counted_seconds: int
    discarded_seconds: int
    interval_count: int
    was_capped: bool

    @property
    def total_observed_seconds(self) -> int:
        return self.counted_seconds + self.discarded_seconds


def measure_field(field_name: str, intervals: tuple[FocusInterval, ...]) -> FieldTiming:
    """Calcula el tiempo imputable a un campo.

    Cada tramo de foco se cuenta entero hasta el umbral de inactividad; lo que
    exceda se descarta y se informa por separado. Descartar en silencio
    impediría distinguir un campo difícil de una pantalla olvidada abierta.
    """
    if not field_name:
        raise ValueError("La medición requiere campo.")

    ordered = sorted(intervals, key=lambda item: item.started_at)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current.started_at < previous.ended_at:
            raise TimeMeasurementError(
                f"Los intervalos de {field_name} se solapan; el foco no puede estar "
                "en dos sitios a la vez."
            )

    counted = 0.0
    discarded = 0.0
    capped = False
    for interval in ordered:
        if interval.duration > INACTIVITY_THRESHOLD_SECONDS:
            counted += INACTIVITY_THRESHOLD_SECONDS
            discarded += interval.duration - INACTIVITY_THRESHOLD_SECONDS
            capped = True
        else:
            counted += interval.duration

    return FieldTiming(
        field_name,
        int(round(counted)),
        int(round(discarded)),
        len(ordered),
        capped,
    )


@dataclass(frozen=True)
class SessionMeasurement:
    timings: tuple[FieldTiming, ...]

    @property
    def counted_seconds(self) -> int:
        return sum(item.counted_seconds for item in self.timings)

    @property
    def discarded_seconds(self) -> int:
        return sum(item.discarded_seconds for item in self.timings)

    @property
    def measured_field_count(self) -> int:
        return len(self.timings)

    @property
    def capped_field_count(self) -> int:
        return sum(1 for item in self.timings if item.was_capped)

    def seconds_per_field(self) -> float | None:
        """Métrica rectora de 10.2. Sin campos medidos no hay media."""
        if not self.timings:
            return None
        return self.counted_seconds / len(self.timings)


def measure_session(
    observations: tuple[tuple[str, tuple[FocusInterval, ...]], ...],
) -> SessionMeasurement:
    """Agrega la medición de una sesión de revisión.

    Un campo sin intervalos no se descarta: se registra con cero segundos, para
    que el recuento de campos medidos no dependa de si alguien lo enfocó.
    """
    names = [name for name, _ in observations]
    if len(set(names)) != len(names):
        raise TimeMeasurementError("Un campo no puede medirse dos veces en la misma sesión.")
    return SessionMeasurement(
        tuple(measure_field(name, intervals) for name, intervals in sorted(observations))
    )
