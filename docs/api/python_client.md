# Python Client

Noupe ships typed sync and async Python clients for the same backend HTTP API.
They are not separate backends and do not introduce a second API contract. They call the same Noupe service, with the same endpoints and response models.

Canonical import:

```python
from noupe import NoupeClient
from noupe import AsyncNoupeClient
```

Repo-local compatibility imports also exist:

```python
from backend.client import NoupeClient
from backend.client import AsyncNoupeClient
from api.client import NoupeClient
from api.client import AsyncNoupeClient
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

- `NoupeClient`: use in standard blocking Python scripts, notebooks, CLIs, and simple backend jobs
- `AsyncNoupeClient`: use inside `asyncio` applications such as FastAPI handlers, async workers, and services that already use `await`
- both call the same Noupe backend routes and return the same typed response models

## Quickstart

Synchronous:

```python
from noupe import NoupeClient

with NoupeClient("http://localhost:8000") as client:
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

from noupe import AsyncNoupeClient


async def main() -> None:
    async with AsyncNoupeClient("http://localhost:8000") as client:
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
NOUPE_API_KEY="dev-secret" ./scripts/launch/run_backend_only.sh
python scripts/examples/sync_client_example.py \
  "Restricted board memo" \
  --api-key dev-secret
```

Returned values are typed Pydantic models from `noupe.backend.schemas`, so they support:

```python
result.model_dump()
result.model_dump_json(indent=2)
```

## API Key

```python
from noupe import NoupeClient

with NoupeClient("http://localhost:8000", api_key="dev-secret") as client:
    result = client.classify(text="Draft board memo")
```

## Batch Classification

```python
from noupe import NoupeClient

items = [
    {"text": "Acme Corp is acquiring GlobalTech next quarter.", "include_offending_spans": True},
    {"text": "Public press release for next week's earnings call."},
]

with NoupeClient("http://localhost:8000") as client:
    batch = client.classify_batch(items)
    for result in batch.results:
        print(result.classification)
```

## Pre-Send Review

Use `review` when the caller needs PII and MNPI findings, source/destination jurisdiction handling, scores, and remediation suggestions before sending a document:

```python
from noupe import NoupeClient

with NoupeClient("http://localhost:8000") as client:
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

For file inputs, pass `document_base64`, `document_filename`, and optionally `document_mime_type`. Supported v1 extraction paths are plain text, DOCX, and PDF when `pypdf` is installed.

## Runtime Status

```python
from noupe import NoupeClient

with NoupeClient("http://localhost:8000") as client:
    print(client.health())
    print(client.ready())
    print(client.diagnostics())
```

Async variant:

```python
import asyncio

from noupe import AsyncNoupeClient


async def main() -> None:
    async with AsyncNoupeClient("http://localhost:8000") as client:
        print(await client.health())
        print(await client.ready())
        print(await client.diagnostics())


asyncio.run(main())
```

## Error Handling

HTTP errors raise `NoupeAPIError` and include the status code plus parsed error detail:

```python
from noupe import NoupeAPIError, NoupeClient

try:
    with NoupeClient("http://localhost:8000", api_key="wrong-key") as client:
        client.classify(text="Public update")
except NoupeAPIError as exc:
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

The async client exposes the same method names and endpoint mapping, but each method is awaited:

- `await async_client.health()`
- `await async_client.ready()`
- `await async_client.diagnostics()`
- `await async_client.metrics()`
- `await async_client.classify(...)`
- `await async_client.classify_batch(...)`
- `await async_client.classify_many(...)`
- `await async_client.review(...)`
