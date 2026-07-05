# Time-Machine Buffer

Source: [`integrations/desktop/time_buffer.py`](../../integrations/desktop/time_buffer.py)

Maturity: `experimental-local-fallback`

The `junas buffer prototype` helper demonstrates a recording-only ring-buffer
workflow for local frame directories. It keeps the most recent `fps * seconds`
frames, applies a retroactive transform to the trailing window, and writes
finalized frames for later MP4 encoding.

This does not unsend pixels from live streams. The prototype reports
`live_stream_undo_supported=false` in JSON output and should be described only as
a recording finalization workflow.

## Prototype Command

Dry-run the buffer plan and metrics:

```sh
uv run junas buffer prototype --frames-dir ./capture-frames --output-dir ./buffer-demo --fps 30 --seconds 30 --redact-last-seconds 5 --dry-run --json
```

Write finalized frames with a redaction box:

```sh
uv run junas buffer prototype --frames-dir ./capture-frames --output-dir ./buffer-demo --fps 30 --seconds 30 --redact-last-seconds 5 --box 0,0,240,120
```

Then encode finalized frames with the direct MP4 sink:

```sh
uv run junas mp4 from-redacted-frames --frames-dir ./buffer-demo/final_frames --output ./captures/redacted-session.mp4
```

## Retroactive Transform

The prototype sorts matching frame files, retains the newest frames up to the
configured ring-buffer capacity, and applies a black rectangle to only the last
`--redact-last-seconds` of retained frames. Earlier retained frames are copied to
`final_frames` unchanged.

Default transform parameters:

| Setting | Default |
|---|---:|
| `--fps` | `30` |
| `--seconds` | `30` |
| `--redact-last-seconds` | `5` |
| `--box` | `0,0,120,80` |

## Memory And Disk Implications

JSON output includes:

| Field | Meaning |
|---|---|
| `capacity_frames` | Maximum retained frames, computed as `fps * seconds`. |
| `retained_frame_count` | Frames kept after ring-buffer eviction. |
| `evicted_frame_count` | Older frames outside the retention window. |
| `memory_bytes_estimate` | Estimated decoded RGBA buffer cost: `width * height * 4` per retained frame. |
| `disk_bytes_estimate` | Sum of retained source-frame file sizes if the buffer were persisted. |
| `final_disk_bytes` | Bytes written under `final_frames` after transform, present for non-dry-run output. |

Example raw decoded-memory estimates:

| Frame size | 30 fps / 30 s |
|---|---:|
| 1280 x 720 | 3.3 GB |
| 1920 x 1080 | 7.5 GB |
| 3840 x 2160 | 29.9 GB |

Persisting raw retained frames is off by default. `--write-buffer-copy` writes
`buffer_frames` for inspection, but operators should use it only with synthetic
or already-approved local recordings.

## Recording Boundary

Use this prototype when a local recording is not finalized yet and the operator
needs to apply a late redaction before producing a file.

Do not use this language for live meetings, streams, or virtual-camera output:
already emitted pixels cannot be recalled by this buffer. For live output, use
OBS or a virtual camera and treat missed redactions as incident response, not
retroactive correction.
