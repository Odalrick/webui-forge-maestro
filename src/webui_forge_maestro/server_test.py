import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import HttpUrl

from webui_forge_maestro.config import Settings
from webui_forge_maestro.forge import ForgeClient
from webui_forge_maestro.models import ForgeModel, ForgeUpscaler
from webui_forge_maestro.server import ToolHandlers, create_server


@pytest.fixture
def settings() -> Settings:
    return Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=Path("/tmp/out"),
    )


@pytest.fixture
def fake_forge() -> Mock:
    forge = Mock(spec=ForgeClient)
    return forge


def test_get_sd_upscalers_returns_just_the_names(fake_forge: Mock, settings: Settings) -> None:
    fake_forge.list_upscalers.return_value = [
        ForgeUpscaler(
            name="ESRGAN_4x",
            model_name=None,
            model_path=None,
            model_url=None,
            scale=4.0,
        ),
        ForgeUpscaler(
            name="R-ESRGAN 4x+",
            model_name="RealESRGAN_x4plus",
            model_path="/models/x4.pth",
            model_url=None,
            scale=4.0,
        ),
    ]
    handlers = ToolHandlers(fake_forge, settings)

    result = handlers.get_sd_upscalers()

    assert result == ["ESRGAN_4x", "R-ESRGAN 4x+"]
    fake_forge.list_upscalers.assert_called_once_with()


def test_create_server_registers_get_sd_upscalers(fake_forge: Mock, settings: Settings) -> None:
    handlers = ToolHandlers(fake_forge, settings)
    mcp = create_server(handlers)
    tools = asyncio.run(mcp.list_tools())
    tool_names = [tool.name for tool in tools]
    assert "get_sd_upscalers" in tool_names


def test_get_sd_models_returns_just_the_titles(fake_forge: Mock, settings: Settings) -> None:
    fake_forge.list_models.return_value = [
        ForgeModel(
            title="sd_xl_base_1.0 [31e35c80fc]",
            model_name="sd_xl_base_1.0",
            hash="31e35c80fc",
            sha256="31e35c80fc7e0d2c",
            filename="/models/sd_xl_base_1.0.safetensors",
            config=None,
        ),
        ForgeModel(
            title="flux1-dev [4af6c1d6a3]",
            model_name="flux1-dev",
            hash="4af6c1d6a3",
            sha256="4af6c1d6a3b9",
            filename="/models/flux1-dev.safetensors",
            config=None,
        ),
    ]
    handlers = ToolHandlers(fake_forge, settings)

    result = handlers.get_sd_models()

    assert result == [
        "sd_xl_base_1.0 [31e35c80fc]",
        "flux1-dev [4af6c1d6a3]",
    ]
