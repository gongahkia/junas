from __future__ import annotations

import ipaddress
import json
import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import tomllib
except ImportError:
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"
DEFAULT_PIPELINE_LAYERS: tuple[str, ...] = ()
DEFAULT_OPTIONAL_LAYERS: tuple[str, ...] = ()
VALID_LAYERS = frozenset(("public_evidence", "llm_adjudicator"))
EXTERNAL_QUERY_POLICIES = frozenset({"sanitized_only", "derived_hashes_only", "disabled"})
IMAGE_SCAN_PROVIDERS = frozenset(
    {"none", "tesseract", "openai_vision", "google_vision", "aws_rekognition", "azure_vision"}
)
TENANCY_AUTH_MODES = frozenset({"api_key", "jwt"})
TENANCY_ROLES = frozenset({"reviewer", "maker", "checker", "admin", "auditor"})
SIEM_FACILITIES = frozenset(
    {
        "auth",
        "authpriv",
        "cron",
        "daemon",
        "kern",
        "local0",
        "local1",
        "local2",
        "local3",
        "local4",
        "local5",
        "local6",
        "local7",
        "syslog",
        "user",
    }
)

KNOWN_CONFIG_KEYS: dict[str, frozenset[str] | None] = {
    "api": frozenset({"allowed_origins"}),
    "local_daemon": frozenset({"acl_enabled", "allowed_origins", "token", "token_file"}),
    "document_ingest": frozenset(
        {
            "fail_closed",
            "min_pdf_text_chars",
            "min_pdf_chars_per_page",
            "max_empty_pdf_page_ratio",
            "reject_image_only_pdf",
        }
    ),
    "public_evidence": frozenset(
        {
            "enabled",
            "provider",
            "endpoint",
            "max_results",
            "timeout_seconds",
        }
    ),
    "llm": frozenset(
        {
            "enabled",
            "provider",
            "base_url",
            "model",
            "timeout_seconds",
            "allow_remote_base_url",
            "allow_remote_raw_text",
            "tenant_opt_in_openai",
            "llm_input_mode",
        }
    ),
    "image_scan": frozenset(
        {
            "provider",
            "timeout_seconds",
            "max_images",
            "max_bytes",
            "max_total_bytes",
            "pdf_render_pages",
            "pdf_render_max_pages",
            "pdf_render_scale",
            "model",
            "openai_base_url",
            "aws_region",
            "azure_endpoint",
            "tenant_opt_in_openai",
            "tenant_opt_in_google",
            "tenant_opt_in_aws",
            "tenant_opt_in_azure",
            "tenant_opt_ins_json",
        }
    ),
    "privacy": frozenset(
        {
            "external_query_policy",
            "max_query_chars",
            "redact_exact_numbers",
        }
    ),
    "pipeline": frozenset({"layers", "optional_layers"}),
    "response_cache": frozenset({"size", "ttl_seconds"}),
    "siem": frozenset({"enabled", "sink", "syslog_address", "facility", "app_name"}),
    "startup": frozenset(
        {"lazy_load_heavy", "prewarm_required_layers", "fail_on_layer_load_error"}
    ),
    "tenancy": frozenset(
        {
            "enabled",
            "auth_modes",
            "tenant_credentials_json",
            "jwt_issuer",
            "jwt_audience",
            "jwt_jwks_url",
            "jwt_hs256_secret",
            "jwt_tenant_claim",
            "jwt_subject_claim",
            "jwt_roles_claim",
        }
    ),
}
_MISSING = object()


class ConfigError(ValueError):
    """Raised when runtime settings fail validation."""


@dataclass(frozen=True)
class PipelineSettings:
    layers: tuple[str, ...]
    optional_layers: tuple[str, ...]


@dataclass(frozen=True)
class ApiSettings:
    allowed_origins: tuple[str, ...]
    api_key: str = ""


@dataclass(frozen=True)
class LocalDaemonSettings:
    acl_enabled: bool
    allowed_origins: tuple[str, ...]
    token: str
    token_file: str


@dataclass(frozen=True)
class DocumentIngestSettings:
    fail_closed: bool
    min_pdf_text_chars: int
    min_pdf_chars_per_page: int
    max_empty_pdf_page_ratio: float
    reject_image_only_pdf: bool


@dataclass(frozen=True)
class TenantCredential:
    api_key: str
    tenant_id: str
    subject: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class TenancySettings:
    enabled: bool
    auth_modes: tuple[str, ...]
    tenant_credentials: tuple[TenantCredential, ...]
    jwt_issuer: str
    jwt_audience: str
    jwt_jwks_url: str
    jwt_hs256_secret: str
    jwt_tenant_claim: str
    jwt_subject_claim: str
    jwt_roles_claim: str


