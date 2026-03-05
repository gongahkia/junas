[![](https://img.shields.io/badge/aki_1.0.0-passing-green)](https://github.com/gongahkia/aki/releases/tag/1.0.0)
![](https://github.com/gongahkia/aki/actions/workflows/ci.yml/badge.svg)

# `Aki`

Real-time [ASCII](https://en.wikipedia.org/wiki/ASCII) [privacy filter](https://www.reddit.com/r/buildapc/comments/wf46j0/privacy_filter_as_a_software/) for [screen capture](https://dictionary.cambridge.org/dictionary/english/screen-sharing) and [livestreaming](https://en.wikipedia.org/wiki/Live_streaming). 

## How does `Aki` do it?

`Aki` [ingests](#architecture) a live video stream, detects [sensitive information](#block-list) in captured frames via OCR, [transforms](#transformations) sensitive regions using configurable effects, then [outputs](#architecture) the sanitized feed to a virtual camera for use with [OBS or other streaming software](#output-support).

For more details, see [here](#nerd-stuff).

## Screenshots

<div align="center">
    <img src="./asset/reference/1.png" width="47%">
    <img src="./asset/reference/2.png" width="47%">
</div>

<div align="center">
    <img src="./asset/reference/3.png" width="47%">
    <img src="./asset/reference/4.png" width="47%">
</div>

## Stack

* *Script*: [Rust](https://www.rust-lang.org/), [Ratatui](https://ratatui.rs/), [Crossterm](https://github.com/crossterm-rs/crossterm), [toml](https://github.com/toml-rs/toml)
* *Screen Capture*: [screencapturekit-rs](https://github.com/svtlabs/screencapturekit-rs), [ashpd](https://github.com/bilelmoussaoui/ashpd)
* *OCR*: [Tesseract](https://github.com/tesseract-ocr/tesseract) via [leptess](https://github.com/houqp/leptess)
* *Virtual Camera*: [v4l2loopback](https://github.com/umlaeute/v4l2loopback), [CoreMediaIO DAL](https://developer.apple.com/documentation/coremediaio)
* *Output*: [HTTP MJPEG](https://en.wikipedia.org/wiki/Motion_JPEG), [OBS WebSocket](https://github.com/obsproject/obs-websocket)
* *Channels*: [crossbeam-channel](https://github.com/crossbeam-rs/crossbeam)

## Usage

The below instructions are for locally running `Aki`.

1. First install `Aki` locally with the following commands.

```console
$ git clone https://github.com/gongahkia/aki && cd aki
$ 
```

2. Then run the below commands to use `Aki`'s core functionality.

```console
$ cargo run -- run # run with TUI
$ cargo run -- list-windows # list available windows
$ cargo run -- test-patterns "SECRET_KEY=abc123" # test sensitivity patterns against text input
$ cargo run -- check-output # verify virtual camera availability
```

3. Once inside `Aki`'s TUI, use the below keybinds.

| Key | Action |
|-----|--------|
| `w` | open window picker, select a source to capture |
| `Space` | pause / resume capture |
| `t` | cycle transform (Blur → Pixelate → Cartoon → ASCII) |
| `+` / `-` | increase / decrease effect intensity |
| `q` / `Ctrl+C` | quit |

### Debug Logging

`Aki` now writes persistent logs to:

```console
~/.config/ascii-privacy/logs/aki.log
```

Set `AKI_LOG_LEVEL` to control file verbosity (`trace`, `debug`, `info`, `warn`, `error`).
Set `AKI_LOG_STDERR=1` only when you explicitly want mirror logs in terminal output.

On startup, `Aki` also auto-selects a likely app window source (instead of full-display capture)
to reduce self-capture feedback artifacts. Press `w` anytime to override.

## Blocked List

Currently `Aki` blocks the below by default.

**API Keys & Tokens**
* AWS access keys (`AKIA...`) and secret access keys
* Stripe secret/publishable keys (`sk_live_`, `pk_test_`, ...)
* GitHub personal access tokens (`ghp_`, `gho_`)
* GitLab personal access tokens (`glpat-`)
* Slack tokens (`xoxb-`, `xoxs-`, `xoxp-`)
* Hugging Face API tokens (`hf_`)
* Anthropic API keys (`sk-ant-`)
* Generic API key prefixes (`sk-`, `pk-`, and similar)
* JWT tokens (`eyJ...`)
* SSH private keys (RSA, EC, DSA, OpenSSH)

**Secrets & Credentials**
* Secret keyword assignments (`api_key:`, `token=`, `secret=`, `password=`, `passwd=`, `credential=`)
* Environment variable assignments (`UPPER_CASE=<value>`)

**PII**
* Email addresses
* IPv4 and IPv6 addresses
* Credit card numbers (Visa, Mastercard, Amex, Discover, JCB)

## Nerd stuff

### Pipeline

Four threads communicate via bounded `crossbeam` channels (capacity 3). Full channels drop the oldest frame rather than block — backpressure is shed, not accumulated.

| Thread | Responsibility |
|--------|---------------|
| `aki-capture` | Pulls frames from ScreenCaptureKit / XCB / PipeWire; optionally crops to a sub-region |
| `aki-detect` | Runs incremental OCR → regex pattern scan → region expansion + merge |
| `aki-transform` | Applies the active transform (with 10-frame pixel-blend crossfade on mode switch) |
| `aki-output` | Forwards transformed frames to the selected `OutputSink` |

### Transformations

Currently `Aki` supports the below morphs.

<table>
<thead>
<tr><th>Transform</th><th>Description</th></tr>
</thead>
<tbody>
<tr>
<td><strong>Blur</strong></td>
<td><ul>
<li>Separable Gaussian blur (σ=15 default)</li>
<li>Two-pass horizontal + vertical for O(n) performance</li>
</ul></td>
</tr>
<tr>
<td><strong>Pixelate</strong></td>
<td><ul>
<li>Block-averaging at 2px–dim/8 block size</li>
<li>Block size scales linearly with intensity</li>
<li>Nearest-neighbour upscale back to original dimensions</li>
</ul></td>
</tr>
<tr>
<td><strong>Cartoon</strong></td>
<td><ul>
<li>Bilateral filter approximation (smoothing)</li>
<li>Sobel edge detection overlay</li>
<li>k-means colour quantization (k=8 colours)</li>
<li>Destroys text readability while preserving approximate colour</li>
</ul></td>
</tr>
<tr>
<td><strong>ASCII</strong></td>
<td><ul>
<li>Pixel luminance mapped to a 15-level density ramp (<code> .,:;i1tfLCG08@</code>)</li>
<li>Each 8×16 pixel block averaged to a single luminance value</li>
<li>Block re-rendered as uniform grey matching density level</li>
</ul></td>
</tr>
<tr>
<td><strong>Neural</strong></td>
<td><ul>
<li>ONNX Runtime inference</li>
<li>Accelerator selection: CUDA / CoreML / CPU (auto-detected)</li>
<li>Falls back to Cartoon if inference exceeds latency guard (default 100ms)</li>
</ul></td>
</tr>
</tbody>
</table>

### Output support

Currently `Aki` supports the following 4 outputs.

| Sink | Platform | Status |
|------|----------|--------|
| v4l2loopback virtual camera | Linux | Available |
| CoreMediaIO DAL virtual camera | macOS | Available |
| HTTP MJPEG stream | All | Available *(default fallback)* |
| OBS WebSocket v5 *(Browser Source → MJPEG)* | All | Available *(falls back to MJPEG if OBS unreachable)* |

### Architecture

![](./asset/reference/architecture.png)

### Incremental OCR

The frame is divided into an 8×6 grid of cells. Between frames, a pixel-threshold diff (`FrameDiff`) marks only changed cells as dirty. Only dirty cells are sent to Tesseract — typically ~70% of OCR work is skipped per frame.

If detection takes longer than the 33ms frame budget, the grid is shrunk (down to 2×2) and transform intensity is reduced to 0.8× to recover headroom. The grid recovers back toward 8×6 when load drops below half-budget.

### Config

`~/.config/ascii-privacy/config.toml` is created with defaults on first run.

```toml
[capture]
fps = 30
region = "0,0,1920,1080"   # optional crop "x,y,w,h"

[detection]
min_confidence = 40         # tesseract confidence threshold (0–100)
grid_cells_x = 8
grid_cells_y = 6
safe_zones = ["0,0,200,50"] # regions never redacted
always_redact_zones = []    # regions always redacted

[transform]
mode = "blur"               # blur | pixelate | cartoon | ascii | neural
intensity = 1.0
accelerator = "auto"        # auto | cuda | coreml | cpu (for neural mode)

[output]
sink = "auto"               # auto | v4l2 | coremedia | mjpeg
http_port = 9876
```

Named profiles (e.g. `[profiles.streaming]`) can override transform mode and intensity for different contexts.

## Reference

The name `Aki` is in reference to the Japanese 空き (*aki*) which roughly means *empty*, *vacant*, or *a gap*, as seen in 空き容量 (*aki yōryō*, free disk space).

<div align="center">
    <img src="./asset/logo/thehand.webp" width="30%">
</div>
