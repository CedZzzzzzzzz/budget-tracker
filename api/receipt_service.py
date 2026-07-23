import io
import os
from threading import BoundedSemaphore

from api.category_service import classify_receipt_items
from api.receipt_providers import GeminiReceiptProvider
from api.receipt_providers.base import ReceiptProviderError
from api.receipt_schema import ReceiptSchemaError, normalize_receipt


ALLOWED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FORMAT_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
}


class ReceiptUploadError(ValueError):
    pass


class ReceiptBusyError(RuntimeError):
    pass


def configured_limit(name, default, minimum=1, maximum=None):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


RECEIPT_GATE = BoundedSemaphore(
    configured_limit("RECEIPT_OCR_CONCURRENCY", 4, maximum=32)
)


def validate_and_normalize_image(file_storage):
    from PIL import Image, ImageOps, UnidentifiedImageError

    filename = str(getattr(file_storage, "filename", "") or "")
    extension = os.path.splitext(filename.lower())[1]
    if extension not in ALLOWED_EXTENSIONS:
        raise ReceiptUploadError("Upload a JPEG, PNG, or WebP receipt image.")
    declared_mime = str(getattr(file_storage, "mimetype", "") or "").lower()
    if declared_mime not in ("", "application/octet-stream", *ALLOWED_FORMATS.values()):
        raise ReceiptUploadError("Upload a JPEG, PNG, or WebP receipt image.")

    max_bytes = configured_limit("RECEIPT_OCR_MAX_BYTES", 8 * 1024 * 1024)
    raw = file_storage.stream.read(max_bytes + 1)
    if not raw:
        raise ReceiptUploadError("Choose a receipt image to scan.")
    if len(raw) > max_bytes:
        raise ReceiptUploadError("The receipt image is too large.")

    try:
        with Image.open(io.BytesIO(raw)) as verified:
            image_format = verified.format
            frames = int(getattr(verified, "n_frames", 1))
            width, height = verified.size
            verified.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise ReceiptUploadError("The selected file is not a safe supported image.") from error

    if (
        image_format not in ALLOWED_FORMATS
        or extension not in FORMAT_EXTENSIONS.get(image_format, set())
        or frames != 1
    ):
        raise ReceiptUploadError("Upload a single JPEG, PNG, or WebP receipt image.")
    if declared_mime not in ("", "application/octet-stream", ALLOWED_FORMATS[image_format]):
        raise ReceiptUploadError("The receipt file type does not match its image data.")
    max_pixels = configured_limit("RECEIPT_OCR_MAX_PIXELS", 20_000_000)
    if width <= 0 or height <= 0 or width * height > max_pixels:
        raise ReceiptUploadError("The receipt image dimensions are too large.")

    try:
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened)
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, "white")
                alpha = image.getchannel("A")
                background.paste(image.convert("RGB"), mask=alpha)
                image = background
            else:
                image = image.convert("RGB")
            maximum_dimension = configured_limit("RECEIPT_OCR_MAX_DIMENSION", 2400)
            image.thumbnail((maximum_dimension, maximum_dimension))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue(), "image/jpeg", {
                "width": image.width,
                "height": image.height,
                "input_bytes": len(raw),
            }
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise ReceiptUploadError("The receipt image could not be processed safely.") from error


def extract_receipt(
    file_storage,
    category_context,
    user_rules=None,
    provider=None,
):
    if not RECEIPT_GATE.acquire(blocking=False):
        raise ReceiptBusyError("Receipt scanning is busy.")
    try:
        image_bytes, mime_type, image_meta = validate_and_normalize_image(file_storage)
        extractor = provider or GeminiReceiptProvider()
        raw_receipt = extractor.extract(image_bytes, mime_type, category_context)
        receipt = normalize_receipt(raw_receipt)
        receipt["items"] = classify_receipt_items(
            receipt["merchant"],
            receipt["items"],
            user_rules=user_rules,
            category_context=category_context,
        )
        receipt["image"] = image_meta
        return receipt
    except (ReceiptSchemaError, ReceiptProviderError):
        raise
    finally:
        RECEIPT_GATE.release()
