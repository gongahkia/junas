# Python Client

Kaypoh ships typed sync and async Python clients for the same backend HTTP API.
They are not separate backends and do not introduce a second API contract. They call the same Kaypoh service, with the same endpoints and response models.

Canonical import:

```python
from kaypoh import KaypohClient
from kaypoh import AsyncKaypohClient
```

Repo-local module import:

```python
from kaypoh.client import KaypohClient
from kaypoh.client import AsyncKaypohClient
```

## Install

From this repository:

```sh
python -m pip install -e .
```

Start the backend first in a separate terminal:

```sh
./scripts/launch/run_backend_only.sh
```

## Which Client To Use

- `KaypohClient`: use in standard blocking Python scripts, notebooks, CLIs, and simple backend jobs
- `AsyncKaypohClient`: use inside `asyncio` applications such as FastAPI handlers, async workers, and services that already use `await`
- both call the same Kaypoh backend routes and return the same typed response models

## Quickstart

Synchronous:

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000") as client:
    result = client.classify(
        text="Acme Corp is acquiring GlobalTech for $2.5 billion next quarter.",
        entity_id="acme-corp",
        include_offending_spans=True,
    )

    print(result.classification)
    print(result.request_id)
    print(result.timings_ms)
```

Asynchronous:

```python
import asyncio

from kaypoh import AsyncKaypohClient


async def main() -> None:
    async with AsyncKaypohClient("http://localhost:8000") as client:
        result = await client.classify(
            text="Acme Corp is acquiring GlobalTech for $2.5 billion next quarter.",
            entity_id="acme-corp",
            include_offending_spans=True,
        )
        print(result.classification)
        print(result.request_id)


asyncio.run(main())
```

## Run The Included Examples

Sync example:

```sh
python scripts/examples/sync_client_example.py \
  "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter." \
  --include-offending-spans
```

Async example:

```sh
python scripts/examples/async_client_example.py \
  "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter." \
  --include-offending-spans
```

Authenticated example:

```sh
KAYPOH_API_KEY="dev-secret" ./scripts/launch/run_backend_only.sh
python scripts/examples/sync_client_example.py \
  "Restricted board memo" \
  --api-key dev-secret
```

Returned values are typed Pydantic models from `kaypoh.backend.schemas`, so they support:

```python
result.model_dump()
result.model_dump_json(indent=2)
```

## API Key

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000", api_key="dev-secret") as client:
    result = client.classify(text="Draft board memo")
```

## Batch Classification

```python
from kaypoh import KaypohClient

items = [
    {"text": "Acme Corp is acquiring GlobalTech next quarter.", "include_offending_spans": True},
    {"text": "Public press release for next week's earnings call."},
]

with KaypohClient("http://localhost:8000") as client:
    batch = client.classify_batch(items)
    for result in batch.results:
        print(result.classification)
```

## Pre-Send Review

Use `review` when the caller needs PII and MNPI findings, source/destination jurisdiction handling, scores, and remediation suggestions before sending a document:

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000") as client:
    result = client.review(
        text="Please send to Tan S1234567D. Confidential: Acme Corp will acquire GlobalTech before announcement.",
        source_jurisdiction="SG",
        destination_jurisdiction="US",
        document_type="research_note",
        entity_id="Acme Corp",
    )

    print(result.overall_risk)
    print(result.pii_score, result.mnpi_score)
    print(result.findings)
    print(result.suggestions)
```

For file inputs, pass `document_base64`, `document_filename`, and optionally `document_mime_type`. Supported v1 extraction paths are plain text, DOCX, and PDF when `pypdf` is installed. PDF review returns degraded fail-open responses when the text layer is absent or too sparse unless `KAYPOH_DOCUMENT_FAIL_CLOSED=1` is set, and metadata leakage findings are returned under `result.document.metadata_findings`.

To scrub supported container metadata before sharing a file:

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000") as client:
    scrubbed = client.scrub_document(
        document_base64=encoded_docx,
        document_filename="draft.docx",
    )

    print(scrubbed.actions)
    print(scrubbed.document_base64)
```

## Pre-Send Privacy Operations

Use `pseudonymize` when the caller needs deterministic placeholders plus a local mapping table for later `/reidentify`:

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000") as client:
    result = client.pseudonymize(
        text="Send Dr Jane Tan S1234567D the confidential draft.",
        source_jurisdiction="SG",
        destination_jurisdiction="US",
        document_type="email",
    )

    print(result.pseudonymized_text)
    print(result.mapping)
    print(result.replacements)
```

Use `anonymize` for irreversible v2 placeholder-only output. It returns no mapping and no `original_text` in replacements. Use `redact` for opaque markers that do not expose entity type.

Set `include_mnpi_scalars=False` when monetary amounts, percentages, and large numbers should remain in the output as review-only findings instead of automatic replacements.

## Runtime Status

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000") as client:
    print(client.health())
    print(client.ready())
    print(client.diagnostics())
```

Async variant:

```python
import asyncio

from kaypoh import AsyncKaypohClient


async def main() -> None:
    async with AsyncKaypohClient("http://localhost:8000") as client:
        print(await client.health())
        print(await client.ready())
        print(await client.diagnostics())


asyncio.run(main())
```

## Error Handling

HTTP errors raise `KaypohAPIError` and include the status code plus parsed error detail:

```python
from kaypoh import KaypohAPIError, KaypohClient

try:
    with KaypohClient("http://localhost:8000", api_key="wrong-key") as client:
        client.classify(text="Public update")
except KaypohAPIError as exc:
    print(exc.status_code)
    print(exc.detail)
```

## Method Mapping

- `client.health()` -> `GET /health`
- `client.ready()` -> `GET /ready`
- `client.diagnostics()` -> `GET /diagnostics`
- `client.metrics()` -> `GET /metrics`
- `client.classify(...)` -> `POST /classify`
- `client.classify_batch(...)` -> `POST /classify/batch`
- `client.classify_many(...)` -> convenience wrapper over `POST /classify/batch`
- `client.review(...)` -> `POST /review`
- `client.pseudonymize(...)` -> `POST /pseudonymize`
- `client.anonymize(...)` -> irreversible `POST /anonymize`
- `client.redact(...)` -> `POST /redact`

The async client exposes the same method names and endpoint mapping, but each method is awaited:

- `await async_client.health()`
- `await async_client.ready()`
- `await async_client.diagnostics()`
- `await async_client.metrics()`
- `await async_client.classify(...)`
- `await async_client.classify_batch(...)`
- `await async_client.classify_many(...)`
- `await async_client.review(...)`
- `await async_client.pseudonymize(...)`
- `await async_client.anonymize(...)`
- `await async_client.redact(...)`
