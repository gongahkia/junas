#!/usr/bin/env python3
"""Generate tenant API-key registry entries for Junas server deployments."""

from __future__ import annotations

import argparse
import json
import secrets
from typing import Any

VALID_ROLES = {"reviewer", "maker", "checker", "admin", "auditor"}


def generate_entry(*, tenant_id: str, subject: str, roles: list[str]) -> dict[str, Any]:
    normalized = sorted({role.strip().lower() for role in roles if role.strip()})
    invalid = sorted(set(normalized) - VALID_ROLES)
    if invalid:
        raise ValueError(f"invalid roles: {', '.join(invalid)}")
    if not tenant_id.strip():
        raise ValueError("tenant_id is required")
    return {
        "api_key": "kp_" + secrets.token_urlsafe(32),
        "tenant_id": tenant_id.strip(),
        "subject": subject.strip() or tenant_id.strip(),
        "roles": normalized or ["reviewer"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate JUNAS_TENANCY_CREDENTIALS_JSON entries")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--subject", default="")
    parser.add_argument("--roles", default="reviewer", help="comma-separated roles")
    args = parser.parse_args(argv)
    entry = generate_entry(
        tenant_id=args.tenant_id,
        subject=args.subject,
        roles=[role for role in args.roles.split(",")],
    )
    print(json.dumps([entry], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
