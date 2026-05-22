# Retry on transient Forge filesystem errors

**Status:** design approved, ready for implementation plan
**BACKLOG item:** "Retry on transient Forge filesystem errors" (under
`Error handling` in `BACKLOG.md`)
**Builds on:** `2026-05-22-error-source-disambiguation-design.md` — its non-goal "Auto-retry on transient Forge
filesystem errors" is exactly this follow-up.

## Problem

When the host serving Forge has just woken up, a remote mount backing Forge's archive directory occasionally hasn't
finished reattaching by the time the first MCP request lands. Forge's response surfaces (after the disambiguation work)
as:

> `[Forge https://forge.example.test/sdapi/v1/txt2img] HTTP 500: OSError: [Errno 19] No such device: '/mnt/archive/...'`

Three seconds later the mount is back and an identical request would succeed. Today the caller sees the failure and has
to retry by hand. This is a single expected, transient class of error; hiding it from the caller is appropriate.

## Goal

Auto-retry exactly this class of error once, transparently. Any other failure — including the Errno-19 case failing
twice in a row — surfaces as the same `ForgeAPIError` callers see today.

## Non-goals

- Configurable retry policy (delay, count, jitter, backoff). Hardcoded is enough for a personal tool; extract to
  `Settings` later if a second use case appears.
- Retrying on `ConnectError` / `TimeoutException`. Forge being unreachable at the transport layer is a different failure
  mode with no evidence that a 3-second retry helps.
- Retrying on other HTTP errors — bad-prompt 422s, real 500s from the generation pipeline, etc. The trigger we have
  evidence for is specifically Errno 19; widening risks masking real failures.
- Logging or any other observable signal. The user explicitly wants the retry transparent. The project has no logging
  convention today, and adding one just for this path would be disproportionate.

## Trigger condition

The retry fires when **both** of these hold on the first attempt:

1. `response.status_code >= 400` (i.e. the call would raise
   `ForgeAPIError` today).
2. `"Errno 19"` appears anywhere in `response.text`.

The `"Errno 19"` substring match is deliberately narrow. Forge surfaces the underlying Python `OSError` representation
in its 500 body, which always includes `[Errno 19]` for this case. We do not parse paths or interpret the body further —
the marker is self-evidently this one transient situation.

`ForgeUnreachableError` (raised on `httpx.ConnectError` /
`httpx.TimeoutException`) is **not** a retry trigger.

## Behaviour

1. First attempt fails matching the trigger condition above.
2. `time.sleep(3.0)`.
3. Retry the same HTTP call once.
4. The second attempt's result — success, `ForgeAPIError` (Errno 19 or otherwise), or `ForgeUnreachableError` — is
   returned or raised as if the first attempt never happened. No further retry.

When the second attempt raises a `ForgeAPIError`, it carries the
*second* response body and status code, not the first. The disambiguation tag in the message (`[Forge {base_url}{path}] HTTP
{status}: ...`) is the same shape either way; the caller cannot tell a retried failure from a fresh one (which is the
point).

## Where the retry lives

In the private helpers `ForgeClient._get` and `ForgeClient._post`. They are the single chokepoint for all HTTP traffic.
Wrapping there means:

- Every endpoint (`list_models`, `set_model`, `txt2img`,
  `extra_batch_images`, `png_info`, `list_upscalers`) inherits the retry without per-method changes. The mount-reattach
  problem can affect any of them — checkpoint reads, archive writes, etc.
- The retry sits next to the existing `ForgeAPIError` construction site, where we already have `response.text` in hand
  to run the matcher against.

Sketch (illustrative, not literal):

```python
_TRANSIENT_RETRY_DELAY_SECONDS = 3.0
_TRANSIENT_BODY_MARKER = "Errno 19"


def _is_transient_forge_filesystem_error(response: httpx.Response) -> bool:
    return response.status_code >= 400 and _TRANSIENT_BODY_MARKER in response.text


def _post(self, path: str, payload: object) -> object:
    response = self._send_post(path, payload)
    if _is_transient_forge_filesystem_error(response):
        time.sleep(_TRANSIENT_RETRY_DELAY_SECONDS)
        response = self._send_post(path, payload)
    if response.status_code >= 400:
        raise ForgeAPIError(self._base_url, path, response.status_code, response.text)
    return response.json()
```

The `_send_post` / `_send_get` inner helper is the only place that talks to `self._client` and translates
`ConnectError` /
`TimeoutException` into `ForgeUnreachableError`. Pulling that out keeps the retry logic readable and keeps
unreachable-style failures out of the retry path entirely.

## Constants

Module-private in `forge.py`:

| Name                             | Value        | Rationale                                                                 |
|----------------------------------|--------------|---------------------------------------------------------------------------|
| `_TRANSIENT_RETRY_DELAY_SECONDS` | `3.0`        | User-specified; long enough for the typical remote-mount reattach window. |
| `_TRANSIENT_BODY_MARKER`         | `"Errno 19"` | Stable substring of Python's `OSError` repr for `ENODEV`.                 |

Both private and module-level — not in `Settings`, not on the class.

## Testing

In `forge_test.py`, using `respx` as today:

| Scenario                                          | Expectation                                                                    |
|---------------------------------------------------|--------------------------------------------------------------------------------|
| 500 + `Errno 19` body, then 200 OK                | Returns parsed payload; route called twice.                                    |
| 500 + `Errno 19` body, then 500 + `Errno 19` body | Raises `ForgeAPIError`; route called twice; exception carries second body.     |
| 500 + `Errno 19` body, then 500 + different body  | Raises `ForgeAPIError` whose `.body` is the *second* body; route called twice. |
| 500 *without* `Errno 19`                          | Raises `ForgeAPIError` immediately; route called once.                         |
| `httpx.ConnectError` first call                   | Raises `ForgeUnreachableError` immediately; route called once.                 |

`time.sleep` is patched in each retry test via `monkeypatch.setattr` so the suite stays fast — record the slept-for
value if convenient, but the value itself isn't load-bearing for these tests (it's a hardcoded constant; one assertion
in one test is enough).

At least one of the retry tests uses `_post` (txt2img path) and one uses `_get` (list_upscalers path), to cover both
helpers.

## Migration / compatibility

- No new exception types. No public API change. No `Settings` change.
- A caller that today sees `ForgeAPIError` on a transient Errno 19 will, after this change, see success when the mount
  reattaches within 3 s. That is the entire observable effect.
- A caller doing its own retries on `ForgeAPIError` keeps working — the inner retry just makes those outer retries
  slightly less likely to be needed.

## Docs to update on landing

- Remove the BACKLOG entry "Retry on transient Forge filesystem errors" under `Error handling` in `BACKLOG.md`.
- No `CLAUDE.md` change — the module count and shapes are unchanged.

## Commit shape (preview)

Conventional-commit scopes from `CLAUDE.md` apply. A single PR, likely two commits:

- `feat(forge): retry once on transient Errno 19 from Forge`
- `docs: remove BACKLOG entry for transient Forge retry`
