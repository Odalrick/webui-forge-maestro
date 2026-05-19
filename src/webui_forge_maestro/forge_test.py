import base64
import json
from pathlib import Path

import httpx
import pytest
import respx
import respx.models
from pydantic import HttpUrl, SecretStr

from webui_forge_maestro.config import Settings
from webui_forge_maestro.forge import ForgeAPIError, ForgeClient, ForgeUnreachableError
from webui_forge_maestro.models import Txt2ImgRequest


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
    assert auth_header.startswith("Basic ")
    decoded = base64.b64decode(auth_header.removeprefix("Basic ")).decode("ascii")
    assert decoded == "alice:hunter2"


@respx.mock
def test_list_models_returns_parsed_entries(client: ForgeClient) -> None:
    respx.get("http://forge.test/sdapi/v1/sd-models").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "title": "sd_xl_base_1.0 [31e35c80fc]",
                    "model_name": "sd_xl_base_1.0",
                    "hash": "31e35c80fc",
                    "sha256": "31e35c80fc7e0d2c...",
                    "filename": "/models/sd_xl_base_1.0.safetensors",
                    "config": None,
                },
                {
                    "title": "flux1-dev [4af6c1d6a3]",
                    "model_name": "flux1-dev",
                    "hash": "4af6c1d6a3",
                    "sha256": "4af6c1d6a3b9...",
                    "filename": "/models/flux1-dev.safetensors",
                    "config": None,
                },
            ],
        )
    )

    models = client.list_models()

    assert [m.title for m in models] == [
        "sd_xl_base_1.0 [31e35c80fc]",
        "flux1-dev [4af6c1d6a3]",
    ]


@respx.mock
def test_set_model_sends_correct_payload(client: ForgeClient) -> None:
    route = respx.post("http://forge.test/sdapi/v1/options").mock(
        return_value=httpx.Response(200, json={})
    )

    client.set_model("flux1-dev")

    assert route.called
    last_call: respx.models.Call = route.calls.last
    body = json.loads(last_call.request.content)
    assert body == {"sd_model_checkpoint": "flux1-dev"}


@respx.mock
def test_set_model_raises_on_500(client: ForgeClient) -> None:
    respx.post("http://forge.test/sdapi/v1/options").mock(
        return_value=httpx.Response(500, text="model not found")
    )

    with pytest.raises(ForgeAPIError):
        client.set_model("nope")


@respx.mock
def test_txt2img_sends_full_payload_and_parses_images(
    client: ForgeClient,
) -> None:
    route = respx.post("http://forge.test/sdapi/v1/txt2img").mock(
        return_value=httpx.Response(200, json={"images": ["BASE64IMAGE1", "BASE64IMAGE2"]})
    )
    request = Txt2ImgRequest(
        prompt="a cat",
        negative_prompt="blurry",
        steps=4,
        width=1024,
        height=1024,
        cfg_scale=1.0,
        sampler_name="Euler",
        scheduler="Simple",
        seed=-1,
        n_iter=1,
        restore_faces=False,
        tiling=False,
        distilled_cfg_scale=3.5,
    )

    response = client.txt2img(request)

    body = json.loads(route.calls.last.request.content)
    assert body["prompt"] == "a cat"
    assert body["n_iter"] == 1
    assert body["scheduler"] == "Simple"
    assert body["distilled_cfg_scale"] == 3.5
    assert response.images == ["BASE64IMAGE1", "BASE64IMAGE2"]


@respx.mock
def test_png_info_returns_info_string(client: ForgeClient) -> None:
    respx.post("http://forge.test/sdapi/v1/png-info").mock(
        return_value=httpx.Response(200, json={"info": "Steps: 4, Seed: 42"})
    )

    result = client.png_info("data:image/png;base64,FAKE")

    assert result == "Steps: 4, Seed: 42"
