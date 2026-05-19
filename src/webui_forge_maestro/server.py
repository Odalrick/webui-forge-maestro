"""MCP server wiring.

``ToolHandlers`` holds one method per tool — testable directly with a fake
``ForgeClient``. ``create_server`` registers each method as an MCP tool on
a fresh ``FastMCP`` instance.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from webui_forge_maestro.config import Settings
from webui_forge_maestro.forge import ForgeClient
from webui_forge_maestro.models import Txt2ImgRequest
from webui_forge_maestro.output import save_generated_image


class ToolHandlers:
    def __init__(self, forge: ForgeClient, settings: Settings) -> None:
        self._forge = forge
        self._settings = settings

    def get_sd_upscalers(self) -> list[str]:
        """Return the names of all upscalers available in Forge."""
        return [u.name for u in self._forge.list_upscalers()]

    def get_sd_models(self) -> list[str]:
        """Return the titles of all checkpoints available in Forge."""
        return [m.title for m in self._forge.list_models()]

    def set_sd_model(self, model_name: str) -> str:
        """Switch the active Stable Diffusion checkpoint to ``model_name``."""
        self._forge.set_model(model_name)
        return f"Model set to: {model_name}"

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        steps: int = 4,
        width: int = 1024,
        height: int = 1024,
        cfg_scale: float = 1.0,
        sampler_name: str = "Euler",
        scheduler_name: str = "Simple",
        seed: int = -1,
        batch_size: int = 1,
        restore_faces: bool = False,
        tiling: bool = False,
        distilled_cfg_scale: float = 3.5,
        output_path: str | None = None,
    ) -> list[dict[str, str]]:
        """Generate one or more images via Forge's txt2img endpoint and save each to disk."""
        request = Txt2ImgRequest(
            prompt=prompt,
            negative_prompt=negative_prompt,
            steps=steps,
            width=width,
            height=height,
            cfg_scale=cfg_scale,
            sampler_name=sampler_name,
            scheduler=scheduler_name,  # input name → wire name
            seed=seed,
            n_iter=batch_size,  # input name → wire name
            restore_faces=restore_faces,
            tiling=tiling,
            distilled_cfg_scale=distilled_cfg_scale,
        )
        response = self._forge.txt2img(request)
        if not response.images:
            raise RuntimeError("No images generated")

        dest_dir = Path(output_path) if output_path else self._settings.output_dir

        results: list[dict[str, str]] = []
        for b64_image in response.images:
            data_url = (
                b64_image if b64_image.startswith("data:") else f"data:image/png;base64,{b64_image}"
            )
            info = self._forge.png_info(data_url)
            path = save_generated_image(b64_image, info=info, dest_dir=dest_dir)
            results.append({"path": str(path), "parameters": info})
        return results


def create_server(handlers: ToolHandlers) -> FastMCP:
    mcp = FastMCP("maestro-webui-forge")
    mcp.tool()(handlers.get_sd_upscalers)
    mcp.tool()(handlers.get_sd_models)
    mcp.tool()(handlers.set_sd_model)
    mcp.tool()(handlers.generate_image)
    return mcp
