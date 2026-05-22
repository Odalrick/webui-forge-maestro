# Error Source Disambiguation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every error raised by `webui-forge-maestro` instantly attributable to either the Forge host or the local MCP host, both programmatically (exception type) and visually (tagged message prefix).

**Architecture:** New `errors.py` module holds a single `MaestroError` base with two trunks — `ForgeError` (with `ForgeUnreachableError`, `ForgeAPIError`, `ForgeEmptyResponseError`) and `LocalIOError`. Each constructor synthesises a tagged message (`[Forge <url>]` or `[local <abs-path>]`). `forge.py`, `output.py`, and `server.py` import from `errors.py` and use the typed constructors at every raise site.

**Tech Stack:** Python 3.14, pydantic, httpx, FastMCP, pytest (with `respx` for forge layer only).

**Spec:** `docs/superpowers/specs/2026-05-22-error-source-disambiguation-design.md`

---

## Project Conventions Recap

- Tests are `*_test.py` (not `test_*.py`), co-located in `src/webui_forge_maestro/`.
- Run commands from the project root:
  - `uv run pytest` — full test suite
  - `uv run pytest src/webui_forge_maestro/foo_test.py -v` — single file
  - `uv run ruff check` — lint
  - `uv run ruff format` — autoformat
  - `uv run pyright` — strict type-check on `src/`
- Commit format: conventional commits, scopes listed in `CLAUDE.md` (`bootstrap`, `config`, `forge`, `output`, `server`, `docs`, `chore`). This plan adds a new `errors` scope — Task 6 documents that.
- The branch already exists: `feat/error-source-disambiguation`. The design spec is committed (`docs/superpowers/specs/2026-05-22-error-source-disambiguation-design.md`).

---

## File Structure

**New files:**
- `src/webui_forge_maestro/errors.py` — exception taxonomy
- `src/webui_forge_maestro/errors_test.py` — unit tests for hierarchy + message format

**Modified files:**
- `src/webui_forge_maestro/forge.py` — import errors, use new constructors, expose `base_url` property
- `src/webui_forge_maestro/forge_test.py` — assert tagged-message prefix
- `src/webui_forge_maestro/output.py` — wrap I/O in `try/except → LocalIOError`
- `src/webui_forge_maestro/output_test.py` — cover `mkdir` / `save` / `write` failures
- `src/webui_forge_maestro/server.py` — raise `ForgeEmptyResponseError` instead of `RuntimeError`
- `src/webui_forge_maestro/server_test.py` — assert new exception type
- `BACKLOG.md` — remove the "Distinguish Forge errors from local MCP errors" item
- `CLAUDE.md` — bump module count from five to six, list `errors.py`, add `errors` to commit-scope list

---

## Task 1: Create `errors.py` taxonomy (TDD)

**Files:**
- Create: `src/webui_forge_maestro/errors.py`
- Create: `src/webui_forge_maestro/errors_test.py`

**Goal:** Stand up the new exception module in isolation. No changes to `forge.py`/`output.py`/`server.py` yet — `forge.py` still has its own duplicate `ForgeError`/`ForgeUnreachableError`/`ForgeAPIError` definitions; both will coexist briefly until Task 3 migrates `forge.py`. Pyright/pytest stay green throughout.

- [ ] **Step 1.1: Write `errors_test.py`**

Create `src/webui_forge_maestro/errors_test.py`:

