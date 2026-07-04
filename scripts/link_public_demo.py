#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
README = ROOT / "README.md"

sys.path.insert(0, str(SCRIPT_DIR))
from verify_public_demo import verify_public_demo  # noqa: E402

START = "<!-- JUNAS_PUBLIC_DEMO_LINK_START -->"
END = "<!-- JUNAS_PUBLIC_DEMO_LINK_END -->"
INSERT_BEFORE = "## Install Locally"
DEFAULT_COLD_START_COPY = (
    "Hosted on free Hugging Face CPU Basic. The first visit after 48 hours of inactivity may take longer while the "
    "Space wakes. The demo runs strict deterministic review only and does not persist submitted text."
)


def public_demo_block(base_url: str, cold_start_copy: str) -> str:
    url = base_url.rstrip("/")
    if not url.startswith("https://"):
        raise ValueError("public demo URL must be HTTPS")
    return (
        f"{START}\n"
        "## Hosted Demo\n\n"
        f"Try the deterministic-only public demo: [Open Junas public demo]({url}/demo).\n\n"
        f"{cold_start_copy}\n"
        f"{END}\n\n"
    )


def update_readme_text(text: str, *, base_url: str, cold_start_copy: str) -> str:
    block = public_demo_block(base_url, cold_start_copy)
    if START in text or END in text:
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError("README public demo markers are inconsistent")
        prefix, rest = text.split(START, 1)
        _, suffix = rest.split(END, 1)
        return prefix + block + suffix.lstrip("\n")
    if INSERT_BEFORE not in text:
        raise ValueError(f"README insertion point not found: {INSERT_BEFORE}")
    prefix, suffix = text.split(INSERT_BEFORE, 1)
    return prefix.rstrip() + "\n\n" + block + INSERT_BEFORE + suffix


def link_public_demo(
    *,
    base_url: str,
    readme_path: Path = README,
    cold_start_copy: str = DEFAULT_COLD_START_COPY,
    ready_timeout: float = 300.0,
    request_timeout: float = 30.0,
) -> None:
    verify_public_demo(base_url, ready_timeout=ready_timeout, request_timeout=request_timeout)
    text = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(
        update_readme_text(text, base_url=base_url, cold_start_copy=cold_start_copy), encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a hosted public demo and link it from README.md.")
    parser.add_argument("--base-url", required=True, help="Direct app URL, e.g. https://owner-space.hf.space")
    parser.add_argument("--readme", default=README, type=Path)
    parser.add_argument("--cold-start-copy", default=DEFAULT_COLD_START_COPY)
    parser.add_argument("--ready-timeout", type=float, default=300.0)
    parser.add_argument("--request-timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        link_public_demo(
            base_url=args.base_url,
            readme_path=args.readme,
            cold_start_copy=args.cold_start_copy,
            ready_timeout=args.ready_timeout,
            request_timeout=args.request_timeout,
        )
    except Exception as exc:
        sys.stderr.write(f"failed to link public demo: {exc}\n")
        return 1
    print(f"public_demo_linked: true | readme: {args.readme} | base_url: {args.base_url.rstrip('/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
