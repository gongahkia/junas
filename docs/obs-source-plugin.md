# OBS Source Plugin Design

This is the v2 design for reaching streamers directly inside OBS while keeping the existing virtual-camera and MJPEG paths intact.

## Goal

Build a native OBS source or filter plugin that sends OBS video frames through Aki's detector and transform pipeline, then returns redacted frames to OBS as a normal source/filter output.

The current production path remains:

```text
screen capture -> Aki pipeline -> virtual camera or MJPEG -> OBS
```

The plugin path would be:

```text
OBS source/filter frame -> Aki detector + transform -> OBS texture output
```

## Frame Flow

1. OBS calls the plugin on its video/render path with a frame from a selected source, scene, or plugin-owned capture source.
2. The plugin stages the frame into an RGBA CPU buffer. GPU texture interop can be added later, but the prototype keeps the boundary explicit.
3. The RGBA buffer is converted into `privacy_core::obs_plugin::ObsSourceFrame`.
4. Aki runs OCR/pattern detection on the frame and produces `DetectedRegions`.
5. Existing transforms are applied through `privacy_core::obs_plugin::apply_transform_to_obs_frame`.
6. The transformed RGBA buffer is uploaded back to an OBS texture and emitted by the source/filter.

The prototype adapter is compiled and tested in [`privacy-core/src/obs_plugin.rs`](../privacy-core/src/obs_plugin.rs). It verifies that an OBS-style RGBA frame can apply an existing Aki transform without going through the virtual-camera path.

## Source vs Filter

The first native implementation should be an OBS filter, not only a source:

- A filter can wrap any existing OBS source, including display capture, window capture, cameras, and browser sources.
- A source can still be useful for an Aki-managed MJPEG/browser-source style setup.
- Both can share the same Rust core adapter once the OBS C/C++ boundary is in place.

## Threading

OBS render callbacks must not block on OCR. The plugin should use the same backpressure principle as Aki's current pipeline:

- Copy or map the newest frame into a bounded queue.
- Run OCR and pattern matching on worker threads.
- Apply the most recent known redaction regions to the render-thread frame.
- Drop stale frames instead of queueing latency.

This means live streams may still have a short detection race window. The plugin does not change that limitation; it just removes the virtual-camera setup step for OBS users.

## Transform Prototype

The current prototype covers transform application:

```console
$ cargo test -p privacy-core obs_plugin -- --nocapture
```

The test builds a fake OBS RGBA frame, marks a region, applies the existing Pixelate transform, and verifies the output frame changes while preserving dimensions.

Next native-plugin prototype steps:

1. Generate an OBS plugin skeleton with `obs-plugintemplate`.
2. Add a Rust staticlib or C ABI wrapper around the Aki core adapter.
3. Copy one OBS frame into RGBA CPU memory and call the adapter.
4. Upload the transformed frame back to an OBS texture.
5. Add UI controls for transform mode, intensity, and detector profile.

## Packaging And Distribution

OBS plugin distribution is separate from Aki's macOS DMG:

- macOS: ship a signed and notarized `.plugin` bundle under `~/Library/Application Support/obs-studio/plugins/aki-obs-source/`.
- Linux: ship a shared object and data files matching OBS plugin layout for Flatpak and native OBS installs.
- Windows: defer until the main Aki app has Windows capture support.

Distribution channels:

- GitHub Releases for versioned plugin artifacts.
- OBS Project forum/resource listing after a signed macOS build and repeatable install docs exist.
- Homebrew cask can stay focused on the Aki app; plugin packaging should be a separate artifact until the OBS install path is stable.

## Non-Goals For The First Plugin

- Replacing the virtual camera path.
- Browser DOM inspection.
- Sending frames or OCR text to a cloud service.
- Supporting every OBS platform before the macOS plugin path is stable.
