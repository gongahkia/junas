# Contributing

Work on text-classifier accuracy, source-evidence integrity, evaluation quality and reproducibility. Native-document/OCR support and product interfaces are outside the current scope. The opt-in automated synthetic-corpus workflow is described in [its research contract](docs/automated-corpus.md).

```sh
uv sync --extra dev
uv run pytest
uv run python scripts/evaluate_accuracy.py
uv run python scripts/generate_accuracy_doc.py --check
```

For every detector change, add a positive case and an appropriate hard negative, inspect missed/unexpected results, and check both recall and precision. Keep independent test labels separate from model-generated candidates. Do not edit a lock to make a regression pass. Use a documented, human-reviewed promotion when a baseline deliberately changes.

Do not enable remote providers in normal tests or CI. Use mocked transport for provider contract tests. Keep external corpora out of Git and avoid including real personal data or credentials in fixtures.

Format and lint changed Python files with Ruff. Run the full retained test suite before proposing a change. Describe the affected detector family, evaluation configuration, measured benefit, and unresolved misses.
