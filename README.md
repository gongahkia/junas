[![](https://img.shields.io/badge/aki_1.0.0-passing-green)](https://github.com/gongahkia/aki/releases/tag/1.0.0)
![](https://github.com/gongahkia/aki/actions/workflows/ci.yml/badge.svg)

# `Aki`

Real-time [ASCII](https://en.wikipedia.org/wiki/ASCII) [privacy filter](https://www.reddit.com/r/buildapc/comments/wf46j0/privacy_filter_as_a_software/) for [screen capture](https://dictionary.cambridge.org/dictionary/english/screen-sharing) and [livestreaming](https://en.wikipedia.org/wiki/Live_streaming). 

## How does `Aki` do it?

`Aki` [ingests](#architecture) a live video stream, detects [sensitive information](#block-list) in captured frames via OCR, [transforms](#transformations) sensitive regions using configurable effects, then [outputs](#architecture) the sanitized feed to a virtual camera for use with [OBS or other streaming software](#output-support).

For more details, see [here](#nerd-stuff).

## Screenshot

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

## Transformations

Currently `Aki` supports the below morphs.

| Transform | Description |
|-----------|-------------|
| Blur | Separable Gaussian blur (σ=15 default); two-pass horizontal + vertical for O(n) performance |
| Pixelate | Block-averaging at 2px–dim/8 block size scaled by intensity; nearest-neighbour upscale |
| Cartoon | Bilateral filter approximation + Sobel edge detection + k-means colour quantization (k=8 colours); destroys text readability while preserving colour |
| ASCII | Pixel luminance mapped to a 15-level density ramp (` .,:;i1tfLCG08@`); each 8×16 pixel block rendered as a uniform grey cell |

## Output support

| Sink | Platform | Status |
|------|----------|--------|
| v4l2loopback virtual camera | Linux | Available |
| CoreMediaIO DAL virtual camera | macOS | Available |
| HTTP MJPEG stream | All | Available *(default fallback)* |
| OBS WebSocket v5 *(Browser Source → MJPEG)* | All | Available *(falls back to MJPEG if OBS unreachable)* |
| Twitch RTMP | All | Planned |

## Architecture

All pipeline stages communicate via bounded `crossbeam` channels (capacity 3 frames). Backpressure drops oldest frame to maintain real-time performance.

## Nerd stuff

...

## Reference

The name `Aki` is in reference to the Japanese 空き (*aki*) which roughly means *empty*, *vacant*, or *a gap* — as seen in 空き容量 (*aki yōryō*, free disk space). The tool creates a "gap" in the stream where sensitive data used to be.