```python
from pathlib import Path

import pytest

from webui_forge_maestro.errors import (
    ForgeAPIError,
    ForgeEmptyResponseError,
    ForgeError,
    ForgeUnreachableError,
    LocalIOError,
    MaestroError,
)


def test_forge_errors_descend_from_forge_error_and_maestro_error() -> None:
    for cls in (ForgeUnreachableError, ForgeAPIError, ForgeEmptyResponseError):
        assert issubclass(cls, ForgeError)
        assert issubclass(cls, MaestroError)


def test_local_io_error_descends_from_maestro_error_but_not_forge_error() -> None:
    assert issubclass(LocalIOError, MaestroError)
    assert not issubclass(LocalIOError, ForgeError)


def test_forge_unreachable_message_format() -> None:
    err = ForgeUnreachableError("http://forge.test", "Connection refused")
    assert str(err) == "[Forge http://forge.test] unreachable: Connection refused"
    assert err.base_url == "http://forge.test"
    assert err.cause == "Connection refused"


def test_forge_api_error_message_format() -> None:
    err = ForgeAPIError("http://forge.test", "/sdapi/v1/txt2img", 500, "boom")
    assert str(err) == "[Forge http://forge.test/sdapi/v1/txt2img] HTTP 500: boom"
    assert err.base_url == "http://forge.test"
    assert err.path == "/sdapi/v1/txt2img"
    assert err.status == 500
    assert err.body == "boom"


def test_forge_api_error_truncates_body_to_2048_chars() -> None:
    body = "x" * 5000
    err = ForgeAPIError("http://forge.test", "/p", 500, body)
    # Message contains the truncated form; the original body is retained on .body.
    assert ("x" * 2048) in str(err)
    assert ("x" * 2049) not in str(err)
    assert err.body == body


def test_forge_empty_response_message_format() -> None:
    err = ForgeEmptyResponseError("http://forge.test", "/sdapi/v1/txt2img")
    assert str(err) == "[Forge http://forge.test/sdapi/v1/txt2img] returned 200 but no images"
    assert err.base_url == "http://forge.test"
    assert err.path == "/sdapi/v1/txt2img"


def test_local_io_error_message_format() -> None:
    err = LocalIOError(Path("/home/user/output"), "mkdir", "Permission denied")
    assert str(err) == "[local /home/user/output] mkdir failed: Permission denied"
    assert err.abs_path == Path("/home/user/output")
    assert err.operation == "mkdir"
    assert err.cause == "Permission denied"


def test_errors_are_raisable_and_catchable_via_base() -> None:
    with pytest.raises(MaestroError):
        raise ForgeUnreachableError("http://forge.test", "boom")
    with pytest.raises(ForgeError):
        raise ForgeAPIError("http://forge.test", "/p", 500, "x")
    with pytest.raises(MaestroError):
        raise LocalIOError(Path("/tmp/x"), "save", "boom")
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
uv run pytest src/webui_forge_maestro/errors_test.py -v
```

Expected: collection error or `ModuleNotFoundError: No module named 'webui_forge_maestro.errors'`.

- [ ] **Step 1.3: Create `errors.py`**

Create `src/webui_forge_maestro/errors.py`:

```python
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
```

- [ ] **Step 1.4: Run the new tests**

```bash
uv run pytest src/webui_forge_maestro/errors_test.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 1.5: Run full test suite + lint + types**

```bash
uv run pytest
uv run ruff check
uv run ruff format
uv run pyright
```

Expected: all green. The new file should not regress any existing tests since nothing imports from `errors.py` yet (apart from `errors_test.py`).

- [ ] **Step 1.6: Commit**

```bash
git add src/webui_forge_maestro/errors.py src/webui_forge_maestro/errors_test.py
git commit -m "$(cat <<'EOF'
feat(errors): introduce MaestroError taxonomy

Adds errors.py with MaestroError as the shared base and two trunks
(ForgeError with three subclasses, plus LocalIOError) so callers can
disambiguate Forge-side failures from local MCP file I/O. Constructors
format a tagged message ([Forge <url>] / [local <abs-path>]).

Not yet wired into forge.py / output.py / server.py — that comes in
the following commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `ForgeClient.base_url` property (TDD)

**Files:**
- Modify: `src/webui_forge_maestro/forge.py`
- Modify: `src/webui_forge_maestro/forge_test.py`

**Goal:** Expose a stable, read-only property so callers (specifically `server.py` in Task 5) can fetch the stripped base URL without reaching into private attributes.

- [ ] **Step 2.1: Add the failing test**

Append to `src/webui_forge_maestro/forge_test.py` (place it near the top, e.g. after the `test_list_upscalers_*` block — or simply at the end of the file):

