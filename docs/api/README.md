# API Integrations

Generated integration artifacts from the live OpenAPI contract:

- `kaypoh.postman_collection.json`: Postman collection
- `curl_snippets.sh`: runnable cURL snippets for each endpoint
- `python_client.md`: typed Python integration client usage
- `versioning.md`: root endpoint and future `/v1` compatibility rules
- `idempotency.md`: request id and adapter retry guidance

Runnable local examples:

- `scripts/examples/sync_client_example.py`
- `scripts/examples/async_client_example.py`

Regenerate:

```sh
python3 scripts/export_openapi_examples.py
```
