"""Entry point for ``uv run webui-forge-maestro``."""

from webui_forge_maestro.config import Settings
from webui_forge_maestro.forge import ForgeClient
from webui_forge_maestro.server import ToolHandlers, create_server


def main() -> None:
    settings = Settings.from_env()
    forge = ForgeClient(settings)
    handlers = ToolHandlers(forge, settings)
    mcp = create_server(handlers)
    mcp.run()


if __name__ == "__main__":
    main()