```python
def test_client_exposes_stripped_base_url(settings: Settings) -> None:
    client = ForgeClient(settings)
    # Settings fixture uses http://forge.test (no trailing slash); pydantic
    # HttpUrl coerces it to "http://forge.test/" but we expect the stripped form.
    assert client.base_url == "http://forge.test"


def test_client_strips_trailing_slash_in_base_url() -> None:
    settings = Settings(
        webui_url=HttpUrl("http://forge.test/"),
        output_dir=Path("/tmp/out"),
    )
    client = ForgeClient(settings)
    assert client.base_url == "http://forge.test"
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
uv run pytest src/webui_forge_maestro/forge_test.py::test_client_exposes_stripped_base_url src/webui_forge_maestro/forge_test.py::test_client_strips_trailing_slash_in_base_url -v
```

Expected: FAIL with `AttributeError: 'ForgeClient' object has no attribute 'base_url'`.

- [ ] **Step 2.3: Implement the property in `forge.py`**

Modify `src/webui_forge_maestro/forge.py`. In `ForgeClient.__init__`, store the stripped URL, and add a property:

```python
class ForgeClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
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
```

(The old inline `str(settings.webui_url).rstrip("/")` in the `httpx.Client(...)` call goes away, replaced by `self._base_url`.)

- [ ] **Step 2.4: Run the new tests**

```bash
uv run pytest src/webui_forge_maestro/forge_test.py::test_client_exposes_stripped_base_url src/webui_forge_maestro/forge_test.py::test_client_strips_trailing_slash_in_base_url -v
```

Expected: both pass.

- [ ] **Step 2.5: Run full suite + lint + types**

```bash
uv run pytest
uv run ruff check
uv run ruff format
uv run pyright
```

Expected: all green.

- [ ] **Step 2.6: Commit**

```bash
git add src/webui_forge_maestro/forge.py src/webui_forge_maestro/forge_test.py
git commit -m "$(cat <<'EOF'
feat(forge): expose stripped base URL on ForgeClient

Adds a read-only ForgeClient.base_url property so callers can include
the Forge host in error messages without poking at private state.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Migrate `forge.py` to use `errors.py` (TDD)

**Files:**
- Modify: `src/webui_forge_maestro/forge.py`
- Modify: `src/webui_forge_maestro/forge_test.py`

**Goal:** Remove the duplicate `ForgeError`/`ForgeUnreachableError`/`ForgeAPIError` definitions from `forge.py`. Import the canonical ones from `errors.py`. Update each raise site to use the new tagged-message constructors. Update test assertions accordingly.

- [ ] **Step 3.1: Update failing-expectation tests for the new message format**

Modify `src/webui_forge_maestro/forge_test.py`. Change the import line at the top to also import from the new location, and tighten the assertions:

Replace:
```python
from webui_forge_maestro.forge import ForgeAPIError, ForgeClient, ForgeUnreachableError
```

with:
```python
from webui_forge_maestro.errors import ForgeAPIError, ForgeUnreachableError
from webui_forge_maestro.forge import ForgeClient
```

Replace `test_list_upscalers_raises_forge_unreachable_on_connect_error` body:
```python
@respx.mock
def test_list_upscalers_raises_forge_unreachable_on_connect_error(
    client: ForgeClient,
) -> None:
    respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(ForgeUnreachableError) as exc:
        client.list_upscalers()
    assert str(exc.value).startswith("[Forge http://forge.test] unreachable:")
    assert "connection refused" in str(exc.value)
```

Replace `test_list_upscalers_raises_api_error_on_500` body:
```python
@respx.mock
def test_list_upscalers_raises_api_error_on_500(client: ForgeClient) -> None:
    respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        return_value=httpx.Response(500, text="internal server error")
    )

    with pytest.raises(ForgeAPIError) as exc:
        client.list_upscalers()
    assert str(exc.value) == (
        "[Forge http://forge.test/sdapi/v1/upscalers] HTTP 500: internal server error"
    )
    assert exc.value.status == 500
    assert exc.value.path == "/sdapi/v1/upscalers"
