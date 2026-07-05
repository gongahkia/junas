# Benchmarks

This repo currently benchmarks Junas text/document review and rewrite paths. It does not ship a legacy live-screen pipeline, so FPS at 1080p/1440p/4K, FrameDiff cell hit-rate, OBS output, virtual-camera output, and video redaction recall are not claimed here.

## Hardware Context

Latest local benchmark context:

- Date: 2026-07-04
- OS: macOS 26.5.1 build 25F80
- CPU: Apple M3
- Memory: 16 GB
- Runtime: `uv`; latency corpus run used CPython 3.12.12, SLO run used CPython 3.13.5

Reproduce hardware capture:

```sh
sw_vers
sysctl -n machdep.cpu.brand_string
sysctl -n hw.memsize
```

## Reproducible Commands

Text latency corpus:

```sh
./scripts/benchmark_latency_corpus.sh --repetitions 1 --warmups 0 --port 8131
```

Review/anonymize p95 SLO gate:

```sh
uv run python scripts/check_latency_slo.py --write-report
```

Detector recall and precision gates:

```sh
uv run python scripts/recall_gate.py
uv run python scripts/recall_gate.py --corpus test/fixtures/legal-corpus-adversarial
uv run python scripts/evaluate_candidate_corpus.py \
  --corpus test/fixtures/legal-corpus-candidates \
  --output reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json
```

External PII breadth eval, when the external fixture is present:

```sh
./scripts/fetch_tab_fixture.sh
uv run python scripts/run_tab_eval.py
```

## Current Latency Results

Generated artifact: [`reports/latency_2026-07-04_09-23-21.txt`](./reports/latency_2026-07-04_09-23-21.txt). JSON and CSV siblings are committed with the same timestamp.

| Fixture | Words | Chars | Runs | p95 ms | Mean server ms | Notes |
|---|---:|---:|---:|---:|---:|---|
| `outlook-short-email.txt` | 69 | 493 | 1 | 3.963 | 2.199 | Outlook-shaped short email. |
| `browser-prompt.txt` | 124 | 818 | 1 | 5.478 | 3.098 | Browser prompt fixture. |
| `legal-memo.txt` | 536 | 3,855 | 1 | 15.993 | 13.871 | Legal memo fixture. |
| `dms-upload-size-document.txt` | 601 | 4,308 | 1 | 17.307 | 15.251 | DMS upload-shaped text. |
| `1k.txt` | 1,334 | 8,728 | 1 | 36.406 | 34.330 | Default SLO fixture size class. |
| `2k.txt` | 2,481 | 16,099 | 1 | 66.269 | 63.751 | Medium text fixture. |
| `5k.txt` | 5,445 | 40,721 | 1 | 155.619 | 151.980 | Large text fixture. |
| `10k.txt` | 10,368 | 76,943 | 1 | 329.086 | 318.816 | Largest committed latency fixture; run degraded. |

Single-run corpus numbers are smoke evidence, not statistically stable p95 latency. Use higher repetitions before citing performance externally.

## Review And Rewrite SLO Results

Generated artifact: [`reports/latency_slo_2026-07-04_09-24-09.json`](./reports/latency_slo_2026-07-04_09-24-09.json).

| Case | Fixture KB | Repetitions | p95 ms | Budget ms | Policy p95 ms | Status |
|---|---:|---:|---:|---:|---:|---|
| `review.strict` | 8.5 | 5 | 33.981 | 500 | 0.042 | PASS |
| `review.audit_grade` | 8.5 | 5 | 32.530 | 3000 | 0.030 | PASS |
| `anonymize.strict` | 8.5 | 5 | 32.404 | 800 | 0.027 | PASS |
| `anonymize.audit_grade` | 8.5 | 5 | 32.947 | 4000 | 0.033 | PASS |

`anonymize.*` is the current rewrite/redaction benchmark proxy because Junas transforms detected spans into deterministic placeholders or redacted document artifacts; live video redaction is not implemented in this repo.

## Fixture Corpora

| Corpus | Count | Purpose |
|---|---:|---|
| `test/fixtures/latency-corpus/` | 8 text fixtures plus README | Latency smoke fixtures for email, browser prompt, legal memo, DMS upload, and 1k/2k/5k/10k text sizes. |
| `test/fixtures/legal-corpus/` | 147 text fixtures | Locked baseline corpus for legal PII/MNPI recall gates. |
| `test/fixtures/legal-corpus-adversarial/` | 134 text fixtures | Precision and adversarial recall corpus, including OCR-like and false-positive bait. |
| `test/fixtures/legal-corpus-candidates/` | 1,428 text fixtures and 1,428 labels | Reviewed candidate corpus across 17 jurisdictions. |
| `test/test_anonymize.py` and `test/test_image_scan.py` | test fixtures in code | Rewrite/redaction fixtures for `/anonymize`, `/redact`, image redaction, and DOCX redacted-document output. |

Current promoted candidate report: [`reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json`](./reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json).

Summary from that report:

- Documents: 1,428
- Strict expected labels: 17,552
- Strict matched labels: 17,552
- Strict missed labels: 0
- Candidate recall: 1.0000
- Candidate precision: 0.9269
- Ideal candidate recall: 0.4234
- Must-not-detect violations: 0

External ai4privacy proxy breadth summary: [`reports/current/ai4privacy_pii_masking_200k_en_us_en_gb_eval.json`](./reports/current/ai4privacy_pii_masking_200k_en_us_en_gb_eval.json). It covers 2,965 documents and 9,958 gold spans across English US/UK proxy slices, with recall 0.371295 for the US proxy slice and 0.108015 for the UK proxy slice. Treat that as breadth-gap evidence, not a promoted product accuracy claim.

## OCR And Video Limits

Image OCR and redacted-image output exist for document/image flows, but OCR accuracy, small-text behavior, and image redaction coverage are not represented by the latency numbers above. Run the image tests before changing OCR/redaction behavior:

```sh
UV_PROJECT_ENVIRONMENT=.venv-uv UV_PYTHON=3.12 PYTHONPATH=src \
  JUNAS_JOURNAL_KEY=test-journal-key \
  uv run pytest test/test_image_scan.py test/test_anonymize.py -q
```

No current benchmark measures RSS, FPS, OCR cell hit-rate, FrameDiff behavior, transform crossfade, MP4 output, OBS integration, or virtual-camera output. Do not cite those metrics until a current Junas implementation and fixture corpus exist.
