from abc import ABC, abstractmethod


class ReceiptProviderError(Exception):
    pass


class ReceiptProviderUnavailable(ReceiptProviderError):
    pass


class ReceiptProvider(ABC):
    @abstractmethod
    def extract(self, image_bytes, mime_type, category_context):
        raise NotImplementedError
