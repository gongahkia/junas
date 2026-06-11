from __future__ import annotations

import base64
import mimetypes
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Protocol

import httpx

from kaypoh.external.privacy_guard import PrivacyGuard

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
    source_type: str = "embedded_image"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "container_path": self.container_path,
            "image_index": self.image_index,
            "source_type": self.source_type,
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
class ImageBoundingBox:
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    def clipped_to_text_range(self, *, text_length: int, start: int, end: int) -> "ImageBoundingBox":
        length = max(1, int(text_length))
        clipped_start = max(0, min(length, int(start)))
        clipped_end = max(clipped_start + 1, min(length, int(end)))
        left_ratio = clipped_start / length
        right_ratio = clipped_end / length
        return ImageBoundingBox(
            x=max(0.0, min(1.0, self.x + self.width * left_ratio)),
            y=self.y,
            width=max(0.0, min(1.0, self.width * (right_ratio - left_ratio))),
            height=self.height,
        )


@dataclass(frozen=True)
class ImageTextRegion:
    text: str
    start_char: int
    end_char: int
    bounding_box: ImageBoundingBox | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }
        if self.bounding_box is not None:
            payload["bounding_box"] = self.bounding_box.to_dict()
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(frozen=True)
class ImageOcrResult:
    text: str
    locator: ImageLocator
    provider: str
    privacy_ledger: list[dict[str, Any]] = field(default_factory=list)
    confidence: float | None = None
    regions: list[ImageTextRegion] = field(default_factory=list)


@dataclass(frozen=True)
class ImageTextSpan:
    start_char: int
    end_char: int
    locator: ImageLocator
    provider: str
    confidence: float | None = None
    regions: list[ImageTextRegion] = field(default_factory=list)


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
                    locator=ImageLocator(container_path=name, image_index=index, source_type="docx_embedded_image"),
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
                        source_type="pdf_embedded_image",
                    ),
                )
            )
            image_index += 1
    return candidates


def collect_pdf_page_renders(
    data: bytes,
    *,
    max_pages: int = 8,
    scale: float = 2.0,
) -> list[ImageCandidate]:
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        raise ImageScanError("PDF page rendering requires the optional pypdfium2 dependency") from exc

    candidates: list[ImageCandidate] = []
    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:
        raise ImageScanError(f"PDF page rendering failed: {exc}") from exc
    page_count = min(len(pdf), max_pages)
    try:
        for page_index in range(page_count):
            page = pdf[page_index]
            try:
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                with BytesIO() as buffer:
                    image.save(buffer, format="PNG")
                    image_data = buffer.getvalue()
            finally:
                close = getattr(page, "close", None)
                if callable(close):
                    close()
            candidates.append(
                ImageCandidate(
                    data=image_data,
                    mime_type="image/png",
                    locator=ImageLocator(
                        container_path=f"page-{page_index + 1}.png",
                        image_index=page_index,
                        page_number=page_index + 1,
                        source_type="pdf_page_render",
                    ),
                )
            )
    finally:
        close = getattr(pdf, "close", None)
        if callable(close):
            close()
    return candidates


def standalone_image_candidate(data: bytes, *, filename: str, mime_type: str) -> ImageCandidate:
    return ImageCandidate(
        data=data,
        mime_type=image_mime_from_name(filename, data) if not mime_type else mime_type,
        locator=ImageLocator(
            container_path=filename or "document-image",
            image_index=0,
            source_type="standalone_image",
        ),
    )


class _CloudImageScanner:
    provider: str

    def __init__(self, *, privacy_guard: PrivacyGuard, tenant_opt_in: bool, tenant_id: str | None = None):
        self.privacy_guard = privacy_guard
        self.tenant_opt_in = tenant_opt_in
        self.tenant_id = tenant_id

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
            import pytesseract
            from PIL import Image
        except Exception as exc:
            raise ImageScanError("Tesseract OCR requires Pillow and pytesseract") from exc

        try:
            with Image.open(BytesIO(candidate.data)) as image:
                text, regions, confidence = _tesseract_text_regions(pytesseract, image)
        except Exception as exc:
            raise ImageScanError(f"Tesseract OCR failed for {candidate.locator.container_path}: {exc}") from exc
        return ImageOcrResult(
            text=clean_ocr_text(text),
            locator=candidate.locator,
            provider=self.provider,
            confidence=confidence,
            regions=regions,
        )


