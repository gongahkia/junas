"""Transport-independent inputs and labels for the classifier."""

from dataclasses import dataclass
from enum import Enum


class Classification(str, Enum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"


@dataclass(frozen=True)
class DocumentInput:
    text: str | None = None
    document_base64: str | None = None
    document_filename: str | None = None
    document_mime_type: str | None = None

    def __post_init__(self) -> None:
        if (self.text is None) == (self.document_base64 is None):
            raise ValueError("supply exactly one of text or document_base64")
        if self.text is not None and not self.text.strip():
            raise ValueError("text must contain non-whitespace content")
        if self.document_base64 is not None and not self.document_base64:
            raise ValueError("document_base64 must not be empty")
