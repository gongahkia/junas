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

## UI Surface

The shell uses a SwiftUI `MenuBarExtra` plus a regular status window. It exposes:

- source picker: display, window, file, clipboard
- transform picker: review, redact, anonymize
- output picker: preview, MP4, OBS, none
- start, pause, and stop controls
- `Open TUI`, which launches `aki --tui` in Terminal
- stats line for redaction count, FPS, and CPU

The app launches as a regular macOS app with a Dock presence and a primary `WindowGroup`.

## Sidecar Control

The shell controls the sidecar through the stdio JSON-RPC protocol in `docs/integrations/menu-bar-sidecar-protocol.md`.

Default sidecar command:

```sh
aki sidecar stdio
```

Override for development or packaging tests:

```sh
JUNAS_SIDECAR_COMMAND="uv run aki sidecar stdio" ./script/build_and_run.sh
```

Start flow:

1. `initialize`
2. `source.select`
3. `transform.select`
4. `output.select`
5. `capture.start`

Pause and stop call `capture.pause` and `capture.stop`. `stats.update` notifications refresh the status line.

## TUI Boundary

The TUI path is preserved as:

```sh
aki --tui
```

This is the power-user terminal surface. It remains separate from the menu-bar shell so scripted and terminal workflows do not depend on SwiftUI.

## Packaging Boundary

`script/build_and_run.sh` stages `dist/JunasMenuBar.app` from the SwiftPM executable. The signed DMG release task must later bundle this app with the packaged sidecar and use the signing policy in `docs/macos-signing-credentials.md`.
