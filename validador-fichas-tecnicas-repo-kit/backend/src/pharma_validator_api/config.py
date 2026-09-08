from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Validador de fichas técnicas"
    env: Literal["development", "test", "production"] = "development"
    # Modo de datos declarado por quien arranca el servicio. No decide de dónde
    # salen los datos —eso lo fija `database_url` y lo que se haya importado—,
    # sino qué promete la interfaz al revisor. Se contrasta con el contenido
    # real de la base en `/database-info`, de modo que una discrepancia entre lo
    # declarado y lo almacenado sea visible en lugar de silenciosa.
    data_mode: Literal["real", "demo"] = "demo"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = Field(default="sqlite:///./data/local/validator.db", repr=False)
    load_demo_fixture: bool = False
    demo_fixture_path: Path = Path('data/examples/omeprazole-demo.json')
    # Conjunto DEMO multi-registro de la vertical de revisión. Desactivado por
    # defecto: los datos de demostración nunca se cargan sin pedirlo.
    load_showcase_fixture: bool = False
    showcase_fixture_path: Path = Path('data/examples/showcase-demo.json')
    cima_base_url: str = 'https://cima.aemps.es/cima/rest'
    cima_timeout_seconds: float = 15.0
    cima_requests_per_second: float = 5.0
    cima_max_retries: int = 3
    cima_backoff_seconds: float = 0.5
    cima_max_retry_delay_seconds: float = 30.0
    cima_cache_dir: Path = Path('data/local/cima-cache')
    # Orígenes permitidos para el frontend de desarrollo. Vacío por defecto:
    # el piloto sirve frontend y backend tras el mismo proxy.
    cors_allow_origins: tuple[str, ...] = ()
    # 10.1: lista configurable de revisores, formato `identificador:Nombre`.
    # Sin entradas no se puede firmar ninguna validación.
    reviewers: tuple[str, ...] = ()

    # --- Banderas de funcionalidad -------------------------------------------
    # Separan lo que está IMPLEMENTADO de lo que está VALIDADO CLÍNICAMENTE.
    # Los valores por defecto son conservadores: una función que dependa de
    # criterio farmacéutico no se enciende sola por haberse programado.
    #
    # `enable_llm_prefill` sigue apagada hasta que D-015 fije umbrales sobre
    # resultados reales; encenderla sin ellos presentaría como propuesta algo
    # cuya tasa de acierto nadie ha medido.
    enable_llm_prefill: bool = False
    enable_second_review: bool = False
    enable_export: bool = False
    # Directorio de artefactos de exportación. El fichero va a disco y la base
    # guarda sólo su metadato: un export de decenas de miles de fichas no cabe
    # razonablemente en una fila.
    export_artifact_dir: Path = Path('data/local/exports')
    enable_cima_link: bool = False
    enable_auto_revalidation: bool = False
    # La cola es infraestructura de trabajo, no criterio clínico: puede usarse
    # en desarrollo sin comprometer ninguna decisión farmacéutica.
    enable_review_queue: bool = True

    @property
    def clinically_validated(self) -> bool:
        """Ninguna función de este despliegue está validada clínicamente.

        Se expone como propiedad y no como ajuste para que no pueda encenderse
        por configuración: la validación clínica es un hecho externo al código,
        y afirmarla desde un fichero de entorno sería exactamente la
        falsificación que el proyecto no permite.
        """
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
