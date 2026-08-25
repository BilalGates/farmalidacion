from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='APP_', env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    app_name: str = 'Validador de fichas técnicas'
    env: Literal['development', 'test', 'production'] = 'development'
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    database_url: str = Field(default='sqlite:///./data/local/validator.db', repr=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