def _mean_confidence(values: list[float]) -> float | None:
    valid = [value for value in values if 0.0 <= value <= 1.0]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _normalize_confidence(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    if value > 1.0:
        value = value / 100.0
    return max(0.0, min(1.0, value))


def _bbox_from_pixels(
    left: Any,
    top: Any,
    width: Any,
    height: Any,
    image_width: int,
    image_height: int,
) -> ImageBoundingBox:
    iw = max(1, int(image_width))
    ih = max(1, int(image_height))
    return ImageBoundingBox(
        x=max(0.0, min(1.0, float(left or 0) / iw)),
        y=max(0.0, min(1.0, float(top or 0) / ih)),
        width=max(0.0, min(1.0, float(width or 0) / iw)),
        height=max(0.0, min(1.0, float(height or 0) / ih)),
    )


def _bbox_from_vertices(vertices: Any) -> ImageBoundingBox | None:
    points: list[tuple[float, float]] = []
    for vertex in vertices or []:
        x = getattr(vertex, "x", None)
        y = getattr(vertex, "y", None)
        if x is None and isinstance(vertex, dict):
            x = vertex.get("x")
            y = vertex.get("y")
        if x is None or y is None:
            continue
        points.append((float(x), float(y)))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = max(0.0, min(xs))
    min_y = max(0.0, min(ys))
    max_x = min(1.0, max(xs))
    max_y = min(1.0, max(ys))
    return ImageBoundingBox(
        x=min_x,
        y=min_y,
        width=max(0.0, max_x - min_x),
        height=max(0.0, max_y - min_y),
    )


def _bbox_from_polygon(raw_polygon: Any) -> ImageBoundingBox | None:
    if raw_polygon is None:
        return None
    values = list(raw_polygon)
    if len(values) < 4:
        return None
    xs = [float(values[index]) for index in range(0, len(values), 2)]
    ys = [float(values[index]) for index in range(1, len(values), 2)]
    min_x = max(0.0, min(xs))
    min_y = max(0.0, min(ys))
    max_x = min(1.0, max(xs))
    max_y = min(1.0, max(ys))
    return ImageBoundingBox(
        x=min_x,
        y=min_y,
        width=max(0.0, max_x - min_x),
        height=max(0.0, max_y - min_y),
    )


def _list_item(values: Any, index: int, default: Any = None) -> Any:
    try:
        return values[index]
    except Exception:
        return default


def _append_region_text(parts: list[str], text: str, *, separator: str = " ") -> int:
    if not text:
        return sum(len(part) for part in parts)
    if parts:
        parts.append(separator)
    start = sum(len(part) for part in parts)
    parts.append(text)
    return start


def _tesseract_text_regions(pytesseract: Any, image: Any) -> tuple[str, list[ImageTextRegion], float | None]:
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception:
        return pytesseract.image_to_string(image), [], None

    width, height = image.size
    parts: list[str] = []
    regions: list[ImageTextRegion] = []
    confidences: list[float] = []
    texts = list(data.get("text", []) or [])
    for index, raw_text in enumerate(texts):
        word = clean_ocr_text(str(raw_text or ""))
        if not word:
            continue
        start = _append_region_text(parts, word)
        end = start + len(word)
        confidence = _normalize_confidence(_list_item(data.get("conf", []), index))
        if confidence is not None:
            confidences.append(confidence)
        regions.append(
            ImageTextRegion(
                text=word,
                start_char=start,
                end_char=end,
                bounding_box=_bbox_from_pixels(
                    _list_item(data.get("left", []), index, 0),
                    _list_item(data.get("top", []), index, 0),
                    _list_item(data.get("width", []), index, 0),
                    _list_item(data.get("height", []), index, 0),
                    width,
                    height,
                ),
                confidence=confidence,
            )
        )
    text = "".join(parts)
    if not text:
        text = pytesseract.image_to_string(image)
    return text, regions, _mean_confidence(confidences)


class OpenAIVisionImageScanner(_CloudImageScanner):
    provider = "openai_vision"

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard, tenant_id: str | None = None):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=_image_scan_tenant_opt_in(settings, "openai_vision", tenant_id),
            tenant_id=tenant_id,
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

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard, tenant_id: str | None = None):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=_image_scan_tenant_opt_in(settings, "google_vision", tenant_id),
            tenant_id=tenant_id,
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
        regions = _google_text_regions(response)
        if not full_text:
            annotations = getattr(response, "text_annotations", []) or []
            if annotations:
                full_text = str(getattr(annotations[0], "description", "") or "")
        return ImageOcrResult(
            text=clean_ocr_text(full_text),
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=ledger,
            regions=regions,
            confidence=_mean_confidence([region.confidence for region in regions if region.confidence is not None]),
        )


