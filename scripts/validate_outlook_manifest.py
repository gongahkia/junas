#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

PROFILES = ("dev", "staging", "production")
REQUIRED_URLS = {
    "Taskpane.Url": "taskpane.html",
    "WebViewRuntime.Url": "commands.html",
    "JSRuntime.Url": "launchevent.js",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


def _is_local_host(hostname: str | None) -> bool:
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _urls_by_id(root: ET.Element) -> dict[str, str]:
    urls: dict[str, str] = {}
    for element in root.iter():
        if _local_name(element.tag) == "Url" and element.attrib.get("id"):
            urls[element.attrib["id"]] = element.attrib.get("DefaultValue", "")
    return urls


def _has_mailbox_requirement(root: ET.Element, minimum: str) -> bool:
    required = _version_tuple(minimum)
    for element in root.iter():
        if _local_name(element.tag) != "Sets":
            continue
        version = element.attrib.get("DefaultMinVersion")
        if version and _version_tuple(version) >= required:
            for child in element:
                if _local_name(child.tag) == "Set" and child.attrib.get("Name") == "Mailbox":
                    return True
    return False


def _launch_events(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == "LaunchEvent"]


def validate_manifest(
    path: Path,
    *,
    profile: str = "dev",
    minimum_mailbox: str = "1.15",
    expected_send_mode: str = "SoftBlock",
) -> list[str]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [f"invalid XML: {exc}"]
    errors: list[str] = []
    if not _has_mailbox_requirement(root, minimum_mailbox):
        errors.append(f"missing Mailbox requirement set >= {minimum_mailbox}")
    matching_events = [
        event
        for event in _launch_events(root)
        if event.attrib.get("Type") == "OnMessageSend" and event.attrib.get("SendMode") == expected_send_mode
    ]
    if not matching_events:
        errors.append(f"missing OnMessageSend LaunchEvent with SendMode={expected_send_mode}")
    elif not matching_events[0].attrib.get("FunctionName"):
        errors.append("OnMessageSend LaunchEvent missing FunctionName")
    urls = _urls_by_id(root)
    for url_id, suffix in REQUIRED_URLS.items():
        value = urls.get(url_id, "")
        if not value:
            errors.append(f"missing runtime URL {url_id}")
            continue
        if "{{" in value or "}}" in value:
            errors.append(f"unrendered placeholder in {url_id}")
            continue
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{url_id} must be an https URL")
            continue
        if not parsed.path.endswith(suffix):
            errors.append(f"{url_id} must end with {suffix}")
        if profile == "production" and _is_local_host(parsed.hostname):
            errors.append(f"{url_id} production host cannot be localhost")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a rendered Outlook add-in manifest")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", choices=PROFILES, default="dev")
    parser.add_argument("--minimum-mailbox", default="1.15")
    parser.add_argument("--expected-send-mode", default="SoftBlock")
    args = parser.parse_args(argv)
    errors = validate_manifest(
        args.manifest,
        profile=args.profile,
        minimum_mailbox=args.minimum_mailbox,
        expected_send_mode=args.expected_send_mode,
    )
    if errors:
        for error in errors:
            print(f"validate_outlook_manifest: {error}", file=sys.stderr)
        return 64
    print(f"validated {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
