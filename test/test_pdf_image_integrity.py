"""Bounded PDF/OCR coverage tests; fake providers are separate from native checks."""

import base64
import importlib.util
import io
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from junas import DocumentInput, ReviewPipeline
from junas.configs.runtime import ConfigError, get_runtime_settings
from junas.review import image_scan
from junas.review.image_scan import ImageCandidate, ImageLocator, ImageOcrResult, ImageScanError
from test.test_email_attachment_integrity import _attach, _email
from test.test_image_scan import FakeImageScanner, _docx_with_embedded_png, _png_bytes

HAS_PDFIUM = importlib.util.find_spec("pypdfium2") is not None
NATIVE_RENDER = pytest.mark.skipif(not HAS_PDFIUM, reason="optional pypdfium2 required")


def _pdf(pages):
    writer = PdfWriter()
    for text, picture in pages:
        page = writer.add_blank_page(width=144, height=144)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 10 90 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
        if picture:
            img = DecodedStreamObject()
            img.set_data(bytes([0, 0, 0]))
            img.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(1),
                    NameObject("/Height"): NumberObject(1),
                    NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                }
            )
            page["/Resources"][NameObject("/XObject")] = DictionaryObject({NameObject("/I"): writer._add_object(img)})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _payload(data, name):
    return DocumentInput(document_base64=base64.b64encode(data).decode(), document_filename=name)


def _settings(*, strict=True, **kw):
    return get_runtime_settings({"image_scan.provider": "tesseract", "document_ingest.fail_closed": strict, **kw})


@pytest.mark.parametrize("strict", [True, False])
def test_empty_ocr_is_not_completed_even_with_existing_text(strict):
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner(text="")):
        if strict:
            with pytest.raises(ImageScanError, match="text|empty"):
                ReviewPipeline(_settings()).review(_payload(_docx_with_embedded_png(), "a.docx"))
        else:
            result = ReviewPipeline(_settings(strict=False)).review(_payload(_docx_with_embedded_png(), "a.docx"))
            assert result.to_dict()["status"] == "degraded"
            assert result.document.extraction_quality == "degraded"


def test_best_effort_sparse_pdf_with_ocr_disabled_is_degraded():
    result = ReviewPipeline(get_runtime_settings({"document_ingest.fail_closed": False})).review(
        _payload(_pdf([("A sufficiently long ordinary text layer", False), ("", False)]), "mixed.pdf")
    )
    assert result.to_dict()["status"] == "degraded"
    assert any("page" in w for w in result.document.extraction_warnings)


@NATIVE_RENDER
def test_embedded_image_does_not_hide_sparse_page_rendering():
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner()) as scanner:
        result = ReviewPipeline(_settings()).review(
            _payload(_pdf([("A sufficiently long ordinary text layer", True), ("", False)]), "mixed.pdf")
        )
    assert scanner.called
    assert any(
        c.locator.page_number == 2 and c.locator.source_type == "pdf_page_render"
        for c in result.document.image_candidates
    )
    assert result.to_dict()["status"] == "completed"


@pytest.mark.parametrize("scale", [4.01, 1e9])
def test_render_scale_has_upper_bound(scale):
    with pytest.raises(ConfigError):
        _settings(**{"image_scan.pdf_render_scale": scale})


def test_decoded_pixel_limit_precedes_scanner(monkeypatch):
    monkeypatch.setattr(image_scan, "MAX_IMAGE_PIXELS", 100, raising=False)
    scanner = Mock(provider="fake")
    scanner.scan.return_value = "text"
    candidate = ImageCandidate(_png_bytes(), "image/png", ImageLocator("large.png", 0))
    with pytest.raises(ImageScanError, match="pixel"):
        image_scan.scan_image_candidates([candidate], scanner=scanner, settings=SimpleNamespace())
    scanner.scan.assert_not_called()


@NATIVE_RENDER
def test_render_pixel_estimate_precedes_rasterization(monkeypatch):
    monkeypatch.setattr(image_scan, "MAX_IMAGE_PIXELS", 100, raising=False)
    with pytest.raises(ImageScanError, match="pixel"):
        image_scan.collect_pdf_page_renders(_pdf([("", False)]), scale=2)


def test_appending_ocr_preserves_existing_analyzed_text_exactly():
    base = "  Body\twith   spaces\n\n\nS1234567D"
    candidate = ImageOcrResult("S1234567D", ImageLocator("p.png", 0), "fake")
    text, spans = image_scan.append_ocr_text_blocks(base, [candidate])
    assert text.startswith(base + "\n\n")
    assert text[spans[0].start_char : spans[0].end_char] == "S1234567D"


