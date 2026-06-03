# Benchmarks

Benchmarks should be reproducible and tied to hardware context. The numbers below are a starting baseline, not a promise that every screen, font, display, or OCR workload will behave the same.

## Hardware Context

Measured on 2026-06-03:

| Field | Value |
|-------|-------|
| CPU | Apple M3 |
| Memory | 16 GiB |
| OS | macOS 26.2 (25C56) |
| Rust | rustc 1.93.0 / cargo 1.93.0 |

## Commands

Run the held-out fixture recall check:

```console
$ cargo test -p privacy-core synthetic_fixture_corpus_recall_is_tracked -- --nocapture
```

Run the synthetic resolution benchmark:

```console
$ /usr/bin/time -l cargo test -p privacy-core synthetic_resolution_benchmark -- --ignored --nocapture
```

For live capture FPS and dropped-frame behavior, run a 60-second headless session and inspect the generated session log:

```console
$ cargo run -p privacy-tui -- --headless --source screen --display 0 --output mjpeg
$ tail -n 20 ~/.config/ascii-privacy/sessions/headless_*.log
```

## Synthetic Resolution Baseline

Command:

```console
$ /usr/bin/time -l cargo test -p privacy-core synthetic_resolution_benchmark -- --ignored --nocapture
```

This benchmark generates synthetic RGBA frames, runs regex scan, region expansion, and a pixelate transform. It does **not** run Tesseract OCR or ScreenCaptureKit capture.

| Resolution | Frames | FPS | Mean frame latency | Recall |
|------------|--------|-----|--------------------|--------|
| 1920x1080 | 120 | 260.8 | 3.83 ms | 1.00 |
| 2560x1440 | 90 | 146.0 | 6.85 ms | 1.00 |
| 3840x2160 | 45 | 68.1 | 14.69 ms | 1.00 |

Peak RSS from `/usr/bin/time -l`: `189,267,968` bytes, about `180.5 MiB`.

## Fixture Corpus

Corpus path:

```console
privacy-core/fixtures/redaction_corpus/synthetic-corpus.toml
```

The corpus is synthetic and held out from the pattern definitions. Fixture values use `AKI_FIXTURE` and `DO_NOT_USE` markers rather than real credentials.

| Frame | Resolution | Expected detections | Detected | Recall |
|-------|------------|---------------------|----------|--------|
| `terminal_1080p_env_and_secret` | 1920x1080 | 2 | 2 | 1.00 |
| `editor_1440p_pii_and_password` | 2560x1440 | 2 | 2 | 1.00 |
| `dashboard_4k_network_and_key_header` | 3840x2160 | 2 | 2 | 1.00 |

Overall fixture recall: `6 / 6 = 1.00`.

Approximate OCR cell hit-rate for the fixture corpus: `17 / 144 = 11.8%`, using the default 8x6 grid across three frames. This is synthetic text-region occupancy, not a live Tesseract dirty-cell measurement.

## Limits

The synthetic benchmark is useful for tracking redaction transform cost and fixture recall, but it is not full end-to-end capture performance.

Live performance is lower because the real pipeline also pays for:

- ScreenCaptureKit frame delivery,
- TIFF conversion before OCR,
- Tesseract OCR latency,
- incremental OCR grid scheduling,
- preview cloning and terminal rendering,
- output sink encoding or virtual-camera writes.

OCR is the least stable part of the pipeline. Tiny text, low contrast, animation, display scaling, and first-frame appearance can reduce recall or add latency. Treat these numbers as a regression baseline, not as proof that every secret on a real screen is caught.
