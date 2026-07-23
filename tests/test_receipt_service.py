import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from api.receipt_schema import ReceiptSchemaError, normalize_receipt, provider_schema
from api.receipt_providers.gemini import GeminiReceiptProvider
from api.receipt_service import ReceiptUploadError, validate_and_normalize_image


def image_upload(fmt="PNG", filename="receipt.png", size=(600, 900)):
    output = io.BytesIO()
    Image.new("RGB", size, "white").save(output, format=fmt)
    output.seek(0)
    return FileStorage(stream=output, filename=filename)


def test_receipt_provider_uses_current_document_extraction_model(monkeypatch):
    monkeypatch.delenv("GEMINI_RECEIPT_MODEL", raising=False)
    provider = GeminiReceiptProvider(api_key="test-key")

    assert provider.model == "gemini-3.5-flash-lite"


def test_provider_schema_keeps_server_enforced_bounds_out_of_api_contract():
    schema = provider_schema(["food", "other"])
    serialized = str(schema)

    assert "maxLength" not in serialized
    assert "maxItems" not in serialized
    assert "minimum" not in serialized
    assert "maximum" not in serialized
    assert schema["properties"]["items"]["items"]["properties"]["category"]["enum"] == [
        "food",
        "other",
    ]


def test_receipt_normalization_uses_total_when_lines_are_unreadable():
    receipt = normalize_receipt({
        "merchant": "Sample Store",
        "purchase_date": "2026-07-23",
        "currency": "PHP",
        "total": 125.5,
        "items": [],
        "warnings": [],
    })

    assert receipt["mode"] == "total"
    assert receipt["items"] == [{
        "name": "Sample Store",
        "quantity": 1.0,
        "unit_price": 125.5,
        "amount": 125.5,
        "category": "",
        "confidence": 0.0,
    }]


def test_receipt_normalization_marks_mismatched_lines():
    receipt = normalize_receipt({
        "merchant": "Sample Store",
        "currency": "PHP",
        "total": 200,
        "items": [
            {"name": "Milk", "amount": 90, "category": "groceries", "confidence": 0.9},
            {"name": "Bread", "amount": 40, "category": "groceries", "confidence": 0.9},
        ],
        "warnings": [],
    })

    assert receipt["reconciled"] is False
    assert receipt["mode"] == "total"
    assert any("do not match" in warning for warning in receipt["warnings"])


def test_receipt_normalization_rejects_negative_total():
    with pytest.raises(ReceiptSchemaError):
        normalize_receipt({
            "merchant": "Sample Store",
            "currency": "PHP",
            "total": -10,
            "items": [],
            "warnings": [],
        })


def test_receipt_normalization_warns_when_php_is_assumed():
    receipt = normalize_receipt({
        "merchant": "Sample Store",
        "total": 125,
        "items": [],
        "warnings": [],
    })

    assert receipt["currency"] == "PHP"
    assert any("PHP was assumed" in warning for warning in receipt["warnings"])


def test_receipt_normalization_warns_for_foreign_currency():
    receipt = normalize_receipt({
        "merchant": "Sample Store",
        "currency": "USD",
        "total": 125,
        "items": [],
        "warnings": [],
    })

    assert receipt["currency"] == "USD"
    assert any("stores amounts in PHP" in warning for warning in receipt["warnings"])


def test_image_validation_reencodes_supported_image():
    normalized, mime_type, metadata = validate_and_normalize_image(image_upload())

    assert mime_type == "image/jpeg"
    assert normalized.startswith(b"\xff\xd8\xff")
    assert metadata["width"] == 600
    assert metadata["height"] == 900


def test_image_validation_rejects_malformed_file():
    upload = FileStorage(stream=io.BytesIO(b"not an image"), filename="receipt.jpg")

    with pytest.raises(ReceiptUploadError):
        validate_and_normalize_image(upload)


def test_image_validation_rejects_unsupported_extension():
    with pytest.raises(ReceiptUploadError):
        validate_and_normalize_image(image_upload(filename="receipt.gif"))


def test_image_validation_rejects_extension_signature_mismatch():
    with pytest.raises(ReceiptUploadError):
        validate_and_normalize_image(image_upload(fmt="PNG", filename="receipt.jpg"))