def _google_text_regions(response: Any) -> list[ImageTextRegion]:
    annotations = list(getattr(response, "text_annotations", []) or [])
    if len(annotations) <= 1:
        return []
    regions: list[ImageTextRegion] = []
    parts: list[str] = []
    for annotation in annotations[1:]:
        word = clean_ocr_text(str(getattr(annotation, "description", "") or ""))
        if not word:
            continue
        start = _append_region_text(parts, word)
        vertices = getattr(getattr(annotation, "bounding_poly", None), "normalized_vertices", None)
        if not vertices:
            vertices = getattr(getattr(annotation, "bounding_poly", None), "vertices", None)
            # Non-normalized Google vertices are not portable without dimensions.
            vertices = None
        regions.append(
            ImageTextRegion(
                text=word,
                start_char=start,
                end_char=start + len(word),
                bounding_box=_bbox_from_vertices(vertices),
                confidence=None,
            )
        )
    return regions


class AWSRekognitionImageScanner(_CloudImageScanner):
    provider = "aws_rekognition"

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard, tenant_id: str | None = None):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=_image_scan_tenant_opt_in(settings, "aws_rekognition", tenant_id),
            tenant_id=tenant_id,
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
        words = [item for item in detections if item.get("Type") == "WORD"]
        lines = [item for item in detections if item.get("Type") == "LINE"]
        items = words or lines
        items.sort(key=_rekognition_sort_key)
        text, regions, confidence = _rekognition_regions(
            items,
            separator=" " if words else "\n",
        )
        return ImageOcrResult(
            text=clean_ocr_text(text),
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=ledger,
            confidence=confidence,
            regions=regions,
        )


def _rekognition_sort_key(item: dict[str, Any]) -> tuple[float, float, int]:
    box = ((item.get("Geometry") or {}).get("BoundingBox") or {})
    return (float(box.get("Top", 0.0) or 0.0), float(box.get("Left", 0.0) or 0.0), int(item.get("Id", 0) or 0))


def _rekognition_regions(
    items: list[dict[str, Any]],
    *,
    separator: str = "\n",
) -> tuple[str, list[ImageTextRegion], float | None]:
    parts: list[str] = []
    regions: list[ImageTextRegion] = []
    confidences: list[float] = []
    for item in items:
        line = clean_ocr_text(str(item.get("DetectedText", "") or ""))
        if not line:
            continue
        start = _append_region_text(parts, line, separator=separator)
        box = ((item.get("Geometry") or {}).get("BoundingBox") or {})
        confidence = _normalize_confidence(item.get("Confidence"))
        if confidence is not None:
            confidences.append(confidence)
        regions.append(
            ImageTextRegion(
                text=line,
                start_char=start,
                end_char=start + len(line),
                bounding_box=ImageBoundingBox(
                    x=float(box.get("Left", 0.0) or 0.0),
                    y=float(box.get("Top", 0.0) or 0.0),
                    width=float(box.get("Width", 0.0) or 0.0),
                    height=float(box.get("Height", 0.0) or 0.0),
                ),
                confidence=confidence,
            )
        )
    return "".join(parts), regions, _mean_confidence(confidences)


