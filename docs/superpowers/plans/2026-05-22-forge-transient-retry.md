# Forge Transient Errno-19 Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-retry Errno-19 (`No such device`) transients from Forge once, transparently to callers — covers the remote-mount-not-yet-reattached case after a host wakes up.

**Architecture:** Wrap the existing single HTTP chokepoints — `ForgeClient._get` and `ForgeClient._post` — with a one-shot retry. The retry is gated by a narrow substring match on the response body (`"Errno 19"` in `response.text`) so that genuine 5xx failures still surface immediately. Transport-level failures (`ConnectError` / `TimeoutException`) propagate as `ForgeUnreachableError` without retrying.

**Tech Stack:** Python 3.14, `httpx`, `respx` (HTTP mocking in tests), `pytest`, `monkeypatch` (for stubbing `time.sleep`).

**Spec:** `docs/superpowers/specs/2026-05-22-forge-transient-retry-design.md`

---

## File Structure

- Modify: `src/webui_forge_maestro/forge.py` — add `time` import, module-level constants, free-function matcher, extract `_send_get` / `_send_post`, wrap `_get` / `_post` with retry.
- Modify: `src/webui_forge_maestro/forge_test.py` — add five new tests under the existing `respx` pattern.
- Modify: `BACKLOG.md` — delete the now-implemented bullet.

No new files. No public API change. No `Settings` change.

---

## Task 1: Retry on `_post` (TDD)

**Files:**
- Modify: `src/webui_forge_maestro/forge.py`
- Test: `src/webui_forge_maestro/forge_test.py`

- [ ] **Step 1: Write the failing test**

Append to `src/webui_forge_maestro/forge_test.py`:

```python
@respx.mock
def test_post_retries_once_on_errno_19_then_succeeds(
    client: ForgeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: slept.append(seconds))
    route = respx.post("http://forge.test/sdapi/v1/options").mock(
        side_effect=[
            httpx.Response(
                500, text="OSError: [Errno 19] No such device: '/mnt/archive'"
            ),
            httpx.Response(200, json={}),
        ]
    )

    client.set_model("flux1-dev")

    assert route.call_count == 2
    assert slept == [3.0]
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest src/webui_forge_maestro/forge_test.py::test_post_retries_once_on_errno_19_then_succeeds -v`

Expected: FAIL with `ForgeAPIError: [Forge http://forge.test/sdapi/v1/options] HTTP 500: OSError: [Errno 19] No such device: '/mnt/archive'`. (No retry happens; the first 500 is raised immediately.)

- [ ] **Step 3: Add the `time` import, constants, and matcher**

Edit `src/webui_forge_maestro/forge.py`. After the existing `import httpx` line, add a new `import time` line above it (alphabetical order — stdlib `time` before third-party `httpx`):

Replace the import block:

```python
import httpx
```

with:

```python
import time

import httpx
```

Then, immediately before the `class ForgeClient:` line, insert the constants and matcher:

```python
_TRANSIENT_RETRY_DELAY_SECONDS = 3.0
_TRANSIENT_BODY_MARKER = "Errno 19"


def _is_transient_forge_filesystem_error(response: httpx.Response) -> bool:
    return response.status_code >= 400 and _TRANSIENT_BODY_MARKER in response.text


```

(Note the blank line at the end — there should be two blank lines between the matcher and the `class ForgeClient:` declaration, per PEP 8.)

- [ ] **Step 4: Refactor `_post` to use `_send_post` and add the retry loop**

In `src/webui_forge_maestro/forge.py`, replace the existing `_post` method:

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

with:

```python
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
```

- [ ] **Step 5: Run the new test to confirm it passes**

Run: `uv run pytest src/webui_forge_maestro/forge_test.py::test_post_retries_once_on_errno_19_then_succeeds -v`

Expected: PASS.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 7: Lint and type-check**

Run in parallel:
- `uv run ruff check`
- `uv run ruff format --check`
- `uv run pyright`

Expected: all clean.

- [ ] **Step 8: Commit**

```bash
git add src/webui_forge_maestro/forge.py src/webui_forge_maestro/forge_test.py
git commit -m "feat(forge): retry once on transient Errno 19 in _post"
```

---

## Task 2: Mirror the retry into `_get` (TDD)

**Files:**
- Modify: `src/webui_forge_maestro/forge.py`
- Test: `src/webui_forge_maestro/forge_test.py`

- [ ] **Step 1: Write the failing test**

Append to `src/webui_forge_maestro/forge_test.py`:

```python
@respx.mock
def test_get_retries_once_on_errno_19_then_succeeds(
    client: ForgeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: slept.append(seconds))
    route = respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        side_effect=[
            httpx.Response(
                500, text="OSError: [Errno 19] No such device: '/mnt/models'"
            ),
            httpx.Response(200, json=[]),
        ]
    )

    upscalers = client.list_upscalers()

    assert route.call_count == 2
    assert slept == [3.0]
    assert upscalers == []
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest src/webui_forge_maestro/forge_test.py::test_get_retries_once_on_errno_19_then_succeeds -v`

Expected: FAIL — `_get` does not yet retry, so the first 500 is raised as `ForgeAPIError` immediately.

- [ ] **Step 3: Refactor `_get` to use `_send_get` and add the retry loop**

In `src/webui_forge_maestro/forge.py`, replace the existing `_get` method:

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