```

Replace `test_set_model_raises_on_500` body:
```python
@respx.mock
def test_set_model_raises_on_500(client: ForgeClient) -> None:
    respx.post("http://forge.test/sdapi/v1/options").mock(
        return_value=httpx.Response(500, text="model not found")
    )

    with pytest.raises(ForgeAPIError) as exc:
        client.set_model("nope")
    assert str(exc.value).startswith(
        "[Forge http://forge.test/sdapi/v1/options] HTTP 500:"
    )
```

Add a new test for the `_get_list` non-list synthetic case:
```python
@respx.mock
def test_get_list_raises_api_error_when_response_is_not_a_list(
    client: ForgeClient,
) -> None:
    respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        return_value=httpx.Response(200, json={"oops": "dict, not list"})
    )

    with pytest.raises(ForgeAPIError) as exc:
        client.list_upscalers()
    assert str(exc.value) == (
        "[Forge http://forge.test/sdapi/v1/upscalers] HTTP 200:"
        " Expected JSON array, got dict"
    )
    assert exc.value.status == 200
```

- [ ] **Step 3.2: Run the updated tests to verify they fail**

```bash
uv run pytest src/webui_forge_maestro/forge_test.py -v
```

Expected: the four tests above fail (message mismatch or wrong import target) but the rest still pass.

- [ ] **Step 3.3: Migrate `forge.py`**

Modify `src/webui_forge_maestro/forge.py`. Delete the inline exception class definitions and import from `errors.py`. Update every raise site to use the new constructors.

Replace lines 7–46 (the top-of-file block up to the end of `__init__`) — i.e. drop the three inline class definitions and change the imports — so the file starts like this:

```python
"""Typed HTTP client for the Forge ``/sdapi/v1/*`` API.

One method per endpoint we use. All network errors map to a small set of
named exceptions (defined in ``errors``) so callers don't need to know
about ``httpx`` internals.
"""

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


class ForgeClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
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
```

Replace `_get_list` to use the new constructor:

```python
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
```

Replace `_get`:

```python
    def _get(self, path: str) -> object:
        try:
            response = self._client.get(path)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ForgeUnreachableError(self._base_url, str(exc)) from exc
        if response.status_code >= 400:
            raise ForgeAPIError(self._base_url, path, response.status_code, response.text)
        return response.json()  # type: ignore[no-any-return]
