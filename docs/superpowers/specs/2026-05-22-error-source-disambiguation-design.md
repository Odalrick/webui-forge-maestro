# Disambiguating Forge errors from local MCP errors

**Status:** design approved, ready for implementation plan
**BACKLOG item:** "Distinguish Forge errors from local MCP errors" (under
`Error handling` in `BACKLOG.md`)

## Problem

When the MCP server runs on one host and Forge runs on another (the
SSH-tunnel case), a filesystem error on Forge's side currently surfaces
identically to one on the MCP side. The motivating example: Forge's
configured archive directory throws `OSError: [Errno 19] No such device`
(remote mount not yet attached). The MCP caller sees:

> `Forge returned 500 for /sdapi/v1/txt2img: ...Errno 19 No such device...`

and can reasonably misread it as "the *local* output directory is bad" —
because nothing in the message names the responsible host.

Two further failure modes share the ambiguity:

1. Local file I/O in `output.py` (`mkdir`, `Image.save`, `write_bytes`)
   raises raw `OSError`, with no signpost that the failure is on the MCP
   host rather than Forge's.
2. `server.py` raises plain `RuntimeError("No images generated")` when
   Forge returns 200 OK with an empty image list — neither HTTP nor
   local-I/O, but currently bucketless.

## Goal

A reader of any error from this MCP can instantly tell **which machine's
filesystem / network is at fault**, both programmatically (exception
type) and visually (message prefix and the relevant URL or absolute
path).

## Non-goals

- Auto-retry on transient Forge filesystem errors (separate BACKLOG
  item; intentionally deferred).
- Wrapping errors at the MCP boundary in `server.py`. FastMCP serialises
  the exception message to the wire; our messages are self-describing
  at the source.
- Parsing Forge's HTTP response body to extract paths. The body is
  surfaced verbatim (truncated to 2048 chars as today); the *tag* makes
  the side unambiguous.

## Exception taxonomy

A single base for errors we raise intentionally, with two trunks for
the two sides. All five classes live in a new `errors.py` module;
`forge.py`, `output.py`, and `server.py` import from there.

```
MaestroError                              base — easy to except in tests / future MCP wrapping
├── ForgeError                            anything originating on the Forge side
│   ├── ForgeUnreachableError             network failure reaching Forge          [existing, re-rooted]
│   ├── ForgeAPIError                     Forge returned a non-2xx HTTP response  [existing, re-rooted]
│   └── ForgeEmptyResponseError           Forge returned 200 but no images        [NEW]
└── LocalIOError                          file I/O on the MCP host failed         [NEW]
```

`ForgeError` and `LocalIOError` as siblings under `MaestroError` *are*
the disambiguation — `except ForgeError` vs `except LocalIOError` is
unambiguous about which machine to look at. Existing names are kept;
external callers `except ForgeAPIError` keep working.

## Message format

Every raised exception gets a tagged, side-naming format. The tag is
the first token of the message so it survives downstream wrapping or
truncation.

`base_url` in every example below is the trailing-slash-stripped
form of `Settings.webui_url` (same normalisation `ForgeClient` already
applies when constructing `httpx.Client(base_url=...)`). When a `path`
is present, it always starts with `/`, so `{base_url}{path}` produces
the canonical full URL.

| Exception | Message template | Example |
|---|---|---|
| `ForgeUnreachableError` | `[Forge {base_url}] unreachable: {cause}` | `[Forge https://forge.example.test] unreachable: Connection refused` |
| `ForgeAPIError` | `[Forge {base_url}{path}] HTTP {status}: {body[:2048]}` | `[Forge https://forge.example.test/sdapi/v1/txt2img] HTTP 500: OSError: [Errno 19] No such device: '/mnt/archive/...'` |
| `ForgeEmptyResponseError` | `[Forge {base_url}{path}] returned 200 but no images` | `[Forge https://forge.example.test/sdapi/v1/txt2img] returned 200 but no images` |
| `LocalIOError` | `[local {abs_path}] {operation} failed: {cause}` | `[local /home/user/output] mkdir failed: [Errno 13] Permission denied` |

- Forge side is always `[Forge <full-url>]`; local side is always
  `[local <abs-path>]`. With this prefix in place, the `Errno 19`
  confusion case reads as `[Forge https://forge.example.test/...]
  HTTP 500: ... Errno 19 ...` — obvious which host the bad path
  lives on.
- HTTP response body stays truncated to 2048 chars as today.
- `{operation}` for `LocalIOError` is a short literal: `"mkdir"`,
  `"save"`, or `"write"`.

