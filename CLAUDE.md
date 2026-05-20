# webui-forge-maestro

Personal Python MCP server for Stable Diffusion WebUI Forge, mirroring the tool
surface of `Ichigo3766/image-gen-mcp`.

## Public-repo identity

This is a **public** repo. Before committing, verify:

```bash
git config user.name   # → Odalrick
git config user.email  # → odalrick@gmail.com
```

Both are set locally on this repo and MUST stay that way — the global git
identity points at the work address.

Do not commit personal hostnames (e.g. `*.annah.local`), absolute paths under
`~/workbench`, or anything else that ties the repo to a specific machine.
README and examples use placeholders.

## Upstream reference

The functional spec of record is `Ichigo3766/image-gen-mcp` pinned at commit
`0829260e`, checked out locally at `~/mcp/image-gen-mcp/`. Read it when in
doubt about tool semantics or response shapes. Any divergence is a bug in this
repo, not in upstream.

## Architecture

Four modules under `src/webui_forge_maestro/`:

- `config.py` — `Settings` model, env-loaded
- `forge.py` — typed `httpx` client for Forge's `/sdapi/v1/*` endpoints
- `output.py` — base64 → PNG file, with optional EXIF embedding
- `server.py` — `ToolHandlers` class + `create_server` factory wiring FastMCP

Tool methods live as methods on `ToolHandlers` and are tested directly with a
fake `ForgeClient` — no `respx` needed at the server layer. `create_server`
just wires those methods into FastMCP. If you find yourself reaching for
`respx` in `server_test.py`, you're testing the wrong layer.

## Sync throughout — by design

One Forge instance, one GPU, one queue. The HTTP client and tool handlers are
synchronous on purpose, even though `httpx` supports async. Don't async-ify
without a concrete reason — concurrency on the client side just queues at the
server side anyway.

## Commit scopes

Conventional commits, scoped:

- `bootstrap` — initial repo setup, dependency wiring
- `config` — `Settings` and env loading
- `forge` — HTTP client, wire-shape models
- `output` — file writing, EXIF
- `server` — FastMCP wiring, tool handlers
- `docs` — README, LICENSE, this file
- `chore` — anything else