```

Replace `_post`:

```python
    def _post(self, path: str, payload: object) -> object:
        try:
            response = self._client.post(path, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ForgeUnreachableError(self._base_url, str(exc)) from exc
        if response.status_code >= 400:
            raise ForgeAPIError(self._base_url, path, response.status_code, response.text)
        return response.json()  # type: ignore[no-any-return]
```

(The `response.text[:2048]` truncation that lived in the old raise site moves into `ForgeAPIError.__init__` — Task 1 already handles it. The raise sites now pass the full body and let the exception class truncate.)

- [ ] **Step 3.4: Run the updated forge tests**

```bash
uv run pytest src/webui_forge_maestro/forge_test.py -v
```

Expected: all forge tests pass, including the four updated tests and the new `_get_list` synthetic case.

- [ ] **Step 3.5: Run full suite + lint + types**

```bash
uv run pytest
uv run ruff check
uv run ruff format
uv run pyright
```

Expected: all green.

- [ ] **Step 3.6: Commit**

```bash
git add src/webui_forge_maestro/forge.py src/webui_forge_maestro/forge_test.py
git commit -m "$(cat <<'EOF'
feat(forge): tag Forge errors with full URL and source side

Removes the inline ForgeError hierarchy from forge.py in favour of the
canonical definitions in errors.py. Every raise site now produces a
"[Forge <url>] ..." tagged message so a reader can tell at a glance
which machine the failure originated on — especially useful when the
MCP and Forge run on different hosts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Wrap `output.py` I/O with `LocalIOError` (TDD)

**Files:**
- Modify: `src/webui_forge_maestro/output.py`
- Modify: `src/webui_forge_maestro/output_test.py`

**Goal:** When local file I/O fails in `output.py`, raise `LocalIOError` with the offending absolute path and operation tag. The happy path is unchanged.

- [ ] **Step 4.1: Write the failing tests**

Append to `src/webui_forge_maestro/output_test.py`. Add imports at the top (the existing imports plus the two below):

```python
import pytest

from webui_forge_maestro.errors import LocalIOError
```

Then append these tests at the end:

```python
def test_save_generated_image_raises_local_io_error_when_mkdir_fails(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(0o500)  # read+execute, no write — mkdir of a child fails
    try:
        dest = parent / "out"
        with pytest.raises(LocalIOError) as exc:
            save_generated_image(ONE_PX_PNG_B64, info="x", dest_dir=dest)
        assert exc.value.operation == "mkdir"
        assert exc.value.abs_path == dest.resolve()
        assert str(exc.value).startswith(f"[local {dest.resolve()}] mkdir failed:")
    finally:
        parent.chmod(0o700)  # restore so pytest can clean up


def test_save_generated_image_raises_local_io_error_when_save_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image as PILImage

    def _broken_save(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(PILImage.Image, "save", _broken_save)

    with pytest.raises(LocalIOError) as exc:
        save_generated_image(ONE_PX_PNG_B64, info="x", dest_dir=tmp_path)
    assert exc.value.operation == "save"
    assert exc.value.abs_path.parent == tmp_path.resolve()
    assert "disk full" in str(exc.value)


def test_save_upscaled_image_raises_local_io_error_when_mkdir_fails(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(0o500)
    try:
        dest = parent / "out"
        with pytest.raises(LocalIOError) as exc:
            save_upscaled_image(ONE_PX_PNG_B64, source_basename="cat.png", dest_dir=dest)
        assert exc.value.operation == "mkdir"
        assert exc.value.abs_path == dest.resolve()
    finally:
        parent.chmod(0o700)


def test_save_upscaled_image_raises_local_io_error_when_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken_write_bytes(self: Path, data: bytes) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", _broken_write_bytes)

    with pytest.raises(LocalIOError) as exc:
        save_upscaled_image(ONE_PX_PNG_B64, source_basename="cat.png", dest_dir=tmp_path)
    assert exc.value.operation == "write"
    assert exc.value.abs_path == (tmp_path / "upscaled_cat.png").resolve()
    assert "disk full" in str(exc.value)
```

- [ ] **Step 4.2: Run the new tests to verify they fail**

```bash
uv run pytest src/webui_forge_maestro/output_test.py -v
```

Expected: the four new tests fail (`OSError` / `PermissionError` leaks raw instead of being wrapped); the existing tests still pass.

- [ ] **Step 4.3: Wrap I/O in `output.py`**

Modify `src/webui_forge_maestro/output.py`:

```python
"""Write base64-encoded images from Forge to PNG files on the host."""

import base64
import io
import uuid
from pathlib import Path

from PIL import Image

from webui_forge_maestro.errors import LocalIOError

# EXIF tag id for the ImageDescription field. Upstream stores the human-
# readable parameter string from /sdapi/v1/png-info here so opening the
# file in any EXIF-aware viewer shows the params used to generate it.
_EXIF_IMAGE_DESCRIPTION = 0x010E


def save_generated_image(b64_image: str, info: str, dest_dir: Path) -> Path:
    """Write a generated PNG with ``info`` embedded as EXIF ImageDescription."""
    _ensure_dir(dest_dir)
    path = dest_dir / f"sd_{uuid.uuid7()}.png"
    image_bytes = base64.b64decode(_strip_data_url_prefix(b64_image))
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            exif = Image.Exif()
            exif[_EXIF_IMAGE_DESCRIPTION] = info
            img.save(path, format="PNG", exif=exif.tobytes())
    except OSError as exc:
        raise LocalIOError(path.resolve(), "save", str(exc)) from exc
    return path.resolve()


def save_upscaled_image(b64_image: str, source_basename: str, dest_dir: Path) -> Path:
    """Write an upscaled PNG next to a fixed prefix; no metadata."""
    _ensure_dir(dest_dir)
    path = dest_dir / f"upscaled_{source_basename}"
    try:
        path.write_bytes(base64.b64decode(_strip_data_url_prefix(b64_image)))
    except OSError as exc:
        raise LocalIOError(path.resolve(), "write", str(exc)) from exc
    return path.resolve()


def _ensure_dir(dest_dir: Path) -> None:
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise LocalIOError(dest_dir.resolve(), "mkdir", str(exc)) from exc


def _strip_data_url_prefix(b64: str) -> str:
    # Forge sometimes returns a data URL ("data:image/png;base64,…") and
    # sometimes the raw base64. Normalise to the latter.
    return b64.split(",", 1)[1] if "," in b64 else b64
```

- [ ] **Step 4.4: Run the updated output tests**

```bash
uv run pytest src/webui_forge_maestro/output_test.py -v
```

Expected: all tests pass (existing + four new).

- [ ] **Step 4.5: Run full suite + lint + types**

```bash
uv run pytest
uv run ruff check
uv run ruff format
uv run pyright
```

Expected: all green.

- [ ] **Step 4.6: Commit**

```bash
git add src/webui_forge_maestro/output.py src/webui_forge_maestro/output_test.py
git commit -m "$(cat <<'EOF'
feat(output): raise LocalIOError on local file I/O failures

Wraps mkdir / Image.save / write_bytes in a small helper that
re-raises as LocalIOError, tagging the message with the absolute path
and operation. Makes it obvious when the failure is on the MCP host's
filesystem (vs Forge's archive directory).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Raise `ForgeEmptyResponseError` from `server.py` (TDD)

**Files:**
- Modify: `src/webui_forge_maestro/server.py`
- Modify: `src/webui_forge_maestro/server_test.py`

**Goal:** Replace the two bare `RuntimeError(...)` raises with the typed `ForgeEmptyResponseError`, including the base URL and the endpoint path. Update server tests.

- [ ] **Step 5.1: Write the failing tests**

Modify `src/webui_forge_maestro/server_test.py`. Add at the top with the other imports:

```python
import pytest

from webui_forge_maestro.errors import ForgeEmptyResponseError
```

Then append these tests at the end of the file:

```python
def test_generate_image_raises_forge_empty_response_when_no_images(
    fake_forge: Mock, settings: Settings
) -> None:
    fake_forge.txt2img.return_value = Txt2ImgResponse(images=[])
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
        "[Forge http://forge.test/sdapi/v1/extra-batch-images]"
        " returned 200 but no images"
    )