class AzureVisionImageScanner(_CloudImageScanner):
    provider = "azure_vision"

    def __init__(self, settings: Any, *, privacy_guard: PrivacyGuard, tenant_id: str | None = None):
        super().__init__(
            privacy_guard=privacy_guard,
            tenant_opt_in=_image_scan_tenant_opt_in(settings, "azure_vision", tenant_id),
            tenant_id=tenant_id,
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
        regions: list[ImageTextRegion] = []
        parts: list[str] = []
        read = getattr(result, "read", None)
        for block in getattr(read, "blocks", []) or []:
            for line in getattr(block, "lines", []) or []:
                text = str(getattr(line, "text", "") or "")
                if text:
                    lines.append(text)
                    cleaned_text = clean_ocr_text(text)
                    words = list(getattr(line, "words", []) or [])
                    if words:
                        for word in words:
                            word_text = clean_ocr_text(str(getattr(word, "text", "") or ""))
                            if not word_text:
                                continue
                            start = _append_region_text(parts, word_text, separator=" ")
                            regions.append(
                                ImageTextRegion(
                                    text=word_text,
                                    start_char=start,
                                    end_char=start + len(word_text),
                                    bounding_box=_bbox_from_polygon(getattr(word, "bounding_polygon", None)),
                                    confidence=_normalize_confidence(getattr(word, "confidence", None)),
                                )
                            )
                    else:
                        start = _append_region_text(parts, cleaned_text, separator="\n")
                        regions.append(
                            ImageTextRegion(
                                text=cleaned_text,
                                start_char=start,
                                end_char=start + len(cleaned_text),
                                bounding_box=_bbox_from_polygon(getattr(line, "bounding_polygon", None)),
                                confidence=None,
                            )
                        )
        return ImageOcrResult(
            text=clean_ocr_text("".join(parts) if parts else "\n".join(lines)),
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=ledger,
            regions=regions,
        )


def _image_scan_tenant_opt_in(settings: Any, provider: str, tenant_id: str | None) -> bool:
    flag_by_provider = {
        "openai_vision": "tenant_opt_in_openai",
        "google_vision": "tenant_opt_in_google",
        "aws_rekognition": "tenant_opt_in_aws",
        "azure_vision": "tenant_opt_in_azure",
    }
    global_flag = bool(getattr(settings, flag_by_provider.get(provider, ""), False))
    tenant_map = getattr(settings, "tenant_opt_ins", {}) or {}
    if tenant_id:
        allowed = set(tenant_map.get(tenant_id, ()) or ())
        if provider in allowed or "*" in allowed:
            return True
    return global_flag


def build_image_scanner(
    settings: Any,
    privacy_guard: PrivacyGuard,
    tenant_id: str | None = None,
) -> ImageScanner | None:
    provider = str(getattr(settings, "provider", "none") or "none").lower()
    if provider == "none":
        return None
    if provider == "tesseract":
        return TesseractImageScanner()
    if provider == "openai_vision":
        return OpenAIVisionImageScanner(settings, privacy_guard=privacy_guard, tenant_id=tenant_id)
    if provider == "google_vision":
        return GoogleVisionImageScanner(settings, privacy_guard=privacy_guard, tenant_id=tenant_id)
    if provider == "aws_rekognition":
        return AWSRekognitionImageScanner(settings, privacy_guard=privacy_guard, tenant_id=tenant_id)
    if provider == "azure_vision":
        return AzureVisionImageScanner(settings, privacy_guard=privacy_guard, tenant_id=tenant_id)
    raise ImageScanError(f"unsupported image OCR provider: {provider}")


def scan_image_candidates(
    candidates: list[ImageCandidate],
    *,
    scanner: ImageScanner,
    settings: Any,
) -> tuple[list[ImageOcrResult], list[dict[str, Any]]]:
    max_images = int(getattr(settings, "max_images", 32) or 32)
    max_bytes = int(getattr(settings, "max_bytes", 10 * 1024 * 1024) or (10 * 1024 * 1024))
    max_total_bytes = int(getattr(settings, "max_total_bytes", max_bytes * max_images) or (max_bytes * max_images))
    if len(candidates) > max_images:
        raise ImageScanError(f"image OCR refused {len(candidates)} images; maximum is {max_images}")
    total_bytes = sum(len(candidate.data) for candidate in candidates)
    if total_bytes > max_total_bytes:
        raise ImageScanError(f"image OCR refused {total_bytes} total image bytes; maximum is {max_total_bytes}")

    results: list[ImageOcrResult] = []
    privacy_ledger: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.mime_type not in SUPPORTED_IMAGE_MIMES:
            raise ImageScanError(
                f"image OCR does not support {candidate.mime_type} at {candidate.locator.container_path}"
            )
        if len(candidate.data) > max_bytes:
            raise ImageScanError(
                f"image OCR refused {candidate.locator.container_path}; "
                f"{len(candidate.data)} bytes exceeds maximum {max_bytes}"
            )
        raw_result = scanner.scan(candidate)
        result = _coerce_scan_result(
            raw_result,
            candidate=candidate,
            provider=getattr(scanner, "provider", "image_ocr"),
        )
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
            confidence=_normalize_confidence(raw_result.get("confidence")),
        )
    raise ImageScanError(f"image scanner returned unsupported result type: {type(raw_result).__name__}")


