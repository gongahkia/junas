# Architecture

`Aki` is built around a bounded real-time frame pipeline. The core rule is simple: do not let slow OCR or output work accumulate unbounded latency.

## Pipeline

```text
             raw frames                 text + regions             redacted frames
+-------------+   raw_tx cap=3   +------------+   cap=3   +---------------+   cap=3   +-------------+
| aki-capture | ---------------> | aki-detect | --------> | aki-transform | --------> | output sink |
| Screen/PTY  |                  | OCR+rules  |           | blur/pixel    |           | cam/http/mp4|
+-------------+                  +------------+           +---------------+           +-------------+
        |                                  |                               |
        |                                  |                               `- 10-frame transform crossfade
        |                                  `- detection events, heatmap, stats
        `- low-rate raw preview for TUI
```

The stages live in `privacy-core/src/pipeline_runner.rs` and communicate with bounded `crossbeam-channel` queues from `privacy-core/src/pipeline.rs`.

| Thread | Responsibility |
|--------|----------------|
| `aki-capture` | Pulls frames from ScreenCaptureKit, PTY capture, or a platform capture source; optionally crops configured capture regions. |
| `aki-detect` | Runs incremental OCR, scans configured patterns, applies whitelist checks, expands/merges regions, and emits detection events. |
| `aki-transform` | Applies the current transform mode and transition blend to detected regions. |
| caller output loop | Receives transformed frames and writes them to an `OutputSink` such as MJPEG, virtual camera, OBS adapter, or MP4 recorder. |

## Backpressure

Every inter-stage channel is bounded to three frames. If a channel is full, the pipeline sheds the incoming frame and increments `dropped_frames` instead of blocking the producer.

That policy matters for real-time use:

- capture keeps sampling current pixels instead of waiting behind stale work,
- OCR cannot build an unbounded queue during spikes,
- transform/output latency stays bounded by recent frames,
- the UI can report dropped frames instead of hiding overload.

This is a latency-first tradeoff. `Aki` prefers dropping a frame over redacting and outputting old pixels late.

## Detection

Detection starts with OCR text regions. The default path uses Tesseract through `OcrEngine`, then scans text with the runtime pattern registry.

The registry includes:

- built-in secret and token patterns,
- PII patterns,
- user-defined patterns,
- optional external rule packs.

Matches are expanded and merged before transform:

1. `expand_and_merge` pads matched boxes so redaction covers OCR jitter and adjacent characters.
2. `expand_to_end_of_line` covers common `KEY=value` and `label: value` layouts.
3. duplicate detection events are suppressed for one second so logs and UI counters stay readable.

The optional local LLM detector is disabled by default. When enabled, it only classifies OCR text below the normal confidence threshold and sends snippets to the configured local endpoint.

## Incremental OCR

The frame is divided into an adaptive grid. Defaults are `8x6`, defined by `GRID_COLS` and `GRID_ROWS`.

`FrameDiff` marks cells as dirty when pixels change. Dirty cells are OCRed; unchanged cells reuse cached OCR results. The first frame and resolution changes invalidate the cache and OCR every cell.

If detection exceeds the 33 ms frame budget, the pipeline shrinks the target grid toward `2x2` and scales transform quality to `0.8`. When detection falls below half budget, the grid recovers toward `8x6`.

This is the main reason the pipeline can target real-time use: OCR work tracks changed screen areas rather than the whole display on every frame.

## Transform

Transforms operate on `DetectedRegions` and the current raw frame.

Supported modes include:

- blur,
- pixelate,
- cartoon,
- ASCII,
- neural with latency-guard fallback.

Mode switches use a 10-frame pixel blend between the previous and new transform. The view changes without abruptly flashing raw or differently redacted pixels.

## Output

Transformed frames leave through `privacy-output` sinks:

| Sink | Purpose |
|------|---------|
| CoreMediaIO | macOS virtual camera path. |
| v4l2loopback | Linux virtual camera path. |
| MJPEG | local HTTP stream and OBS browser-source fallback. |
| OBS adapter | setup path that falls back to MJPEG when OBS is unreachable. |
| MP4 | direct local recording through ffmpeg. |

Output sinks do not own detection logic. They receive already transformed frames.

## Control Surfaces

The Rust binary is the single pipeline implementation.

The macOS menu-bar app starts it as a sidecar, then controls it through the localhost WebSocket protocol documented in `docs/sidecar-protocol.md`. The same sidecar model is used by Shortcuts actions in `docs/apple-shortcuts.md`.

The TUI remains a power-user surface and local preview, not a separate engine.

## Real-Time Boundaries

`Aki` reduces leak risk, but it does not guarantee prevention.

Known real-time boundaries:

- newly appeared sensitive text can be visible before OCR catches it,
- tiny or low-contrast text may be missed,
- multi-display capture increases OCR and transform cost,
- retroactive buffers can fix local recordings before finalization but cannot unsend livestream or screen-share pixels,
- MP4 and OBS output add encoder or integration overhead after transform.

The project tracks reproducible baseline numbers in `BENCHMARKS.md`.
