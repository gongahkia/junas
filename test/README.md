# Classifier tests

`uv run pytest` runs the retained detector, document parsing, OCR, provider contract, corpus curation and evaluation tests. Optional native OCR checks skip when Tesseract or its Python dependencies are absent.

`fixtures/` retains labelled synthetic corpora and the preserved OCR failure fixture. External TAB and ai4privacy datasets are fetched explicitly and ignored by Git. Corpus text mentioning email or prompts remains useful detection data; product adapter fixtures have been removed.

Use `uv run python scripts/evaluate_accuracy.py` for measurements. A passing unit suite or regression lock is not a general accuracy claim.
