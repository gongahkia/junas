#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "integrations" / "outlook_addin" / "manifest.xml"
OUT_DIR = ROOT / "dist" / "outlook-addin"
PLACEHOLDER = "{{JUNAS_OUTLOOK_ADDIN_ORIGIN}}"
PROFILES = ("dev", "staging", "production")


def normalized_origin(raw: str, *, profile: str) -> str:
    origin = raw.strip().rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Outlook add-in origin must be an https URL")
    if profile in {"staging", "production"} and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(f"{profile} Outlook add-in origin cannot be localhost")
    return origin


def origin_for_profile(profile: str, raw_origin: str | None) -> str:
    if raw_origin:
        return normalized_origin(raw_origin, profile=profile)
    if profile == "dev":
        return "https://localhost:3000"
    raise ValueError(f"--origin is required for {profile}")


def render_manifest(template_path: Path, *, profile: str, origin: str) -> str:
    template = template_path.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise ValueError(f"missing placeholder {PLACEHOLDER} in {template_path}")
    rendered = template.replace(PLACEHOLDER, origin)
    if PLACEHOLDER in rendered:
        raise ValueError(f"unresolved placeholder {PLACEHOLDER}")
    return rendered


def default_output(profile: str) -> Path:
    return OUT_DIR / profile / "manifest.xml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Outlook add-in manifest for a deployment profile")
    parser.add_argument("--profile", choices=PROFILES, default="dev")
    parser.add_argument("--origin", help="HTTPS origin serving taskpane.html, commands.html, and launchevent.js")
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        origin = origin_for_profile(args.profile, args.origin)
        rendered = render_manifest(args.template, profile=args.profile, origin=origin)
        output = args.output or default_output(args.profile)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"render_outlook_manifest: {exc}", file=sys.stderr)
        return 64
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
