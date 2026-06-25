"""Authentication, tenant resolution, and role checks for protected API routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any

from junas.backend.siem import emit_security_event
from junas.configs.runtime import TENANCY_ROLES, RuntimeSettings

REVIEW_ROLES = frozenset({"reviewer", "maker", "checker", "admin"})
DECISION_ROLES = frozenset({"maker", "checker", "admin"})
AUDIT_ROLES = frozenset({"auditor", "checker", "admin"})

_TENANT_STORAGE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class AuthFailure(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    subject: str
    roles: frozenset[str]
    auth_mode: str
    enabled: bool

    @property
    def storage_tenant_id(self) -> str | None:
        if not self.enabled:
            return None
        safe = _TENANT_STORAGE_RE.sub("_", self.tenant_id.strip())[:128].strip("._-")
        return safe or hashlib.sha256(self.tenant_id.encode("utf-8")).hexdigest()[:32]


DISABLED_TENANT_CONTEXT = TenantContext(
    tenant_id="",
    subject="",
    roles=frozenset(TENANCY_ROLES),
    auth_mode="disabled",
    enabled=False,
)


def _emit_auth_denial(
    *,
    settings: RuntimeSettings,
    request_id: str | None,
    action: str,
    detail: str,
    path: str,
    method: str,
) -> None:
    emit_security_event(
        action=action,
        outcome="denied",
        request_id=request_id,
        details={"reason": detail, "path": path, "method": method},
        settings=settings.siem,
    )


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _decode_json_part(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(_b64url_decode(value).decode("utf-8"))
    except Exception as exc:
        raise AuthFailure(401, "invalid bearer token") from exc
    if not isinstance(decoded, dict):
        raise AuthFailure(401, "invalid bearer token")
    return decoded


def _normalize_roles(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        roles = {part.strip().lower() for part in value.replace(",", " ").split() if part.strip()}
    elif isinstance(value, list | tuple | set):
        roles = {str(part).strip().lower() for part in value if str(part).strip()}
    else:
        roles = set()
    return frozenset(role for role in roles if role in TENANCY_ROLES)


def _validate_claims(payload: dict[str, Any], settings: RuntimeSettings) -> None:
    now = int(time.time())
    exp = payload.get("exp")
    if exp is not None and int(exp) <= now:
        raise AuthFailure(401, "bearer token expired")
    nbf = payload.get("nbf")
    if nbf is not None and int(nbf) > now:
        raise AuthFailure(401, "bearer token not yet valid")
    issuer = settings.tenancy.jwt_issuer
    if issuer and payload.get("iss") != issuer:
        raise AuthFailure(401, "bearer token issuer mismatch")
    audience = settings.tenancy.jwt_audience
    if audience:
        aud = payload.get("aud")
        if isinstance(aud, str):
            valid_audience = hmac.compare_digest(aud, audience)
        elif isinstance(aud, list):
            valid_audience = audience in {str(item) for item in aud}
        else:
            valid_audience = False
        if not valid_audience:
            raise AuthFailure(401, "bearer token audience mismatch")


def _decode_hs256_jwt(token: str, settings: RuntimeSettings) -> dict[str, Any]:
    try:
        raw_header, raw_payload, raw_signature = token.split(".")
    except ValueError as exc:
        raise AuthFailure(401, "invalid bearer token") from exc
    header = _decode_json_part(raw_header)
    if header.get("alg") != "HS256":
        raise AuthFailure(401, "unsupported bearer token algorithm")
    signing_input = f"{raw_header}.{raw_payload}".encode("ascii")
    expected = hmac.new(settings.tenancy.jwt_hs256_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        supplied = _b64url_decode(raw_signature)
    except Exception as exc:
        raise AuthFailure(401, "invalid bearer token signature") from exc
    if not hmac.compare_digest(expected, supplied):
        raise AuthFailure(401, "invalid bearer token signature")
    payload = _decode_json_part(raw_payload)
    _validate_claims(payload, settings)
    return payload


def _decode_jwt(token: str, settings: RuntimeSettings) -> dict[str, Any]:
    if settings.tenancy.jwt_hs256_secret:
        return _decode_hs256_jwt(token, settings)

    try:
        import jwt
    except Exception as exc:
        raise AuthFailure(503, "JWT validation requires PyJWT for JWKS-backed tokens") from exc

    try:
        key_client = jwt.PyJWKClient(settings.tenancy.jwt_jwks_url)
        signing_key = key_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.tenancy.jwt_audience or None,
            issuer=settings.tenancy.jwt_issuer or None,
        )
    except Exception as exc:
        raise AuthFailure(401, "invalid bearer token") from exc
    if not isinstance(decoded, dict):
        raise AuthFailure(401, "invalid bearer token")
    return decoded


def _resolve_api_key_context(settings: RuntimeSettings, x_api_key: str | None) -> TenantContext | None:
    if not x_api_key:
        return None
    for credential in settings.tenancy.tenant_credentials:
        if hmac.compare_digest(x_api_key, credential.api_key):
            return TenantContext(
                tenant_id=credential.tenant_id,
                subject=credential.subject,
                roles=frozenset(credential.roles),
                auth_mode="api_key",
                enabled=True,
            )
    return None


def _resolve_jwt_context(settings: RuntimeSettings, authorization: str | None) -> TenantContext | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthFailure(401, "invalid Authorization header")
    payload = _decode_jwt(token.strip(), settings)
    tenant_id = str(payload.get(settings.tenancy.jwt_tenant_claim, "") or "").strip()
    subject = str(payload.get(settings.tenancy.jwt_subject_claim, "") or "").strip()
    roles = _normalize_roles(payload.get(settings.tenancy.jwt_roles_claim))
    if not tenant_id:
        raise AuthFailure(401, "bearer token missing tenant claim")
    if not roles:
        raise AuthFailure(403, "bearer token has no recognized roles")
    return TenantContext(
        tenant_id=tenant_id,
        subject=subject or tenant_id,
        roles=roles,
        auth_mode="jwt",
        enabled=True,
    )


def resolve_tenant_context(
    *,
    settings: RuntimeSettings,
    request_id: str | None,
    path: str,
    method: str,
    x_api_key: str | None,
    authorization: str | None,
) -> TenantContext:
    if not settings.tenancy.enabled:
        expected = settings.api.api_key
        if expected and x_api_key != expected:
            _emit_auth_denial(
                settings=settings,
                request_id=request_id,
                action="api_key_check",
                detail="invalid or missing API key",
                path=path,
                method=method,
            )
            raise AuthFailure(401, "invalid or missing API key")
        return DISABLED_TENANT_CONTEXT

    try:
        context: TenantContext | None = None
        if "api_key" in settings.tenancy.auth_modes:
            context = _resolve_api_key_context(settings, x_api_key)
        if context is None and "jwt" in settings.tenancy.auth_modes:
            context = _resolve_jwt_context(settings, authorization)
    except AuthFailure as exc:
        _emit_auth_denial(
            settings=settings,
            request_id=request_id,
            action="tenant_auth",
            detail=exc.detail,
            path=path,
            method=method,
        )
        raise

    if context is None:
        _emit_auth_denial(
            settings=settings,
            request_id=request_id,
            action="tenant_auth",
            detail="missing or invalid tenant credential",
            path=path,
            method=method,
        )
        raise AuthFailure(401, "missing or invalid tenant credential")
    return context


def require_roles(
    context: TenantContext,
    allowed_roles: frozenset[str],
    *,
    settings: RuntimeSettings,
    request_id: str | None,
    path: str,
    method: str,
) -> None:
    if not context.enabled:
        return
    if context.roles & allowed_roles:
        return
    emit_security_event(
        action="rbac_check",
        outcome="denied",
        request_id=request_id,
        details={
            "tenant_id": context.tenant_id,
            "subject": context.subject,
            "auth_mode": context.auth_mode,
            "required_roles": sorted(allowed_roles),
            "path": path,
            "method": method,
        },
        settings=settings.siem,
    )
    raise AuthFailure(403, "insufficient role for this endpoint")
