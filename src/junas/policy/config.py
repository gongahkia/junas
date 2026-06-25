from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .engine import DEFAULT_POLICY_PROFILE, TenantPolicyProfile

POLICY_ACTIONS = frozenset(
    {
        "retry_review",
        "redact_pii",
        "safe_rewrite",
        "request_approval",
        "hold_until_public",
        "cite_public_source",
        "proceed_with_warning",
    }
)
POLICY_KEYS = frozenset(
    {
        "policy_id",
        "policy_version",
        "internal_domains",
        "warn_on_low_risk_findings",
        "degraded_block_action",
        "high_pii_required_actions",
        "high_mnpi_external_actions",
        "public_mnpi_recommended_actions",
        "reviewer_override_roles",
        "medium_risk_recommended_actions",
        "low_risk_recommended_actions",
    }
)


class PolicyConfigError(ValueError):
    """Raised when tenant policy config fails validation."""


def load_policy_profile(
    config_path: str | Path | None = None,
    *,
    tenant_id: str | None = None,
    production: bool = False,
) -> TenantPolicyProfile:
    if config_path is None:
        return DEFAULT_POLICY_PROFILE

    path = Path(config_path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PolicyConfigError(f"policy config parse failure: {path}: {exc}") from exc
    except OSError as exc:
        raise PolicyConfigError(f"cannot read policy config: {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PolicyConfigError("policy config root must be a TOML table")

    unknown_sections = set(raw) - {"policy", "tenants"}
    if unknown_sections:
        raise PolicyConfigError(f"unknown policy config sections: {sorted(unknown_sections)}")

    base_table = _table(raw.get("policy", {}), "policy")
    if production and "policy_version" not in base_table:
        raise PolicyConfigError("production policy config requires policy.policy_version")

    merged: dict[str, Any] = dict(base_table)
    tenant_table: dict[str, Any] = {}
    if tenant_id:
        tenants = _table(raw.get("tenants", {}), "tenants")
        if tenant_id in tenants:
            tenant_table = _table(tenants[tenant_id], f"tenants.{tenant_id}")
            if production and "policy_version" not in tenant_table:
                raise PolicyConfigError(
                    f"production tenant policy override requires tenants.{tenant_id}.policy_version"
                )
            merged.update(tenant_table)

    profile = _profile_from_table(merged)
    if production and not profile.policy_version.strip():
        raise PolicyConfigError("production policy config requires non-empty policy_version")
    return profile


def _profile_from_table(table: Mapping[str, Any]) -> TenantPolicyProfile:
    unknown_keys = set(table) - POLICY_KEYS
    if unknown_keys:
        raise PolicyConfigError(f"unknown policy config keys: {sorted(unknown_keys)}")

    defaults = DEFAULT_POLICY_PROFILE
    return TenantPolicyProfile(
        policy_id=_string_value(table, "policy_id", defaults.policy_id),
        policy_version=_string_value(table, "policy_version", defaults.policy_version),
        internal_domains=_domain_tuple(table, "internal_domains", defaults.internal_domains),
        warn_on_low_risk_findings=_bool_value(
            table,
            "warn_on_low_risk_findings",
            defaults.warn_on_low_risk_findings,
        ),
        degraded_block_action=_action_value(table, "degraded_block_action", defaults.degraded_block_action),
        high_pii_required_actions=_action_tuple(
            table,
            "high_pii_required_actions",
            defaults.high_pii_required_actions,
        ),
        high_mnpi_external_actions=_action_tuple(
            table,
            "high_mnpi_external_actions",
            defaults.high_mnpi_external_actions,
        ),
        public_mnpi_recommended_actions=_action_tuple(
            table,
            "public_mnpi_recommended_actions",
            defaults.public_mnpi_recommended_actions,
        ),
        reviewer_override_roles=_string_tuple(
            table,
            "reviewer_override_roles",
            defaults.reviewer_override_roles,
        ),
        medium_risk_recommended_actions=_action_tuple(
            table,
            "medium_risk_recommended_actions",
            defaults.medium_risk_recommended_actions,
        ),
        low_risk_recommended_actions=_action_tuple(
            table,
            "low_risk_recommended_actions",
            defaults.low_risk_recommended_actions,
        ),
    )


def _table(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PolicyConfigError(f"{label} must be a TOML table")
    return value


def _string_value(table: Mapping[str, Any], key: str, default: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise PolicyConfigError(f"{key} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise PolicyConfigError(f"{key} must be non-empty")
    if len(cleaned) > 128:
        raise PolicyConfigError(f"{key} must be <= 128 characters")
    return cleaned


def _bool_value(table: Mapping[str, Any], key: str, default: bool) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise PolicyConfigError(f"{key} must be a boolean")
    return value


def _domain_tuple(table: Mapping[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = table.get(key, default)
    if not isinstance(value, (list, tuple)):
        raise PolicyConfigError(f"{key} must be an array of domains")
    domains: list[str] = []
    for domain in value:
        if not isinstance(domain, str):
            raise PolicyConfigError(f"{key} entries must be strings")
        cleaned = domain.strip().lower().rstrip(".")
        if not cleaned:
            continue
        if len(cleaned) > 253:
            raise PolicyConfigError(f"{key} entry exceeds 253 characters")
        if any(ch.isspace() for ch in cleaned):
            raise PolicyConfigError(f"{key} entries cannot contain whitespace")
        domains.append(cleaned)
    return tuple(domains)


def _action_value(table: Mapping[str, Any], key: str, default: str) -> str:
    value = _string_value(table, key, default)
    if value not in POLICY_ACTIONS:
        raise PolicyConfigError(f"{key} contains unsupported action: {value}")
    return value


def _action_tuple(table: Mapping[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = table.get(key, default)
    if not isinstance(value, (list, tuple)):
        raise PolicyConfigError(f"{key} must be an array of actions")
    actions: list[str] = []
    for action in value:
        if not isinstance(action, str):
            raise PolicyConfigError(f"{key} entries must be strings")
        cleaned = action.strip()
        if cleaned not in POLICY_ACTIONS:
            raise PolicyConfigError(f"{key} contains unsupported action: {cleaned}")
        actions.append(cleaned)
    if not actions:
        raise PolicyConfigError(f"{key} must contain at least one action")
    return tuple(actions)


def _string_tuple(table: Mapping[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = table.get(key, default)
    if not isinstance(value, (list, tuple)):
        raise PolicyConfigError(f"{key} must be an array of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PolicyConfigError(f"{key} entries must be strings")
        cleaned = item.strip()
        if not cleaned:
            raise PolicyConfigError(f"{key} entries must be non-empty")
        items.append(cleaned)
    if not items:
        raise PolicyConfigError(f"{key} must contain at least one value")
    return tuple(items)
