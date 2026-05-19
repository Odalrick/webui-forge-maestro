"""Server configuration loaded from environment variables.

All env vars are optional — defaults match the upstream
``Ichigo3766/image-gen-mcp`` behaviour exactly so that an empty
environment produces the same server as upstream.
"""

import os
from pathlib import Path

from pydantic import BaseModel, HttpUrl, SecretStr


class Settings(BaseModel):
    """Typed view of the SD_*/REQUEST_TIMEOUT environment variables."""

    webui_url: HttpUrl = HttpUrl("http://127.0.0.1:7860")
    output_dir: Path = Path("./output")
    auth_user: str | None = None
    auth_pass: SecretStr | None = None
    # REQUEST_TIMEOUT, in seconds. Upstream image-gen-mcp reads this env
    # var as milliseconds (default 300_000 ms); httpx wants seconds, so we
    # diverge from upstream here. Migrating users will need to adjust.
    request_timeout: int = 300
    resize_mode: int = 0
    upscale_multiplier: float = 4.0
    upscale_width: int = 512
    upscale_height: int = 512
    upscaler_1: str = "R-ESRGAN 4x+"
    upscaler_2: str = "None"

    def has_auth(self) -> bool:
        return self.auth_user is not None and self.auth_pass is not None

    @classmethod
    def from_env(cls) -> "Settings":
        env_map: dict[str, object] = {
            "webui_url": os.environ.get("SD_WEBUI_URL"),
            "output_dir": os.environ.get("SD_OUTPUT_DIR"),
            "auth_user": os.environ.get("SD_AUTH_USER"),
            "auth_pass": os.environ.get("SD_AUTH_PASS"),
            "request_timeout": os.environ.get("REQUEST_TIMEOUT"),
            "resize_mode": os.environ.get("SD_RESIZE_MODE"),
            "upscale_multiplier": os.environ.get("SD_UPSCALE_MULTIPLIER"),
            "upscale_width": os.environ.get("SD_UPSCALE_WIDTH"),
            "upscale_height": os.environ.get("SD_UPSCALE_HEIGHT"),
            "upscaler_1": os.environ.get("SD_UPSCALER_1"),
            "upscaler_2": os.environ.get("SD_UPSCALER_2"),
        }
        # Drop missing keys so pydantic falls back to the field default
        # for unset env vars instead of trying to coerce ``None``.
        return cls.model_validate({k: v for k, v in env_map.items() if v})
