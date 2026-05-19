"""Wire-shape pydantic models for the ``/sdapi/v1/*`` endpoints we use.

Field names match Forge's JSON exactly — translation between tool-input
names and these wire names happens in ``server.py``.
"""

from pydantic import BaseModel


class ForgeUpscaler(BaseModel):
    name: str
    model_name: str | None
    model_path: str | None
    model_url: str | None
    scale: float


class ForgeModel(BaseModel):
    title: str
    model_name: str
    hash: str | None
    sha256: str | None
    filename: str
    config: str | None


class Txt2ImgRequest(BaseModel):
    """Payload sent to /sdapi/v1/txt2img.

    Field names match Forge's JSON exactly. ``scheduler`` (not
    ``scheduler_name``) and ``n_iter`` (not ``batch_size``) are the wire
    names — translation happens in ``server.py``.
    """

    prompt: str
    negative_prompt: str
    steps: int
    width: int
    height: int
    cfg_scale: float
    sampler_name: str
    scheduler: str
    seed: int
    n_iter: int
    restore_faces: bool
    tiling: bool
    distilled_cfg_scale: float


class Txt2ImgResponse(BaseModel):
    images: list[str]  # base64; may have a "data:image/png;base64," prefix


class PngInfoResponse(BaseModel):
    info: str


class ExtraBatchImageItem(BaseModel):
    data: str  # base64
    name: str  # filename


class ExtraBatchImagesRequest(BaseModel):
    resize_mode: int
    show_extras_results: bool
    gfpgan_visibility: float
    codeformer_visibility: float
    codeformer_weight: float
    upscaling_resize: float
    upscaling_resize_w: int
    upscaling_resize_h: int
    upscaling_crop: bool
    upscaler_1: str
    upscaler_2: str
    extras_upscaler_2_visibility: float
    upscale_first: bool
    imageList: list[ExtraBatchImageItem]  # upstream wire name (camelCase intentional)


class ExtraBatchImagesResponse(BaseModel):
    images: list[str]  # base64
