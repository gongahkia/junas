from __future__ import annotations

import base64
import mimetypes
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Protocol

import httpx

from kaypoh.workflow.privacy_guard import PrivacyGuard

SUPPORTED_IMAGE_MIMES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/tiff",
        "image/bmp",
    }
)
AWS_REKOGNITION_MIMES = frozenset({"image/jpeg", "image/png"})


class ImageScanError(ValueError):
    """Raised when configured image OCR cannot complete safely."""


@dataclass(frozen=True)
class ImageLocator:
    container_path: str
    image_index: int
    page_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "container_path": self.container_path,
            "image_index": self.image_index,
        }
        if self.page_number is not None:
            payload["page_number"] = self.page_number
        return payload


@dataclass(frozen=True)
class ImageCandidate:
    data: bytes
    mime_type: str
    locator: ImageLocator


@dataclass(frozen=True)
class ImageOcrResult:
    text: str
    locator: ImageLocator
    provider: str
    privacy_ledger: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ImageTextSpan:
    start_char: int
    end_char: int
    locator: ImageLocator
    provider: str


class ImageScanner(Protocol):
    provider: str

    def scan(self, candidate: ImageCandidate) -> ImageOcrResult:
        ...


def clean_ocr_text(text: str) -> str:
    cleaned = text.replace("\x00", "")
    cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", "\r", "\t"))
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def image_mime_from_name(name: str, data: bytes | None = None) -> str:
    guessed = (mimetypes.guess_type(name)[0] or "").lower()
    if guessed in SUPPORTED_IMAGE_MIMES:
        return guessed
    if data:
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if data.startswith((b"II*\x00", b"MM\x00*")):
            return "image/tiff"
        if data.startswith(b"BM"):
            return "image/bmp"
    return guessed or "application/octet-stream"


def collect_docx_images(data: bytes) -> list[ImageCandidate]:
    import zipfile

    candidates: list[ImageCandidate] = []
    with zipfile.ZipFile(BytesIO(data)) as archive:
        media_names = sorted(name for name in archive.namelist() if name.startswith("word/media/"))
        for index, name in enumerate(media_names):
            image_data = archive.read(name)
            mime_type = image_mime_from_name(name, image_data)
            candidates.append(
                ImageCandidate(
                    data=image_data,
                    mime_type=mime_type,
                    locator=ImageLocator(container_path=name, image_index=index),
                )
            )
    return candidates


def collect_pdf_images(data: bytes) -> list[ImageCandidate]:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ImageScanError("PDF image extraction requires the optional pypdf dependency") from exc

    candidates: list[ImageCandidate] = []
    reader = PdfReader(BytesIO(data))
    image_index = 0
    for page_index, page in enumerate(reader.pages):
        try:
            page_images = getattr(page, "images", None) or []
        except Exception as exc:
            raise ImageScanError(f"PDF image enumeration failed on page {page_index + 1}: {exc}") from exc
        for raw_image in page_images:
            image_data = getattr(raw_image, "data", None)
            if not image_data:
                continue
            name = str(getattr(raw_image, "name", "") or f"page-{page_index + 1}-image-{image_index}")
            candidates.append(
                ImageCandidate(
                    data=bytes(image_data),
                    mime_type=image_mime_from_name(name, bytes(image_data)),
                    locator=ImageLocator(
                        container_path=name,
                        image_index=image_index,
                        page_number=page_index + 1,
                    ),
                )
            )
            image_index += 1
    return candidates


def standalone_image_candidate(data: bytes, *, filename: str, mime_type: str) -> ImageCandidate:
    return ImageCandidate(
        data=data,
        mime_type=image_mime_from_name(filename, data) if not mime_type else mime_type,
        locator=ImageLocator(container_path=filename or "document-image", image_index=0),
    )


class _CloudImageScanner:
    provider: str

    def __init__(self, *, privacy_guard: PrivacyGuard, tenant_opt_in: bool):
        self.privacy_guard = privacy_guard
        self.tenant_opt_in = tenant_opt_in

    def _ledger_or_raise(self, candidate: ImageCandidate) -> list[dict[str, Any]]:
        entry = self.privacy_guard.check_external_content(
            candidate.data,
            destination=self.provider,
            content_type=candidate.mime_type,
            tenant_opt_in=self.tenant_opt_in,
            operation="image_ocr",
        )
        if not entry.allowed:
            raise ImageScanError(f"{self.provider} blocked by privacy policy: {entry.reason}")
        return [entry.to_dict()]


class TesseractImageScanner:
    provider = "tesseract"

    def scan(self, candidate: ImageCandidate) -> ImageOcrResult:
        try:
            from PIL import Image
            import pytesseract
        except Exception as exc:
            raise ImageScanError("Tesseract OCR requires Pillow and pytesseract") from exc

        try:
            with Image.open(BytesIO(candidate.data)) as image:
                text = pytesseract.image_to_string(image)
        except Exception as exc:
            raise ImageScanError(f"Tesseract OCR failed for {candidate.locator.container_path}: {exc}") from exc
        return ImageOcrResult(
            text=clean_ocr_text(text),
            locator=candidate.locator,
            provider=self.provider,
        )


