# Offline Video Redaction

`junas redact` processes an existing local recording into a redacted MP4 without screen capture, OBS, or a virtual camera.

```bash
uv run junas redact ./recording.mov \
  --output ./captures/recording-redacted.mp4 \
  --box 0,0,240,120
```

The command extracts video frames with `ffmpeg`, applies the same `time_buffer.redaction_box` transform used by the buffer and OBS prototypes, then writes the result through the direct MP4 sink. It does not overwrite the input video or an existing output file unless `--overwrite` is passed. The output path must be explicit and end in `.mp4`; missing parents require `--create-parent`.

## Detection Manifest

Manual box mode redacts every extracted frame with `--box`. For detector-driven fixtures or OCR handoff, pass a local detection manifest and a local Gitleaks-compatible rule pack:

```bash
uv run junas redact ./recording.mov \
  --output ./captures/recording-redacted.mp4 \
  --detections-json ./detections.json \
  --gitleaks rules/community/gitleaks-acme-demo.toml \
  --fps 30 \
  --json
```

Detection manifest shape:

```json
{
  "frames": [
    {
      "frame": 1,
      "text": "ACME_API_KEY = a1b2c3d4e5f6g7h8i9j0",
      "boxes": [[0, 0, 240, 80]]
    }
  ]
}
```

`text` is scanned through the existing opt-in secret rule-pack importer. Frames with at least one secret finding are redacted at their listed boxes. JSON output reports `manifest_secret_rules`, detected rule IDs, counts, paths, and `audio_preserved=false`; it does not include matched secret text.

## Output Behavior

- `--output` is required and must be separate from the input.
- Existing outputs fail fast unless `--overwrite` is passed.
- Audio is not copied in this prototype; `audio_preserved=false`.
- `--fps` controls the output MP4 frame rate.
- `--detections-json` requires `--gitleaks`; without a manifest, `--box` applies to every frame.

This is an offline transform path for local recordings. It reuses the frame transform and MP4 writer, but it is not a live-stream rollback mechanism.
