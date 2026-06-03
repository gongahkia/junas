# AppleScript And Shortcuts Automation

The macOS menu-bar app exposes a small Shortcuts surface through App Intents. The menu-bar app remains the primary UI; automation routes through the same `AkiMenuController` that backs the menu extra.

## Shortcuts Actions

The first exposed action is `Control Aki`.

Supported values:

- `Start`
- `Stop`
- `Pause or Resume`
- `Open TUI`

The app also donates prebuilt App Shortcuts:

- `Start Aki`
- `Stop Aki`
- `Pause or Resume`
- `Open TUI`

These actions control the existing Rust sidecar process. They do not introduce a second automation-only runtime.

## AppleScript Entry

AppleScript users can invoke the Shortcuts action through the macOS `shortcuts` command:

```applescript
do shell script "shortcuts run 'Start Aki'"
do shell script "shortcuts run 'Pause or Resume'"
do shell script "shortcuts run 'Stop Aki'"
```

Direct AppleScript commands are intentionally not a separate control surface yet. Keeping AppleScript routed through Shortcuts avoids another protocol while preserving a scriptable path.

## Entitlements And Permissions

App Intents and App Shortcuts do not require an extra entitlement by themselves when they are compiled into the app target.

For the current menu-bar shell:

| Capability | Required for | Notes |
|------------|--------------|-------|
| Screen Recording permission | ScreenCaptureKit sidecar capture | User grants this in System Settings for the shipped app or sidecar binary. |
| Apple Events automation | `Open TUI` when sandboxed | The app launches Terminal through AppleScript. A sandboxed distribution needs `com.apple.security.automation.apple-events` and `NSAppleEventsUsageDescription`. |
| Network client | Local WebSocket control when sandboxed | The menu-bar app talks to `ws://127.0.0.1:9877`; sandboxed builds need outbound network client entitlement. |

The current Developer ID DMG flow is not sandboxed, so the entitlement list is a packaging guide for future sandboxed/App Store-style builds rather than a new requirement for source builds.

## Build Check

Run:

```console
$ swift build --package-path macos/AkiMenuBar
```

The Shortcuts metadata is compiled into the `AkiMenuBar` target. After launching the built app bundle, macOS can discover the shortcuts through the Shortcuts app.
