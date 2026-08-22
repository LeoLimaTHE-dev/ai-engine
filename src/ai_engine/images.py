from io import BytesIO

from PIL import Image

from ai_engine.models import DocumentImage


def normalize_image(
    image: DocumentImage,
) -> DocumentImage:
    """
    Opens and re-encodes an image into a safe format
    for multimodal API providers.

    JPEG remains JPEG when possible.
    Everything else is normalized to PNG.
    """

    try:
        with Image.open(BytesIO(image.data)) as pil_image:
            pil_image.load()

            original_format = (pil_image.format or "").upper()

            output = BytesIO()

            # -------------------------
            # JPEG
            # -------------------------

            if original_format in (
                "JPEG",
                "JPG",
            ):
                if pil_image.mode not in (
                    "RGB",
                    "L",
                ):
                    pil_image = pil_image.convert("RGB")

                pil_image.save(
                    output,
                    format="JPEG",
                    quality=95,
                )

                return DocumentImage(
                    name=(f"{image.name.rsplit('.', 1)[0]}.jpg"),
                    data=output.getvalue(),
                    media_type="image/jpeg",
                )

            # -------------------------
            # Everything else → PNG
            # -------------------------

            if pil_image.mode not in (
                "RGB",
                "RGBA",
                "L",
            ):
                pil_image = pil_image.convert("RGBA")

            pil_image.save(
                output,
                format="PNG",
            )

            return DocumentImage(
                name=(f"{image.name.rsplit('.', 1)[0]}.png"),
                data=output.getvalue(),
                media_type="image/png",
            )

    except Exception as exc:
        raise ValueError(f"Could not normalize image {image.name}: {exc}") from exc
