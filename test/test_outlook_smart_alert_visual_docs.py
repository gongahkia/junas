import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / "test" / "fixtures" / "outlook_smart_alert_messages.json"
OUTLOOK_ASSET_DIR = ROOT / "docs" / "assets" / "outlook"
STATE_IMAGES = {
    "allow": "outlook-smart-alert-allow.png",
    "warn": "outlook-smart-alert-warn.png",
    "block": "outlook-smart-alert-block.png",
    "approval_required": "outlook-smart-alert-approval_required.png",
}


def test_outlook_smart_alert_rendered_images_are_valid():
    for filename in STATE_IMAGES.values():
        image_path = OUTLOOK_ASSET_DIR / filename
        assert image_path.exists()
        assert image_path.stat().st_size < 1_000_000
        with Image.open(image_path) as image:
            assert image.format == "PNG"
            assert image.size == (1200, 760)


def test_outlook_smart_alert_docs_match_fixture_strings():
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    doc = (ROOT / "docs" / "integrations" / "outlook.md").read_text(encoding="utf-8")
    asset_doc = (OUTLOOK_ASSET_DIR / "README.md").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "render_outlook_smart_alert_screenshots.py").read_text(encoding="utf-8")

    assert "rendered fixtures, not live Outlook screenshots" in doc
    assert "Validate real Smart Alert UI on each assigned Outlook client family" in doc
    assert "test/fixtures/outlook_smart_alert_messages.json" in asset_doc
    assert "Validate real Smart Alert UI on each Outlook client family" in asset_doc
    assert "outlook_smart_alert_messages.json" in script
    for state, filename in STATE_IMAGES.items():
        fixture = fixtures[state]
        assert f"`{state}`" in doc
        assert f"`{fixture['mode']}`" in doc
        assert f"../assets/outlook/{filename}" in doc
        message = fixture.get("errorMessage") or "No Smart Alert dialog is shown for `allowEvent=true`."
        assert message in doc


def test_outlook_smart_alert_renderings_are_linked_from_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for filename in STATE_IMAGES.values():
        assert f"./docs/assets/outlook/{filename}" in readme
    assert "./test/fixtures/outlook_smart_alert_messages.json" in readme
    assert "./docs/integrations/outlook.md" in readme