def test_pdf_attachment_ocr_is_not_claimed_complete():
    mail = _email("Body with enough reviewable text")
    _attach(mail, _pdf([("A sufficiently long ordinary text layer", True)]), "attached.pdf", "application/pdf")
    with patch("junas.pipeline.build_image_scanner") as scanner:
        result = ReviewPipeline(_settings()).review(_payload(mail.as_bytes(), "mail.eml"))
    scanner.assert_not_called()
    assert result.to_dict()["status"] == "degraded"
    assert any("text layer only" in w for w in result.document.extraction_warnings)


def test_text_only_pdf_has_no_ocr_work():
    with patch("junas.pipeline.build_image_scanner") as scanner:
        result = ReviewPipeline(_settings()).review(
            _payload(_pdf([("A sufficiently long ordinary text layer", False)]), "text.pdf")
        )
    scanner.assert_not_called()
    assert result.to_dict()["status"] == "completed"


def _docx_media(count=1, *, unsupported=False):
    import zipfile

    from test.test_email_attachment_integrity import _docx

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_docx("Original body S1234567D with enough ordinary text"))) as original:
        with zipfile.ZipFile(out, "w") as archive:
            for name in original.namelist():
                archive.writestr(name, original.read(name))
            for index in range(count):
                archive.writestr(f"word/media/image{index}.png", _png_bytes())
            if unsupported:
                archive.writestr("word/media/movie.mp4", b"not a supported reviewable image")
    return out.getvalue()


def _summary(result):
    import json

    return json.loads(next(m["detail"] for m in result.document.metadata_findings if m["id"] == "ocr-summary"))


def _assert_integrity(result):
    seen = set()
    for f in result.review.findings:
        assert 0 <= f.start_char < f.end_char <= len(result.document.text)
        assert result.document.text[f.start_char : f.end_char] == f.matched_text
        key = (f.rule, f.source, f.start_char, f.end_char)
        assert key not in seen
        seen.add(key)


@pytest.mark.parametrize("strict", [True, False])
def test_partial_empty_ocr_with_text_body(strict):
    scanner = Mock(provider="fake")
    scanner.scan.side_effect = ["S1234567D", ""]
    with patch("junas.pipeline.build_image_scanner", return_value=scanner):
        if strict:
            with pytest.raises(ImageScanError, match="empty"):
                ReviewPipeline(_settings()).review(_payload(_docx_media(2), "two.docx"))
        else:
            result = ReviewPipeline(_settings(strict=False)).review(_payload(_docx_media(2), "two.docx"))
            assert result.to_dict()["status"] == "degraded"
            assert result.document.extraction_quality == "degraded"
            assert _summary(result) == dict(
                discovered=2, submitted=2, processed=1, empty=1, failed=0, not_submitted=0, retained=1
            )
            _assert_integrity(result)


@pytest.mark.parametrize("error", [ImageScanError("provider unavailable"), TimeoutError("timeout")])
@pytest.mark.parametrize("strict", [True, False])
def test_provider_failure_is_refusal_or_degraded(error, strict):
    scanner = Mock(provider="fake")
    scanner.scan.side_effect = error
    with patch("junas.pipeline.build_image_scanner", return_value=scanner):
        if strict:
            with pytest.raises(ImageScanError):
                ReviewPipeline(_settings()).review(_payload(_docx_media(2), "two.docx"))
        else:
            result = ReviewPipeline(_settings(strict=False)).review(_payload(_docx_media(2), "two.docx"))
            assert result.to_dict()["status"] == "degraded"
            assert _summary(result) == dict(
                discovered=2, submitted=1, processed=0, empty=0, failed=1, not_submitted=1, retained=0
            )
            assert "Original body" in result.document.text
            _assert_integrity(result)


def test_repeated_identifiers_keep_separate_ocr_and_body_provenance():
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner()):
        result = ReviewPipeline(_settings()).review(_payload(_docx_media(2), "two.docx"))
    ids = [f for f in result.review.findings if f.rule == "sg_nric_fin"]
    assert len(ids) == 3
    assert len({f.start_char for f in ids}) == 3
    assert len({f.image_locator["container_path"] for f in ids if f.source == "image_ocr"}) == 2
    for f in ids:
        if f.source == "image_ocr":
            assert f.image_ocr_confidence == 0.98
            assert f.image_ocr_regions[0]["bounding_box"]
            assert f.metadata["original_document"] == "two.docx"
            assert f.metadata["image_ocr_provider"] == "fake_ocr"
    assert _summary(result)["processed"] == 2
    _assert_integrity(result)


