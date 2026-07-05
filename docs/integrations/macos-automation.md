# macOS Automation

Source: [`integrations/macos_automation/`](../../integrations/macos_automation/)

Maturity: `experimental-local-fallback`

Primary UI: the future menu-bar app remains the primary UI. These AppleScript and
Shortcuts paths are explicit power-user wrappers around the local daemon and
`junas-watch`; they are not endpoint enforcement.

## AppleScript Action

`review-and-redact-clipboard.applescript` reviews the current macOS clipboard via
the local daemon. When findings exist, it calls `/anonymize` and copies the
anonymized text back to the clipboard.

Prerequisites:

- local daemon running on `http://127.0.0.1:8765`
- `junas-watch` installed or `JUNAS_WATCH_COMMAND` pointing to the console script
- optional `JUNAS_LOCAL_TOKEN_FILE` when the local daemon requires a token

Run from a checkout:

```sh
JUNAS_WATCH_COMMAND="$PWD/.venv/bin/junas-watch" \
osascript integrations/macos_automation/review-and-redact-clipboard.applescript
```

For packaged installs, set `JUNAS_WATCH_COMMAND` to the installed `junas-watch`
path for that package.

The script returns the `junas-watch` JSON summary and displays a local
notification. It does not print raw clipboard text.

## Shortcuts

Use macOS Shortcuts with a "Run Shell Script" action that calls the same
`osascript` command above. Keep this shortcut manual or explicitly user-triggered;
do not bind it to broad background automation.

For a "Run AppleScript" action, paste the script body and set `watchCommand` to
the installed `junas-watch` path if the Shortcuts environment cannot resolve it
from `PATH`.

## Entitlements

Current script form:

- no Junas app entitlement is declared by this repo change because the action is
  a user-run AppleScript/Shortcuts wrapper over a local CLI
- clipboard access is through `pbpaste` and `pbcopy` inside `junas-watch`
- local daemon access is loopback HTTP plus optional `X-Junas-Local-Token`
- notifications use AppleScript `display notification`

If this action is later moved into a signed sandboxed menu-bar app:

- keep the menu-bar app as the primary UI and expose this as an optional command
- add `NSAppleEventsUsageDescription` only if the app sends Apple Events to other
  apps
- add `com.apple.security.automation.apple-events` only for a sandboxed app that
  sends Apple Events to other apps
- use App Intents/App Shortcuts for native Shortcuts integration when the app
  bundle exists

Apple references checked 2026-07-04:

- <https://developer.apple.com/documentation/appintents>
- <https://developer.apple.com/documentation/bundleresources/entitlements/com_apple_security_automation_apple-events>
- <https://developer.apple.com/documentation/bundleresources/information-property-list/nsappleeventsusagedescription>

## Limits

- This does not capture or redact video.
- This does not inspect browser DOM.
- This does not block paste, send, upload, or save.
- Clipboard mode remains explicit opt-in.
