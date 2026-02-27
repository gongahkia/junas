[![](https://img.shields.io/badge/aki_1.0.0-passing-green)](https://github.com/gongahkia/aki/releases/tag/1.0.0)
![](https://github.com/gongahkia/aki/actions/workflows/ci.yml/badge.svg)

# `Aki`

Real-time [ASCII](https://en.wikipedia.org/wiki/ASCII) [privacy filter](https://www.reddit.com/r/buildapc/comments/wf46j0/privacy_filter_as_a_software/) for [screen capture](https://dictionary.cambridge.org/dictionary/english/screen-sharing) and [livestreaming](https://en.wikipedia.org/wiki/Live_streaming). 

## How does `Aki` do that?

Via XXX, `Aki` detects [sensitive information](#blocklist) in captured frames via OCR, transforms sensitive regions using configurable effects (blur, pixelation, cartoon, ASCII art), and outputs the sanitized feed to a virtual camera for use with OBS or other streaming software.

## Stack

| Layer | Technology |
|-------|-----------|
| Language | Rust |
| TUI | Ratatui + Crossterm |
| Screen capture (macOS) | ScreenCaptureKit (`screencapturekit-rs`) |
| Screen capture (Linux X11) | XCB |
| Screen capture (Linux Wayland) | PipeWire via `ashpd` |
| OCR | Tesseract (`tesseract-rs`) |
| Virtual camera (Linux) | v4l2loopback |
| Virtual camera (macOS) | CoreMediaIO DAL plugin |
| Fallback output | HTTP MJPEG stream |
| Channels | `crossbeam-channel` |
| Config | TOML (`~/.config/ascii-privacy/config.toml`) |

## Screenshot

...

## Usage

The below instructions are for locally running `Aki`.

```console
# run with TUI
aki run

# list available windows
aki list-windows

# test sensitivity patterns against text input
aki test-patterns "SECRET_KEY=abc123"

# verify virtual camera availability
aki check-output
```

## Architecture

```
CaptureSource
    ↓ RawFrame (RGBA + dims + timestamp)
SensitivityDetector  (OCR → pattern matching)
    ↓ DetectedRegions
Transformer  (blur / pixelate / cartoon / ASCII)
    ↓ TransformedFrame
OutputSink  (v4l2loopback / CoreMediaIO / HTTP MJPEG)
```

All pipeline stages communicate via bounded `crossbeam` channels (capacity 3 frames). Backpressure drops oldest frame to maintain real-time performance.

## Blocked List

Currently `Aki` blocks the below by default.

* API keys
* Tokens
* Passwords
* PII
* ...

## Reference

The name `Aki` is in reference to the Japanese 空き (*aki*) which roughly means *empty*, *vacant*, or *a gap* — as seen in 空き容量 (*aki yōryō*, free disk space). The tool creates a "gap" in the stream where sensitive data used to be.
