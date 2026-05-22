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
