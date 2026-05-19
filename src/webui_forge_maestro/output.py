"""Write base64-encoded images from Forge to PNG files on the host."""

import base64
import io
import uuid
from pathlib import Path

from PIL import Image

# EXIF tag id for the ImageDescription field. Upstream stores the human-
# readable parameter string from /sdapi/v1/png-info here so opening the
# file in any EXIF-aware viewer shows the params used to generate it.
_EXIF_IMAGE_DESCRIPTION = 0x010E


def save_generated_image(b64_image: str, info: str, dest_dir: Path) -> Path:
    """Write a generated PNG with ``info`` embedded as EXIF ImageDescription."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"sd_{uuid.uuid4()}.png"
    image_bytes = base64.b64decode(_strip_data_url_prefix(b64_image))
    with Image.open(io.BytesIO(image_bytes)) as img:
        exif = Image.Exif()
        exif[_EXIF_IMAGE_DESCRIPTION] = info
        img.save(path, format="PNG", exif=exif.tobytes())
    return path.resolve()


def save_upscaled_image(
    b64_image: str, source_basename: str, dest_dir: Path
) -> Path:
    """Write an upscaled PNG next to a fixed prefix; no metadata."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"upscaled_{source_basename}"
    path.write_bytes(base64.b64decode(_strip_data_url_prefix(b64_image)))
    return path.resolve()


def _strip_data_url_prefix(b64: str) -> str:
    # Forge sometimes returns a data URL ("data:image/png;base64,…") and
    # sometimes the raw base64. Normalise to the latter.
    return b64.split(",", 1)[1] if "," in b64 else b64
