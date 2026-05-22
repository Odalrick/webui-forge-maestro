import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import HttpUrl

from webui_forge_maestro.config import Settings
from webui_forge_maestro.errors import ForgeEmptyResponseError
from webui_forge_maestro.forge import ForgeClient
from webui_forge_maestro.models import ForgeModel, ForgeUpscaler, Txt2ImgResponse
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


def test_set_sd_model_calls_forge_and_returns_confirmation_string(
    fake_forge: Mock, settings: Settings
) -> None:
    handlers = ToolHandlers(fake_forge, settings)

    result = handlers.set_sd_model("flux1-dev")

    assert result == "Model set to: flux1-dev"
    fake_forge.set_model.assert_called_once_with("flux1-dev")


def test_generate_image_full_flow(fake_forge: Mock, settings: Settings, tmp_path: Path) -> None:
    settings = Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=tmp_path,
    )
    fake_forge.txt2img.return_value = Txt2ImgResponse(
        images=[
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
        ]
    )
    fake_forge.png_info.return_value = "Steps: 4, Seed: 42"
    handlers = ToolHandlers(fake_forge, settings)

    result = handlers.generate_image(prompt="a cat")

    assert len(result) == 1
    assert "path" in result[0]
    assert result[0]["parameters"] == "Steps: 4, Seed: 42"
    assert Path(result[0]["path"]).exists()
    assert Path(result[0]["path"]).name.startswith("sd_")

    # Wire-side fields renamed correctly:
    request = fake_forge.txt2img.call_args.args[0]
    assert request.scheduler == "Simple"
    assert request.n_iter == 1
    assert request.distilled_cfg_scale == 3.5
    # Defaults diverge from upstream (see README): SD-family-friendly, not Flux.
    assert request.steps == 25
    assert request.cfg_scale == 7.0


def test_generate_image_respects_output_path_override(fake_forge: Mock, tmp_path: Path) -> None:
    settings = Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=tmp_path / "default",
    )
    fake_forge.txt2img.return_value = Txt2ImgResponse(
        images=[
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
        ]
    )
    fake_forge.png_info.return_value = ""
    handlers = ToolHandlers(fake_forge, settings)

    override = tmp_path / "alt"
    result = handlers.generate_image(prompt="a cat", output_path=str(override))

    assert Path(result[0]["path"]).parent == override.resolve()
    assert not (tmp_path / "default").exists()


def test_upscale_images_reads_files_and_writes_outputs(fake_forge: Mock, tmp_path: Path) -> None:
    from webui_forge_maestro.models import ExtraBatchImagesResponse

    settings = Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=tmp_path / "out",
    )
    source = tmp_path / "cat.png"
    source.write_bytes(b"FAKE_PNG_BYTES")

    fake_forge.extra_batch_images.return_value = ExtraBatchImagesResponse(
        images=[
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
        ]
    )
    handlers = ToolHandlers(fake_forge, settings)

    result = handlers.upscale_images(images=[str(source)])

    assert len(result) == 1
    out_path = Path(result[0]["path"])
    assert out_path.name == "upscaled_cat.png"
    assert out_path.exists()

    request = fake_forge.extra_batch_images.call_args.args[0]
    assert len(request.imageList) == 1
    assert request.imageList[0].name == "cat.png"
    # Hardcoded payload bits the tool surface doesn't expose:
    assert request.gfpgan_visibility == 0
    assert request.upscaling_crop is True
    assert request.show_extras_results is True
    # Defaults pulled from Settings:
    assert request.upscaler_1 == "R-ESRGAN 4x+"
    assert request.upscaler_2 == "None"
    assert request.upscaling_resize == 4.0


def test_upscale_images_coerces_resize_mode_string_to_int(fake_forge: Mock, tmp_path: Path) -> None:
    from webui_forge_maestro.models import ExtraBatchImagesResponse

    settings = Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=tmp_path / "out",
    )
    source = tmp_path / "cat.png"
    source.write_bytes(b"FAKE")

    fake_forge.extra_batch_images.return_value = ExtraBatchImagesResponse(
        images=[
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
        ]
    )
    handlers = ToolHandlers(fake_forge, settings)

    handlers.upscale_images(images=[str(source)], resize_mode="1")

    assert fake_forge.extra_batch_images.call_args.args[0].resize_mode == 1


def test_generate_image_raises_forge_empty_response_when_no_images(
    fake_forge: Mock, settings: Settings
) -> None:
    fake_forge.txt2img.return_value = Txt2ImgResponse(images=[])
    fake_forge.base_url = "http://forge.test"
    handlers = ToolHandlers(fake_forge, settings)

    with pytest.raises(ForgeEmptyResponseError) as exc:
        handlers.generate_image(prompt="a cat")

    assert str(exc.value) == (
        "[Forge http://forge.test/sdapi/v1/txt2img] returned 200 but no images"
    )
    assert exc.value.base_url == "http://forge.test"
    assert exc.value.path == "/sdapi/v1/txt2img"


def test_upscale_images_raises_forge_empty_response_when_no_images(
    fake_forge: Mock, tmp_path: Path
) -> None:
    from webui_forge_maestro.models import ExtraBatchImagesResponse

    settings = Settings(
        webui_url=HttpUrl("http://forge.test"),
        output_dir=tmp_path / "out",
    )
    source = tmp_path / "cat.png"
    source.write_bytes(b"FAKE")
    fake_forge.extra_batch_images.return_value = ExtraBatchImagesResponse(images=[])
    fake_forge.base_url = "http://forge.test"
    handlers = ToolHandlers(fake_forge, settings)

    with pytest.raises(ForgeEmptyResponseError) as exc:
        handlers.upscale_images(images=[str(source)])

    assert str(exc.value) == (
        "[Forge http://forge.test/sdapi/v1/extra-batch-images] returned 200 but no images"
    )
    assert exc.value.path == "/sdapi/v1/extra-batch-images"
