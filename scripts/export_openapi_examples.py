#!/usr/bin/env python3
"""Export Postman and cURL examples from the backend OpenAPI contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def dereference_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/components/schemas/"):
            return {}
        name = ref.rsplit("/", 1)[-1]
        target = components.get(name, {})
        if isinstance(target, dict):
            return target
        return {}
    return schema


def _choose_schema_variant(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        for variant in schema["anyOf"]:
            if isinstance(variant, dict) and variant.get("type") != "null":
                return dereference_schema(variant, components)
    return dereference_schema(schema, components)


def example_for_schema(
    schema: dict[str, Any],
    components: dict[str, Any],
    *,
    field_name: str = "",
) -> Any:
    schema = _choose_schema_variant(schema, components)
    if not isinstance(schema, dict):
        return None

    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    schema_type = schema.get("type")
    if schema_type == "object" or ("properties" in schema):
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            return {}
        required = schema.get("required", [])
        if not isinstance(required, list):
            required = []

        out: dict[str, Any] = {}
        ordered_keys = list(props.keys())
        for key in ordered_keys:
            if key in required:
                out[key] = example_for_schema(props[key], components, field_name=key)

        # Include a few commonly useful optional fields for better defaults.
        for optional_key in ("include_offending_spans", "debug", "entity_id"):
            if optional_key in props and optional_key not in out:
                if optional_key == "include_offending_spans":
                    out[optional_key] = True
                elif optional_key == "debug":
                    out[optional_key] = False
                elif optional_key == "entity_id":
                    out[optional_key] = "acme-corp"

        return out

    if schema_type == "array":
        items_schema = schema.get("items", {})
        sample = example_for_schema(items_schema, components, field_name=field_name)
        return [sample]

    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 0.5
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        lowered = field_name.lower()
        if lowered == "text":
            return "Acme Corp is acquiring GlobalTech for $2.5 billion"
        if lowered.endswith("_id"):
            return "sample-id"
        return "string"

    return None


def build_request_body(operation: dict[str, Any], components: dict[str, Any]) -> dict[str, Any] | None:
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content", {})
    if not isinstance(content, dict):
        return None
    app_json = content.get("application/json", {})
    if not isinstance(app_json, dict):
        return None
    schema = app_json.get("schema", {})
    if not isinstance(schema, dict):
        return None

    body = example_for_schema(schema, components)
    if isinstance(body, dict) and "items" in body and isinstance(body["items"], list) and body["items"]:
        first = body["items"][0]
        if isinstance(first, dict) and "text" in first and first["text"] == "string":
            first["text"] = "Acme Corp is acquiring GlobalTech for $2.5 billion"
    return body


def build_response_example(operation: dict[str, Any], components: dict[str, Any]) -> dict[str, Any] | None:
    responses = operation.get("responses", {})
    if not isinstance(responses, dict):
        return None
    ok_response = responses.get("200")
    if not isinstance(ok_response, dict):
        return None
    content = ok_response.get("content", {})
    if not isinstance(content, dict):
        return None
    app_json = content.get("application/json", {})
    if not isinstance(app_json, dict):
        return None
    schema = app_json.get("schema", {})
    if not isinstance(schema, dict):
        return None
    example = example_for_schema(schema, components)
    return example if isinstance(example, dict) else None


def build_postman_item(
    *,
    base_url_var: str,
    path: str,
    method: str,
    operation: dict[str, Any],
    components: dict[str, Any],
) -> dict[str, Any]:
    body_payload = build_request_body(operation, components)
    response_example = build_response_example(operation, components)

    headers: list[dict[str, str]] = []
    if body_payload is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
    if path.startswith("/classify"):
        headers.append({"key": "X-API-Key", "value": "{{junasApiKey}}"})
    if path == "/local/pairing/approve":
        headers.append({"key": "X-Junas-Local-Token", "value": "{{junasLocalToken}}"})

    path_parts = [part for part in path.split("/") if part]
    url = {
        "raw": f"{{{{{base_url_var}}}}}{path}",
        "host": [f"{{{{{base_url_var}}}}}"],
        "path": path_parts,
    }

    request_payload: dict[str, Any] = {
        "method": method.upper(),
        "header": headers,
        "url": url,
    }
    if body_payload is not None:
        request_payload["body"] = {
            "mode": "raw",
            "raw": json.dumps(body_payload, indent=2),
            "options": {"raw": {"language": "json"}},
        }

    item = {
        "name": f"{method.upper()} {path}",
        "request": request_payload,
        "response": [],
        "description": operation.get("summary", ""),
    }
    if response_example is not None:
        item["response"] = [
            {
                "name": "Example 200 response",
                "originalRequest": request_payload,
                "status": "OK",
                "code": 200,
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": json.dumps(response_example, indent=2),
            }
        ]
    return item


def build_curl_block(
    *,
    path: str,
    method: str,
    operation: dict[str, Any],
    components: dict[str, Any],
) -> str:
    lines: list[str] = []
    summary = operation.get("summary", "").strip()
    if summary:
        lines.append(f"# {method.upper()} {path} - {summary}")
    else:
        lines.append(f"# {method.upper()} {path}")

    base = f'curl -sS -X {method.upper()} "${{BASE_URL}}{path}"'
    body_payload = build_request_body(operation, components)

    if body_payload is None and not path.startswith("/classify"):
        lines.append(base)
        return "\n".join(lines)

    lines.append(f"{base} \\")
    if body_payload is not None:
        lines.append('  -H "Content-Type: application/json" \\')
    if path.startswith("/classify"):
        lines.append('  -H "X-API-Key: ${JUNAS_API_KEY:-dev-secret}" \\')
    if path == "/local/pairing/approve":
        lines.append('  -H "X-Junas-Local-Token: ${JUNAS_LOCAL_DAEMON_TOKEN}" \\')
    if body_payload is not None:
        compact = json.dumps(body_payload, separators=(",", ":"))
        lines.append(f"  -d '{compact}'")
    else:
        lines[-1] = lines[-1].rstrip(" \\")

    return "\n".join(lines)


HERO_MARKER_START = "<!-- JUNAS_REVIEW_HERO_START -->"
HERO_MARKER_END = "<!-- JUNAS_REVIEW_HERO_END -->"

HERO_REVIEW_REQUEST: dict[str, Any] = {
    "text": (
        "Subject: Project Raven draft\n\n"
        "Before Monday's announcement, send Dr Jane Tan S1234567D the draft SPA. "
        "Project Raven will acquire GlobalTech for USD 2.5 billion; keep this off "
        "ChatGPT unless redacted."
    ),
    "source_jurisdiction": "SG",
    "destination_jurisdiction": "US",
    "document_type": "genai_prompt",
    "entity_id": "Project Raven",
    "surface": "browser_genai",
    "workflow": "prompt_submit",
    "requested_action": "send",
    "external_destination": True,
    "include_suggestions": True,
    "review_profile": "strict",
}


@asynccontextmanager
async def _noop_lifespan(app):
    yield


@contextmanager
def _deterministic_demo_env():
    updates = {
        "PIPELINE_LAYERS": "",
        "JUNAS_PUBLIC_EVIDENCE_ENABLED": "0",
        "JUNAS_LLM_ENABLED": "0",
        "JUNAS_LLM_DEFINED_TERMS_ENABLED": "0",
        "JUNAS_LLM_COVERAGE_AUDIT_ENABLED": "0",
        "JUNAS_IMAGE_SCAN_PROVIDER": "none",
        "JUNAS_REVIEW_PERSIST": "0",
        "JUNAS_TENANCY_ENABLED": "0",
    }
    unset = ("JUNAS_API_KEY",)
    original = {key: os.environ.get(key) for key in (*updates.keys(), *unset)}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        for key in unset:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_hero_review() -> dict[str, Any]:
    from fastapi.testclient import TestClient

    import junas.backend.main as backend_main

    original_lifespan = backend_main.app.router.lifespan_context
    with _deterministic_demo_env():
        backend_main._state.clear()
        backend_main.app.openapi_schema = None
        backend_main.app.router.lifespan_context = _noop_lifespan
        try:
            with TestClient(backend_main.app) as client:
                response = client.post("/review", json=HERO_REVIEW_REQUEST)
            if response.status_code != 200:
                raise RuntimeError(f"hero /review failed: {response.status_code} {response.text}")
            payload = response.json()
        finally:
            backend_main.app.router.lifespan_context = original_lifespan
            backend_main._state.clear()

    policy = payload.get("policy_decision") or {}
    findings = payload.get("findings") or []
    if payload.get("send_allowed") is not False or policy.get("send_allowed") is not False:
        raise RuntimeError("hero response must show send_allowed=false")
    if policy.get("decision") != "block":
        raise RuntimeError("hero response must produce policy_decision=block")
    if not any(finding.get("category") == "PII" for finding in findings):
        raise RuntimeError("hero response must include at least one PII finding")
    if not any(finding.get("category") == "MNPI" for finding in findings):
        raise RuntimeError("hero response must include at least one MNPI finding")
    if not all(finding.get("legal_basis") for finding in findings):
        raise RuntimeError("hero response findings must include legal_basis")
    return payload


def _select_finding(
    findings: list[dict[str, Any]],
    *,
    category: str,
    preferred_rules: tuple[str, ...],
) -> dict[str, Any]:
    for rule in preferred_rules:
        for finding in findings:
            if finding.get("category") == category and finding.get("rule") == rule:
                return finding
    for finding in findings:
        if finding.get("category") == category:
            return finding
    raise RuntimeError(f"hero response has no {category} finding")


def _suggestion_for(response_payload: dict[str, Any], finding_id: str) -> str:
    for suggestion in response_payload.get("suggestions") or []:
        if suggestion.get("finding_id") == finding_id:
            return str(suggestion.get("rationale") or "")
    return ""


def _truncate(value: str, limit: int) -> str:
    compact = " ".join(value.replace("→", "=>").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _markdown_inline(value: Any) -> str:
    return str(value).replace("|", "\\|")


def build_hero_markdown(response_payload: dict[str, Any]) -> str:
    findings = list(response_payload.get("findings") or [])
    pii = _select_finding(findings, category="PII", preferred_rules=("sg_nric_fin",))
    mnpi = _select_finding(
        findings,
        category="MNPI",
        preferred_rules=("transaction_codename", "definitive_agreement", "material_event"),
    )
    pii_rationale = _suggestion_for(response_payload, str(pii["id"]))
    mnpi_rationale = _suggestion_for(response_payload, str(mnpi["id"]))
    policy = response_payload["policy_decision"]
    required_actions = ", ".join(policy.get("required_actions") or [])
    blocking = ", ".join(policy.get("blocking_findings") or [])

    return "\n".join(
        [
            "## 60-second verdict",
            "",
            "Generated by `python3 scripts/export_openapi_examples.py` from a real local `/review` run. "
            "Full artifacts: [`request`](./docs/api/review_hero_request.json), "
            "[`response`](./docs/api/review_hero_response.json).",
            "",
            "| Confidential input | Junas verdict |",
            "|---|---|",
            "| <pre>Subject: Project Raven draft<br><br>"
            "Before Monday's announcement, send Dr Jane Tan S1234567D the draft SPA. "
            "Project Raven will acquire GlobalTech for USD 2.5 billion; keep this off ChatGPT unless redacted.</pre> "
            "| **`send_allowed: false`**<br>`policy_decision: block`<br>"
            f"`overall_risk: {response_payload['overall_risk']}`<br>"
            f"`pii_score: {response_payload['pii_score']}` / `mnpi_score: {response_payload['mnpi_score']}`<br>"
            f"`required_actions: {required_actions}` |",
            "",
            "| Finding | Generated legal basis | Generated citation string |",
            "|---|---|---|",
            f"| `{pii['category']}:{pii['rule']}` on `{_markdown_inline(pii['matched_text'])}` "
            f"| `{_markdown_inline(pii['legal_basis'])}` | {_markdown_inline(_truncate(pii_rationale, 260))} |",
            f"| `{mnpi['category']}:{mnpi['rule']}` on `{_markdown_inline(mnpi['matched_text'])}` "
            f"| `{_markdown_inline(mnpi['legal_basis'])}` | {_markdown_inline(_truncate(mnpi_rationale, 260))} |",
            "",
            f"`blocking_findings: {blocking}`",
        ]
    )


def write_review_hero_artifacts(output_dir: Path) -> dict[str, Path]:
    response_payload = _run_hero_review()
    request_path = output_dir / "review_hero_request.json"
    response_path = output_dir / "review_hero_response.json"
    markdown_path = output_dir / "review_hero.md"
    request_path.write_text(json.dumps(HERO_REVIEW_REQUEST, indent=2) + "\n", encoding="utf-8")
    response_path.write_text(json.dumps(response_payload, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(build_hero_markdown(response_payload) + "\n", encoding="utf-8")
    return {"request": request_path, "response": response_path, "markdown": markdown_path}


def update_readme_hero(readme_path: Path, hero_markdown: str) -> None:
    original = readme_path.read_text(encoding="utf-8")
    replacement = f"{HERO_MARKER_START}\n{hero_markdown}\n{HERO_MARKER_END}"
    if HERO_MARKER_START in original and HERO_MARKER_END in original:
        before, rest = original.split(HERO_MARKER_START, 1)
        _, after = rest.split(HERO_MARKER_END, 1)
        updated = before.rstrip() + "\n\n" + replacement + after
    else:
        anchor = "## Table of Contents"
        if anchor not in original:
            raise RuntimeError("README Table of Contents anchor not found")
        before, after = original.split(anchor, 1)
        updated = before.rstrip() + "\n\n" + replacement + "\n\n" + anchor + after
    readme_path.write_text(updated, encoding="utf-8")


def main() -> int:
    import junas.backend.main as backend_main

    parser = argparse.ArgumentParser(description="Export Postman collection and curl snippets from OpenAPI")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL used in generated examples",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "docs" / "api"),
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--skip-readme-hero",
        action="store_true",
        help="Write generated API artifacts without updating the README hero block.",
    )
    args = parser.parse_args()

    openapi = backend_main.app.openapi()
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(components, dict):
        components = {}

    operations: list[tuple[str, str, dict[str, Any]]] = []
    for path in sorted(openapi.get("paths", {}).keys()):
        methods = openapi["paths"].get(path, {})
        if not isinstance(methods, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            operation = methods.get(method)
            if isinstance(operation, dict):
                operations.append((path, method, operation))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    collection = {
        "info": {
            "name": "Junas API (Generated from OpenAPI)",
            "description": "Generated from junas.backend.main:app OpenAPI contract.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "baseUrl", "value": args.base_url},
            {"key": "junasApiKey", "value": "dev-secret"},
            {"key": "junasLocalToken", "value": ""},
        ],
        "item": [
            build_postman_item(
                base_url_var="baseUrl",
                path=path,
                method=method,
                operation=operation,
                components=components,
            )
            for path, method, operation in operations
        ],
    }

    postman_path = output_dir / "junas.postman_collection.json"
    postman_path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")

    curl_lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "",
        "# Generated from junas.backend.main:app OpenAPI contract.",
        'BASE_URL="${BASE_URL:-http://localhost:8000}"',
        "",
    ]
    for index, (path, method, operation) in enumerate(operations):
        if index > 0:
            curl_lines.append("")
        curl_lines.append(
            build_curl_block(path=path, method=method, operation=operation, components=components)
        )

    curl_path = output_dir / "curl_snippets.sh"
    curl_path.write_text("\n".join(curl_lines) + "\n", encoding="utf-8")
    curl_path.chmod(0o755)

    hero_paths = write_review_hero_artifacts(output_dir)
    if not args.skip_readme_hero:
        update_readme_hero(ROOT / "README.md", hero_paths["markdown"].read_text(encoding="utf-8").rstrip())

    print(f"Wrote {postman_path}")
    print(f"Wrote {curl_path}")
    print(f"Wrote {hero_paths['request']}")
    print(f"Wrote {hero_paths['response']}")
    print(f"Wrote {hero_paths['markdown']}")
    if not args.skip_readme_hero:
        print(f"Updated {ROOT / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
