from pathlib import Path

import pytest
from pydantic import SecretStr

from webui_forge_maestro.config import Settings


def test_from_env_uses_upstream_defaults_when_env_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in [
        "SD_WEBUI_URL",
        "SD_OUTPUT_DIR",
        "SD_AUTH_USER",
        "SD_AUTH_PASS",
        "REQUEST_TIMEOUT",
        "SD_RESIZE_MODE",
        "SD_UPSCALE_MULTIPLIER",
        "SD_UPSCALE_WIDTH",
        "SD_UPSCALE_HEIGHT",
        "SD_UPSCALER_1",
        "SD_UPSCALER_2",
    ]:
        monkeypatch.delenv(var, raising=False)

    settings = Settings.from_env()

    assert str(settings.webui_url) == "http://127.0.0.1:7860/"
    assert settings.output_dir == Path("./output")
    assert settings.auth_user is None
    assert settings.auth_pass is None
    assert settings.request_timeout == 300
    assert settings.resize_mode == 0
    assert settings.upscale_multiplier == 4.0
    assert settings.upscale_width == 512
    assert settings.upscale_height == 512
    assert settings.upscaler_1 == "R-ESRGAN 4x+"
    assert settings.upscaler_2 == "None"


def test_from_env_reads_all_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SD_WEBUI_URL", "http://forge.test")
    monkeypatch.setenv("SD_OUTPUT_DIR", "/tmp/out")
    monkeypatch.setenv("SD_AUTH_USER", "alice")
    monkeypatch.setenv("SD_AUTH_PASS", "hunter2")
    monkeypatch.setenv("REQUEST_TIMEOUT", "60")
    monkeypatch.setenv("SD_RESIZE_MODE", "1")
    monkeypatch.setenv("SD_UPSCALE_MULTIPLIER", "2.5")
    monkeypatch.setenv("SD_UPSCALE_WIDTH", "2048")
    monkeypatch.setenv("SD_UPSCALE_HEIGHT", "2048")
    monkeypatch.setenv("SD_UPSCALER_1", "ESRGAN_4x")
    monkeypatch.setenv("SD_UPSCALER_2", "R-ESRGAN 4x+")

    settings = Settings.from_env()

    assert str(settings.webui_url) == "http://forge.test/"
    assert settings.output_dir == Path("/tmp/out")
    assert settings.auth_user == "alice"
    assert isinstance(settings.auth_pass, SecretStr)
    assert settings.auth_pass.get_secret_value() == "hunter2"
    assert settings.request_timeout == 60
    assert settings.resize_mode == 1
    assert settings.upscale_multiplier == 2.5
    assert settings.upscale_width == 2048
    assert settings.upscale_height == 2048
    assert settings.upscaler_1 == "ESRGAN_4x"
    assert settings.upscaler_2 == "R-ESRGAN 4x+"


def test_partial_auth_credentials_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SD_AUTH_USER", "alice")
    monkeypatch.delenv("SD_AUTH_PASS", raising=False)

    settings = Settings.from_env()

    # Both must be set for the model to retain either — matches upstream
    # behaviour where partial credentials produce no Authorization header.
    assert settings.has_auth() is False
