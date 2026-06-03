# Time-Machine Redaction Buffer

This is a prototype for retroactive redaction in local recordings. It is not a live-stream undo feature.

## UX Boundary

The time-machine buffer can help when the user is making a local recording and wants to fix a missed redaction before finalizing the recording file.

It cannot unsend pixels that have already gone to:

- a livestream,
- a virtual camera,
- an OBS/MJPEG client,
- a screen-share call.

The UI must present this as a recording workflow only. Copy should say "fix before saving recording", not "undo a leak".

## Prototype

The compiled prototype lives in [`privacy-core/src/time_machine.rs`](../privacy-core/src/time_machine.rs).

It supports:

- a bounded ring buffer of recent raw frames and their detected regions,
- automatic dropping of the oldest frames when capacity is reached,
- adding a manual missed region to recent buffered frames,
- re-rendering buffered frames with an existing transform before a local recording is finalized,
- raw RGBA memory estimation.

Run:

```console
$ cargo test -p privacy-core time_machine -- --nocapture
```

## Memory Cost

Raw RGBA buffering is expensive. A 30-second buffer at 30 FPS keeps 900 frames.

| Resolution | Bytes per frame | 30s raw RGBA buffer |
|------------|-----------------|---------------------|
| 1280x720 | 3,686,400 | 3.09 GiB |
| 1920x1080 | 8,294,400 | 6.95 GiB |
| 3840x2160 | 33,177,600 | 27.80 GiB |

This makes a full-resolution raw frame buffer too expensive as the default. Practical follow-ups should evaluate:

- lower-resolution detection buffers,
- compressed intra-frame snapshots,
- shorter default retention,
- disk-backed buffers with explicit opt-in,
- storing detection metadata plus keyframes instead of every raw frame.

## Disk Cost

The prototype does not write the buffer to disk. If a future recording workflow uses disk-backed retention, the UI must show the configured location and retention size before enabling it.

Disk-backed buffers should be treated as sensitive local artifacts because missed secrets may still be present in pre-redaction frames.

## Recording Flow

Prototype flow for local recording:

1. Keep recent frames and detected regions in `TimeMachineBuffer`.
2. If the user spots missed content before finalizing the recording, add a manual region over the affected recent frames.
3. Re-render buffered frames with the selected transform.
4. Write the corrected frames into the local recording output.
5. Drop the raw buffer after finalization.

Live output continues to use the normal real-time pipeline and does not wait for retroactive fixes.
