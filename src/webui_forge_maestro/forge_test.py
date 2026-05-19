from pathlib import Path

import httpx
import pytest
import respx
import respx.models
from pydantic import HttpUrl, SecretStr

from webui_forge_maestro.config import Settings
from webui_forge_maestro.forge import ForgeAPIError, ForgeClient, ForgeUnreachableError


@pytest.fixture
def settings() -> Settings:
    return Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=Path("/tmp/out"),
    )


@pytest.fixture
def client(settings: Settings) -> ForgeClient:
    return ForgeClient(settings)


@respx.mock
def test_list_upscalers_returns_parsed_entries(client: ForgeClient) -> None:
    respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "ESRGAN_4x",
                    "model_name": None,
                    "model_path": None,
                    "model_url": None,
                    "scale": 4.0,
                },
                {
                    "name": "R-ESRGAN 4x+",
                    "model_name": "RealESRGAN_x4plus",
                    "model_path": "/models/RealESRGAN_x4plus.pth",
                    "model_url": "https://example.com/RealESRGAN_x4plus.pth",
                    "scale": 4.0,
                },
            ],
        )
    )

    upscalers = client.list_upscalers()

    assert [u.name for u in upscalers] == ["ESRGAN_4x", "R-ESRGAN 4x+"]
    assert upscalers[1].model_name == "RealESRGAN_x4plus"


@respx.mock
def test_list_upscalers_raises_forge_unreachable_on_connect_error(
    client: ForgeClient,
) -> None:
    respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(ForgeUnreachableError) as exc:
        client.list_upscalers()
    assert "forge.test" in str(exc.value)


@respx.mock
def test_list_upscalers_raises_api_error_on_500(client: ForgeClient) -> None:
    respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        return_value=httpx.Response(500, text="internal server error")
    )

    with pytest.raises(ForgeAPIError) as exc:
        client.list_upscalers()
    assert "500" in str(exc.value)


@respx.mock
def test_client_sends_basic_auth_when_configured() -> None:
    settings = Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=Path("/tmp/out"),
        auth_user="alice",
        auth_pass=SecretStr("hunter2"),
    )
    client = ForgeClient(settings)
    route = respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        return_value=httpx.Response(200, json=[])
    )

    client.list_upscalers()

    last_call: respx.models.Call = route.calls.last
    auth_header = last_call.request.headers.get("authorization", "")
    # Basic alice:hunter2 base64-encoded
    assert auth_header.startswith("Basic ")
