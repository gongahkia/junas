from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WARN_IMAGE = ROOT / "docs" / "assets" / "browser-extension" / "browser-extension-warn-confirm.png"
BLOCK_IMAGE = ROOT / "docs" / "assets" / "browser-extension" / "browser-extension-policy-block.png"


def test_browser_extension_screenshots_are_valid_and_scoped():
    for image_path in (WARN_IMAGE, BLOCK_IMAGE):
        assert image_path.exists()
        assert image_path.stat().st_size < 2_000_000
        with Image.open(image_path) as image:
            assert image.format == "PNG"
            width, height = image.size
            assert width >= 1200
            assert height >= 800

    asset_doc = (ROOT / "docs" / "assets" / "browser-extension" / "README.md").read_text(encoding="utf-8")
    for token in (
        "synthetic prompt text",
        "Playwright-routed `https://chatgpt.com/` fixture",
        "real unpacked MV3 extension",
        "deterministic local Junas backend",
        "not proof of universal browser capture",
        "third-party DOM stability",
    ):
        assert token in asset_doc


def test_browser_extension_visuals_are_linked_from_docs_and_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    integration_doc = (ROOT / "docs" / "integrations" / "genai-browser.md").read_text(encoding="utf-8")
    for path in (
        "./docs/assets/browser-extension/browser-extension-warn-confirm.png",
        "./docs/assets/browser-extension/browser-extension-policy-block.png",
    ):
        assert path in readme
    for path in (
        "../assets/browser-extension/browser-extension-warn-confirm.png",
        "../assets/browser-extension/browser-extension-policy-block.png",
    ):
        assert path in integration_doc
    for token in (
        "synthetic `chatgpt.com` fixture",
        "real MV3 extension",
        "illustrative",
        "coverage still depends on third-party DOM stability",
        "#junas-review-result",
    ):
        assert token in integration_doc