def _offset_regions(regions: list[ImageTextRegion], offset: int) -> list[ImageTextRegion]:
    return [
        ImageTextRegion(
            text=region.text,
            start_char=region.start_char + offset,
            end_char=region.end_char + offset,
            bounding_box=region.bounding_box,
            confidence=region.confidence,
        )
        for region in regions
    ]


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
                confidence=result.confidence,
                regions=_offset_regions(result.regions, start),
            )
        )
    return text, spans


def image_locator_for_span(spans: list[ImageTextSpan], start: int, end: int) -> dict[str, Any] | None:
    for span in spans:
        if span.start_char <= start and end <= span.end_char:
            return span.locator.to_dict()
    return None


def image_ocr_metadata_for_span(spans: list[ImageTextSpan], start: int, end: int) -> dict[str, Any] | None:
    for span in spans:
        if span.start_char <= start and end <= span.end_char:
            regions = image_regions_for_span(spans, start, end)
            return {
                "locator": span.locator.to_dict(),
                "provider": span.provider,
                "confidence": span.confidence,
                "regions": [region.to_dict() for region in regions],
            }
    return None


def image_regions_for_span(spans: list[ImageTextSpan], start: int, end: int) -> list[ImageTextRegion]:
    regions: list[ImageTextRegion] = []
    for span in spans:
        if end < span.start_char or start > span.end_char:
            continue
        for region in span.regions:
            if region.end_char <= start or region.start_char >= end:
                continue
            regions.append(_clip_region_to_span(region, start, end))
    return regions


def image_boxes_for_span(spans: list[ImageTextSpan], start: int, end: int) -> list[ImageBoundingBox]:
    return [
        region.bounding_box
        for region in image_regions_for_span(spans, start, end)
        if region.bounding_box is not None
    ]


def _clip_region_to_span(region: ImageTextRegion, start: int, end: int) -> ImageTextRegion:
    overlap_start = max(region.start_char, start)
    overlap_end = min(region.end_char, end)
    if overlap_start <= region.start_char and overlap_end >= region.end_char:
        return region
    local_start = max(0, overlap_start - region.start_char)
    local_end = max(local_start + 1, overlap_end - region.start_char)
    text = region.text[local_start:local_end] if region.text else region.text
    box = region.bounding_box
    if box is not None:
        box = box.clipped_to_text_range(
            text_length=len(region.text or ""),
            start=local_start,
            end=local_end,
        )
    return ImageTextRegion(
        text=text,
        start_char=overlap_start,
        end_char=overlap_end,
        bounding_box=box,
        confidence=region.confidence,
    )


