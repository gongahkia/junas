# Multi-Display Capture

Multi-display capture lets `Aki` read one or more full displays instead of a single window or the primary display.

## Commands

List currently available displays:

```console
$ aki list-displays
```

Capture a specific display:

```console
$ aki --headless --source screen --display 1
```

Capture multiple displays into one redacted output canvas:

```console
$ aki --headless --source screen --display 0 --display 1
$ aki --headless --source screen --display 0,1 --record-output ./multi-display.redacted.mp4
```

The `--display` flag can be repeated or comma-separated. It is only valid with screen capture; PTY capture rejects display indexes.

## Layout

Multiple selected displays are composed left-to-right in the order provided on the command line. `--display 1 --display 0` intentionally produces a different canvas from `--display 0 --display 1`.

Displays are not scaled. Shorter displays are padded with opaque black pixels below their frame so OCR, transforms, and output sinks receive one stable RGBA canvas.

## Connect And Disconnect Behavior

Display indexes are resolved from the display list at startup. Run `aki list-displays` after connecting or removing monitors, then restart capture with the desired indexes.

If a requested display index is not present at startup, capture fails instead of silently choosing another display.

If a display is disconnected while capture is running, `Aki` does not silently remap that slot to a different display. The active capture either reports a capture error or stops producing new frames for that display; restart capture after running `aki list-displays`.

## Performance Impact

Multi-display capture increases the canvas that OCR and transforms must inspect. The compositor emits raw RGBA frames at the combined width and maximum height of the selected displays.

At 30 FPS, approximate raw RGBA throughput is:

| Selection | Output canvas | Bytes per frame | Raw RGBA throughput |
|-----------|---------------|-----------------|---------------------|
| 1x 1080p | 1920x1080 | 8,294,400 | 237.3 MiB/s |
| 2x 1080p | 3840x1080 | 16,588,800 | 474.6 MiB/s |
| 1x 1440p | 2560x1440 | 14,745,600 | 421.9 MiB/s |
| 2x 1440p | 5120x1440 | 29,491,200 | 843.8 MiB/s |
| 1x 4K | 3840x2160 | 33,177,600 | 949.2 MiB/s |
| 2x 4K | 7680x2160 | 66,355,200 | 1.85 GiB/s |
| 1080p + 1440p | 4480x1440 | 25,804,800 | 738.3 MiB/s |

These numbers are only the raw canvas bytes moving through the pipeline. OCR, redaction transforms, preview cloning, MP4 encoding, and output sinks add work on top. For CPU-bound setups, start with one display or reduce capture FPS before trying two 4K displays.
