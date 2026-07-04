# junas-local packaging

Builds the offline-default desktop SKU as a single-folder PyInstaller distribution.

## Prereqs

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
```

## Build

```sh
uv run pyinstaller packaging/junas-local.spec
```

Artifacts land in `dist/junas-local/`. The launcher is `dist/junas-local/junas-local`.

## Run

```sh
./dist/junas-local/junas-local
# binds 127.0.0.1:8765 by default; deterministic engine only; cloud paths disabled
```

Override the loopback bind at launch:

```sh
JUNAS_HOST=127.0.0.1 JUNAS_PORT=8765 ./dist/junas-local/junas-local
```

Use a Unix-domain socket instead of TCP loopback when the client supports it:

```sh
JUNAS_LOCAL_SOCKET_PATH=/tmp/junas-local.sock ./dist/junas-local/junas-local
```

`integrations/browser_extension/` is the MV3 thin-client template for ChatGPT / Claude / Gemini. `integrations/outlook_addin/` is the Office.js taskpane template for Outlook pre-send review.

The local spec excludes the public-evidence and LLM-adjudicator modules. Use the source or Docker server runtime when a tenant has opted into those cloud-capable paths.

## macOS release

```sh
JUNAS_CODESIGN_IDENTITY="Developer ID Application: Example Pte Ltd (TEAMID)" \
JUNAS_NOTARYTOOL_PROFILE=junas-notary \
JUNAS_RELEASE_SIGNING_REQUIRED=1 \
./scripts/package_macos_desktop.sh
```

Release signing uses the project-level Developer ID policy in `docs/macos-signing-credentials.md`. Local contributors can omit these variables for unsigned developer artifacts.

Optional LaunchAgent lifecycle, admin-controlled and not a developer quickstart:

```sh
packaging/macos/install.sh
packaging/macos/update.sh
packaging/macos/uninstall.sh
```

The LaunchAgent binds `127.0.0.1:8765`, enables local daemon ACLs, and starts at login.
Run `./dist/junas-local/junas-local` directly for developer smoke tests unless an
operator has approved LaunchAgent auto-start.

Use `packaging/macos/install.sh` only after the packaged artifact has been built and an
operator has approved login-time auto-start for the local profile. Use
`packaging/macos/update.sh` after rebuilding `dist/junas-local/` when the existing
LaunchAgent-managed install should move to the new artifact. Use
`packaging/macos/uninstall.sh` to remove the LaunchAgent-managed bundle during rollback,
device handoff, pilot exit, or when the profile should return to direct manual launch.

## Extension and Office surfaces

```sh
./scripts/package_browser_extension.sh
```

`integrations/browser_extension/` is the MV3 browser thin client. `integrations/outlook_addin/` is the Outlook taskpane plus Smart Alerts pre-send hook. `integrations/word_addin/` is the Word taskpane review surface.

Chrome/Edge extension rollout should use the Chrome Web Store, Edge Add-ons, or enterprise policy. Office add-ins should use Microsoft 365 admin-managed deployment for production users.
