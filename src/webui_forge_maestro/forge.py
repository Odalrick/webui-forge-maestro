"""Typed HTTP client for the Forge ``/sdapi/v1/*`` API.

One method per endpoint we use. All network errors map to a small set of
named exceptions (defined in ``errors``) so callers don't need to know
about ``httpx`` internals.
"""

import time

import httpx

from webui_forge_maestro.config import Settings
from webui_forge_maestro.errors import ForgeAPIError, ForgeUnreachableError
from webui_forge_maestro.models import (
    ExtraBatchImagesRequest,
    ExtraBatchImagesResponse,
    ForgeModel,
    ForgeUpscaler,
    PngInfoResponse,
    Txt2ImgRequest,
    Txt2ImgResponse,
)

_TRANSIENT_RETRY_DELAY_SECONDS = 3.0
_TRANSIENT_BODY_MARKER = "Errno 19"


def _is_transient_forge_filesystem_error(response: httpx.Response) -> bool:
    return response.status_code >= 400 and _TRANSIENT_BODY_MARKER in response.text


class ForgeClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = str(settings.webui_url).rstrip("/")
        auth: tuple[str, str] | None = None
        if settings.has_auth():
            assert settings.auth_user is not None
            assert settings.auth_pass is not None
            auth = (settings.auth_user, settings.auth_pass.get_secret_value())
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=settings.request_timeout,
            headers={"Content-Type": "application/json"},
            auth=auth,
        )

    @property
    def base_url(self) -> str:
        """Stripped base URL (no trailing slash) for use in error messages."""
        return self._base_url

    def list_upscalers(self) -> list[ForgeUpscaler]:
        data = self._get_list("/sdapi/v1/upscalers")
        return [ForgeUpscaler.model_validate(item) for item in data]

    def list_models(self) -> list[ForgeModel]:
        data = self._get_list("/sdapi/v1/sd-models")
        return [ForgeModel.model_validate(item) for item in data]

    def set_model(self, model_name: str) -> None:
        """Switch the active checkpoint to ``model_name``."""
        self._post("/sdapi/v1/options", {"sd_model_checkpoint": model_name})

    def txt2img(self, request: Txt2ImgRequest) -> Txt2ImgResponse:
        data = self._post("/sdapi/v1/txt2img", request.model_dump())
        return Txt2ImgResponse.model_validate(data)

    def extra_batch_images(self, request: ExtraBatchImagesRequest) -> ExtraBatchImagesResponse:
        data = self._post("/sdapi/v1/extra-batch-images", request.model_dump())
        return ExtraBatchImagesResponse.model_validate(data)

    def png_info(self, image_data_url: str) -> str:
        data = self._post("/sdapi/v1/png-info", {"image": image_data_url})
        return PngInfoResponse.model_validate(data).info

    def _get_list(self, path: str) -> list[object]:
        result = self._get(path)
        if not isinstance(result, list):
            raise ForgeAPIError(
                self._base_url,
                path,
                200,
                f"Expected JSON array, got {type(result).__name__}",
            )
        return result  # type: ignore[return-value]  # pyright strict: list[Unknown] vs list[object]

    def _send_get(self, path: str) -> httpx.Response:
        try:
            return self._client.get(path)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ForgeUnreachableError(self._base_url, str(exc)) from exc

    def _get(self, path: str) -> object:
        response = self._send_get(path)
        if _is_transient_forge_filesystem_error(response):
            time.sleep(_TRANSIENT_RETRY_DELAY_SECONDS)
            response = self._send_get(path)
        if response.status_code >= 400:
            raise ForgeAPIError(self._base_url, path, response.status_code, response.text)
        return response.json()  # type: ignore[no-any-return]

    def _send_post(self, path: str, payload: object) -> httpx.Response:
        try:
            return self._client.post(path, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ForgeUnreachableError(self._base_url, str(exc)) from exc

    def _post(self, path: str, payload: object) -> object:
        response = self._send_post(path, payload)
        if _is_transient_forge_filesystem_error(response):
            time.sleep(_TRANSIENT_RETRY_DELAY_SECONDS)
            response = self._send_post(path, payload)
        if response.status_code >= 400:
            raise ForgeAPIError(self._base_url, path, response.status_code, response.text)
        return response.json()  # type: ignore[no-any-return]