```

Note: `Mock(spec=ForgeClient)` doesn't auto-provide `base_url` because it's a property. Either set `fake_forge.base_url = "http://forge.test"` on the mock (as the second test does), or configure it via the `fake_forge` fixture once. To keep the existing fixture untouched, the first test relies on the property *not* being read (since `txt2img` returns no images and `generate_image` raises before calling `base_url`) — except… actually we *do* need `base_url` to build the error message. Both tests must set `fake_forge.base_url = "http://forge.test"`.

Update the first test accordingly:

```python
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
```

Also update the existing `test_generate_image_full_flow` and `test_upscale_images_reads_files_and_writes_outputs` happy-path tests to set `fake_forge.base_url = "http://forge.test"` for symmetry — even though the happy path doesn't read it, doing this keeps the fixture story consistent (you can otherwise simply leave the happy-path tests alone since they never reach the empty-response branch).

- [ ] **Step 5.2: Run the new tests to verify they fail**

```bash
uv run pytest src/webui_forge_maestro/server_test.py -v
```

Expected: the two new tests fail (`RuntimeError` raised instead of `ForgeEmptyResponseError`).

- [ ] **Step 5.3: Update `server.py`**

Modify `src/webui_forge_maestro/server.py`. Add the import:

```python
from webui_forge_maestro.errors import ForgeEmptyResponseError
```

Replace the `raise RuntimeError("No images generated")` line in `generate_image`:

```python
        if not response.images:
            raise ForgeEmptyResponseError(self._forge.base_url, "/sdapi/v1/txt2img")
