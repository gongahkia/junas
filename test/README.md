# Test Folder

This folder contains the automated test suite and test fixtures.

- API contract tests
- observability and startup-path tests
- launcher and benchmark smoke tests
- backend-only layout and archived-asset pruning tests
- pre-send review and anonymization tests
- `fixtures/latency-corpus/` is the canonical home for benchmark input `.txt` files
- `fixtures/external/text-anonymization-benchmark/` is the ignored, read-only TAB clone populated by `scripts/fetch_tab_fixture.sh`
- `fixtures/external/ai4privacy-pii-masking-200k/` is the ignored, read-only ai4privacy fixture populated by `scripts/fetch_ai4privacy_fixture.py`
