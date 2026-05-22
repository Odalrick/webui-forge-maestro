"""Exception taxonomy for webui-forge-maestro.

Two trunks under ``MaestroError`` make it unambiguous which machine to look
at when something fails:

* ``ForgeError`` and its subclasses — the failure happened on the Forge
  host (HTTP transport, HTTP response, or empty/malformed payload).
* ``LocalIOError`` — the failure happened on the MCP host's filesystem.

Each constructor formats a tagged message so the side is visible even if
only the message string survives downstream.
"""

from pathlib import Path

_BODY_TRUNCATE_LIMIT = 2048


class MaestroError(Exception):
    """Base for all errors raised intentionally by webui-forge-maestro."""


class ForgeError(MaestroError):
    """Anything originating on the Forge side."""


class ForgeUnreachableError(ForgeError):
    """Network-level failure — could not reach Forge."""

    def __init__(self, base_url: str, cause: str) -> None:
        super().__init__(f"[Forge {base_url}] unreachable: {cause}")
        self.base_url = base_url
        self.cause = cause


class ForgeAPIError(ForgeError):
    """Forge returned a non-2xx response (or a 200 with a malformed payload)."""

    def __init__(self, base_url: str, path: str, status: int, body: str) -> None:
        truncated = body[:_BODY_TRUNCATE_LIMIT]
        super().__init__(f"[Forge {base_url}{path}] HTTP {status}: {truncated}")
        self.base_url = base_url
        self.path = path
        self.status = status
        self.body = body


class ForgeEmptyResponseError(ForgeError):
    """Forge returned 200 OK but the response carried no images."""

    def __init__(self, base_url: str, path: str) -> None:
        super().__init__(f"[Forge {base_url}{path}] returned 200 but no images")
        self.base_url = base_url
        self.path = path


class LocalIOError(MaestroError):
    """File I/O on the MCP host failed (mkdir / save / write)."""

    def __init__(self, abs_path: Path, operation: str, cause: str) -> None:
        super().__init__(f"[local {abs_path}] {operation} failed: {cause}")
        self.abs_path = abs_path
        self.operation = operation
        self.cause = cause
