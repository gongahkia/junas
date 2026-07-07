# Menu-Bar Sidecar Protocol

Status: v1 decision.

## Decision

The macOS menu-bar shell talks to the local sidecar over newline-delimited stdio JSON-RPC 2.0.

Chosen command:

```sh
uv run junas sidecar stdio
```

The shell owns the child process lifecycle. The sidecar reads one JSON object per stdin line and writes one JSON object per stdout line. Responses use JSON-RPC ids. Stats are sent as `stats.update` notifications without ids.

## Why stdio

Stdio is the v1 default because the menu-bar app can spawn, monitor, and terminate the sidecar without opening another local port or binding a socket path. It also keeps release signing simple: the shell ships the sidecar binary, starts it as a child process, and treats process exit as a hard failure.

Rejected options:

| Option | Decision | Reason |
|---|---|---|
| Unix socket | Defer | Useful after multi-client local control is needed; current v1 shell is one parent and one child. |
| FFI | Reject for v1 | Adds ABI, memory ownership, crash isolation, and signing complexity without a current need. |

## Methods

| Method | Params | Result |
|---|---|---|
| `initialize` | `{}` | Protocol version, capabilities, and transport. |
| `source.select` | `{"kind":"display|window|file|clipboard","id":"optional"}` | Selected source. |
| `transform.select` | `{"kind":"review_only|redaction_box|anonymize", ...}` | Selected transform. |
| `output.select` | `{"kind":"preview|mp4|obs|none", ...}` | Selected output. |
| `capture.start` | `{}` | Current state snapshot. |
| `capture.pause` | `{}` | Current state snapshot. |
| `capture.stop` | `{}` | Current state snapshot. |
| `stats.snapshot` | `{}` | Current state, selections, frame count, and last error. |
| `shutdown` | `{}` | Stops capture and tells the shell the sidecar can exit. |

State-changing calls also emit:

```json
{"jsonrpc":"2.0","method":"stats.update","params":{"state":"running","frames_processed":0}}
```

## V1 Execution Boundary

The sidecar now executes one-shot text workflows for `file` and `clipboard`
sources:

- source path: `source.select` with `{"kind":"file","path":"draft.txt"}` reads
  UTF-8 text, or `{"kind":"clipboard","text":"..."}` uses caller-provided
  clipboard text.
- transform path: `review_only` runs the local Junas deterministic review engine;
  `anonymize` runs deterministic review and placeholder anonymization.
- output path: `preview` returns a structured preview in `last_output`; `none`
  runs the transform and updates stats without preview text.

Display/window capture, `redaction_box`, `mp4`, and `obs` remain selected protocol
states for the Swift shell, but they are not real capture/output execution paths
in this v1 sidecar. File/clipboard one-shot execution ends with `state="stopped"`
and `last_status="completed"` or `last_status="failed"`.

Stats snapshots include real work counters:

- `frames_processed`: one-shot work units completed.
- `files_processed`: file sources completed.
- `findings_count`: cumulative findings seen by completed review/anonymize runs.
- `runs_started`, `runs_succeeded`, and `runs_failed`.
- `last_output`: sanitized transform/output summary.

## Process Lifecycle

1. Shell launches the sidecar with pipes for stdin/stdout/stderr.
2. Shell sends `initialize`.
3. Shell sends `source.select`, `transform.select`, and `output.select`.
4. Shell sends `capture.start`.
5. Shell handles `stats.update` notifications until pause, stop, error, or shutdown.
6. Shell sends `capture.pause`, `capture.stop`, or `shutdown`.
7. If stdin closes or the process exits, the shell marks capture stopped and shows the last stderr line or JSON-RPC error.

`source.select`, `transform.select`, and `output.select` are accepted only while stopped or paused. `capture.start` requires all three selections. `capture.pause` requires running state. `capture.stop` is idempotent. `shutdown` stops a running capture before returning `should_exit=true`.

## Error Handling

The sidecar uses JSON-RPC errors:

| Code | Meaning |
|---|---|
| `-32700` | Invalid JSON. |
| `-32600` | Invalid request envelope. |
| `-32601` | Unknown method. |
| `-32602` | Invalid params. |
| `-32000` | Invalid lifecycle state. |

Errors never include raw screen text, matched text, local tokens, endpoint URLs, or file contents. Execution failures return generic messages such as `execution failed` or field-level validation errors without echoing source text or paths.

Implementation: `integrations/desktop/sidecar_protocol.py`.
