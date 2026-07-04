# Direct MP4 Sink

Source: [`integrations/desktop/mp4_sink.py`](../../integrations/desktop/mp4_sink.py)

Maturity: `experimental-local-fallback`

The `aki mp4 from-redacted-frames` helper encodes an explicit directory of
already-redacted PNG frames into a local MP4 file with `ffmpeg`. It is a file
output sink for demos, audit review, and offline handoff. It does not capture
the screen, inspect pixels for PII, or stream to a live camera device.

## Encode Redacted Frames

Dry-run the encoder plan:

```sh
uv run aki mp4 from-redacted-frames --frames-dir ./redacted-frames --output ./captures/redacted-session.mp4 --dry-run
```

Write the MP4:

```sh
uv run aki mp4 from-redacted-frames --frames-dir ./redacted-frames --output ./captures/redacted-session.mp4
```

Use a specific frame rate or filename pattern:

```sh
uv run aki mp4 from-redacted-frames --frames-dir ./redacted-frames --pattern 'frame-*.png' --fps 24 --output ./captures/redacted-session.mp4
```

## Start And Stop Behavior

The command is not a daemon. Start is the first sorted frame that matches the
pattern in `--frames-dir`; stop is the last sorted matching frame. Each frame is
assigned `1 / --fps` seconds, and the output duration is `frame_count / fps`.

For a live capture workflow, use the capture path first, run the existing review
or redaction transform that produces redacted frames, then call this sink on the
redacted frame directory.

## Output Path Safety

`--output` is required and must end in `.mp4`.

Safety checks:

- existing files fail unless `--overwrite` is passed
- symlink output paths are rejected
- directory outputs are rejected
- missing parent directories fail unless `--create-parent` is passed
- `--pattern` cannot escape `--frames-dir`

## When To Use MP4 Instead Of OBS

Use this sink when the operator needs a local file: compliance review, support
handoff, async demo capture, or an attachment to an internal ticket.

Use OBS or a virtual camera when the operator needs live output into a meeting,
streaming tool, or another app that expects a camera device. MP4 output is
bounded and replayable; OBS and virtual-camera output is live and operationally
separate.

## Dependencies

The helper shells out to `ffmpeg` and adds no Python package dependency.
Install it with Homebrew on macOS:

```sh
brew install ffmpeg
```