def health_check_image_scan(settings: Any) -> dict[str, Any]:
    provider = str(getattr(settings, "provider", "none") or "none").lower()
    if provider == "none":
        return {
            "status": "disabled",
            "configured": False,
            "healthy": None,
            "detail": "image OCR is disabled",
        }
    if provider == "tesseract":
        try:
            import pytesseract
            from PIL import Image  # noqa: F401

            version = pytesseract.get_tesseract_version()
        except Exception as exc:
            return {
                "status": "down",
                "configured": True,
                "healthy": False,
                "detail": f"provider=tesseract unavailable: {exc}",
            }
        return {
            "status": "up",
            "configured": True,
            "healthy": True,
            "detail": f"provider=tesseract; version={version}",
        }
    if provider == "openai_vision":
        configured = bool(getattr(settings, "openai_api_key", ""))
        healthy = configured and _cloud_provider_has_any_opt_in(settings, provider)
        detail = "provider=openai_vision"
        if not configured:
            detail += "; OPENAI_API_KEY missing"
        if not _cloud_provider_has_any_opt_in(settings, provider):
            detail += "; tenant opt-in missing"
        return {
            "status": "configured" if healthy else "down",
            "configured": configured,
            "healthy": healthy,
            "detail": detail,
        }
    if provider == "google_vision":
        try:
            from google.cloud import vision  # noqa: F401
            import_ok = True
        except Exception as exc:
            import_ok = False
            import_error = str(exc)
        else:
            import_error = ""
        healthy = import_ok and _cloud_provider_has_any_opt_in(settings, provider)
        detail = "provider=google_vision"
        if not import_ok:
            detail += f"; google-cloud-vision unavailable: {import_error}"
        if not _cloud_provider_has_any_opt_in(settings, provider):
            detail += "; tenant opt-in missing"
        return {"status": "configured" if healthy else "down", "configured": True, "healthy": healthy, "detail": detail}
    if provider == "aws_rekognition":
        try:
            import boto3  # noqa: F401
            import_ok = True
        except Exception as exc:
            import_ok = False
            import_error = str(exc)
        else:
            import_error = ""
        healthy = import_ok and _cloud_provider_has_any_opt_in(settings, provider)
        detail = f"provider=aws_rekognition; region={getattr(settings, 'aws_region', '') or 'default'}"
        if not import_ok:
            detail += f"; boto3 unavailable: {import_error}"
        if not _cloud_provider_has_any_opt_in(settings, provider):
            detail += "; tenant opt-in missing"
        return {"status": "configured" if healthy else "down", "configured": True, "healthy": healthy, "detail": detail}
    if provider == "azure_vision":
        configured = bool(getattr(settings, "azure_endpoint", "")) and bool(getattr(settings, "azure_key", ""))
        try:
            from azure.ai.vision.imageanalysis import ImageAnalysisClient  # noqa: F401
            import_ok = True
        except Exception as exc:
            import_ok = False
            import_error = str(exc)
        else:
            import_error = ""
        healthy = configured and import_ok and _cloud_provider_has_any_opt_in(settings, provider)
        detail = "provider=azure_vision"
        if not configured:
            detail += "; AZURE_VISION_ENDPOINT or AZURE_VISION_KEY missing"
        if not import_ok:
            detail += f"; azure-ai-vision-imageanalysis unavailable: {import_error}"
        if not _cloud_provider_has_any_opt_in(settings, provider):
            detail += "; tenant opt-in missing"
        return {
            "status": "configured" if healthy else "down",
            "configured": configured,
            "healthy": healthy,
            "detail": detail,
        }
    return {
        "status": "down",
        "configured": True,
        "healthy": False,
        "detail": f"unsupported image OCR provider: {provider}",
    }


def _cloud_provider_has_any_opt_in(settings: Any, provider: str) -> bool:
    if _image_scan_tenant_opt_in(settings, provider, None):
        return True
    tenant_map = getattr(settings, "tenant_opt_ins", {}) or {}
    return any(provider in set(value or ()) or "*" in set(value or ()) for value in tenant_map.values())


