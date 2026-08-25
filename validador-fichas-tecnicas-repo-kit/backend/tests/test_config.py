from pharma_validator_api.config import Settings


def test_settings_read_typed_environment(monkeypatch) -> None:
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('APP_LOG_LEVEL', 'WARNING')
    settings = Settings(_env_file=None)
    assert settings.env == 'test'
    assert settings.log_level == 'WARNING'