@pytest.mark.parametrize("strict", [True, False])
def test_unsupported_office_media_is_visibly_unreviewed(strict):
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner()):
        result = ReviewPipeline(_settings(strict=strict)).review(_payload(_docx_media(unsupported=True), "media.docx"))
    assert result.to_dict()["status"] == "degraded"
    assert "movie.mp4" in " ".join(result.document.extraction_warnings)
    _assert_integrity(result)


@pytest.mark.parametrize("strict", [True, False])
@NATIVE_RENDER
def test_page_limit_cannot_hide_later_text_or_omitted_page(strict):
    pages = [("", False), ("Late text contains S1234567D and remains reviewable", False), ("", False)]
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner()):
        if strict:
            with pytest.raises(ImageScanError, match="page limit"):
                ReviewPipeline(_settings(**{"image_scan.pdf_render_max_pages": 1})).review(
                    _payload(_pdf(pages), "three.pdf")
                )
        else:
            result = ReviewPipeline(_settings(strict=False, **{"image_scan.pdf_render_max_pages": 1})).review(
                _payload(_pdf(pages), "three.pdf")
            )
            assert "Late text contains S1234567D" in result.document.text
            assert result.to_dict()["status"] == "degraded"
            assert any("page limit" in w for w in result.document.extraction_warnings)
            assert [c.locator.page_number for c in result.document.image_candidates] == [1]
            _assert_integrity(result)


@pytest.mark.parametrize("strict", [True, False])
def test_disabled_rendering_cannot_complete_sparse_pdf(strict):
    with patch("junas.pipeline.build_image_scanner") as scanner:
        if strict:
            with pytest.raises(ImageScanError, match="disabled"):
                ReviewPipeline(_settings(**{"image_scan.pdf_render_pages": False})).review(
                    _payload(_pdf([("", False)]), "scan.pdf")
                )
        else:
            result = ReviewPipeline(_settings(strict=False, **{"image_scan.pdf_render_pages": False})).review(
                _payload(_pdf([("", False)]), "scan.pdf")
            )
            assert result.to_dict()["status"] == "degraded"
        scanner.assert_not_called()


@pytest.mark.parametrize("strict", [True, False])
def test_sparse_pdf_attachment_does_not_claim_ocr(strict):
    mail = _email("Body with enough reviewable text")
    _attach(
        mail,
        _pdf([("Ordinary text layer with enough characters", False), ("", False)]),
        "attached.pdf",
        "application/pdf",
    )
    if strict:
        with pytest.raises(ValueError, match="attachment OCR"):
            ReviewPipeline(_settings()).review(_payload(mail.as_bytes(), "mail.eml"))
    else:
        result = ReviewPipeline(_settings(strict=False)).review(_payload(mail.as_bytes(), "mail.eml"))
        assert result.to_dict()["status"] == "degraded"
        assert "attachment OCR" in " ".join(result.document.extraction_warnings)


@pytest.mark.parametrize("pixels,accepted", [(2399, False), (2400, True), (2401, True)])
def test_header_pixel_boundary(monkeypatch, pixels, accepted):
    monkeypatch.setattr(image_scan, "MAX_IMAGE_PIXELS", pixels)
    if accepted:
        assert image_scan.image_pixel_count(_png_bytes()) == 2400
    else:
        with pytest.raises(ImageScanError, match="pixel"):
            image_scan.image_pixel_count(_png_bytes())


def test_image_header_admission_does_not_load_pixels(monkeypatch):
    data = _png_bytes()
    with patch.object(image_scan, "MAX_IMAGE_DIMENSION", 16):
        with patch("PIL.Image.Image.load", side_effect=AssertionError("must not decode")):
            with pytest.raises(ImageScanError, match="dimension"):
                image_scan.image_pixel_count(data)


def test_aggregate_pixels_checked_before_any_provider_call(monkeypatch):
    monkeypatch.setattr(image_scan, "MAX_TOTAL_IMAGE_PIXELS", 4799)
    scanner = Mock(provider="fake")
    c = ImageCandidate(_png_bytes(), "image/png", ImageLocator("x.png", 0))
    with pytest.raises(ImageScanError, match="aggregate"):
        image_scan.scan_image_candidates([c, c], scanner=scanner, settings=SimpleNamespace())
    scanner.scan.assert_not_called()


