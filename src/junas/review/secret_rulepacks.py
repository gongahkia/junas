from __future__ import annotations

import math
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ENV_GITLEAKS_RULE_PACKS = "JUNAS_GITLEAKS_RULE_PACKS"
ENV_GITLEAKS_MAX_RULES = "JUNAS_GITLEAKS_MAX_RULES"
ENV_GITLEAKS_MAX_MATCHES = "JUNAS_GITLEAKS_MAX_MATCHES"
ENV_GITLEAKS_RULE_PACK_MAX_BYTES = "JUNAS_GITLEAKS_RULE_PACK_MAX_BYTES"
DEFAULT_GITLEAKS_MAX_RULES = 512
DEFAULT_GITLEAKS_MAX_MATCHES = 64
DEFAULT_GITLEAKS_RULE_PACK_MAX_BYTES = 2 * 1024 * 1024
_MAX_REGEX_CHARS = 4096
_VALID_ALLOWLIST_TARGETS = frozenset({"secret", "match", "line"})
_VALID_ALLOWLIST_CONDITIONS = frozenset({"OR", "AND"})
_ENV_CACHE: dict[tuple[str, str, str], tuple["SecretRulePack", ...]] = {}


class SecretRulePackError(ValueError):
    """Raised when an opt-in external secret rule-pack is malformed."""


@dataclass(frozen=True)
class SecretAllowlist:
    regexes: tuple[re.Pattern[str], ...] = ()
    stopwords: tuple[str, ...] = ()
    regex_target: str = "secret"
    condition: str = "OR"
    target_rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class SecretRule:
    rule_id: str
    description: str
    pattern: re.Pattern[str]
    secret_group: int
    entropy: float | None
    keywords: tuple[str, ...]
    tags: tuple[str, ...]
    allowlists: tuple[SecretAllowlist, ...] = ()


@dataclass(frozen=True)
class SecretRulePack:
    title: str
    path: str
    rules: tuple[SecretRule, ...]
    allowlists: tuple[SecretAllowlist, ...] = ()


NewFinding = Callable[..., Any]


def load_secret_rule_packs_from_env() -> tuple[SecretRulePack, ...]:
    value = os.environ.get(ENV_GITLEAKS_RULE_PACKS, "").strip()
    if not value:
        return ()
    cache_key = (
        value,
        os.environ.get(ENV_GITLEAKS_MAX_RULES, "").strip(),
        os.environ.get(ENV_GITLEAKS_RULE_PACK_MAX_BYTES, "").strip(),
    )
    if cache_key in _ENV_CACHE:
        return _ENV_CACHE[cache_key]
    max_rules = _positive_int_from_env(ENV_GITLEAKS_MAX_RULES, DEFAULT_GITLEAKS_MAX_RULES)
    max_bytes = _positive_int_from_env(ENV_GITLEAKS_RULE_PACK_MAX_BYTES, DEFAULT_GITLEAKS_RULE_PACK_MAX_BYTES)
    paths = tuple(part.strip() for part in value.split(os.pathsep) if part.strip())
    if not paths:
        return ()
    packs = tuple(load_gitleaks_rule_pack(path, max_rules=max_rules, max_bytes=max_bytes) for path in paths)
    _ENV_CACHE[cache_key] = packs
    return packs


def clear_secret_rule_pack_cache_for_tests() -> None:
    _ENV_CACHE.clear()


