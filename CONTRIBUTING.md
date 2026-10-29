# Contributing

Work on classifier accuracy, document/OCR coverage, evaluation independence and reproducibility. Product interfaces and deployment work are deferred until detection quality is established.

```sh
uv sync --extra dev
uv run pytest
uv run python scripts/evaluate_accuracy.py
uv run python scripts/generate_accuracy_doc.py --check
```

For every detector change, add a positive case and an appropriate hard negative, inspect missed/unexpected results, and check both recall and precision. Keep independent test labels separate from model-generated candidates. Do not edit a lock to make a regression pass. Use a documented, human-reviewed promotion when a baseline deliberately changes.

Do not enable remote providers in normal tests or CI. Use mocked transport for provider contract tests. Keep external corpora out of Git and avoid including real personal data or credentials in fixtures.

Format and lint changed Python files with Ruff. Run the full retained test suite before proposing a change. Describe the affected detector family, evaluation configuration, measured benefit, and unresolved misses.