```

Replace the `raise RuntimeError("No images upscaled")` line in `upscale_images`:

```python
        if not response.images:
            raise ForgeEmptyResponseError(
                self._forge.base_url, "/sdapi/v1/extra-batch-images"
            )
```

- [ ] **Step 5.4: Run the updated server tests**

```bash
uv run pytest src/webui_forge_maestro/server_test.py -v
```

Expected: all tests pass, including the two new ones.

- [ ] **Step 5.5: Run full suite + lint + types**

```bash
uv run pytest
uv run ruff check
uv run ruff format
uv run pyright
```

Expected: all green.

- [ ] **Step 5.6: Commit**

```bash
git add src/webui_forge_maestro/server.py src/webui_forge_maestro/server_test.py
git commit -m "$(cat <<'EOF'
feat(server): raise ForgeEmptyResponseError on empty Forge responses

Replaces the two bare RuntimeError raises in generate_image and
upscale_images with the typed ForgeEmptyResponseError, carrying the
Forge base URL and endpoint path. Slots the "Forge returned 200 but
nothing came back" case into the same Forge-side bucket as transport
and HTTP errors.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Docs updates

**Files:**
- Modify: `BACKLOG.md`
- Modify: `CLAUDE.md`

**Goal:** Remove the now-implemented BACKLOG item, bump the module count in `CLAUDE.md`, list `errors.py`, and add the `errors` scope to the commit-scope list.

- [ ] **Step 6.1: Remove the BACKLOG item**

Edit `BACKLOG.md`. Delete the entire "Distinguish Forge errors from local MCP errors" bullet (currently lines 44–51) under the "Error handling" section. Leave the surrounding "Retry on transient Forge filesystem errors" bullet intact.

After the edit, the "Error handling" section should read:

```markdown
## Error handling

- **Retry on transient Forge filesystem errors.** When Forge returns
  errors that look like a not-yet-attached volume — specifically `Errno 19
  No such device` on its configured archive path — auto-retry once after
  a short delay. Triggered when the host serving Forge has just woken up
  and a remote mount hasn't finished reattaching by the time the first
  request lands.
```

- [ ] **Step 6.2: Update `CLAUDE.md` module listing**

