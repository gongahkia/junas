from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"
DEFAULT_PIPELINE_LAYERS = (
    "lexicon",
    "embedding",
    "clustering",
    "model1",
    "model2",
    "mosaic",
    "regression",
)
DEFAULT_OPTIONAL_LAYERS = ("mosaic",)
VALID_LAYERS = frozenset(DEFAULT_PIPELINE_LAYERS + ("public_evidence", "llm_adjudicator"))
LEXICON_SCORE_THRESHOLD_MODES = frozenset({"static", "dynamic"})
EXTERNAL_QUERY_POLICIES = frozenset({"sanitized_only", "derived_hashes_only", "disabled"})

KNOWN_CONFIG_KEYS: dict[str, frozenset[str] | None] = {
    "api": frozenset({"allowed_origins"}),
    "embeddings": frozenset({"model_name", "cache_size"}),
    "isolation_forest": frozenset({"contamination", "max_features", "n_estimators"}),
    "lexicon": frozenset(
        {
            "score_threshold",
            "score_threshold_mode",
            "dynamic_chars_per_point",
            "dynamic_threshold_increment",
        }
    ),
    "lexicon_weights": None,
    "mosaic": frozenset(
        {
            "ttl_hours",
            "threshold",
            "redis_host",
            "redis_port",
            "connect_timeout_seconds",
            "socket_timeout_seconds",
            "retry_attempts",
            "retry_backoff_ms",
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
            "tenant_opt_in_openai",
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
    "startup": frozenset(
        {"lazy_load_heavy", "prewarm_required_layers", "fail_on_layer_load_error"}
    ),
    "thresholds": frozenset({"mnpi_abs", "mnpi_pct", "model1", "model2", "lock_path"}),
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
class ThresholdSettings:
    mnpi_abs: float
    mnpi_pct: float
    model1: float
    model2: float
    lock_path: str


@dataclass(frozen=True)
class IsolationForestSettings:
    contamination: float
    max_features: float
    n_estimators: int


@dataclass(frozen=True)
class EmbeddingsSettings:
    model_name: str
    cache_size: int


@dataclass(frozen=True)
class MosaicSettings:
    ttl_hours: float
    threshold: int
    redis_host: str
    redis_port: int
    connect_timeout_seconds: float
    socket_timeout_seconds: float
    retry_attempts: int
    retry_backoff_ms: int


@dataclass(frozen=True)
class PublicEvidenceSettings:
    enabled: bool
    provider: str
    api_key: str
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
    # Tenant-level opt-in flag for the OpenAI provider specifically. Distinct from
    # `allow_remote_base_url`: that flag is the deployer-level gate ("remote URLs are
    # permitted"); this flag is the tenant-level gate ("this specific tenant has signed
    # off on OpenAI as the LLM backend"). Both must be true to use provider=openai.
    # Default False — must be explicitly turned on per tenant.
    tenant_opt_in_openai: bool = False


@dataclass(frozen=True)
class PrivacySettings:
    external_query_policy: str
    max_query_chars: int
    redact_exact_numbers: bool


@dataclass(frozen=True)
class LexiconSettings:
    score_threshold: float
    score_threshold_mode: str
    dynamic_chars_per_point: float
    dynamic_threshold_increment: float


@dataclass(frozen=True)
class ResponseCacheSettings:
    size: int
    ttl_seconds: float


@dataclass(frozen=True)
class StartupSettings:
    lazy_load_heavy: bool
    prewarm_required_layers: bool
    fail_on_layer_load_error: bool
    batch_max_concurrency: int
    artifact_manifest: str
    pretty_logs: bool


@dataclass(frozen=True)
class RuntimeSettings:
    config_path: Path
    raw_config: dict[str, Any] = field(repr=False)
    pipeline: PipelineSettings
    api: ApiSettings
    thresholds: ThresholdSettings
    isolation_forest: IsolationForestSettings
    embeddings: EmbeddingsSettings
    mosaic: MosaicSettings
    public_evidence: PublicEvidenceSettings
    llm: LLMSettings
    privacy: PrivacySettings
    lexicon: LexiconSettings
    lexicon_weights: dict[str, float]
    response_cache: ResponseCacheSettings
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


def _parse_dict(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    raise ConfigError(f"invalid mapping for {label}: expected table/object")


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


def _parse_lexicon_weights(value: Any) -> dict[str, float]:
    payload = _parse_dict(value, label="lexicon_weights")
    out: dict[str, float] = {}
    for key, raw_val in payload.items():
        text_key = str(key).strip()
        if not text_key:
            raise ConfigError("lexicon_weights contains an empty rule key")
        out[text_key] = _parse_float(raw_val, label=f"lexicon_weights.{text_key}", minimum=0.0)
    return out


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

    thresholds = ThresholdSettings(
        mnpi_abs=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="thresholds",
                key="mnpi_abs",
                env_vars=("MNPI_ABS_THRESHOLD",),
                default=1000000.0,
            ),
            label="thresholds.mnpi_abs",
            minimum=0.0,
        ),
        mnpi_pct=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="thresholds",
                key="mnpi_pct",
                env_vars=("MNPI_PCT_THRESHOLD",),
                default=5.0,
            ),
            label="thresholds.mnpi_pct",
            minimum=0.0,
        ),
        model1=_parse_probability(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="thresholds",
                key="model1",
                env_vars=("MODEL1_THRESHOLD",),
                default=0.5,
            ),
            label="thresholds.model1",
        ),
        model2=_parse_probability(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="thresholds",
                key="model2",
                env_vars=("MODEL2_THRESHOLD",),
                default=0.5,
            ),
            label="thresholds.model2",
        ),
        lock_path=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="thresholds",
                key="lock_path",
                env_vars=("THRESHOLDS_LOCK_PATH",),
                default="configs/thresholds.lock.json",
            ),
            label="thresholds.lock_path",
        )
        or "configs/thresholds.lock.json",
    )

    isolation_forest = IsolationForestSettings(
        contamination=_parse_probability(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="isolation_forest",
                key="contamination",
                env_vars=("IF_CONTAMINATION",),
                default=0.05,
            ),
            label="isolation_forest.contamination",
        ),
        max_features=_parse_probability(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="isolation_forest",
                key="max_features",
                env_vars=("IF_MAX_FEATURES",),
                default=0.3,
            ),
            label="isolation_forest.max_features",
        ),
        n_estimators=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="isolation_forest",
                key="n_estimators",
                env_vars=("IF_N_ESTIMATORS",),
                default=100,
            ),
            label="isolation_forest.n_estimators",
            minimum=1,
        ),
    )

    embeddings = EmbeddingsSettings(
        model_name=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="embeddings",
                key="model_name",
                env_vars=("EMBEDDINGS_MODEL",),
                default="all-mpnet-base-v2",
            ),
            label="embeddings.model_name",
        )
        or "all-mpnet-base-v2",
        cache_size=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="embeddings",
                key="cache_size",
                env_vars=("EMBEDDINGS_CACHE_SIZE",),
                default=512,
            ),
            label="embeddings.cache_size",
            minimum=0,
        ),
    )

    mosaic = MosaicSettings(
        ttl_hours=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="ttl_hours",
                env_vars=("MOSAIC_TTL_HOURS",),
                default=24.0,
            ),
            label="mosaic.ttl_hours",
            minimum=0.1,
        ),
        threshold=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="threshold",
                env_vars=("MOSAIC_THRESHOLD",),
                default=10,
            ),
            label="mosaic.threshold",
            minimum=1,
        ),
        redis_host=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="redis_host",
                env_vars=("REDIS_HOST",),
                default="localhost",
            ),
            label="mosaic.redis_host",
        )
        or "localhost",
        redis_port=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="redis_port",
                env_vars=("REDIS_PORT",),
                default=6379,
            ),
            label="mosaic.redis_port",
            minimum=1,
            maximum=65535,
        ),
        connect_timeout_seconds=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="connect_timeout_seconds",
                env_vars=("MOSAIC_CONNECT_TIMEOUT_SECONDS",),
                default=0.5,
            ),
            label="mosaic.connect_timeout_seconds",
            minimum=0.1,
        ),
        socket_timeout_seconds=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="socket_timeout_seconds",
                env_vars=("MOSAIC_SOCKET_TIMEOUT_SECONDS",),
                default=0.5,
            ),
            label="mosaic.socket_timeout_seconds",
            minimum=0.1,
        ),
        retry_attempts=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="retry_attempts",
                env_vars=("MOSAIC_RETRY_ATTEMPTS",),
                default=3,
            ),
            label="mosaic.retry_attempts",
            minimum=1,
        ),
        retry_backoff_ms=_parse_int(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="mosaic",
                key="retry_backoff_ms",
                env_vars=("MOSAIC_RETRY_BACKOFF_MS",),
                default=100,
            ),
            label="mosaic.retry_backoff_ms",
            minimum=0,
        ),
    )

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
    if public_evidence.provider not in {"exa", "tinyfish", "none"}:
        raise ConfigError("public_evidence.provider must be one of: exa, tinyfish, none")

    llm = LLMSettings(
        enabled=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="llm",
                key="enabled",
                env_vars=("KAYPOH_LLM_ENABLED",),
                default=False,
            ),
            label="llm.enabled",
        ),
        provider=_parse_str(
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
        or "vllm",
        api_key=_parse_str(os.environ.get("KAYPOH_LLM_API_KEY", ""), label="KAYPOH_LLM_API_KEY"),
        base_url=_parse_str(
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
        or "http://127.0.0.1:8001/v1",
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
        allow_remote_base_url=_parse_bool(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="llm",
                key="allow_remote_base_url",
                env_vars=("KAYPOH_LLM_ALLOW_REMOTE_BASE_URL",),
                default=False,
            ),
            label="llm.allow_remote_base_url",
        ),
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
    )
    if llm.provider not in {"vllm", "ollama", "openai", "none"}:
        raise ConfigError("llm.provider must be one of: vllm, ollama, openai, none")
    # belt-and-braces: refuse to even construct LLMSettings with provider=openai unless
    # both gates are explicitly set. Surfacing the error at config-load time means a
    # misconfigured tenant fails fast instead of silently degrading to local-private.
    if llm.provider == "openai" and not (llm.allow_remote_base_url and llm.tenant_opt_in_openai):
        raise ConfigError(
            "llm.provider=openai requires BOTH llm.allow_remote_base_url=true "
            "(deployer-level gate) AND llm.tenant_opt_in_openai=true (tenant-level gate)"
        )

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

    lexicon = LexiconSettings(
        score_threshold=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="lexicon",
                key="score_threshold",
                env_vars=("LEXICON_SCORE_THRESHOLD",),
                default=10.0,
            ),
            label="lexicon.score_threshold",
            minimum=0.0,
        ),
        score_threshold_mode=_parse_str(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="lexicon",
                key="score_threshold_mode",
                env_vars=("LEXICON_SCORE_THRESHOLD_MODE",),
                default="static",
            ),
            label="lexicon.score_threshold_mode",
        ).lower(),
        dynamic_chars_per_point=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="lexicon",
                key="dynamic_chars_per_point",
                env_vars=("LEXICON_DYNAMIC_CHARS_PER_POINT",),
                default=1000.0,
            ),
            label="lexicon.dynamic_chars_per_point",
            minimum=1.0,
        ),
        dynamic_threshold_increment=_parse_float(
            _resolve_raw_value(
                raw_config,
                cli_overrides,
                section="lexicon",
                key="dynamic_threshold_increment",
                env_vars=("LEXICON_DYNAMIC_THRESHOLD_INCREMENT",),
                default=1.0,
            ),
            label="lexicon.dynamic_threshold_increment",
            minimum=0.0,
        ),
    )
    if lexicon.score_threshold_mode not in LEXICON_SCORE_THRESHOLD_MODES:
        raise ConfigError(
            "lexicon.score_threshold_mode must be one of "
            + ", ".join(sorted(LEXICON_SCORE_THRESHOLD_MODES))
        )

    lexicon_weights = _parse_lexicon_weights(raw_config.get("lexicon_weights", {}))

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
        artifact_manifest=_parse_str(
            os.environ.get("KAYPOH_ARTIFACT_MANIFEST", "artifacts/manifest.json"),
            label="KAYPOH_ARTIFACT_MANIFEST",
        )
        or "artifacts/manifest.json",
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
        thresholds=thresholds,
        isolation_forest=isolation_forest,
        embeddings=embeddings,
        mosaic=mosaic,
        public_evidence=public_evidence,
        llm=llm,
        privacy=privacy,
        lexicon=lexicon,
        lexicon_weights=lexicon_weights,
        response_cache=response_cache,
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
