from io import BytesIO

import pytest
from PIL import Image

from ai_engine.images import normalize_image
from ai_engine.models import DocumentImage


def create_image_bytes(format_name, mode="RGB"):
    output = BytesIO()
    color = (20, 40, 60) if mode == "RGB" else 100
    Image.new(mode, (4, 3), color=color).save(output, format=format_name)
    return output.getvalue()


def test_normalize_image_reencodes_jpeg_as_jpeg(tmp_path):
    path = tmp_path / "photo.jpeg"
    path.write_bytes(create_image_bytes("JPEG"))
    image = DocumentImage(
        name=path.name,
        data=path.read_bytes(),
        media_type="image/jpeg",
    )

    normalized = normalize_image(image)

    assert normalized.name == "photo.jpg"
    assert normalized.media_type == "image/jpeg"
    with Image.open(BytesIO(normalized.data)) as reopened:
        assert reopened.format == "JPEG"
        assert reopened.size == (4, 3)


@pytest.mark.parametrize(
    ("format_name", "extension"),
    [
        ("PNG", ".png"),
        ("BMP", ".bmp"),
        ("GIF", ".gif"),
        ("TIFF", ".tiff"),
        ("WEBP", ".webp"),
    ],
)
def test_normalize_image_converts_non_jpeg_formats_to_png(
    format_name,
    extension,
    tmp_path,
):
    path = tmp_path / f"source{extension}"
    path.write_bytes(create_image_bytes(format_name))
    image = DocumentImage(name=path.name, data=path.read_bytes())

    normalized = normalize_image(image)

    assert normalized.name == "source.png"
    assert normalized.media_type == "image/png"
    with Image.open(BytesIO(normalized.data)) as reopened:
        assert reopened.format == "PNG"
        assert reopened.size == (4, 3)


def test_normalize_image_rejects_invalid_bytes():
    image = DocumentImage(
        name="broken.png",
        data=b"not-an-image",
        media_type="image/png",
    )

    with pytest.raises(ValueError, match="Could not normalize image broken.png"):
        normalize_image(image)