def redacted_image_artifacts(
    candidates: list[ImageCandidate],
    spans: list[ImageTextSpan],
    replacement_spans: list[tuple[int, int]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    boxes_by_key, missing_boxes = _boxes_by_source_key(spans, replacement_spans)
    artifacts: list[dict[str, Any]] = []
    degraded_modes: list[dict[str, Any]] = []
    candidate_by_key = {
        (candidate.locator.container_path, candidate.locator.image_index, candidate.locator.page_number): candidate
        for candidate in candidates
    }
    for key, boxes in boxes_by_key.items():
        candidate = candidate_by_key.get(key)
        if candidate is None:
            continue
        try:
            artifacts.append(_redact_candidate(candidate, boxes))
        except Exception as exc:
            degraded_modes.append(
                {
                    "mode": "image_redaction",
                    "status": "unavailable",
                    "reason": f"redaction failed for {candidate.locator.container_path}: {exc}",
                }
            )
    for key in sorted(missing_boxes - set(boxes_by_key)):
        degraded_modes.append(
            {
                "mode": "image_redaction",
                "status": "unavailable",
                "reason": f"OCR provider returned no bounding boxes for {key[0]}#{key[1]}",
            }
        )
    return artifacts, degraded_modes


def redacted_document_artifact(
    *,
    original_data: bytes | None,
    filename: str,
    mime_type: str,
    candidates: list[ImageCandidate],
    spans: list[ImageTextSpan],
    replacement_spans: list[tuple[int, int]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not original_data:
        return None, []
    boxes_by_key, missing_boxes = _boxes_by_source_key(spans, replacement_spans)
    degraded_modes = _missing_box_degraded_modes(missing_boxes, boxes_by_key)
    if not boxes_by_key:
        return None, degraded_modes
    normalized = mime_type.lower()
    candidate_by_key = {
        (candidate.locator.container_path, candidate.locator.image_index, candidate.locator.page_number): candidate
        for candidate in candidates
    }
    try:
        if normalized == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            payload = _redact_docx_document(original_data, candidate_by_key, boxes_by_key)
            count = sum(len(boxes) for boxes in boxes_by_key.values())
            return {
                "filename": _redacted_filename(filename, ".docx"),
                "mime_type": normalized,
                "document_base64": base64.b64encode(payload).decode("ascii"),
                "method": "docx_media_rewrite",
                "redaction_count": count,
                "warnings": [],
            }, degraded_modes
        if normalized == "application/pdf":
            payload = _redact_pdf_document(original_data, candidate_by_key, boxes_by_key)
            count = sum(len(boxes) for boxes in boxes_by_key.values())
            return {
                "filename": _redacted_filename(filename, ".pdf"),
                "mime_type": "application/pdf",
                "document_base64": base64.b64encode(payload).decode("ascii"),
                "method": "pdf_flattened_page_pixels",
                "redaction_count": count,
                "warnings": ["PDF was flattened; signatures, forms, layers, and editable text are not preserved."],
            }, degraded_modes
        if normalized in {"image/png", "image/jpeg"} and len(candidates) == 1:
            boxes = next(iter(boxes_by_key.values()))
            payload, output_mime = _redact_image_bytes(candidates[0].data, boxes, output_mime=normalized)
            return {
                "filename": _redacted_filename(filename, ".png" if output_mime == "image/png" else ".jpg"),
                "mime_type": output_mime,
                "document_base64": base64.b64encode(payload).decode("ascii"),
                "method": "standalone_image_pixels",
                "redaction_count": len(boxes),
                "warnings": [],
            }, degraded_modes
    except Exception as exc:
        degraded_modes.append(
            {
                "mode": "document_redaction",
                "status": "unavailable",
                "reason": f"redacted document output failed for {filename}: {exc}",
            }
        )
    return None, degraded_modes


def _boxes_by_source_key(
    spans: list[ImageTextSpan],
    replacement_spans: list[tuple[int, int]],
) -> tuple[dict[tuple[str, int, int | None], list[ImageBoundingBox]], set[tuple[str, int, int | None]]]:
    boxes_by_key: dict[tuple[str, int, int | None], list[ImageBoundingBox]] = {}
    missing_boxes: set[tuple[str, int, int | None]] = set()
    for start, end in replacement_spans:
        matched_span = next((span for span in spans if span.start_char <= start and end <= span.end_char), None)
        if matched_span is None:
            continue
        key = (
            matched_span.locator.container_path,
            matched_span.locator.image_index,
            matched_span.locator.page_number,
        )
        boxes = image_boxes_for_span(spans, start, end)
        if boxes:
            boxes_by_key.setdefault(key, []).extend(boxes)
        else:
            missing_boxes.add(key)
    return boxes_by_key, missing_boxes


def _missing_box_degraded_modes(
    missing_boxes: set[tuple[str, int, int | None]],
    boxes_by_key: dict[tuple[str, int, int | None], list[ImageBoundingBox]],
) -> list[dict[str, Any]]:
    degraded_modes: list[dict[str, Any]] = []
    for key in sorted(missing_boxes - set(boxes_by_key)):
        degraded_modes.append(
            {
                "mode": "image_redaction",
                "status": "unavailable",
                "reason": f"OCR provider returned no bounding boxes for {key[0]}#{key[1]}",
            }
        )
    return degraded_modes


def _redact_candidate(candidate: ImageCandidate, boxes: list[ImageBoundingBox]) -> dict[str, Any]:
    payload, _ = _redact_image_bytes(candidate.data, boxes, output_mime="image/png")
    encoded = base64.b64encode(payload).decode("ascii")
    return {
        "container_path": candidate.locator.container_path,
        "image_index": candidate.locator.image_index,
        "page_number": candidate.locator.page_number,
        "source_type": candidate.locator.source_type,
        "mime_type": "image/png",
        "document_base64": encoded,
        "redaction_count": len(boxes),
    }


def _redact_image_bytes(
    data: bytes,
    boxes: list[ImageBoundingBox],
    *,
    output_mime: str = "image/png",
) -> tuple[bytes, str]:
    from PIL import Image

    with Image.open(BytesIO(data)) as image:
        redacted = image.convert("RGB")
        _draw_boxes(redacted, boxes)
        with BytesIO() as buffer:
            if output_mime == "image/jpeg":
                redacted.save(buffer, format="JPEG", quality=95)
                return buffer.getvalue(), "image/jpeg"
            redacted.save(buffer, format="PNG")
            return buffer.getvalue(), "image/png"


def _draw_boxes(image: Any, boxes: list[ImageBoundingBox]) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    width, height = image.size
    for box in boxes:
        left = int(max(0.0, min(1.0, box.x)) * width)
        top = int(max(0.0, min(1.0, box.y)) * height)
        right = int(max(0.0, min(1.0, box.x + box.width)) * width)
        bottom = int(max(0.0, min(1.0, box.y + box.height)) * height)
        draw.rectangle((left, top, max(left + 1, right), max(top + 1, bottom)), fill=(0, 0, 0))


def _redact_docx_document(
    original_data: bytes,
    candidate_by_key: dict[tuple[str, int, int | None], ImageCandidate],
    boxes_by_key: dict[tuple[str, int, int | None], list[ImageBoundingBox]],
) -> bytes:
    replacements: dict[str, bytes] = {}
    for key, boxes in boxes_by_key.items():
        candidate = candidate_by_key.get(key)
        if candidate is None:
            continue
        path = candidate.locator.container_path
        output_mime = (
            "image/jpeg"
            if candidate.mime_type == "image/jpeg" or path.lower().endswith((".jpg", ".jpeg"))
            else "image/png"
        )
        payload, _ = _redact_image_bytes(candidate.data, boxes, output_mime=output_mime)
        replacements[path] = payload
    if not replacements:
        raise ImageScanError("no DOCX media entries could be mapped for redaction")
    with BytesIO() as buffer:
        with (
            zipfile.ZipFile(BytesIO(original_data), "r") as source,
            zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target,
        ):
            for item in source.infolist():
                content = source.read(item.filename)
                target.writestr(item, replacements.get(item.filename, content))
        return buffer.getvalue()


def _redact_pdf_document(
    original_data: bytes,
    candidate_by_key: dict[tuple[str, int, int | None], ImageCandidate],
    boxes_by_key: dict[tuple[str, int, int | None], list[ImageBoundingBox]],
) -> bytes:
    page_boxes: dict[int, list[ImageBoundingBox]] = {}
    for key, boxes in boxes_by_key.items():
        candidate = candidate_by_key.get(key)
        if candidate is None:
            continue
        if candidate.locator.source_type != "pdf_page_render" or candidate.locator.page_number is None:
            raise ImageScanError("PDF embedded-image redaction requires rendered page coordinates")
        page_boxes.setdefault(candidate.locator.page_number, []).extend(boxes)
    if not page_boxes:
        raise ImageScanError("no PDF page-render boxes available for document redaction")
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        raise ImageScanError("PDF flattened redaction requires pypdfium2") from exc
    pdf = pdfium.PdfDocument(original_data)
    images: list[Any] = []
    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            try:
                bitmap = page.render(scale=2.0)
                image = bitmap.to_pil().convert("RGB")
            finally:
                close = getattr(page, "close", None)
                if callable(close):
                    close()
            boxes = page_boxes.get(page_index + 1, [])
            if boxes:
                _draw_boxes(image, boxes)
            images.append(image)
    finally:
        close = getattr(pdf, "close", None)
        if callable(close):
            close()
    if not images:
        raise ImageScanError("PDF rendered no pages for document redaction")
    with BytesIO() as buffer:
        images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:])
        return buffer.getvalue()


def _redacted_filename(filename: str, suffix: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return f"{stem}.redacted{suffix}"
