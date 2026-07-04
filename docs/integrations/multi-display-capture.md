# Multi-Display Capture

Source: [`integrations/desktop/displays.py`](../../integrations/desktop/displays.py)

Maturity: `experimental-local-fallback`

The `aki displays` helper lists currently connected macOS displays and builds
explicit `screencapture -D` commands for one or more selected display indexes.
This is a local helper for demos, presentations, and recording workflows; it is
not endpoint enforcement.

## Select Displays

List displays:

```sh
uv run aki displays list
uv run aki displays list --json
```

Build a capture plan for all online displays:

```sh
uv run aki displays capture --output-dir ./captures --dry-run
```

Select specific displays:

```sh
uv run aki displays capture --display 1 --display 2 --output-dir ./captures --dry-run
```

Record video from selected displays:

```sh
uv run aki displays capture --display 1 --display 2 --video-seconds 30 --output-dir ./captures --dry-run
```

Remove `--dry-run` to run `screencapture`.

## Connected Or Removed Displays

Display indexes are resolved from the current `system_profiler SPDisplaysDataType
-json` inventory each time the command runs. The main display is index `1`;
other displays are sorted by display name for stable capture plans.

Predictable behavior:

- no `--display` selection captures all currently online displays
- a missing selected display fails fast with `display index not available`
- `--ignore-missing` skips disconnected selected displays
- if all selected displays are missing, the command fails with `no online displays selected`
- output filenames include `display-<index>` plus optional `--timestamp`

## Performance Impact

The table is a raw frame bandwidth estimate for 30 fps RGBA frames before any
macOS capture/encoder compression. It is a sizing guide, not a runtime benchmark.

| Capture set | Pixels per frame | Raw estimate |
|---|---:|---:|
| 1920 x 1080 | 2.1 MP | 248.8 MB/s |
| 2560 x 1440 | 3.7 MP | 442.4 MB/s |
| 3840 x 2160 | 8.3 MP | 995.3 MB/s |
| 2 x 3840 x 2160 | 16.6 MP | 1990.7 MB/s |

Operational guidance:

- prefer one selected display during demos unless the workflow needs multiple
- use `--video-seconds` to bound recording duration
- re-run `aki displays list` after hot-plugging displays
- avoid recording mirrored confidential displays unless the operator explicitly
  selected them
