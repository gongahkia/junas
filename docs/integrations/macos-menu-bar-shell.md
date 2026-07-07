# macOS Menu-Bar Shell

Status: SwiftPM shell scaffold for v1.

Source: `apps/macos-menu-bar/`

Run:

```sh
./script/build_and_run.sh
```

Verify build and launch:

```sh
./script/build_and_run.sh --verify
```

Runtime QA evidence:

```sh
bash script/menu_bar_runtime_qa.sh
```

Recorded transcript: `docs/integrations/macos-menu-bar-runtime-qa-2026-07-07.md`

## UI Surface

The shell uses a SwiftUI `MenuBarExtra` plus a regular status window. It exposes:

- source picker: display, window, file, clipboard
- transform picker: review, redact, anonymize
- output picker: preview, MP4, OBS, none
- start, pause, and stop controls
- `Open TUI`, which launches `junas --tui` in Terminal
- stats line for redaction count, FPS, and CPU

The app launches as a regular macOS app with a Dock presence and a primary `WindowGroup`.

## Sidecar Control

The shell controls the sidecar through the stdio JSON-RPC protocol in `docs/integrations/menu-bar-sidecar-protocol.md`.

Default sidecar command:

```sh
junas sidecar stdio
```

Override for development or packaging tests:

```sh
JUNAS_SIDECAR_COMMAND="uv run junas sidecar stdio" ./script/build_and_run.sh
```

The runtime QA script verifies the override, normal launch, sidecar child launch,
sidecar unavailable handling, invalid sidecar response handling, and app
shutdown.

Start flow:

1. `initialize`
2. `source.select`
3. `transform.select`
4. `output.select`
5. `capture.start`

Pause and stop call `capture.pause` and `capture.stop`. `stats.update` notifications refresh the status line.

## V1 Execution Boundary

The current sidecar executes real one-shot text workflows:

- `file` source: reads a UTF-8 text file selected by path.
- `clipboard` source: reviews caller-provided clipboard text in the JSON-RPC
  request.
- `review_only` transform: runs the local deterministic Junas review engine.
- `anonymize` transform: runs deterministic review plus placeholder
  anonymization.
- `preview` output: returns a structured preview in the sidecar snapshot.

The sidecar updates `frames_processed`, `files_processed`, `findings_count`,
`runs_started`, `runs_succeeded`, `runs_failed`, `last_status`, and
`last_output` from real work. File and clipboard one-shot runs stop
automatically after completion. `shutdown` stops an active capture before exit.

Display/window capture, `redaction_box`, MP4 output, and OBS output remain UI and
protocol selections until the local capture/redaction/video path is implemented.
The shell must not market those selections as functional capture/output yet.

## TUI Boundary

The TUI path is preserved as:

```sh
junas --tui
```

This is the power-user terminal surface. It remains separate from the menu-bar shell so scripted and terminal workflows do not depend on SwiftUI.

## Packaging Boundary

`script/build_and_run.sh` stages `dist/JunasMenuBar.app` from the SwiftPM executable. The signed DMG release task must later bundle this app with the packaged sidecar and use the signing policy in `docs/macos-signing-credentials.md`.
The packaged sidecar lookup path is `Contents/Resources/junas-sidecar/junas-sidecar`; local unsigned builds record `packaged_resource_lookup=deferred` until the signed DMG task bundles that executable.
