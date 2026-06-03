# Aki v1 Sidecar Protocol

## Decision

V1 uses a Rust sidecar process controlled by the SwiftUI menu-bar app:

- Launch/lifecycle channel: Swift starts `aki` as a child process and passes boot-time choices as CLI arguments.
- Runtime control channel: the sidecar exposes a localhost WebSocket server at `ws://127.0.0.1:9877`.
- No FFI is used in v1.

This keeps the shipped Rust pipeline as the single implementation, avoids ABI and crash-coupling risk, and lets the Swift shell use `URLSessionWebSocketTask` without native socket glue.

## Launch Contract

The menu-bar app starts the sidecar with:

```console
aki --headless --source screen|pty --transform blur|pixelate|cartoon|ascii|neural --output auto|coremedia|mjpeg|obs --http-port 9876
```

`--pty` remains as a compatibility alias for `--source pty`, but the menu-bar app uses `--source` so source selection is explicit.

Start and stop are process lifecycle operations:

- Start: resolve the sidecar binary, spawn the process, then poll the WebSocket stats endpoint until it is ready.
- Stop: terminate the child process and wait for exit.
- Unexpected exit: mark the menu-bar status as exited and clear running state.

Source and output selection are launch-time settings in v1. If either changes while the sidecar is running, the menu-bar app restarts the process with the new arguments. Transform selection can change live through the WebSocket control channel.

## WebSocket Messages

Each request is one JSON text message. Each response is one JSON message with `ok: true` on success or `ok: false` plus `error` on failure.

Pause:

```json
{"cmd":"pause"}
```

Resume:

```json
{"cmd":"resume"}
```

Set transform:

```json
{"cmd":"set_transform","mode":"ascii"}
```

Stats:

```json
{"cmd":"stats"}
```

Successful stats responses include:

```json
{
  "ok": true,
  "cmd": "stats",
  "protocol_version": 1,
  "mode": "ascii",
  "intensity": 1.0,
  "paused": false,
  "source": "screen",
  "output": "mjpeg:9876",
  "fps": 29.8,
  "redactions": 12,
  "dropped_frames": 0
}
```

The control server still accepts the older `switch_mode` and `get_stats` command names for compatibility.

## Errors

Malformed JSON, missing `cmd`, unknown commands, and unknown transform modes return `ok: false` responses. WebSocket connection failures are treated by the Swift shell as a transient startup/control-server-unavailable state while the process is alive.

If the Rust process cannot bind `127.0.0.1:9877`, it logs the bind failure and continues without runtime control. The Swift shell surfaces that as control unavailable because stats polling cannot connect.

## Rejected Alternatives

Stdio JSON-RPC was rejected for v1 because stdout and stderr are already useful for process diagnostics, and multiplexing logs plus control would make failure handling more brittle.

Unix sockets were rejected for v1 because the extra path management, cleanup, and sandbox/notarization questions do not buy enough over a loopback-only WebSocket for a local menu-bar shell.

FFI was rejected for v1 because it would add ABI boundaries, memory ownership concerns, tighter crash coupling, and extra signing/notarization complexity without improving the first release experience.
