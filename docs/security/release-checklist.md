# Release Checklist

Use this checklist before tagging any server, local desktop, or adapter release. A
release candidate is blocked until every applicable gate below has passing command
output attached to the release ticket.

## API Contract

OpenAPI snapshot and generated examples must match the intended API surface.

```sh
uv run pytest test/test_openapi_snapshot.py test/test_openapi_docs.py
uv run python scripts/export_openapi_examples.py
```

If the snapshot changes intentionally, update `test/fixtures/openapi_contract_snapshot.json`
in the same PR as the schema change and include adapter compatibility notes.

## Auth And Tenant Isolation

API-key/JWT auth, role checks, local daemon token gates, and tenant isolation must pass.

```sh
uv run pytest \
  test/test_api_auth.py \
  test/test_tenant_isolation.py \
  test/test_mapping_store.py \
  test/test_subject_erasure.py \
  test/test_review_endpoints.py
```

Release blockers:

- Any endpoint accepting `review_id`, `document_hash`, mapping ids, subject-erasure
  targets, matter ids, or tenant-scoped ids bypasses auth or tenant checks.
- Any production mode accepts local-dev-only reviewer headers or caller-supplied tenant
  headers.

## No-Body Logs And SIEM Privacy

Backend logs, SIEM exports, fixtures, and generated reports must not contain raw request
body text, matched spans, reversible mapping values, or auth headers.

```sh
uv run pytest \
  test/test_backend_log_privacy.py \
  test/test_siem_export.py \
  test/test_fixture_scrub.py
uv run python scripts/check_fixture_scrub.py
```

## Local Daemon CSRF

Loopback binding is not the CSRF boundary. Origin checks, custom token headers, CORS
preflight, pairing approval, and protected endpoint denial must pass.

```sh
uv run pytest test/test_local_daemon_acl.py test/test_local_daemon_acl_smoke.py
uv run python scripts/smoke_local_daemon_acl.py
```

The expected evidence is denial for disallowed origins, denial for missing/invalid
`X-Junas-Local-Token`, denial for simple form posts to protected endpoints, and allowed
CORS preflight only for configured origins.

## Adapter Privacy

Adapter releases must prove raw prompt, email, or document text is not stored in browser
extension storage, Office Runtime storage, local storage, console logs, or adapter
telemetry. Run the adapter suite for the adapter being released:

```sh
uv run pytest \
  test/test_frontend_integration.py \
  test/test_browser_extension.py \
  test/test_outlook_manifest_render.py \
  test/test_outlook_manifest_validate.py \
  test/test_outlook_smart_alert_visual_docs.py
```

Do not promote a browser adapter release if the release depends on unimplemented
selector-failure or prompt-storage privacy tests. Keep the maturity label aligned with
`docs/integrations/maturity-matrix.md`.

## Dependency, SBOM, And Packaging Evidence

Dependency scan and SBOM evidence must be regenerated from the lockfile for each
release candidate.

```sh
uv run python scripts/generate_sbom.py --target all --out-dir reports/sbom
```

For dependency/security scanning commands, use `docs/security/dependency-scanning.md`.
For desktop bundle SBOM requirements, use `docs/security/sbom.md` and require
`--require-desktop-artifact` after the PyInstaller build.

## Release Record

Attach these items to the release ticket:

- Test command output for every gate above.
- OpenAPI snapshot diff or statement that there is no API surface change.
- Dependency scan exceptions, if any, with owner and expiry date.
- SBOM paths and artifact hashes.
- Adapter maturity label and known unsupported surfaces.
- Production config summary proving secrets, journal keys, mapping-store encryption, and
  tenant auth are configured outside local-dev defaults.