class OpenAIVisionImageScanner(_CloudImageScanner):
    provider = "openai_vision"

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=bool(getattr(settings, "tenant_opt_in_openai", False)),
        )
        self.api_key = str(getattr(settings, "openai_api_key", "") or "")
        self.base_url = str(getattr(settings, "openai_base_url", "https://api.openai.com/v1/responses") or "")
        self.model = str(getattr(settings, "model", "gpt-4o-mini") or "gpt-4o-mini")
        self.timeout_seconds = max(0.1, float(getattr(settings, "timeout_seconds", 20.0) or 20.0))
        if not self.api_key:
            raise ImageScanError("openai_vision requires OPENAI_API_KEY")

    def scan(self, candidate: ImageCandidate) -> ImageOcrResult:
        ledger = self._ledger_or_raise(candidate)
        data_url = f"data:{candidate.mime_type};base64,{base64.b64encode(candidate.data).decode('ascii')}"
        body = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract only visible text from this image. Return plain text only. "
                                "If no text is visible, return an empty string."
                            ),
                        },
                        {"type": "input_image", "image_url": data_url, "detail": "high"},
                    ],
                }
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self.base_url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise ImageScanError(f"openai_vision OCR failed: {exc}") from exc
        return ImageOcrResult(
            text=clean_ocr_text(_extract_openai_output_text(payload)),
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=ledger,
        )


def _extract_openai_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct
    texts: list[str] = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                texts.append(content["text"])
    return "\n".join(texts)


class GoogleVisionImageScanner(_CloudImageScanner):
    provider = "google_vision"

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=bool(getattr(settings, "tenant_opt_in_google", False)),
        )
        try:
            from google.cloud import vision
        except Exception as exc:
            raise ImageScanError("google_vision requires google-cloud-vision") from exc
        self.vision = vision
        self.client = vision.ImageAnnotatorClient()

    def scan(self, candidate: ImageCandidate) -> ImageOcrResult:
        ledger = self._ledger_or_raise(candidate)
        try:
            image = self.vision.Image(content=candidate.data)
            response = self.client.document_text_detection(image=image)
        except Exception as exc:
            raise ImageScanError(f"google_vision OCR failed: {exc}") from exc
        error = getattr(getattr(response, "error", None), "message", "")
        if error:
            raise ImageScanError(f"google_vision OCR failed: {error}")
        full_text = getattr(getattr(response, "full_text_annotation", None), "text", "")
        if not full_text:
            annotations = getattr(response, "text_annotations", []) or []
            if annotations:
                full_text = str(getattr(annotations[0], "description", "") or "")
        return ImageOcrResult(
            text=clean_ocr_text(full_text),
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=ledger,
        )


class AWSRekognitionImageScanner(_CloudImageScanner):
    provider = "aws_rekognition"

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=bool(getattr(settings, "tenant_opt_in_aws", False)),
        )
        try:
            import boto3
        except Exception as exc:
            raise ImageScanError("aws_rekognition requires boto3") from exc
        region = str(getattr(settings, "aws_region", "") or "") or None
        self.client = boto3.client("rekognition", region_name=region)

    def scan(self, candidate: ImageCandidate) -> ImageOcrResult:
        if candidate.mime_type not in AWS_REKOGNITION_MIMES:
            raise ImageScanError("aws_rekognition supports JPEG and PNG image OCR only")
        ledger = self._ledger_or_raise(candidate)
        try:
            response = self.client.detect_text(Image={"Bytes": candidate.data})
        except Exception as exc:
            raise ImageScanError(f"aws_rekognition OCR failed: {exc}") from exc
        detections = response.get("TextDetections", []) or []
        lines = [item for item in detections if item.get("Type") == "LINE"]
        if not lines:
            lines = [item for item in detections if item.get("Type") == "WORD"]
        lines.sort(key=_rekognition_sort_key)
        text = "\n".join(str(item.get("DetectedText", "") or "") for item in lines)
        return ImageOcrResult(
            text=clean_ocr_text(text),
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=ledger,
        )


def _rekognition_sort_key(item: dict[str, Any]) -> tuple[float, float, int]:
    box = ((item.get("Geometry") or {}).get("BoundingBox") or {})
    return (float(box.get("Top", 0.0) or 0.0), float(box.get("Left", 0.0) or 0.0), int(item.get("Id", 0) or 0))


