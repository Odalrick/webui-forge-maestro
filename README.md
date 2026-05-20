# webui-forge-maestro

A personal Python MCP server that exposes Stable Diffusion WebUI Forge's
`/sdapi/v1/*` HTTP API to Claude Code (and any other MCP client).

## What this is — and what it isn't

A from-scratch Python port of [`Ichigo3766/image-gen-mcp`][upstream],
written to learn the MCP protocol surface end-to-end and to provide a
foundation for personal tweaks (custom defaults, output handling,
Forge-only extras, etc.).

It is **not** trying to replace the upstream MCP. If you want a
battle-tested image-gen MCP, use [`Ichigo3766/image-gen-mcp`][upstream]
directly — the project this one ports from. The two are not maintained
in lockstep.

> **Status: experimental.**

[upstream]: https://github.com/Ichigo3766/image-gen-mcp

## Prerequisites

- A running Forge instance launched with `--api`. Browser UI alone isn't
  enough; the HTTP API has to be exposed.
- Sanity check:
  ```sh
  curl http://your-forge-host.example.local/sdapi/v1/sd-models
  ```
  should return a JSON array of checkpoint entries.
- Python 3.14 (version pinned in `.python-version`).
- [`uv`](https://docs.astral.sh/uv/).

## Install

```sh
git clone https://github.com/Odalrick/webui-forge-maestro.git
cd webui-forge-maestro
uv sync --locked
```

## Configuration

All configuration is through environment variables. Every variable is
optional; defaults match upstream `Ichigo3766/image-gen-mcp` exactly.

| Variable                  | Default                  | Purpose                                                        |
|---------------------------|--------------------------|----------------------------------------------------------------|
| `SD_WEBUI_URL`            | `http://127.0.0.1:7860`  | Forge HTTP base URL                                            |
| `SD_OUTPUT_DIR`           | `./output`               | Where generated/upscaled images land                           |
| `SD_AUTH_USER`            | *(unset)*                | Basic-auth user (both `_USER` and `_PASS` required to enable)  |
| `SD_AUTH_PASS`            | *(unset)*                | Basic-auth password                                            |
| `REQUEST_TIMEOUT`         | `300`                    | HTTP timeout in seconds                                        |
| `SD_RESIZE_MODE`          | `0`                      | `0` = multiplier mode, `1` = explicit dimensions               |
| `SD_UPSCALE_MULTIPLIER`   | `4`                      | Default multiplier when `SD_RESIZE_MODE=0`                     |
| `SD_UPSCALE_WIDTH`        | `512`                    | Target width when `SD_RESIZE_MODE=1`                           |
| `SD_UPSCALE_HEIGHT`       | `512`                    | Target height when `SD_RESIZE_MODE=1`                          |
| `SD_UPSCALER_1`           | `R-ESRGAN 4x+`           | Default primary upscaler                                       |
| `SD_UPSCALER_2`           | `None`                   | Default secondary upscaler (literal string `None` = disabled)  |

Note that the `REQUEST_TIMEOUT` unit differs from upstream's: upstream reads it as
milliseconds (default `300_000`); this server reads it as seconds (default `300`).
Migrating from upstream means dividing your previous value by 1000.

## Registering with Claude Code

```sh
mkdir -p ~/path/to/output

claude mcp add maestro-webui-forge --scope local -- \
  env \
    SD_WEBUI_URL=http://your-forge-host.example.local \
    SD_OUTPUT_DIR=$HOME/path/to/output \
  uv run --project /path/to/webui-forge-maestro webui-forge-maestro
```

`--scope local` registers the server only for the directory you ran the
command from (and its subdirectories), which avoids loading the MCP in
sessions where Forge isn't reachable.

## Tools exposed

- `generate_image` — txt2img with full parameter control. Returns an
  array of `{path, parameters}` per saved file; `parameters` is the
  human-readable string from Forge's `/sdapi/v1/png-info`, also embedded
  in the PNG's EXIF `ImageDescription`.
- `get_sd_models` — list available checkpoint titles.
- `set_sd_model` — switch the active checkpoint by `model_name`.
- `get_sd_upscalers` — list available upscaler names.
- `upscale_images` — upscale one or more files via the `extra-batch-images`
  endpoint. Writes `upscaled_<original-name>` next to the output dir.

LoRAs aren't a separate tool — pass them inline in the prompt as
`<lora:name:weight>` exactly like in the WebUI.

## Differences from upstream

Intentional behavioural divergences from
[`Ichigo3766/image-gen-mcp`][upstream]. Anything *not* on this list is
either a bug in this repo or upstream getting there first.

- **Server-side archive.** Every `generate_image` call sets
  `save_images=true` on the txt2img payload, so Forge mirrors each
  generation into its own `outdir_txt2img_samples` (with WebUI-style
  metadata) on top of the client-side copy this server writes. Upstream
  doesn't, so API-driven generations are absent from Forge's archive
  there.
- **Filename ordering.** Generated PNGs are named `sd_<uuid7>.png`;
  upstream uses UUIDv4. UUIDv7 puts a millisecond timestamp in the high
  bits, so `ls -1` (or any sort-by-name file browser) shows generations
  in chronological order without a separate sort step.
- **`REQUEST_TIMEOUT` is in seconds.** Upstream reads the same variable
  as milliseconds. Migration math is in the [Configuration](#configuration)
  note above the table.

## Acknowledgements

This server is a from-scratch Python implementation of
[`Ichigo3766/image-gen-mcp`][upstream], which is MIT-licensed. The
upstream is the project of record for everything the WebUI API supports;
this fork exists for personal learning and customisation. See
[Differences from upstream](#differences-from-upstream) for the
intentional divergences.

## License

MIT — see [LICENSE](LICENSE).
