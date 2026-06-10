#!/usr/bin/env python3
"""Export Postman and cURL examples from the backend OpenAPI contract."""

from __future__ import annotations

import argparse
import json
import sys
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


def build_postman_item(
    *,
    base_url_var: str,
    path: str,
    method: str,
    operation: dict[str, Any],
    components: dict[str, Any],
) -> dict[str, Any]:
    body_payload = build_request_body(operation, components)

    headers: list[dict[str, str]] = []
    if body_payload is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
    if path.startswith("/classify"):
        headers.append({"key": "X-API-Key", "value": "{{kaypohApiKey}}"})
    if path == "/local/pairing/approve":
        headers.append({"key": "X-Kaypoh-Local-Token", "value": "{{kaypohLocalToken}}"})

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

    return {
        "name": f"{method.upper()} {path}",
        "request": request_payload,
        "response": [],
        "description": operation.get("summary", ""),
    }


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
        lines.append('  -H "X-API-Key: ${KAYPOH_API_KEY:-dev-secret}" \\')
    if path == "/local/pairing/approve":
        lines.append('  -H "X-Kaypoh-Local-Token: ${KAYPOH_LOCAL_DAEMON_TOKEN}" \\')
    if body_payload is not None:
        compact = json.dumps(body_payload, separators=(",", ":"))
        lines.append(f"  -d '{compact}'")
    else:
        lines[-1] = lines[-1].rstrip(" \\")

    return "\n".join(lines)


def main() -> int:
    import backend.main as backend_main

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
            "name": "Kaypoh API (Generated from OpenAPI)",
            "description": "Generated from backend.main:app OpenAPI contract.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "baseUrl", "value": args.base_url},
            {"key": "kaypohApiKey", "value": "dev-secret"},
            {"key": "kaypohLocalToken", "value": ""},
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

    postman_path = output_dir / "kaypoh.postman_collection.json"
    postman_path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")

    curl_lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "",
        "# Generated from backend.main:app OpenAPI contract.",
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

    print(f"Wrote {postman_path}")
    print(f"Wrote {curl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