def load_gitleaks_rule_pack(
    path: str | Path,
    *,
    max_rules: int = DEFAULT_GITLEAKS_MAX_RULES,
    max_bytes: int = DEFAULT_GITLEAKS_RULE_PACK_MAX_BYTES,
) -> SecretRulePack:
    pack_path = Path(path)
    try:
        stat = pack_path.stat()
    except OSError as exc:
        raise SecretRulePackError(f"cannot read Gitleaks rule pack {pack_path}: {exc}") from exc
    if stat.st_size > max_bytes:
        raise SecretRulePackError(f"Gitleaks rule pack {pack_path} is {stat.st_size} bytes; limit is {max_bytes}")
    try:
        raw = pack_path.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
    except Exception as exc:
        raise SecretRulePackError(f"invalid Gitleaks TOML rule pack {pack_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SecretRulePackError(f"Gitleaks rule pack {pack_path} must be a TOML table")
    extend = data.get("extend")
    if isinstance(extend, dict) and (extend.get("useDefault") or extend.get("path")):
        raise SecretRulePackError("Gitleaks [extend] is not resolved by Junas; pass a materialized TOML pack")
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        raise SecretRulePackError("Gitleaks rule pack field [[rules]] must be an array")
    if len(raw_rules) > max_rules:
        raise SecretRulePackError(f"Gitleaks rule pack has {len(raw_rules)} rules; limit is {max_rules}")
    rules: list[SecretRule] = []
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            raise SecretRulePackError(f"Gitleaks rule {index} must be a table")
        rule = _parse_gitleaks_rule(raw_rule, index=index)
        if rule is not None:
            rules.append(rule)
    if not rules:
        raise SecretRulePackError(f"Gitleaks rule pack {pack_path} has no text regex rules")
    return SecretRulePack(
        title=_string_value(data.get("title")) or pack_path.stem,
        path=str(pack_path),
        rules=tuple(rules),
        allowlists=_parse_allowlists(data, default_regex_target="match"),
    )


def detect_secret_findings(
    *,
    text: str,
    rule_packs: Sequence[SecretRulePack],
    jurisdiction: str,
    idx_start: int,
    new_finding: NewFinding,
    max_matches: int | None = None,
) -> list[Any]:
    if not rule_packs:
        return []
    match_limit = max_matches
    if match_limit is None:
        match_limit = _positive_int_from_env(ENV_GITLEAKS_MAX_MATCHES, DEFAULT_GITLEAKS_MAX_MATCHES)
    if match_limit <= 0:
        return []
    findings: list[Any] = []
    seen: set[tuple[str, int, int]] = set()
    lowered_text = text.casefold()
    for pack in rule_packs:
        for rule in pack.rules:
            if rule.keywords and not any(keyword.casefold() in lowered_text for keyword in rule.keywords):
                continue
            for match in rule.pattern.finditer(text):
                secret_span = _secret_span(match, rule.secret_group)
                if secret_span is None:
                    continue
                start, end = secret_span
                if end <= start:
                    continue
                secret = text[start:end]
                full_match = match.group(0)
                line = _line_context(text, start, end)
                if rule.entropy is not None and shannon_entropy(secret) < rule.entropy:
                    continue
                if _is_allowlisted(pack.allowlists, rule.rule_id, secret=secret, full_match=full_match, line=line):
                    continue
                if _is_allowlisted(rule.allowlists, rule.rule_id, secret=secret, full_match=full_match, line=line):
                    continue
                key = (rule.rule_id, start, end)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    new_finding(
                        idx=idx_start + len(findings),
                        category="PII",
                        rule=f"external_secret_{_slug(rule.rule_id)}",
                        jurisdiction=jurisdiction,
                        severity="high",
                        matched_text=secret,
                        start=start,
                        end=end,
                        reason=f"External secret rule-pack match: {rule.description or rule.rule_id}",
                        legal_basis="EXTERNAL_SECRET_RULE_PACK",
                        metadata={
                            "detector_source": "gitleaks",
                            "rule_pack": pack.path,
                            "rule_pack_title": pack.title,
                            "rule_id": rule.rule_id,
                            "description": rule.description,
                            "tags": list(rule.tags),
                            "secret_group": rule.secret_group,
                            "entropy_threshold": rule.entropy,
                            "observed_entropy": round(shannon_entropy(secret), 4),
                        },
                    )
                )
                if len(findings) >= match_limit:
                    return findings
    return findings


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _parse_gitleaks_rule(raw_rule: dict[str, Any], *, index: int) -> SecretRule | None:
    rule_id = _string_value(raw_rule.get("id")) or f"rule-{index}"
    regex = raw_rule.get("regex")
    if regex is None:
        return None
    if not isinstance(regex, str) or not regex.strip():
        raise SecretRulePackError(f"Gitleaks rule {rule_id} regex must be a non-empty string")
    if len(regex) > _MAX_REGEX_CHARS:
        raise SecretRulePackError(f"Gitleaks rule {rule_id} regex exceeds {_MAX_REGEX_CHARS} chars")
    pattern = _compile_gitleaks_regex(regex, rule_id=rule_id)
    secret_group = raw_rule.get("secretGroup", 0)
    if isinstance(secret_group, bool) or not isinstance(secret_group, int) or secret_group < 0:
        raise SecretRulePackError(f"Gitleaks rule {rule_id} secretGroup must be a non-negative integer")
    entropy = raw_rule.get("entropy")
    if entropy is not None and (isinstance(entropy, bool) or not isinstance(entropy, int | float)):
        raise SecretRulePackError(f"Gitleaks rule {rule_id} entropy must be numeric")
    return SecretRule(
        rule_id=rule_id,
        description=_string_value(raw_rule.get("description")),
        pattern=pattern,
        secret_group=secret_group,
        entropy=float(entropy) if entropy is not None else None,
        keywords=_string_tuple(raw_rule.get("keywords")),
        tags=_string_tuple(raw_rule.get("tags")),
        allowlists=_parse_allowlists(raw_rule, default_regex_target="secret"),
    )


