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


def create_server(handlers: ToolHandlers) -> FastMCP:
    mcp = FastMCP("maestro-webui-forge")
    mcp.tool()(handlers.get_sd_upscalers)
    return mcp