@dataclass(frozen=True)
class PublicEvidenceSettings:
    enabled: bool
    provider: str
    api_key: str
    backup_api_key: str
    endpoint: str
    max_results: int
    timeout_seconds: float


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    allow_remote_base_url: bool
    # Separate, explicit consent for sending raw document text to a remote LLM endpoint.
    # `allow_remote_base_url` permits remote transport in general; this flag permits the
    # highest-risk payload shape. Remote endpoints default to structured_tokens unless
    # this is set and llm_input_mode is explicitly raw_text.
    allow_remote_raw_text: bool = False
    # Tenant-level opt-in flag for the OpenAI provider specifically. Distinct from
    # `allow_remote_base_url`: that flag is the deployer-level gate ("remote URLs are
    # permitted"); this flag is the tenant-level gate ("this specific tenant has signed
    # off on OpenAI as the LLM backend"). Both must be true to use provider=openai.
    # Default False — must be explicitly turned on per tenant.
    tenant_opt_in_openai: bool = False
    # Privacy-hardened mode for regulated tenants. `raw_text` (default) ships the
    # document text + sanitised context. `structured_tokens` ships only abstract
    # tokens — rule names, severities, jurisdiction codes, SHA-256 hashes of the
    # body and per-finding context windows — and clamps the LLM's response against
    # a closed vocabulary (`STRUCTURED_REASONS`). The doc text never leaves the
    # process boundary via this path.
    llm_input_mode: str = "raw_text"


@dataclass(frozen=True)
class ImageScanSettings:
    provider: str
    timeout_seconds: float
    max_images: int
    max_bytes: int
    max_total_bytes: int
    pdf_render_pages: bool
    pdf_render_max_pages: int
    pdf_render_scale: float
    model: str
    openai_api_key: str
    openai_base_url: str
    google_credentials_path: str
    aws_region: str
    azure_key: str
    azure_endpoint: str
    tenant_opt_in_openai: bool = False
    tenant_opt_in_google: bool = False
    tenant_opt_in_aws: bool = False
    tenant_opt_in_azure: bool = False
    tenant_opt_ins: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class PrivacySettings:
    external_query_policy: str
    max_query_chars: int
    redact_exact_numbers: bool


@dataclass(frozen=True)
class ResponseCacheSettings:
    size: int
    ttl_seconds: float


@dataclass(frozen=True)
class SIEMSettings:
    enabled: bool
    sink: str
    syslog_address: str
    facility: str
    app_name: str


@dataclass(frozen=True)
class StartupSettings:
    lazy_load_heavy: bool
    prewarm_required_layers: bool
    fail_on_layer_load_error: bool
    batch_max_concurrency: int
    pretty_logs: bool


@dataclass(frozen=True)
class RuntimeSettings:
    config_path: Path
    raw_config: dict[str, Any] = field(repr=False)
    pipeline: PipelineSettings
    api: ApiSettings
    local_daemon: LocalDaemonSettings
    document_ingest: DocumentIngestSettings
    tenancy: TenancySettings
    public_evidence: PublicEvidenceSettings
    llm: LLMSettings
    image_scan: ImageScanSettings
    privacy: PrivacySettings
    response_cache: ResponseCacheSettings
    siem: SIEMSettings
    startup: StartupSettings