class AzureVisionImageScanner(_CloudImageScanner):
    provider = "azure_vision"

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=bool(getattr(settings, "tenant_opt_in_azure", False)),
        )
        endpoint = str(getattr(settings, "azure_endpoint", "") or "")
        key = str(getattr(settings, "azure_key", "") or "")
        if not endpoint or not key:
            raise ImageScanError("azure_vision requires AZURE_VISION_ENDPOINT and AZURE_VISION_KEY")
        try:
            from azure.ai.vision.imageanalysis import ImageAnalysisClient
            from azure.ai.vision.imageanalysis.models import VisualFeatures
            from azure.core.credentials import AzureKeyCredential
        except Exception as exc:
            raise ImageScanError("azure_vision requires azure-ai-vision-imageanalysis") from exc
        self.visual_features = VisualFeatures
        self.client = ImageAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    def scan(self, candidate: ImageCandidate) -> ImageOcrResult:
        ledger = self._ledger_or_raise(candidate)
        try:
            result = self.client.analyze(
                image_data=candidate.data,
                visual_features=[self.visual_features.READ],
            )
        except Exception as exc:
            raise ImageScanError(f"azure_vision OCR failed: {exc}") from exc
        lines: list[str] = []
        read = getattr(result, "read", None)
        for block in getattr(read, "blocks", []) or []:
            for line in getattr(block, "lines", []) or []:
                text = str(getattr(line, "text", "") or "")
                if text:
                    lines.append(text)
        return ImageOcrResult(
            text=clean_ocr_text("\n".join(lines)),
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=ledger,
        )


def build_image_scanner(settings: Any, privacy_guard: PrivacyGuard) -> ImageScanner | None:
    provider = str(getattr(settings, "provider", "none") or "none").lower()
    if provider == "none":
        return None
    if provider == "tesseract":
        return TesseractImageScanner()
    if provider == "openai_vision":
        return OpenAIVisionImageScanner(settings, privacy_guard=privacy_guard)
    if provider == "google_vision":
        return GoogleVisionImageScanner(settings, privacy_guard=privacy_guard)
    if provider == "aws_rekognition":
        return AWSRekognitionImageScanner(settings, privacy_guard=privacy_guard)
    if provider == "azure_vision":
        return AzureVisionImageScanner(settings, privacy_guard=privacy_guard)
    raise ImageScanError(f"unsupported image OCR provider: {provider}")


def scan_image_candidates(
    candidates: list[ImageCandidate],
    *,
    scanner: ImageScanner,
    settings: Any,
) -> tuple[list[ImageOcrResult], list[dict[str, Any]]]:
    max_images = int(getattr(settings, "max_images", 32) or 32)
    max_bytes = int(getattr(settings, "max_bytes", 10 * 1024 * 1024) or (10 * 1024 * 1024))
    if len(candidates) > max_images:
        raise ImageScanError(f"image OCR refused {len(candidates)} images; maximum is {max_images}")

    results: list[ImageOcrResult] = []
    privacy_ledger: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.mime_type not in SUPPORTED_IMAGE_MIMES:
            raise ImageScanError(f"image OCR does not support {candidate.mime_type} at {candidate.locator.container_path}")
        if len(candidate.data) > max_bytes:
            raise ImageScanError(
                f"image OCR refused {candidate.locator.container_path}; "
                f"{len(candidate.data)} bytes exceeds maximum {max_bytes}"
            )
        raw_result = scanner.scan(candidate)
        result = _coerce_scan_result(raw_result, candidate=candidate, provider=getattr(scanner, "provider", "image_ocr"))
        privacy_ledger.extend(result.privacy_ledger)
        if result.text:
            results.append(result)
    return results, privacy_ledger


def _coerce_scan_result(raw_result: Any, *, candidate: ImageCandidate, provider: str) -> ImageOcrResult:
    if isinstance(raw_result, ImageOcrResult):
        return raw_result
    if isinstance(raw_result, str):
        return ImageOcrResult(
            text=clean_ocr_text(raw_result),
            locator=candidate.locator,
            provider=provider,
        )
    if isinstance(raw_result, dict):
        return ImageOcrResult(
            text=clean_ocr_text(str(raw_result.get("text", "") or "")),
            locator=candidate.locator,
            provider=str(raw_result.get("provider", provider) or provider),
            privacy_ledger=list(raw_result.get("privacy_ledger", []) or []),
        )
    raise ImageScanError(f"image scanner returned unsupported result type: {type(raw_result).__name__}")


def append_ocr_text_blocks(
    base_text: str,
    ocr_results: list[ImageOcrResult],
) -> tuple[str, list[ImageTextSpan]]:
    text = clean_ocr_text(base_text)
    spans: list[ImageTextSpan] = []
    for result in ocr_results:
        ocr_text = clean_ocr_text(result.text)
        if not ocr_text:
            continue
        prefix = ""
        if text:
            prefix += "\n\n"
        prefix += f"[Image OCR: {result.locator.container_path}#{result.locator.image_index}]\n"
        start = len(text) + len(prefix)
        text = text + prefix + ocr_text
        end = start + len(ocr_text)
        spans.append(
            ImageTextSpan(
                start_char=start,
                end_char=end,
                locator=result.locator,
                provider=result.provider,
            )
        )
    return text, spans


def image_locator_for_span(spans: list[ImageTextSpan], start: int, end: int) -> dict[str, Any] | None:
    for span in spans:
        if span.start_char <= start and end <= span.end_char:
            return span.locator.to_dict()
    return None
