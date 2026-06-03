# Local Redaction Log

## Decision

V1 includes a local-only redaction event log in the TUI, but it is in-memory by default.

The value is practical debugging and trust-building: users can confirm what Aki detected, when it was detected, and which rule fired. The privacy risk is that even redacted snippets and pattern metadata can reveal sensitive context, so Aki does not persist per-event logs automatically.

## Default Behavior

- UI exposure: the TUI detection panel shows recent detections.
- Retention: the app keeps the most recent 50 detection entries in memory for the current session.
- Stored fields: timestamp, pattern name, severity, redacted snippet, and bounds.
- Persistence: none by default. Closing Aki drops the in-memory entries.
- Uploads: none. The log is never sent to a server by Aki.

Headless mode only exposes aggregate counters through the local control server stats and writes periodic aggregate session stats. It does not persist per-redaction event entries.

## Explicit Export

Press `e` in the TUI to export the current in-memory session log.

Export path:

```text
~/.config/ascii-privacy/sessions/aki_session_<timestamp>.json
```

Exports are local files and may contain sensitive metadata. Treat them like debug artifacts: keep them only when needed, do not share them casually, and delete them when the investigation is done.

## Deferred

Automatic retention policies, encrypted log storage, and opt-in diagnostics upload are not part of v1.