def _is_truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_bool(value: Any, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(f"invalid boolean for {label}: {value!r}")


def _parse_list(value: Any, *, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return tuple(out)
    raise ConfigError(f"invalid list for {label}: expected comma-separated string or array")


def _parse_str(value: Any, *, label: str) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _parse_int(value: Any, *, label: str, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid integer for {label}: {value!r}") from exc
    if minimum is not None and parsed < minimum:
        raise ConfigError(f"{label} must be >= {minimum}, got {parsed}")
    if maximum is not None and parsed > maximum:
        raise ConfigError(f"{label} must be <= {maximum}, got {parsed}")
    return parsed


def _parse_float(value: Any, *, label: str, minimum: float | None = None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid float for {label}: {value!r}") from exc
    if minimum is not None and parsed < minimum:
        raise ConfigError(f"{label} must be >= {minimum}, got {parsed}")
    return parsed


def _parse_probability(value: Any, *, label: str) -> float:
    parsed = _parse_float(value, label=label, minimum=0.0)
    if parsed > 1.0:
        raise ConfigError(f"{label} must be <= 1.0, got {parsed}")
    return parsed


def _is_private_or_local_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return host.endswith(".local")


def _parse_tenant_credentials(value: Any, *, label: str) -> tuple[TenantCredential, ...]:
    if value in (None, ""):
        return ()
    raw = value
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{label} must be valid JSON") from exc

    entries: list[dict[str, Any]] = []
    if isinstance(raw, Mapping):
        for api_key, body in raw.items():
            if not isinstance(body, Mapping):
                raise ConfigError(f"{label} mapping values must be objects")
            entries.append({"api_key": str(api_key), **dict(body)})
    elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray, str)):
        for item in raw:
            if not isinstance(item, Mapping):
                raise ConfigError(f"{label} array items must be objects")
            entries.append(dict(item))
    else:
        raise ConfigError(f"{label} must be a JSON object or array")

    credentials: list[TenantCredential] = []
    seen_keys: set[str] = set()
    for index, item in enumerate(entries):
        api_key = _parse_str(item.get("api_key", ""), label=f"{label}[{index}].api_key")
        tenant_id = _parse_str(item.get("tenant_id", ""), label=f"{label}[{index}].tenant_id")
        subject = _parse_str(item.get("subject", ""), label=f"{label}[{index}].subject") or tenant_id
        roles = tuple(role.lower() for role in _parse_list(item.get("roles", ()), label=f"{label}[{index}].roles"))
        if not api_key:
            raise ConfigError(f"{label}[{index}].api_key must not be empty")
        if api_key in seen_keys:
            raise ConfigError(f"{label} contains a duplicate api_key")
        if not tenant_id:
            raise ConfigError(f"{label}[{index}].tenant_id must not be empty")
        invalid_roles = sorted(set(roles) - TENANCY_ROLES)
        if invalid_roles:
            raise ConfigError(f"{label}[{index}].roles contains invalid roles: {', '.join(invalid_roles)}")
        if not roles:
            raise ConfigError(f"{label}[{index}].roles must not be empty")
        seen_keys.add(api_key)
        credentials.append(
            TenantCredential(api_key=api_key, tenant_id=tenant_id, subject=subject, roles=roles)
        )
    return tuple(credentials)


def _parse_provider_opt_in_map(value: Any, *, label: str) -> dict[str, tuple[str, ...]]:
    if value in (None, ""):
        return {}
    raw = value
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{label} must be valid JSON") from exc
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{label} must be a JSON object")

    out: dict[str, tuple[str, ...]] = {}
    for tenant_id, providers in raw.items():
        tenant = _parse_str(tenant_id, label=f"{label}.tenant_id")
        if not tenant:
            raise ConfigError(f"{label} tenant ids must not be empty")
        if isinstance(providers, Mapping):
            provider_names = [
                name
                for name, enabled in providers.items()
                if _parse_bool(enabled, label=f"{label}.{tenant}.{name}")
            ]
        else:
            provider_names = list(_parse_list(providers, label=f"{label}.{tenant}"))
        normalized: list[str] = []
        for provider in provider_names:
            provider_name = str(provider).strip().lower()
            if provider_name != "*" and provider_name not in IMAGE_SCAN_PROVIDERS:
                raise ConfigError(f"{label}.{tenant} contains unknown provider: {provider_name}")
            if provider_name == "none":
                continue
            normalized.append(provider_name)
        out[tenant] = tuple(sorted(set(normalized)))
    return out


def _default_response_cache_size() -> int:
    return 0 if os.environ.get("PROMETHEUS_MULTIPROC_DIR") else 256


def _config_path_from_overrides(cli_overrides: Mapping[str, Any] | None = None) -> Path:
    override = None
    if cli_overrides is not None:
        override = cli_overrides.get("config_path")
    raw_path = override or os.environ.get("KAYPOH_CONFIG") or DEFAULT_CONFIG_PATH
    return Path(raw_path).expanduser().resolve()


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    except Exception as exc:
        raise ConfigError(f"config parse failure ({path}): {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"config root must be a TOML table: {path}")
    return dict(payload)


def _validate_known_keys(raw_config: Mapping[str, Any], *, config_path: Path) -> None:
    unknown_sections = sorted(set(raw_config) - set(KNOWN_CONFIG_KEYS))
    if unknown_sections:
        raise ConfigError(
            f"unknown config sections in {config_path}: {', '.join(unknown_sections)}"
        )
    for section, value in raw_config.items():
        if not isinstance(value, Mapping):
            raise ConfigError(f"config section '{section}' in {config_path} must be a table")
        allowed_keys = KNOWN_CONFIG_KEYS.get(section)
        if allowed_keys is None:
            continue
        unknown_keys = sorted(set(value) - set(allowed_keys))
        if unknown_keys:
            raise ConfigError(
                f"unknown keys in [{section}] of {config_path}: {', '.join(unknown_keys)}"
            )


def load_config(config_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = Path(config_path).expanduser().resolve() if config_path is not None else _config_path_from_overrides()
    payload = _load_toml(path)
    _validate_known_keys(payload, config_path=path)
    return payload


def _resolve_raw_value(
    raw_config: Mapping[str, Any],
    cli_overrides: Mapping[str, Any] | None,
    *,
    section: str,
    key: str,
    env_vars: Sequence[str],
    default: Any,
) -> Any:
    cli_key = f"{section}.{key}"
    if cli_overrides is not None and cli_key in cli_overrides:
        return cli_overrides[cli_key]
    for env_var in env_vars:
        value = os.environ.get(env_var)
        if value is not None:
            return value
    section_payload = raw_config.get(section, {})
    if isinstance(section_payload, Mapping) and key in section_payload:
        return section_payload[key]
    return default


def load_runtime_settings(cli_overrides: Mapping[str, Any] | None = None) -> RuntimeSettings:
    config_path = _config_path_from_overrides(cli_overrides)
    raw_config = load_config(config_path)

    pipeline_layers = _parse_list(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="pipeline",
            key="layers",
            env_vars=("PIPELINE_LAYERS",),
            default=DEFAULT_PIPELINE_LAYERS,
        ),
        label="pipeline.layers",
    ) or DEFAULT_PIPELINE_LAYERS
    optional_layers = _parse_list(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="pipeline",
            key="optional_layers",
            env_vars=("KAYPOH_OPTIONAL_LAYERS",),
            default=DEFAULT_OPTIONAL_LAYERS,
        ),
        label="pipeline.optional_layers",
    ) or DEFAULT_OPTIONAL_LAYERS
    invalid_layers = sorted(set(pipeline_layers) - VALID_LAYERS)
    if invalid_layers:
        raise ConfigError(f"invalid pipeline layers: {', '.join(invalid_layers)}")
    invalid_optional_layers = sorted(set(optional_layers) - VALID_LAYERS)
    if invalid_optional_layers:
        raise ConfigError(
            "optional layers must be valid known layers: "
            + ", ".join(invalid_optional_layers)
        )

    allowed_origins = _parse_list(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="api",
            key="allowed_origins",
            env_vars=("KAYPOH_ALLOWED_ORIGINS",),
            default=("http://localhost", "http://127.0.0.1"),
        ),
        label="api.allowed_origins",
    ) or ("http://localhost", "http://127.0.0.1")
    api_key = _parse_str(os.environ.get("KAYPOH_API_KEY", ""), label="KAYPOH_API_KEY")

    local_daemon_allowed_origins = _parse_list(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="local_daemon",
            key="allowed_origins",
            env_vars=("KAYPOH_LOCAL_DAEMON_ALLOWED_ORIGINS",),
            default=(
                "chrome-extension://*",
                "https://chatgpt.com",
                "https://claude.ai",
                "https://gemini.google.com",
            ),
        ),
        label="local_daemon.allowed_origins",
    ) or (
        "chrome-extension://*",
        "https://chatgpt.com",
        "https://claude.ai",
        "https://gemini.google.com",
    )
    local_daemon = LocalDaemonSettings(
        acl_enabled=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="local_daemon",
                key="acl_enabled",
                env_vars=("KAYPOH_LOCAL_DAEMON_ACL_ENABLED",),
                default=False,
            ),
            label="local_daemon.acl_enabled",
        ),
        allowed_origins=tuple(dict.fromkeys(local_daemon_allowed_origins)),
        token=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="local_daemon",
                key="token",
                env_vars=("KAYPOH_LOCAL_DAEMON_TOKEN",),
                default="",
            ),
            label="local_daemon.token",
        ),
        token_file=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="local_daemon",
                key="token_file",
                env_vars=("KAYPOH_LOCAL_DAEMON_TOKEN_FILE",),
                default="",
            ),
            label="local_daemon.token_file",
        ),
    )

    document_ingest = DocumentIngestSettings(
        fail_closed=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="document_ingest",
                key="fail_closed",
                env_vars=("KAYPOH_DOCUMENT_FAIL_CLOSED",),
                default=True,
            ),
            label="document_ingest.fail_closed",
        ),
        min_pdf_text_chars=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="document_ingest",
                key="min_pdf_text_chars",
                env_vars=("KAYPOH_PDF_MIN_TEXT_CHARS",),
                default=20,
            ),
            label="document_ingest.min_pdf_text_chars",
            minimum=0,
        ),
        min_pdf_chars_per_page=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="document_ingest",
                key="min_pdf_chars_per_page",
                env_vars=("KAYPOH_PDF_MIN_CHARS_PER_PAGE",),
                default=20,
            ),
            label="document_ingest.min_pdf_chars_per_page",
            minimum=0,
        ),
        max_empty_pdf_page_ratio=_parse_probability(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="document_ingest",
                key="max_empty_pdf_page_ratio",
                env_vars=("KAYPOH_PDF_MAX_EMPTY_PAGE_RATIO",),
                default=0.2,
            ),
            label="document_ingest.max_empty_pdf_page_ratio",
        ),
        reject_image_only_pdf=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="document_ingest",
                key="reject_image_only_pdf",
                env_vars=("KAYPOH_REJECT_IMAGE_ONLY_PDF",),
                default=True,
            ),
            label="document_ingest.reject_image_only_pdf",
        ),
    )

    tenancy_auth_modes = tuple(
        mode.lower()
        for mode in (
            _parse_list(
                _resolve_raw_value(
                    raw_config,
                    cli_overrides,
                    section="tenancy",
                    key="auth_modes",
                    env_vars=("KAYPOH_TENANCY_AUTH_MODES",),
                    default=("api_key", "jwt"),
                ),
                label="tenancy.auth_modes",
            )
            or ("api_key", "jwt")
        )
    )
    invalid_auth_modes = sorted(set(tenancy_auth_modes) - TENANCY_AUTH_MODES)
    if invalid_auth_modes:
        raise ConfigError(f"tenancy.auth_modes contains invalid modes: {', '.join(invalid_auth_modes)}")
    tenancy = TenancySettings(
        enabled=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="enabled",
                env_vars=("KAYPOH_TENANCY_ENABLED",),
                default=False,
            ),
            label="tenancy.enabled",
        ),
        auth_modes=tenancy_auth_modes,
        tenant_credentials=_parse_tenant_credentials(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="tenant_credentials_json",
                env_vars=("KAYPOH_TENANT_CREDENTIALS_JSON",),
                default="",
            ),
            label="tenancy.tenant_credentials_json",
        ),
        jwt_issuer=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="jwt_issuer",
                env_vars=("KAYPOH_JWT_ISSUER",),
                default="",
            ),
            label="tenancy.jwt_issuer",
        ),
        jwt_audience=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="jwt_audience",
                env_vars=("KAYPOH_JWT_AUDIENCE",),
                default="",
            ),
            label="tenancy.jwt_audience",
        ),
        jwt_jwks_url=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="jwt_jwks_url",
                env_vars=("KAYPOH_JWT_JWKS_URL",),
                default="",
            ),
            label="tenancy.jwt_jwks_url",
        ),
        jwt_hs256_secret=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="jwt_hs256_secret",
                env_vars=("KAYPOH_JWT_HS256_SECRET",),
                default="",
            ),
            label="tenancy.jwt_hs256_secret",
        ),
        jwt_tenant_claim=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="jwt_tenant_claim",
                env_vars=("KAYPOH_JWT_TENANT_CLAIM",),
                default="tenant_id",
            ),
            label="tenancy.jwt_tenant_claim",
        )
        or "tenant_id",
        jwt_subject_claim=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="jwt_subject_claim",
                env_vars=("KAYPOH_JWT_SUBJECT_CLAIM",),
                default="sub",
            ),
            label="tenancy.jwt_subject_claim",
        )
        or "sub",
        jwt_roles_claim=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="tenancy",
                key="jwt_roles_claim",
                env_vars=("KAYPOH_JWT_ROLES_CLAIM",),
                default="roles",
            ),
            label="tenancy.jwt_roles_claim",
        )
        or "roles",
    )
    if tenancy.enabled and not tenancy.auth_modes:
        raise ConfigError("tenancy.auth_modes must not be empty when tenancy.enabled=true")
    if tenancy.enabled and "api_key" in tenancy.auth_modes and not tenancy.tenant_credentials:
        raise ConfigError("tenancy.tenant_credentials_json is required when tenancy api_key mode is enabled")
    if tenancy.enabled and "jwt" in tenancy.auth_modes and not (tenancy.jwt_hs256_secret or tenancy.jwt_jwks_url):
        raise ConfigError("tenancy.jwt_hs256_secret or tenancy.jwt_jwks_url is required when jwt mode is enabled")

    public_evidence_provider = (
        _parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="public_evidence",
                key="provider",
                env_vars=("KAYPOH_PUBLIC_EVIDENCE_PROVIDER",),
                default="exa",
            ),
            label="public_evidence.provider",
        ).lower()
        or "exa"
    )
    # provider-specific defaults: api key env name + endpoint default.
    _provider_defaults = {
        "exa": ("EXA_API_KEY", "https://api.exa.ai/search"),
        "tinyfish": ("TINYFISH_API_KEY", "https://api.search.tinyfish.ai/"),
        "serper": ("SERPER_API_KEY", "https://google.serper.dev/search"),
        "serpapi": ("SERPAPI_KEY_PRIMARY", "https://serpapi.com/search.json"),
        "none": ("", ""),
    }
    _key_env, _endpoint_default = _provider_defaults.get(public_evidence_provider, ("", ""))
    public_evidence_api_key = (
        _parse_str(os.environ.get(_key_env, ""), label=_key_env) if _key_env else ""
    )

    _resolved_endpoint = _parse_str(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="public_evidence",
            key="endpoint",
            env_vars=("KAYPOH_PUBLIC_EVIDENCE_ENDPOINT",),
            default=_endpoint_default,
        ),
        label="public_evidence.endpoint",
    ) or _endpoint_default
    # if the resolved endpoint is the exa default but the provider is not exa, the user has
    # likely flipped only `provider` without updating the legacy endpoint in config.toml.
    # snap to the provider's default endpoint in that case so tinyfish requests don't hit exa.
    if public_evidence_provider != "exa" and _resolved_endpoint == "https://api.exa.ai/search":
        _resolved_endpoint = _endpoint_default

    public_evidence = PublicEvidenceSettings(
        enabled=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="public_evidence",
                key="enabled",
                env_vars=("KAYPOH_PUBLIC_EVIDENCE_ENABLED",),
                default=False,
            ),
            label="public_evidence.enabled",
        ),
        provider=public_evidence_provider,
        api_key=public_evidence_api_key,
        backup_api_key=(
            _parse_str(os.environ.get("SERPAPI_KEY_BACKUP", ""), label="SERPAPI_KEY_BACKUP")
            if public_evidence_provider == "serpapi"
            else ""
        ),
        endpoint=_resolved_endpoint,
        max_results=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="public_evidence",
                key="max_results",
                env_vars=("KAYPOH_PUBLIC_EVIDENCE_MAX_RESULTS",),
                default=5,
            ),
            label="public_evidence.max_results",
            minimum=1,
            maximum=20,
        ),
        timeout_seconds=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="public_evidence",
                key="timeout_seconds",
                env_vars=("KAYPOH_PUBLIC_EVIDENCE_TIMEOUT_SECONDS",),
                default=8.0,
            ),
            label="public_evidence.timeout_seconds",
            minimum=0.1,
        ),
    )
    if public_evidence.provider not in {"exa", "tinyfish", "serper", "serpapi", "none"}:
        raise ConfigError("public_evidence.provider must be one of: exa, tinyfish, serper, serpapi, none")

    llm_enabled = _parse_bool(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="llm",
            key="enabled",
            env_vars=("KAYPOH_LLM_ENABLED",),
            default=False,
        ),
        label="llm.enabled",
    )
    llm_provider = (
        _parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="llm",
                key="provider",
                env_vars=("KAYPOH_LLM_PROVIDER",),
                default="vllm",
            ),
            label="llm.provider",
        ).lower()
        or "vllm"
    )
    llm_base_url = (
        _parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="llm",
                key="base_url",
                env_vars=("KAYPOH_LLM_BASE_URL",),
                default="http://127.0.0.1:8001/v1",
            ),
            label="llm.base_url",
        )
        or "http://127.0.0.1:8001/v1"
    )
    llm_allow_remote_base_url = _parse_bool(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="llm",
            key="allow_remote_base_url",
            env_vars=("KAYPOH_LLM_ALLOW_REMOTE_BASE_URL",),
            default=False,
        ),
        label="llm.allow_remote_base_url",
    )
    llm_allow_remote_raw_text = _parse_bool(
        _resolve_raw_value(
            raw_config,
            cli_overrides,
            section="llm",
            key="allow_remote_raw_text",
            env_vars=("KAYPOH_LLM_ALLOW_REMOTE_RAW_TEXT",),
            default=False,
        ),
        label="llm.allow_remote_raw_text",
    )
    raw_llm_input_mode = _resolve_raw_value(
        raw_config,
        cli_overrides,
        section="llm",
        key="llm_input_mode",
        env_vars=("KAYPOH_LLM_INPUT_MODE",),
        default=_MISSING,
    )
    llm_base_is_remote = bool(llm_base_url) and not _is_private_or_local_base_url(llm_base_url)
    llm_input_mode_explicit = raw_llm_input_mode is not _MISSING
    if llm_input_mode_explicit:
        llm_input_mode = _parse_str(raw_llm_input_mode, label="llm.llm_input_mode") or "raw_text"
    else:
        llm_input_mode = "structured_tokens" if llm_base_is_remote else "raw_text"

    llm = LLMSettings(
        enabled=llm_enabled,
        provider=llm_provider,
        api_key=_parse_str(os.environ.get("KAYPOH_LLM_API_KEY", ""), label="KAYPOH_LLM_API_KEY"),
        base_url=llm_base_url,
        model=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="llm",
                key="model",
                env_vars=("KAYPOH_LLM_MODEL",),
                default="gpt-oss-20b",
            ),
            label="llm.model",
        )
        or "gpt-oss-20b",
        timeout_seconds=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="llm",
                key="timeout_seconds",
                env_vars=("KAYPOH_LLM_TIMEOUT_SECONDS",),
                default=20.0,
            ),
            label="llm.timeout_seconds",
            minimum=0.1,
        ),
        allow_remote_base_url=llm_allow_remote_base_url,
        allow_remote_raw_text=llm_allow_remote_raw_text,
        tenant_opt_in_openai=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="llm",
                key="tenant_opt_in_openai",
                env_vars=("KAYPOH_LLM_TENANT_OPT_IN_OPENAI",),
                default=False,
            ),
            label="llm.tenant_opt_in_openai",
        ),
        llm_input_mode=llm_input_mode,
    )
    if llm.provider not in {"vllm", "ollama", "openai", "local_distilled", "none"}:
        raise ConfigError(
            "llm.provider must be one of: vllm, ollama, openai, local_distilled, none"
        )
    if llm.llm_input_mode not in {"raw_text", "structured_tokens"}:
        raise ConfigError("llm.llm_input_mode must be one of: raw_text, structured_tokens")
    if (
        llm.enabled
        and llm.provider not in {"local_distilled", "none"}
        and llm_base_is_remote
        and llm.llm_input_mode == "raw_text"
        and not llm.allow_remote_raw_text
    ):
        raise ConfigError(
            "remote llm_input_mode=raw_text requires llm.allow_remote_raw_text=true "
            "(env KAYPOH_LLM_ALLOW_REMOTE_RAW_TEXT=1). Omit llm.llm_input_mode to use "
            "the remote default structured_tokens mode."
        )
    # belt-and-braces: refuse to even construct LLMSettings with provider=openai unless
    # both gates are explicitly set. Surfacing the error at config-load time means a
    # misconfigured tenant fails fast instead of silently degrading to local-private.
    if llm.provider == "openai" and not (llm.allow_remote_base_url and llm.tenant_opt_in_openai):
        raise ConfigError(
            "llm.provider=openai requires BOTH llm.allow_remote_base_url=true "
            "(deployer-level gate) AND llm.tenant_opt_in_openai=true (tenant-level gate)"
        )

    image_scan_provider = (
        _parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="provider",
                env_vars=("KAYPOH_IMAGE_SCAN_PROVIDER",),
                default="none",
            ),
            label="image_scan.provider",
        ).lower()
        or "none"
    )
    image_scan = ImageScanSettings(
        provider=image_scan_provider,
        timeout_seconds=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="timeout_seconds",
                env_vars=("KAYPOH_IMAGE_SCAN_TIMEOUT_SECONDS",),
                default=20.0,
            ),
            label="image_scan.timeout_seconds",
            minimum=0.1,
        ),
        max_images=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="max_images",
                env_vars=("KAYPOH_IMAGE_SCAN_MAX_IMAGES",),
                default=32,
            ),
            label="image_scan.max_images",
            minimum=1,
            maximum=500,
        ),
        max_bytes=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="max_bytes",
                env_vars=("KAYPOH_IMAGE_SCAN_MAX_BYTES",),
                default=10 * 1024 * 1024,
            ),
            label="image_scan.max_bytes",
            minimum=1024,
            maximum=50 * 1024 * 1024,
        ),
        max_total_bytes=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="max_total_bytes",
                env_vars=("KAYPOH_IMAGE_SCAN_MAX_TOTAL_BYTES",),
                default=100 * 1024 * 1024,
            ),
            label="image_scan.max_total_bytes",
            minimum=1024,
            maximum=500 * 1024 * 1024,
        ),
        pdf_render_pages=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="pdf_render_pages",
                env_vars=("KAYPOH_IMAGE_SCAN_PDF_RENDER_PAGES",),
                default=True,
            ),
            label="image_scan.pdf_render_pages",
        ),
        pdf_render_max_pages=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="pdf_render_max_pages",
                env_vars=("KAYPOH_IMAGE_SCAN_PDF_RENDER_MAX_PAGES",),
                default=8,
            ),
            label="image_scan.pdf_render_max_pages",
            minimum=1,
            maximum=100,
        ),
        pdf_render_scale=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="pdf_render_scale",
                env_vars=("KAYPOH_IMAGE_SCAN_PDF_RENDER_SCALE",),
                default=2.0,
            ),
            label="image_scan.pdf_render_scale",
            minimum=0.25,
        ),
        model=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="model",
                env_vars=("KAYPOH_IMAGE_SCAN_MODEL",),
                default="gpt-4o-mini",
            ),
            label="image_scan.model",
        )
        or "gpt-4o-mini",
        openai_api_key=_parse_str(os.environ.get("OPENAI_API_KEY", ""), label="OPENAI_API_KEY"),
        openai_base_url=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="openai_base_url",
                env_vars=("KAYPOH_IMAGE_SCAN_OPENAI_BASE_URL",),
                default="https://api.openai.com/v1/responses",
            ),
            label="image_scan.openai_base_url",
        )
        or "https://api.openai.com/v1/responses",
        google_credentials_path=_parse_str(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            label="GOOGLE_APPLICATION_CREDENTIALS",
        ),
        aws_region=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="aws_region",
                env_vars=("AWS_REGION", "AWS_DEFAULT_REGION"),
                default="",
            ),
            label="image_scan.aws_region",
        ),
        azure_key=_parse_str(os.environ.get("AZURE_VISION_KEY", ""), label="AZURE_VISION_KEY"),
        azure_endpoint=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="azure_endpoint",
                env_vars=("AZURE_VISION_ENDPOINT",),
                default="",
            ),
            label="image_scan.azure_endpoint",
        ),
        tenant_opt_in_openai=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="tenant_opt_in_openai",
                env_vars=("KAYPOH_IMAGE_SCAN_TENANT_OPT_IN_OPENAI",),
                default=False,
            ),
            label="image_scan.tenant_opt_in_openai",
        ),
        tenant_opt_in_google=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="tenant_opt_in_google",
                env_vars=("KAYPOH_IMAGE_SCAN_TENANT_OPT_IN_GOOGLE",),
                default=False,
            ),
            label="image_scan.tenant_opt_in_google",
        ),
        tenant_opt_in_aws=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="tenant_opt_in_aws",
                env_vars=("KAYPOH_IMAGE_SCAN_TENANT_OPT_IN_AWS",),
                default=False,
            ),
            label="image_scan.tenant_opt_in_aws",
        ),
        tenant_opt_in_azure=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="tenant_opt_in_azure",
                env_vars=("KAYPOH_IMAGE_SCAN_TENANT_OPT_IN_AZURE",),
                default=False,
            ),
            label="image_scan.tenant_opt_in_azure",
        ),
        tenant_opt_ins=_parse_provider_opt_in_map(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="image_scan",
                key="tenant_opt_ins_json",
                env_vars=("KAYPOH_IMAGE_SCAN_TENANT_OPT_INS_JSON",),
                default="",
            ),
            label="image_scan.tenant_opt_ins_json",
        ),
    )
    if image_scan.provider not in IMAGE_SCAN_PROVIDERS:
        raise ConfigError(
            "image_scan.provider must be one of: " + ", ".join(sorted(IMAGE_SCAN_PROVIDERS))
        )
    provider_has_tenant_map = any(
        image_scan.provider in set(providers) or "*" in set(providers)
        for providers in image_scan.tenant_opt_ins.values()
    )
    if image_scan.max_total_bytes < image_scan.max_bytes:
        raise ConfigError("image_scan.max_total_bytes must be >= image_scan.max_bytes")
    if image_scan.provider == "openai_vision" and not (image_scan.tenant_opt_in_openai or provider_has_tenant_map):
        raise ConfigError("image_scan.provider=openai_vision requires image_scan.tenant_opt_in_openai=true")
    if image_scan.provider == "google_vision" and not (image_scan.tenant_opt_in_google or provider_has_tenant_map):
        raise ConfigError("image_scan.provider=google_vision requires image_scan.tenant_opt_in_google=true")
    if image_scan.provider == "aws_rekognition" and not (image_scan.tenant_opt_in_aws or provider_has_tenant_map):
        raise ConfigError("image_scan.provider=aws_rekognition requires image_scan.tenant_opt_in_aws=true")
    if image_scan.provider == "azure_vision" and not (image_scan.tenant_opt_in_azure or provider_has_tenant_map):
        raise ConfigError("image_scan.provider=azure_vision requires image_scan.tenant_opt_in_azure=true")

    privacy = PrivacySettings(
        external_query_policy=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="privacy",
                key="external_query_policy",
                env_vars=("KAYPOH_EXTERNAL_QUERY_POLICY",),
                default="sanitized_only",
            ),
            label="privacy.external_query_policy",
        ).lower()
        or "sanitized_only",
        max_query_chars=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="privacy",
                key="max_query_chars",
                env_vars=("KAYPOH_PRIVACY_MAX_QUERY_CHARS",),
                default=180,
            ),
            label="privacy.max_query_chars",
            minimum=32,
            maximum=512,
        ),
        redact_exact_numbers=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="privacy",
                key="redact_exact_numbers",
                env_vars=("KAYPOH_PRIVACY_REDACT_EXACT_NUMBERS",),
                default=True,
            ),
            label="privacy.redact_exact_numbers",
        ),
    )
    if privacy.external_query_policy not in EXTERNAL_QUERY_POLICIES:
        raise ConfigError(
            "privacy.external_query_policy must be one of "
            + ", ".join(sorted(EXTERNAL_QUERY_POLICIES))
        )

    response_cache = ResponseCacheSettings(
        size=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="response_cache",
                key="size",
                env_vars=("KAYPOH_RESPONSE_CACHE_SIZE",),
                default=_default_response_cache_size(),
            ),
            label="response_cache.size",
            minimum=0,
        ),
        ttl_seconds=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="response_cache",
                key="ttl_seconds",
                env_vars=("KAYPOH_RESPONSE_CACHE_TTL_SECONDS",),
                default=60.0,
            ),
            label="response_cache.ttl_seconds",
            minimum=0.0,
        ),
    )

    siem = SIEMSettings(
        enabled=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="siem",
                key="enabled",
                env_vars=("KAYPOH_SIEM_ENABLED",),
                default=False,
            ),
            label="siem.enabled",
        ),
        sink=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="siem",
                key="sink",
                env_vars=("KAYPOH_SIEM_SINK",),
                default="syslog",
            ),
            label="siem.sink",
        ).lower()
        or "syslog",
        syslog_address=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="siem",
                key="syslog_address",
                env_vars=("KAYPOH_SIEM_SYSLOG_ADDRESS",),
                default="/var/run/syslog",
            ),
            label="siem.syslog_address",
        )
        or "/var/run/syslog",
        facility=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="siem",
                key="facility",
                env_vars=("KAYPOH_SIEM_FACILITY",),
                default="local4",
            ),
            label="siem.facility",
        ).lower()
        or "local4",
        app_name=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="siem",
                key="app_name",
                env_vars=("KAYPOH_SIEM_APP_NAME",),
                default="kaypoh",
            ),
            label="siem.app_name",
        )
        or "kaypoh",
    )
    if siem.sink not in {"syslog", "stdout"}:
        raise ConfigError("siem.sink must be one of: syslog, stdout")
    if siem.facility not in SIEM_FACILITIES:
        raise ConfigError("siem.facility must be a known syslog facility")
    if not siem.app_name:
        raise ConfigError("siem.app_name must not be empty")

    startup = StartupSettings(
        lazy_load_heavy=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="startup",
                key="lazy_load_heavy",
                env_vars=("KAYPOH_LAZY_LOAD_HEAVY",),
                default=True,
            ),
            label="startup.lazy_load_heavy",
        ),
        prewarm_required_layers=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="startup",
                key="prewarm_required_layers",
                env_vars=("KAYPOH_PREWARM_REQUIRED_LAYERS",),
                default=True,
            ),
            label="startup.prewarm_required_layers",
        ),
        fail_on_layer_load_error=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="startup",
                key="fail_on_layer_load_error",
                env_vars=("KAYPOH_FAIL_ON_LAYER_LOAD_ERROR",),
                default=False,
            ),
            label="startup.fail_on_layer_load_error",
        ),
        batch_max_concurrency=_parse_int(
            os.environ.get("KAYPOH_BATCH_MAX_CONCURRENCY", min(4, os.cpu_count() or 1)),
            label="KAYPOH_BATCH_MAX_CONCURRENCY",
            minimum=1,
        ),
        pretty_logs=_parse_bool(
            os.environ.get("KAYPOH_PRETTY_LOGS", "1"),
            label="KAYPOH_PRETTY_LOGS",
        ),
    )

    return RuntimeSettings(
        config_path=config_path,
        raw_config=raw_config,
        pipeline=PipelineSettings(layers=tuple(pipeline_layers), optional_layers=tuple(optional_layers)),
        api=ApiSettings(allowed_origins=tuple(dict.fromkeys(allowed_origins)), api_key=api_key),
        local_daemon=local_daemon,
        document_ingest=document_ingest,
        tenancy=tenancy,
        public_evidence=public_evidence,
        llm=llm,
        image_scan=image_scan,
        privacy=privacy,
        response_cache=response_cache,
        siem=siem,
        startup=startup,
    )


def get_runtime_settings(cli_overrides: Mapping[str, Any] | None = None) -> RuntimeSettings:
    return load_runtime_settings(cli_overrides=cli_overrides)


def get_config_val(
    section: str,
    key: str,
    env_var: str,
    default: Any,
    cast_type: Any = str,
) -> Any:
    raw_config = load_config()
    value = _resolve_raw_value(
        raw_config,
        cli_overrides=None,
        section=section,
        key=key,
        env_vars=(env_var,),
        default=default,
    )
    try:
        return cast_type(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"invalid value for {section}.{key} from {env_var or 'config'}: {value!r}"
        ) from exc


class _ConfigProxy(Mapping[str, Any]):
    def __getitem__(self, key: str) -> Any:
        return load_config()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(load_config())

    def __len__(self) -> int:
        return len(load_config())

    def get(self, key: str, default: Any = None) -> Any:
        return load_config().get(key, default)


_cfg = _ConfigProxy()
