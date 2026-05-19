"""Typed HTTP client for the Forge ``/sdapi/v1/*`` API.

One method per endpoint we use. All network errors map to a small set of
named exceptions so callers don't need to know about ``httpx`` internals.
"""

from typing import cast

import httpx

from webui_forge_maestro.config import Settings
from webui_forge_maestro.models import ForgeUpscaler


class ForgeError(Exception):
    """Base class for Forge HTTP failures."""


class ForgeUnreachableError(ForgeError):
    """Network-level failure — could not reach Forge."""


class ForgeAPIError(ForgeError):
    """Forge returned a non-2xx response."""


class ForgeClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        auth: tuple[str, str] | None = None
        if settings.has_auth():
            assert settings.auth_user is not None
            assert settings.auth_pass is not None
            auth = (settings.auth_user, settings.auth_pass.get_secret_value())
        self._client = httpx.Client(
            base_url=str(settings.webui_url).rstrip("/"),
            timeout=settings.request_timeout,
            headers={"Content-Type": "application/json"},
            auth=auth,
        )

    def list_upscalers(self) -> list[ForgeUpscaler]:
        data = self._get_list("/sdapi/v1/upscalers")
        return [ForgeUpscaler.model_validate(item) for item in data]

    def _get_list(self, path: str) -> list[object]:
        result = self._get(path)
        if not isinstance(result, list):
            raise ForgeAPIError(f"Expected a JSON array from {path}, got {type(result).__name__}")
        return cast(list[object], result)

    def _get(self, path: str) -> object:
        try:
            response = self._client.get(path)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ForgeUnreachableError(
                f"Forge unreachable at {self._settings.webui_url}: {exc}"
            ) from exc
        if response.status_code >= 400:
            raise ForgeAPIError(
                f"Forge returned {response.status_code} for {path}: {response.text[:2048]}"
            )
        return response.json()  # type: ignore[no-any-return]

    def _post(self, path: str, payload: object) -> object:
        try:
            response = self._client.post(path, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ForgeUnreachableError(
                f"Forge unreachable at {self._settings.webui_url}: {exc}"
            ) from exc
        if response.status_code >= 400:
            raise ForgeAPIError(
                f"Forge returned {response.status_code} for {path}: {response.text[:2048]}"
            )
        return response.json()  # type: ignore[no-any-return]