def _parse_allowlists(data: dict[str, Any], *, default_regex_target: str) -> tuple[SecretAllowlist, ...]:
    raw_allowlists: list[Any] = []
    legacy = data.get("allowlist")
    if legacy is not None:
        raw_allowlists.append(legacy)
    current = data.get("allowlists")
    if isinstance(current, list):
        raw_allowlists.extend(current)
    elif current is not None:
        raw_allowlists.append(current)
    allowlists: list[SecretAllowlist] = []
    for index, raw_allowlist in enumerate(raw_allowlists):
        if not isinstance(raw_allowlist, dict):
            raise SecretRulePackError(f"allowlist {index} must be a table")
        target = _string_value(raw_allowlist.get("regexTarget")) or default_regex_target
        if target not in _VALID_ALLOWLIST_TARGETS:
            raise SecretRulePackError(f"allowlist {index} regexTarget must be secret, match, or line")
        condition = (_string_value(raw_allowlist.get("condition")) or "OR").upper()
        if condition not in _VALID_ALLOWLIST_CONDITIONS:
            raise SecretRulePackError(f"allowlist {index} condition must be OR or AND")
        regexes = tuple(
            _compile_gitleaks_regex(regex, rule_id=f"allowlist-{index}")
            for regex in _string_tuple(raw_allowlist.get("regexes"))
        )
        stopwords = tuple(stopword.casefold() for stopword in _string_tuple(raw_allowlist.get("stopwords")))
        target_rules = _string_tuple(raw_allowlist.get("targetRules"))
        allowlists.append(
            SecretAllowlist(
                regexes=regexes,
                stopwords=stopwords,
                regex_target=target,
                condition=condition,
                target_rules=target_rules,
            )
        )
    return tuple(allowlists)


def _compile_gitleaks_regex(pattern: str, *, rule_id: str) -> re.Pattern[str]:
    flags = re.MULTILINE
    normalized = pattern.replace(r"\z", r"\Z")
    if "(?i)" in normalized:
        flags |= re.IGNORECASE
        normalized = normalized.replace("(?i)", "")
    try:
        return re.compile(normalized, flags)
    except re.error as exc:
        raise SecretRulePackError(f"Gitleaks rule {rule_id} regex is not Python-compatible: {exc}") from exc


def _secret_span(match: re.Match[str], secret_group: int) -> tuple[int, int] | None:
    if secret_group > 0:
        if match.lastindex is None or secret_group > match.lastindex:
            return None
        return match.span(secret_group)
    return match.span(0)


def _is_allowlisted(
    allowlists: Sequence[SecretAllowlist],
    rule_id: str,
    *,
    secret: str,
    full_match: str,
    line: str,
) -> bool:
    for allowlist in allowlists:
        if allowlist.target_rules and rule_id not in allowlist.target_rules:
            continue
        checks: list[bool] = []
        if allowlist.stopwords:
            lowered = secret.casefold()
            checks.append(any(stopword in lowered for stopword in allowlist.stopwords))
        if allowlist.regexes:
            target = secret
            if allowlist.regex_target == "match":
                target = full_match
            elif allowlist.regex_target == "line":
                target = line
            checks.append(any(regex.search(target) for regex in allowlist.regexes))
        if not checks:
            continue
        if allowlist.condition == "AND" and all(checks):
            return True
        if allowlist.condition == "OR" and any(checks):
            return True
    return False


def _line_context(text: str, start: int, end: int) -> str:
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", end)
    if right < 0:
        right = len(text)
    return text[left:right]


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _positive_int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SecretRulePackError(f"{name} must be an integer") from exc
    if value <= 0:
        raise SecretRulePackError(f"{name} must be positive")
    return value


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())[:80].strip("._-")
    return slug or "rule"
