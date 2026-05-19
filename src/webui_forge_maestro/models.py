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
