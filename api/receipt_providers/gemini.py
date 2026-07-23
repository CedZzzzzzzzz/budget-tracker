import os

from api.receipt_providers.base import (
    ReceiptProvider,
    ReceiptProviderError,
    ReceiptProviderUnavailable,
)
from api.receipt_schema import parse_provider_text, provider_schema


class GeminiReceiptProvider(ReceiptProvider):
    def __init__(self, api_key=None, model=None, timeout_seconds=None):
        self.api_key = api_key or self.configured_api_key()
        self.model = model or os.environ.get(
            "GEMINI_RECEIPT_MODEL",
            "gemini-3.5-flash-lite",
        )
        try:
            configured_timeout = float(
                timeout_seconds
                or os.environ.get("RECEIPT_OCR_TIMEOUT_SECONDS", "12")
            )
        except (TypeError, ValueError):
            configured_timeout = 12
        self.timeout_seconds = max(1, min(configured_timeout, 60))

    @staticmethod
    def configured_api_key():
        receipt_key = (os.environ.get("GEMINI_RECEIPT_API_KEY") or "").strip()
        if receipt_key:
            return receipt_key
        allow_general = os.environ.get(
            "RECEIPT_OCR_ALLOW_GENERAL_KEY",
            "false",
        ).strip().lower() in ("1", "true", "yes", "on")
        if allow_general:
            return (os.environ.get("GEMINI_API_KEY") or "").strip()
        return ""

    def extract(self, image_bytes, mime_type, category_context):
        if not self.api_key:
            raise ReceiptProviderUnavailable("Receipt extraction is not configured.")
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    timeout=int(self.timeout_seconds * 1000),
                ),
            )
            categories = [row["slug"] for row in category_context]
            category_lines = "\n".join(
                (
                    f"- {row['slug']}: {row['label']} — "
                    f"{row.get('description') or 'No description'}; "
                    f"keywords: {', '.join((row.get('keywords') or [])[:12]) or 'none'}"
                )
                for row in category_context
            )
            prompt = (
                "Extract this purchase receipt into the required schema. "
                "Use null for unreadable optional amounts or dates. "
                "Do not invent line items. Use ISO YYYY-MM-DD dates. "
                "For each readable line, choose exactly one allowed category slug. "
                "Allowed categories:\n"
                f"{category_lines}"
            )
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=provider_schema(categories),
                ),
            )
            return parse_provider_text(response.text)
        except ReceiptProviderError:
            raise
        except Exception as error:
            raise ReceiptProviderError("Receipt extraction failed.") from error
        finally:
            if "client" in locals():
                try:
                    client.close()
                except Exception:
                    pass