@pytest.mark.parametrize("width,height", [(0, 1), (-1, 1), (float("inf"), 1), (20000, 1), (6000, 6000)])
def test_invalid_or_excessive_dimensions(width, height):
    with pytest.raises(ImageScanError):
        image_scan._check_dimensions(width, height)


@pytest.mark.parametrize("scale", [float("nan"), float("inf"), -1, 0, 4.01])
def test_direct_renderer_rejects_scale_before_native_open(scale):
    with patch.dict("sys.modules", {"pypdfium2": SimpleNamespace(PdfDocument=Mock())}):
        import pypdfium2

        native = pypdfium2.PdfDocument
        with pytest.raises(ImageScanError):
            image_scan.collect_pdf_page_renders(b"no native parser needed", scale=scale)
        native.assert_not_called()


@NATIVE_RENDER
def test_oversized_pdf_page_checked_before_render():
    writer = PdfWriter()
    writer.add_blank_page(width=20000, height=144)
    stream = io.BytesIO()
    writer.write(stream)
    with patch("pypdfium2.PdfPage.render") as render:
        with pytest.raises(ImageScanError, match="dimension"):
            image_scan.collect_pdf_page_renders(stream.getvalue(), scale=1)
        render.assert_not_called()


@NATIVE_RENDER
def test_render_aggregate_pixel_budget_stops_next_raster(monkeypatch):
    monkeypatch.setattr(image_scan, "MAX_TOTAL_IMAGE_PIXELS", 20736)
    import pypdfium2

    original = pypdfium2.PdfPage.render
    calls = []

    def record(page, **kwargs):
        calls.append(page)
        return original(page, **kwargs)

    with patch("pypdfium2.PdfPage.render", record):
        with pytest.raises(ImageScanError, match="aggregate"):
            image_scan.collect_pdf_page_renders(_pdf([("", False), ("", False)]), scale=1)
    assert len(calls) == 1


def test_pdf_image_declarations_checked_before_conversion():
    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    img = DecodedStreamObject()
    img.set_data(b"x")
    img.update(
        {
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(20000),
            NameObject("/Height"): NumberObject(1),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/I"): writer._add_object(img)})}
    )
    out = io.BytesIO()
    writer.write(out)
    with patch("pypdf.generic._image_xobject._xobj_to_image") as decoder:
        with pytest.raises(ImageScanError, match="dimension"):
            image_scan.collect_pdf_images(out.getvalue())
        decoder.assert_not_called()


def test_multiframe_image_refuses_incomplete_first_frame_review():
    from PIL import Image

    out = io.BytesIO()
    a = Image.new("RGB", (2, 2), "red")
    b = Image.new("RGB", (2, 2), "blue")
    a.save(out, format="GIF", save_all=True, append_images=[b])
    with pytest.raises(ImageScanError, match="multi-frame"):
        image_scan.image_pixel_count(out.getvalue())


def test_invalid_ocr_region_is_refused_without_searching():
    from junas.review.image_scan import ImageTextRegion

    c = ImageCandidate(_png_bytes(), "image/png", ImageLocator("x.png", 0))
    scanner = Mock(provider="fake")
    scanner.scan.return_value = ImageOcrResult("same same", c.locator, "fake", regions=[ImageTextRegion("same", 2, 6)])
    with pytest.raises(ImageScanError, match="offset"):
        image_scan.scan_image_candidates([c], scanner=scanner, settings=SimpleNamespace())


def test_standalone_image_success_is_counted_with_exact_provenance():
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner()):
        result = ReviewPipeline(_settings()).review(_payload(_png_bytes(), "scan.png"))
    assert _summary(result) == dict(
        discovered=1, submitted=1, processed=1, empty=0, failed=0, not_submitted=0, retained=1
    )
    assert result.document.image_text_spans[0].locator.container_path == "scan.png"
    _assert_integrity(result)


@NATIVE_RENDER
def test_real_pdfium_raster_and_fake_provider_are_distinguished():
    # real PDFium rasterization, synthetic OCR: this is not OCR accuracy evidence.
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner()):
        result = ReviewPipeline(_settings()).review(_payload(_pdf([("", False), ("", False)]), "scan.pdf"))
    assert [s.locator.page_number for s in result.document.image_text_spans] == [1, 2]
    assert _summary(result)["processed"] == 2
    _assert_integrity(result)
