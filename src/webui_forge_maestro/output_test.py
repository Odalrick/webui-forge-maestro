import base64
import uuid
from pathlib import Path

from PIL import Image

from webui_forge_maestro.output import (
    save_generated_image,
    save_upscaled_image,
)

# Canonical 1x1 transparent PNG, base64-encoded.
ONE_PX_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)


def test_save_generated_image_creates_dest_dir_when_missing(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "nested" / "out"
    assert not dest.exists()

    path = save_generated_image(ONE_PX_PNG_B64, info="Steps: 4", dest_dir=dest)

    assert dest.is_dir()
    assert path.name.startswith("sd_")
    assert path.name.endswith(".png")
    assert path.exists()
    assert path.parent == dest.resolve()


def test_save_generated_image_embeds_info_as_exif_image_description(
    tmp_path: Path,
) -> None:
    info = "Steps: 4, CFG: 1, Seed: 42"

    path = save_generated_image(ONE_PX_PNG_B64, info=info, dest_dir=tmp_path)

    with Image.open(path) as img:
        exif = img.getexif()
        # 0x010E is the EXIF tag id for ImageDescription
        assert exif.get(0x010E) == info


def test_save_generated_image_produces_unique_names(tmp_path: Path) -> None:
    paths = {save_generated_image(ONE_PX_PNG_B64, info="", dest_dir=tmp_path) for _ in range(5)}
    assert len(paths) == 5  # all distinct


def test_save_generated_image_uses_uuid7_so_filenames_sort_by_time(
    tmp_path: Path,
) -> None:
    # UUIDv7 puts a Unix-ms timestamp in the high bits, so successive
    # generations sort chronologically by filename.
    path = save_generated_image(ONE_PX_PNG_B64, info="", dest_dir=tmp_path)

    stem = path.name.removeprefix("sd_").removesuffix(".png")
    assert uuid.UUID(stem).version == 7


def test_save_upscaled_image_uses_upscaled_prefix(tmp_path: Path) -> None:
    path = save_upscaled_image(ONE_PX_PNG_B64, source_basename="cat.png", dest_dir=tmp_path)

    assert path.name == "upscaled_cat.png"
    assert path.parent == tmp_path.resolve()
    assert path.exists()


def test_save_upscaled_image_writes_raw_bytes_without_metadata(
    tmp_path: Path,
) -> None:
    path = save_upscaled_image(ONE_PX_PNG_B64, source_basename="cat.png", dest_dir=tmp_path)

    # Round-trip check: the decoded bytes match base64-decoded input.
    expected = base64.b64decode(ONE_PX_PNG_B64)
    assert path.read_bytes() == expected
