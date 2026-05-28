#!/usr/bin/env python3
"""One-command preflight checks for the current Kaypoh runtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kaypoh.configs.runtime import ConfigError, load_runtime_settings  # noqa: E402


def _has_env(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _is_truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _check_spacy_model() -> tuple[bool, str]:
    try:
        import spacy

        spacy.load("en_core_web_sm")
        return True, "spaCy model en_core_web_sm loaded"
    except Exception as exc:
        return False, f"spaCy model load failed: {exc}"


def _check_optional_import(module_name: str, label: str) -> tuple[bool, str]:
    try:
        __import__(module_name)
        return True, f"{label} import available"
    except Exception as exc:
        return False, f"{label} import unavailable: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kaypoh runtime preflight checks")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on any warning")
    parser.add_argument("--config", type=str, help="override config.toml path for this run")
    parser.add_argument("--layers", type=str, help="override active pipeline layers for this run")
    parser.add_argument(
        "--deployment",
        choices=("local", "production"),
        default=os.environ.get("KAYPOH_DEPLOYMENT_MODE", "local").strip().lower() or "local",
        help="deployment posture to validate; production fails strict preflight when dev-only auth is enabled",
    )
    args = parser.parse_args()
    if args.deployment not in {"local", "production"}:
        parser.error("--deployment must be one of: local, production")

    cli_overrides: dict[str, object] = {}
    if args.config:
        cli_overrides["config_path"] = args.config
    if args.layers:
        cli_overrides["pipeline.layers"] = [layer.strip() for layer in args.layers.split(",") if layer.strip()]

    checks: list[str] = []
    warnings: list[str] = []

    try:
        settings = load_runtime_settings(cli_overrides=cli_overrides)
    except ConfigError as exc:
        settings = None
        warnings.append(str(exc))
    else:
        checks.append(f"settings validated: {settings.config_path}")
        checks.append(f"pipeline layers valid: {list(settings.pipeline.layers)}")

    ok_spacy, msg_spacy = _check_spacy_model()
    (checks if ok_spacy else warnings).append(msg_spacy)

    ok_pypdf, msg_pypdf = _check_optional_import("pypdf", "PDF extractor")
    (checks if ok_pypdf else warnings).append(msg_pypdf)

    ok_pillow, msg_pillow = _check_optional_import("PIL", "image metadata scrubber")
    (checks if ok_pillow else warnings).append(msg_pillow)

    if args.deployment == "production" and _is_truthy_env("KAYPOH_DEV_AUTH"):
        warnings.append(
            "KAYPOH_DEV_AUTH=1 enables dev-only X-Reviewer-ID attribution; disable it for production"
        )
    elif _is_truthy_env("KAYPOH_DEV_AUTH"):
        checks.append("dev reviewer header accepted for local deployment only")
    else:
        checks.append("dev reviewer header disabled")

    if settings is not None:
        provider_keys = {
            "exa": ("EXA_API_KEY",),
            "tinyfish": ("TINYFISH_API_KEY",),
            "serper": ("SERPER_API_KEY",),
            "serpapi": ("SERPAPI_KEY_PRIMARY", "SERPAPI_KEY_BACKUP"),
            "none": (),
        }
        if settings.public_evidence.enabled and settings.public_evidence.provider != "none":
            accepted = provider_keys.get(settings.public_evidence.provider, ())
            if any(_has_env(name) for name in accepted):
                checks.append(
                    f"public evidence provider configured: {settings.public_evidence.provider}"
                )
            else:
                warnings.append(
                    "public evidence is enabled but no key is set for "
                    f"{settings.public_evidence.provider}: {', '.join(accepted)}"
                )
        else:
            checks.append("public evidence disabled")

        if settings.llm.enabled and settings.llm.provider != "none":
            if settings.llm.provider == "openai" and not _has_env("KAYPOH_LLM_API_KEY"):
                warnings.append("OpenAI LLM provider enabled but KAYPOH_LLM_API_KEY is empty")
            else:
                checks.append(f"LLM adjudicator configured: {settings.llm.provider}")
        else:
            checks.append("LLM adjudicator disabled")

    print("=== Kaypoh Preflight ===")
    config_path = settings.config_path if settings is not None else (
        Path(args.config).expanduser().resolve() if args.config else ROOT / "config.toml"
    )
    print(f"config_path: {config_path}")
    print(f"deployment: {args.deployment}")
    print("checks:")
    for item in checks:
        print(f"  - {item}")
    print("warnings:")
    if warnings:
        for item in warnings:
            print(f"  - {item}")
    else:
        print("  - none")

    print("summary_json:")
    print(json.dumps({"checks": checks, "warnings": warnings}, indent=2))

    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
