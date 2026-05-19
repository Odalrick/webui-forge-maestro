"""MCP server wiring.

``ToolHandlers`` holds one method per tool — testable directly with a fake
``ForgeClient``. ``create_server`` registers each method as an MCP tool on
a fresh ``FastMCP`` instance.
"""

from mcp.server.fastmcp import FastMCP

from webui_forge_maestro.config import Settings
from webui_forge_maestro.forge import ForgeClient


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


def create_server(handlers: ToolHandlers) -> FastMCP:
    mcp = FastMCP("maestro-webui-forge")
    mcp.tool()(handlers.get_sd_upscalers)
    mcp.tool()(handlers.get_sd_models)
    mcp.tool()(handlers.set_sd_model)
    return mcp