with:

```python
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
```

- [ ] **Step 4: Run the new test to confirm it passes**

Run: `uv run pytest src/webui_forge_maestro/forge_test.py::test_get_retries_once_on_errno_19_then_succeeds -v`

Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 6: Lint and type-check**

Run in parallel:
- `uv run ruff check`
- `uv run ruff format --check`
- `uv run pyright`

Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add src/webui_forge_maestro/forge.py src/webui_forge_maestro/forge_test.py
git commit -m "feat(forge): mirror Errno 19 retry into _get"
```

---

## Task 3: Add the negative and persistent-failure tests

These tests describe behaviour the implementation from Tasks 1–2 already provides; this task is *test only*. No production code changes.

**Files:**
- Modify: `src/webui_forge_maestro/forge_test.py`

- [ ] **Step 1: Add the four remaining tests**

Append to `src/webui_forge_maestro/forge_test.py`:

```python
@respx.mock
def test_post_raises_after_retry_when_errno_19_persists(
    client: ForgeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    route = respx.post("http://forge.test/sdapi/v1/options").mock(
        side_effect=[
            httpx.Response(500, text="OSError: [Errno 19] No such device: first"),
            httpx.Response(500, text="OSError: [Errno 19] No such device: second"),
        ]
    )

    with pytest.raises(ForgeAPIError) as exc:
        client.set_model("flux1-dev")
    assert "No such device: second" in exc.value.body
    assert route.call_count == 2


@respx.mock
def test_post_raises_with_second_body_when_retry_returns_different_error(
    client: ForgeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    route = respx.post("http://forge.test/sdapi/v1/options").mock(
        side_effect=[
            httpx.Response(500, text="OSError: [Errno 19] No such device"),
            httpx.Response(500, text="unrelated server error"),
        ]
    )

    with pytest.raises(ForgeAPIError) as exc:
        client.set_model("flux1-dev")
    assert exc.value.body == "unrelated server error"
    assert exc.value.status == 500
    assert route.call_count == 2


@respx.mock
def test_post_does_not_retry_on_non_errno_19_500(
    client: ForgeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: slept.append(seconds))
    route = respx.post("http://forge.test/sdapi/v1/options").mock(
        return_value=httpx.Response(500, text="model not found"),
    )

    with pytest.raises(ForgeAPIError):
        client.set_model("nope")
    assert route.call_count == 1
    assert slept == []


@respx.mock
def test_get_does_not_retry_on_connect_error(
    client: ForgeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: slept.append(seconds))
    route = respx.get("http://forge.test/sdapi/v1/upscalers").mock(
        side_effect=httpx.ConnectError("connection refused"),
    )

    with pytest.raises(ForgeUnreachableError):
        client.list_upscalers()
    assert route.call_count == 1
    assert slept == []
```

- [ ] **Step 2: Run the new tests and confirm they pass**

Run: `uv run pytest src/webui_forge_maestro/forge_test.py -v -k "does_not_retry or raises_after_retry or raises_with_second_body"`

Expected: all four tests pass.

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 4: Lint and format-check**

Run in parallel:
- `uv run ruff check`
- `uv run ruff format --check`
- `uv run pyright`

Expected: all clean.

- [ ] **Step 5: Commit**

```bash
git add src/webui_forge_maestro/forge_test.py
git commit -m "test(forge): cover persistent-failure and no-retry paths for Errno 19 retry"
```

---

## Task 4: Remove the BACKLOG entry

**Files:**
- Modify: `BACKLOG.md`

- [ ] **Step 1: Delete the "Error handling" section**

In `BACKLOG.md`, find this block:

```markdown
## Error handling

- **Retry on transient Forge filesystem errors.** When Forge returns
  errors that look like a not-yet-attached volume — specifically `Errno 19
  No such device` on its configured archive path — auto-retry once after
  a short delay. Triggered when the host serving Forge has just woken up
  and a remote mount hasn't finished reattaching by the time the first
  request lands.

## Workflow
```

and replace it with:

```markdown
## Workflow
```

(The whole `## Error handling` section goes, since this was its only entry. A new error-handling item can recreate the section later if one appears.)

- [ ] **Step 2: Confirm the file structure**

Run: `uv run ruff check` (no-op for markdown, but verifies nothing else broke as a side effect)

Eyeball check: open `BACKLOG.md`, confirm the section between `## Output management` and `## Workflow` is exactly one blank line (no orphaned header, no double blank).

- [ ] **Step 3: Commit**

```bash
git add BACKLOG.md
git commit -m "docs: remove BACKLOG entry for transient Forge retry"
```

---

## Wrap-up

After Task 4, branch state:

- 1 spec commit (already on the branch): `docs: add design spec for transient Forge retry`
- 3 implementation/test commits from Tasks 1–3
- 1 backlog cleanup commit from Task 4

The PR title for the squash-merge should be:

> `feat(forge): retry once on transient Errno 19 from Forge`

Per project workflow (CLAUDE.md → user's preferences): open the PR as a **draft**.

### Final verification before opening the PR

- [ ] `uv run pytest` — green
- [ ] `uv run ruff check` — clean
- [ ] `uv run ruff format --check` — clean
- [ ] `uv run pyright` — clean
- [ ] `git log feat/forge-transient-retry --oneline` — commits read in a sensible narrative order
