# Junas

A research codebase for accurate detection of personal data (PII) and material non-public information (MNPI) in text and documents.

The current priority is to measure and improve the classifier. The repository contains the detection engine, document extraction and optional OCR, jurisdiction rules, experimental advisory layers, labelled corpora, and evaluation tools. Product interfaces, HTTP services, approval workflows, rewriting services, deployment templates, and desktop distribution have been removed. Their previous versions remain in Git history.

## Run locally

Python 3.11 or newer:

```sh
uv sync --extra dev
uv run junas classify --text 'Contact alice@example.com about the confidential acquisition.'
uv run junas classify --file document.docx --source-jurisdiction SG
printf 'Contact alice@example.com' | uv run junas classify --file -
```

The command emits JSON containing findings, offsets, severity, PII/MNPI scores, citations, extraction metadata, and degraded modes. Offsets refer to `document.text` in that output. `SAFE` means no configured risk signal was detected; it is not proof that the input contains no sensitive information. Exit codes: `0` completed analysis, `1` degraded analysis, `2` invalid input or analysis failure. Risk classification itself does not determine the exit code.

The default configuration is deterministic and makes no provider calls. Unsupported or unreadable documents are rejected by default. Optional OCR and NER are separate experiments:

```sh
uv sync --extra dev --extra ner
uv run python -m spacy download en_core_web_sm
JUNAS_LOCAL_NER_FALLBACK=1 uv run junas classify --file sample.txt

# Install native Tesseract separately before enabling local OCR.
uv sync --extra dev --extra ocr
JUNAS_IMAGE_SCAN_PROVIDER=tesseract uv run junas classify --file scan.png
```

## Measure accuracy

```sh
uv run python scripts/evaluate_accuracy.py
uv run pytest
```

The accuracy command evaluates all nine locked corpora, writes `reports/current/core_accuracy.json`, and fails on an existing recall/precision regression. It never changes labels or lowers locks. External evaluations run when their fixtures are available; missing external datasets are explicitly reported, not counted as passing. Use `--external require` to require both external evaluations.

```sh
./scripts/fetch_tab_fixture.sh
uv run python scripts/fetch_ai4privacy_fixture.py
uv run python scripts/evaluate_accuracy.py --external require
```

Internal fixture agreement, independently labelled external results, and OCR/extraction results answer different questions. Keep them separate. Internal near-perfect regression scores do not establish general accuracy; the committed external reports expose substantial coverage gaps. See [evaluation methodology](BENCHMARKS.md), [current baseline](docs/baseline.md), and [limitations](docs/known-limitations.md).

## Python library

```python
from junas import ReviewPipeline, classify_text

result = classify_text("Contact alice@example.com", source_jurisdiction="SG")
for finding in result.findings:
    print(finding.rule, finding.matched_text, finding.severity)

analysis = ReviewPipeline().review_file("document.docx", source_jurisdiction="SG")
print(analysis.to_dict())
```

For direct detector experiments, `PreSendReviewEngine.review()` remains available. Related-document experiments can pass an explicit `context_terms` set; the classifier does not create persistent review sessions.

## Optional Secret Rule Packs

Local Gitleaks TOML packs have no cloud dependency. Set `JUNAS_GITLEAKS_RULE_PACKS` to opt in; findings carry `EXTERNAL_SECRET_RULE_PACK` provenance. Use `junas rules test` to evaluate a pack against a synthetic fixture. See [secret packs](docs/secret-rule-packs.md) and [community packs](docs/community-rule-packs.md).

## Repository map

- `src/junas/review/`: detectors, scoring, jurisdiction packs, citations, parsing, OCR and optional advisory interfaces.
- `src/junas/pipeline.py`: local document-to-findings orchestration.
- `src/junas/advisory/`, `src/junas/external/`: explicitly configured retrieval/LLM experiments and privacy gates.
- `test/fixtures/`: labelled regression and adversarial corpora; external fixtures are fetched separately.
- `scripts/`: corpus curation, provenance checks, evaluation and miss analysis.
- `training/`: experimental calibration and distillation, separate from the default runtime.
- `reports/`: measured results, including historical baselines.

Read [architecture](ARCHITECTURE.md), [contributing](CONTRIBUTING.md), and the [documentation index](docs/README.md).
