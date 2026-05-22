# Changelog

## [1.1.0](https://github.com/Odalrick/webui-forge-maestro/compare/v1.0.0...v1.1.0) (2026-05-22)


### Features

* disambiguate Forge errors from local MCP errors ([#3](https://github.com/Odalrick/webui-forge-maestro/issues/3)) ([fb5dda3](https://github.com/Odalrick/webui-forge-maestro/commit/fb5dda32ddf1c68080f7259df3c71db977bcbfbb))
* **forge:** retry once on transient Errno 19 from Forge ([#4](https://github.com/Odalrick/webui-forge-maestro/issues/4)) ([39dddff](https://github.com/Odalrick/webui-forge-maestro/commit/39dddffafa5ccae325f1a16fad01ca44a0ab23d5))
* **output:** use UUIDv7 for generated filenames ([d13b237](https://github.com/Odalrick/webui-forge-maestro/commit/d13b23702e36cfea018ee7c3badcb800ff594737))
* **server:** archive generations via Forge's save_images flag ([5a61015](https://github.com/Odalrick/webui-forge-maestro/commit/5a61015e423928eb7c1f3b4a59f1c25df77bb225))
* **server:** saner generate_image defaults for SD-family models ([7fbc8ad](https://github.com/Odalrick/webui-forge-maestro/commit/7fbc8ad3ec38f3b113421055f1fc124b79b9accf))


### Documentation

* add BACKLOG.md wishlist ([2caaf6f](https://github.com/Odalrick/webui-forge-maestro/commit/2caaf6f52b67a857966b3f1c4cdbf3f04ab8f5b1))
* add commands section and document models.py module ([7984141](https://github.com/Odalrick/webui-forge-maestro/commit/798414104dc014c4c9f23c9019b8c5dfb3b523a0))
* correct Python version in README ([bdf8170](https://github.com/Odalrick/webui-forge-maestro/commit/bdf81707f470977fe72198ac57ec99309b8fb1d0))
* extend backlog with error-handling and output-policy items ([05a40d4](https://github.com/Odalrick/webui-forge-maestro/commit/05a40d4de1a0986e054946056e2491dd1a07e1fd))
* note intentional divergences from upstream ([6a681b2](https://github.com/Odalrick/webui-forge-maestro/commit/6a681b2a0f2bd33c0cffcc80e3e3c193452eddf5))
* note uv.lock self-entry drift after releases ([c49c48d](https://github.com/Odalrick/webui-forge-maestro/commit/c49c48d7630e1c1f41fbb2e0b86ef93923f0c875))

## [1.0.0](https://github.com/Odalrick/webui-forge-maestro/compare/v0.1.0...v1.0.0) (2026-05-20)


### Features

* **config:** Settings model with from_env loader ([7afb743](https://github.com/Odalrick/webui-forge-maestro/commit/7afb743f0c4dab95d4fa725269bca3fa2b559a4b))
* **forge:** ForgeClient with list_upscalers and typed errors ([8a80396](https://github.com/Odalrick/webui-forge-maestro/commit/8a80396d8f4f1a85f2b642a79ee49780f9776b84))
* **output:** save_generated_image with EXIF + save_upscaled_image ([424b7db](https://github.com/Odalrick/webui-forge-maestro/commit/424b7db9abef48807e437e1ee6ffdd6b8f0214ef))
* **server:** FastMCP wiring with first tool (get_sd_upscalers) ([00c9766](https://github.com/Odalrick/webui-forge-maestro/commit/00c9766b0003006dcb286477305cfffba47ef594))
* **server:** generate_image tool with png-info EXIF embedding ([d7b2355](https://github.com/Odalrick/webui-forge-maestro/commit/d7b2355ddf638b0d0697d8469af6640645d14770))
* **server:** get_sd_models tool wrapping ForgeClient.list_models ([2d7d693](https://github.com/Odalrick/webui-forge-maestro/commit/2d7d693694ec9cb2e71e6a220b23f4a79942d0dc))
* **server:** set_sd_model tool with confirmation string ([d43e332](https://github.com/Odalrick/webui-forge-maestro/commit/d43e332234eb2dad92e284c7ec8baf42c881cfd2))
* **server:** upscale_images tool via extra-batch-images endpoint ([b9332fb](https://github.com/Odalrick/webui-forge-maestro/commit/b9332fb131930fee5208b0ab8661f9f0dd64fc0d))


### Bug Fixes

* **config:** document REQUEST_TIMEOUT unit divergence and tighten env filter ([03006ab](https://github.com/Odalrick/webui-forge-maestro/commit/03006ab88728d135edb98b26d046da37236e82bd))


### Documentation

* add CLAUDE.md with public-repo guard and design constraints ([919f3f5](https://github.com/Odalrick/webui-forge-maestro/commit/919f3f5c25945e06a899ba134e2a369c092627fd))
* full README for v1 release ([cc9c92f](https://github.com/Odalrick/webui-forge-maestro/commit/cc9c92f86544c00cfbf9df04c3cfb891c692455c))
