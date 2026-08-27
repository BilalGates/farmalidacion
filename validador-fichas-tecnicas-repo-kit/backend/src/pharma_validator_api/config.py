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
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = Field(default="sqlite:///./data/local/validator.db", repr=False)
    load_demo_fixture: bool = False
    demo_fixture_path: Path = Path('data/examples/omeprazole-demo.json')
    cima_base_url: str = 'https://cima.aemps.es/cima/rest'
    cima_timeout_seconds: float = 15.0
    cima_requests_per_second: float = 5.0
    cima_max_retries: int = 3
    cima_backoff_seconds: float = 0.5
    cima_max_retry_delay_seconds: float = 30.0
    cima_cache_dir: Path = Path('data/local/cima-cache')


@lru_cache
def get_settings() -> Settings:
    return Settings()
