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