Edit `CLAUDE.md`. Change "Five modules under" to "Six modules under" and add the `errors.py` line. Replace the existing list block (currently lines 43–55, the "Architecture" section's module bullets) so it reads:

```markdown
Six modules under `src/webui_forge_maestro/`:

- `config.py` — `Settings` model, env-loaded
- `errors.py` — exception taxonomy (`MaestroError` base, `ForgeError`
  trunk with three subclasses, plus `LocalIOError` for local file I/O)
- `forge.py` — typed `httpx` client for Forge's `/sdapi/v1/*` endpoints
- `models.py` — pydantic wire-shape models; field names match Forge's JSON
  exactly. Tool-input → wire-name translation (`scheduler_name` → `scheduler`,
  `batch_size` → `n_iter`) lives in `server.py`
- `output.py` — base64 → PNG file, with optional EXIF embedding
- `server.py` — `ToolHandlers` class + `create_server` factory wiring FastMCP
```

- [ ] **Step 6.3: Add `errors` to the commit-scopes list in `CLAUDE.md`**

Edit `CLAUDE.md`. In the "Commit scopes" section, add a bullet for `errors` (alphabetical insertion between `config` and `forge`):

```markdown
- `bootstrap` — initial repo setup, dependency wiring
- `config` — `Settings` and env loading
- `errors` — exception taxonomy in `errors.py`
- `forge` — HTTP client, wire-shape models
- `output` — file writing, EXIF
- `server` — FastMCP wiring, tool handlers
- `docs` — README, LICENSE, this file
- `chore` — anything else
```

- [ ] **Step 6.4: Run full suite + lint (no code change, but cheap sanity)**

```bash
uv run pytest
uv run ruff check
```

Expected: all green.

- [ ] **Step 6.5: Commit**

```bash
git add BACKLOG.md CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: record error-disambiguation work in CLAUDE.md and BACKLOG

Removes the implemented "Distinguish Forge errors from local MCP errors"
backlog item, bumps the module count to six with errors.py listed,
and adds an `errors` commit scope.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final checks before PR

- [ ] **Step F.1: Diff vs main**

```bash
git fetch origin main
git diff origin/main -- src/ docs/ CLAUDE.md BACKLOG.md | head -200
```

Sanity-check the change surface: new `errors.py` + `errors_test.py`, edits to `forge.py`/`forge_test.py`/`output.py`/`output_test.py`/`server.py`/`server_test.py`, plus `CLAUDE.md`/`BACKLOG.md` + the design spec already committed.

- [ ] **Step F.2: All checks green**

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run pyright
```

Expected: every check passes. (Use `ruff format --check` to confirm the working tree is already formatted; switch to `uv run ruff format` if it complains.)

- [ ] **Step F.3: Push the branch**

```bash
git push -u origin feat/error-source-disambiguation
```

- [ ] **Step F.4: Open the PR as a draft**

```bash
gh pr create --draft --title "feat: disambiguate Forge errors from local MCP errors" --body "$(cat <<'EOF'
## Summary

- Introduces a `MaestroError` taxonomy in a new `errors.py` module with two trunks: `ForgeError` (subclasses `ForgeUnreachableError`, `ForgeAPIError`, `ForgeEmptyResponseError`) and `LocalIOError`.
- Tags every error message with `[Forge <full-url>]` or `[local <abs-path>]` so a reader can tell at a glance which machine is at fault — especially useful when the MCP and Forge run on different hosts.
- Wraps `output.py` file I/O so `mkdir`/`save`/`write` failures surface as `LocalIOError` rather than raw `OSError`.
- Replaces the bare `RuntimeError("No images generated")` raises in `server.py` with `ForgeEmptyResponseError`.

Closes the BACKLOG item "Distinguish Forge errors from local MCP errors".

## Test plan

- [x] `uv run pytest` — full suite green (including new `errors_test.py` and additional cases in `forge_test.py`, `output_test.py`, `server_test.py`)
- [x] `uv run ruff check` — clean
- [x] `uv run ruff format --check` — clean
- [x] `uv run pyright` — clean (strict on `src/`)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implementing task(s) |
|---|---|
| Exception taxonomy (`MaestroError` + 5 subclasses) | Task 1 |
| Message format templates | Task 1 (definitions) + Tasks 3/4/5 (raise sites use them) |
| Synthetic `ForgeAPIError` for `_get_list` non-list | Task 3 (Step 3.3 + new test in Step 3.1) |
| `ForgeClient.base_url` property | Task 2 |
| `forge.py` raise-site migration | Task 3 |
| `output.py` wrapping | Task 4 |
| `server.py` empty-response raise | Task 5 |
| No catch-and-rewrap at MCP boundary | Honoured implicitly — Task 5 just changes the raise, no surrounding try/except added |
| Testing strategy | Each task includes the matching test additions; new `errors_test.py` covers the hierarchy/format invariant |
| BACKLOG removal | Task 6 |
| CLAUDE.md module bump | Task 6 |
| Commit-shape preview | Each task's commit message matches the spec's preview |
| Out-of-scope: `Errno 19` auto-retry | Not addressed (correct — separate BACKLOG entry) |

No gaps.

**2. Placeholder scan:** none found.

**3. Type consistency:**
- `MaestroError`, `ForgeError`, `ForgeUnreachableError`, `ForgeAPIError`, `ForgeEmptyResponseError`, `LocalIOError` — names consistent across Tasks 1, 3, 4, 5.
- Constructor signatures stable:
  - `ForgeUnreachableError(base_url: str, cause: str)`
  - `ForgeAPIError(base_url: str, path: str, status: int, body: str)`
  - `ForgeEmptyResponseError(base_url: str, path: str)`
  - `LocalIOError(abs_path: Path, operation: str, cause: str)`
- `ForgeClient.base_url` property name consistent between Tasks 2, 3, 5.
- `operation` literal strings `"mkdir"`, `"save"`, `"write"` consistent between Task 4's implementation and tests.
