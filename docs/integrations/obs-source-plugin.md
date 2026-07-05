# OBS Source Plugin Design

Source prototype: [`src/junas/integrations/obs_source.py`](../../src/junas/integrations/obs_source.py)

Runtime prototype: `junas obs prototype-source`

Maturity: `experimental-local-fallback`

This page evaluates an OBS source-plugin path without claiming a native OBS
binary is shipped. The local prototype processes frame PNGs with the existing
`time_buffer.redaction_box` transform and writes processed frames that can be
fed into the direct MP4 sink.

Reference docs:

- OBS plugin docs: <https://docs.obsproject.com>
- OBS plugin template: <https://github.com/obsproject/obs-plugintemplate>

## Frame Handoff

Native source-plugin design:

1. A native OBS plugin registers an `obs_source_info` implementation.
2. The source owns a configured input: capture source, media frames, or an
   intermediate frame provider.
3. Frames enter the Junas/Junas transform boundary as RGBA or BGRA pixel buffers.
4. The transform returns a processed frame or a no-op frame when disabled.
5. The source uploads the processed frame to an OBS texture and renders it from
   the source render callback.
6. OBS scene composition, recording, streaming, and virtual camera output remain
   downstream of the source.

The prototype maps that flow to files:

```sh
uv run junas obs prototype-source --frames-dir ./obs-input-frames --output-dir ./obs-prototype --box 0,0,240,120 --json
uv run junas mp4 from-redacted-frames --frames-dir ./obs-prototype/processed_frames --output ./captures/obs-prototype.mp4
```

Prototype JSON reports `native_plugin_shipped=false` and
`virtual_camera_unchanged=true`.

## Existing Transform

The prototype applies `time_buffer.redaction_box`, the same rectangle redaction
transform used by the recording time-buffer prototype. This proves the OBS
source boundary can invoke an existing transform without adding a second
redaction implementation.

The prototype does not call the Junas backend, OCR, or policy engine. A future
native plugin must decide whether transform configuration is local-only,
backend-driven, or paired with the local daemon.

## Source Versus Filter

An OBS source plugin is appropriate when Junas owns the frame provider or wraps a
known capture path. An OBS filter may be a better fit when users need to modify
arbitrary existing OBS sources. This issue keeps the source-plugin evaluation
separate from the existing virtual-camera path. The virtual-camera path remains intact.

## Packaging And Distribution

A native plugin should start from the official OBS plugin template and keep
platform packaging separate from the Python package:

| Platform | Requirement |
|---|---|
| macOS | Universal or architecture-specific bundle, hardened runtime, signing, notarization, OBS plugin install layout, and uninstall docs. |
| Windows | Signed DLL/package, OBS version compatibility matrix, installer or zip layout, and Defender false-positive handling. |
| Linux | OBS plugin shared object, distro package or tarball layout, glibc/Qt/OBS ABI compatibility notes. |

Distribution checklist:

- build against supported OBS Studio versions
- publish a changelog and compatibility matrix
- keep Junas local daemon/backend config explicit
- avoid raw-frame logs and crash dumps where possible
- document whether transforms run CPU-side or GPU-side
- preserve OBS virtual camera support and document any conflicts
- submit only after a native binary, installer, and QA evidence exist

OBS resource-channel publication should wait until there is a native plugin
artifact, reproducible build instructions, macOS/Windows/Linux install guidance,
and a clear support boundary. The current Python prototype is not an OBS plugin
release.