### Synthetic `ForgeAPIError` for protocol violations

`_get_list` raises when Forge returns a 200 OK whose JSON payload is
not a list. The HTTP request *did* succeed, so to keep
`ForgeAPIError` shape-consistent we synthesise the message with
`status="200"` and `body="Expected JSON array, got {type_name}"`:

> `[Forge https://forge.example.test/sdapi/v1/sd-models] HTTP 200: Expected JSON array, got dict`

This deliberately reuses `ForgeAPIError` rather than introducing a
fourth Forge variant — it's still a Forge-side contract violation,
just at the payload-shape layer rather than the HTTP-status layer.

## Where each error is raised

```
forge.py
├── _get/_post: httpx.ConnectError/TimeoutException → ForgeUnreachableError(base_url, cause)
├── _get/_post: response.status_code >= 400         → ForgeAPIError(base_url, path, status, body)
└── _get_list: non-list payload                     → ForgeAPIError (synthetic — Forge protocol violation)

output.py
├── save_generated_image: wrap mkdir + Image.save    → LocalIOError(abs_path, "mkdir"|"save", cause)
└── save_upscaled_image:  wrap mkdir + write_bytes   → LocalIOError(abs_path, "mkdir"|"write", cause)

server.py
├── generate_image: empty response.images           → ForgeEmptyResponseError(base_url, "/sdapi/v1/txt2img")
└── upscale_images: empty response.images           → ForgeEmptyResponseError(base_url, "/sdapi/v1/extra-batch-images")
```

### Supporting changes

- **`ForgeClient.base_url`.** New read-only property exposing
  `self._settings.webui_url` (as a stripped string, matching how
  `httpx.Client(base_url=...)` was constructed) so `server.py` can
  include it in `ForgeEmptyResponseError`. No behaviour change.
- **No catch-and-rewrap at the MCP boundary.** `server.py` does *not*
  wrap calls in `try/except` to relabel — the exceptions at the source
  already disambiguate.
- **`mkdir(exist_ok=True)` happy path unchanged** — only failing
  operations get wrapped.

## Testing

The project uses `*_test.py` naming (see `CLAUDE.md`).

- **`forge_test.py`** — existing assertions for `ForgeAPIError` and
  `ForgeUnreachableError` keep passing; add checks that the message
  starts with `[Forge <base_url>...]`.
- **`output_test.py`** — new tests: `mkdir` denied on a read-only
  `tmp_path` parent → `LocalIOError("mkdir failed", ...)`; `save`/
  `write` to a read-only directory → `LocalIOError`. Use `chmod` on
  a `tmp_path` subdir for deterministic permission denial.
- **`server_test.py`** — fake `ForgeClient.txt2img` returns
  `Txt2ImgResponse(images=[])` → `ForgeEmptyResponseError`; same for
  `upscale_images`. The existing `RuntimeError`-asserting tests get
  rewritten to the new type.
- **New `errors_test.py`** — minimal: instantiate each error class,
  assert the message format and base-class hierarchy
  (`isinstance(e, MaestroError)`, `isinstance(forge_err, ForgeError)`,
  etc.). Cheap regression net for the message templates that are now
  load-bearing.

## Migration / compatibility

- Existing exception names are preserved, just re-rooted under
  `MaestroError`. Code that does `except ForgeAPIError` keeps working.
- `RuntimeError("No images generated")` → `ForgeEmptyResponseError` is
  a type change in raised exception. Shipped as `feat(server)`, not
  marked `BREAKING CHANGE`: `RuntimeError` was never part of the
  documented contract, and a 2.0.0 bump for a personal tool is
  overkill.

## Docs to update on landing

- Remove the BACKLOG entry "Distinguish Forge errors from local MCP
  errors" under `Error handling` in `BACKLOG.md`.
- Update `CLAUDE.md`'s "Five modules under `src/webui_forge_maestro/`"
  section to list six modules, with a one-liner for `errors.py`
  (e.g. "`errors.py` — exception taxonomy for Forge-side vs local I/O
  failures").

## Commit shape (preview)

Conventional-commit scopes from `CLAUDE.md` apply. Likely a single PR
with a few logically separated commits:

- `feat(errors): introduce MaestroError taxonomy with Forge/local trunks`
- `feat(forge): tag Forge errors with base URL`
- `feat(output): raise LocalIOError on file I/O failures`
- `feat(server): raise ForgeEmptyResponseError on empty Forge responses`
- `docs: remove BACKLOG entry and update CLAUDE.md module listing`
