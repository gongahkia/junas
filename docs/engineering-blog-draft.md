# 30 FPS OCR-and-redact on a laptop, in Rust

Draft status: companion engineering post for the Aki repository. This is intended for a blog, launch post, or project write-up after the release/install path is ready.

Repo: <https://github.com/gongahkia/aki>

Demo: [`asset/demo/hero-ascii-redaction.gif`](../asset/demo/hero-ascii-redaction.gif)

Architecture reference: [`ARCHITECTURE.md`](../ARCHITECTURE.md)

Benchmark reference: [`BENCHMARKS.md`](../BENCHMARKS.md)

## The Problem

Screen sharing makes accidental disclosure easy. A terminal can reveal an environment variable, an editor can show a token, and a dashboard can expose an email address or IP-shaped value. Browser extensions only help when the sensitive text lives in a browser DOM. They do not cover terminals, local editors, design tools, documents, or arbitrary app windows.

Aki takes a pixel-level approach: capture frames, find sensitive-looking text in those pixels, redact the matching regions, and send the transformed frame to a local output sink.

The goal is not perfect prevention. Newly appearing text can be visible before OCR catches it, and OCR can miss small or low-contrast text. The engineering target is narrower and measurable: keep the pipeline current enough for screen-sharing use while bounding latency and avoiding unbounded queues.

## Pipeline Shape

The runtime is a four-stage pipeline:

```text
capture -> detect -> transform -> output
```

The capture stage samples screen or PTY frames. The detect stage turns changed pixels into OCR text regions, scans those regions with built-in and configured rules, expands matches, and emits redaction regions. The transform stage applies blur, pixelate, cartoon, ASCII, or neural fallback transforms to those regions. The output stage writes already-redacted frames to a virtual camera, MJPEG stream, OBS adapter path, or MP4 recorder.

Those stages communicate through bounded queues with capacity three. When a downstream stage is full, the pipeline drops incoming work and increments a counter instead of blocking capture. That is a deliberate real-time tradeoff: a late redacted frame is less useful than a current frame with measured dropped-frame behavior.

Implementation detail: this backpressure policy lives in `privacy-core/src/pipeline_runner.rs` and the bounded channel definitions live in `privacy-core/src/pipeline.rs`.

## Frame Diffing

The expensive part is not scanning regexes. It is OCR.

Running OCR on a full display every frame is too expensive for a steady interactive pipeline. Aki divides the frame into an adaptive grid. The default target is `8x6`. `FrameDiff` marks cells dirty when pixels change; unchanged cells reuse cached OCR results. The first frame and resolution changes invalidate the cache.

This gives the detector a way to spend OCR work on changed regions rather than the whole display. A terminal cursor blink, a changing counter, or a single edited line should not force full-frame OCR if most cells are unchanged.

Implementation detail: when detection work exceeds the 33 ms frame budget, the pipeline can reduce grid detail toward `2x2` and lower transform quality. When detection falls below half budget, the grid recovers toward the default target.

## OCR And Rules

Aki uses OCR text regions as detector input, then scans text with a runtime pattern registry. The registry includes built-in secret patterns, PII patterns, user-defined patterns, and optional imported rule packs.

Matching text is not redacted as a single tight OCR rectangle. The box is expanded and merged before transform. The detector pads matches for OCR jitter and extends common `KEY=value` and `label: value` layouts to the end of the line so the value is covered even when the exact OCR bounds are imperfect.

The detector also suppresses duplicate events for one second. That does not affect redaction; it keeps logs, counters, and UI events readable during repeated frames.

## Transform Path

Transforms receive a raw frame plus the detected regions. They do not own detection logic. This keeps output sinks simple: by the time a frame reaches the virtual camera, MJPEG stream, OBS path, or MP4 recorder, sensitive regions have already been transformed.

Mode changes use a 10-frame blend between the previous and new transform. The practical reason is to avoid flashing raw pixels or abrupt visual state during a transform switch.

The output paths are deliberately local. The project does not need a cloud service to inspect frames, and the documented v1 behavior has no telemetry endpoint.

## Benchmark Evidence

The benchmark numbers currently available are synthetic. They measure regex scan, region expansion, and pixelate transform over generated RGBA frames. They do not include Tesseract OCR, ScreenCaptureKit capture, preview rendering, or output encoding.

Measured on 2026-06-03 with an Apple M3, 16 GiB memory, macOS 26.2, and Rust 1.93.0:

| Resolution | Frames | FPS | Mean frame latency | Recall |
|------------|--------|-----|--------------------|--------|
| 1920x1080 | 120 | 260.8 | 3.83 ms | 1.00 |
| 2560x1440 | 90 | 146.0 | 6.85 ms | 1.00 |
| 3840x2160 | 45 | 68.1 | 14.69 ms | 1.00 |

Peak RSS for that run was `189,267,968` bytes, about `180.5 MiB`.

The fixture corpus recall test detected `6 / 6` expected synthetic patterns across three held-out frames. The approximate synthetic OCR cell hit-rate was `17 / 144 = 11.8%` using the default `8x6` grid across those frames.

These numbers support one claim: the non-OCR redaction path has headroom in the synthetic benchmark. They do not prove full live capture is always above 30 FPS. Live performance also pays for ScreenCaptureKit, image conversion, Tesseract, preview cloning, terminal rendering, and output sinks.

## Why Rust

Rust is useful here because the pipeline is mostly explicit data movement: frame buffers, bounded queues, detector output, and sink writes. The code needs predictable ownership around large RGBA buffers and should make it hard to accidentally share mutable frame state across stages.

The current design keeps the Rust binary as the single engine. The macOS menu-bar app is a sidecar controller over a local protocol, not a second implementation of capture or redaction.

## What I Would Measure Next

The synthetic baseline is a regression check, not a launch claim. The next useful measurements are:

- 60-second live capture FPS and dropped frames on a stock Mac.
- First-frame and changed-cell OCR latency with Tesseract enabled.
- Multi-display cost at common display combinations.
- Output sink overhead for MJPEG, virtual camera, and MP4 recording.
- Missed-redaction examples for tiny, low-contrast, or fast-changing text.

Those measurements should live next to the existing benchmarks and include hardware, OS, command, and caveat context.

## Closing

Aki is not trying to make screenshots safe by promise. It is a local pipeline that tries to keep redaction work close to current pixels, drops stale work under load, and publishes the limits alongside the benchmark numbers.

The interesting engineering problem is not only detection accuracy. It is keeping capture, OCR, transform, and output coordinated tightly enough that the user sees current redacted frames instead of a delayed backlog.
