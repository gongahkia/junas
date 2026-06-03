# macOS Release Process

This process builds the SwiftUI menu-bar app, embeds the Rust `aki` sidecar, vendors non-system dylib dependencies, signs the bundle, notarizes it with Apple, staples tickets, and creates a DMG.

## Prerequisites

Install local build dependencies:

```console
$ brew install rust tesseract libarchive
```

The signed release path requires:

- A Developer ID Application certificate in the signing keychain.
- Apple notarization credentials, preferably stored as a `notarytool` keychain profile.
- Xcode command line tools with `codesign`, `hdiutil`, `stapler`, and `notarytool`.

The current development machine only has an Apple Development identity. That can build and run locally, but it cannot produce a Gatekeeper-clean public DMG. Public releases must use a Developer ID Application identity.

## Local Unsigned Validation

Use this to verify bundle layout, dylib vendoring, install-name rewriting, and DMG creation without Apple credentials:

```console
$ scripts/release_macos_dmg.sh --unsigned
```

This produces an ad-hoc-signed local test artifact under `dist/macos/`. It is not a release artifact and will not satisfy Gatekeeper for downloaded distribution.

## Signed And Notarized Release

Use either a keychain profile:

```console
$ export AKI_SIGN_IDENTITY="Developer ID Application: Example Name (TEAMID)"
$ export AKI_NOTARY_KEYCHAIN_PROFILE="aki-notary"
$ scripts/release_macos_dmg.sh --version 0.1.0
```

Or pass notary credentials through environment variables:

```console
$ export AKI_SIGN_IDENTITY="Developer ID Application: Example Name (TEAMID)"
$ export AKI_NOTARY_APPLE_ID="apple-id@example.com"
$ export AKI_NOTARY_TEAM_ID="TEAMID"
$ export AKI_NOTARY_PASSWORD="app-specific-password"
$ scripts/release_macos_dmg.sh --version 0.1.0
```

The script writes:

- `dist/macos/Aki-<version>-macos.dmg`
- `dist/macos/Aki-<version>-macos.dmg.sha256`

## What The Script Verifies

The release script:

- Builds `privacy-tui` in release mode.
- Builds `macos/AkiMenuBar` in release mode.
- Creates `Aki.app` with `AkiMenuBar` in `Contents/MacOS/` and the Rust sidecar in `Contents/Resources/aki`.
- Recursively copies Homebrew-linked dylibs into `Contents/Frameworks/`.
- Rewrites copied dylib install names to `@executable_path/../Frameworks/...` for the sidecar.
- Signs dylibs, the sidecar, the Swift executable, the app bundle, and the DMG.
- Notarizes and staples the app bundle and the DMG.
- Runs `codesign --verify`, `xcrun stapler validate`, and `spctl --assess`.

## GitHub Release Workflow

The manual workflow at `.github/workflows/release-macos.yml` packages and uploads the DMG to a GitHub Release. Required secrets:

- `MACOS_DEVELOPER_ID_APPLICATION_CERT_P12_BASE64`
- `MACOS_DEVELOPER_ID_APPLICATION_CERT_PASSWORD`
- `MACOS_DEVELOPER_ID_APPLICATION_IDENTITY`
- `AKI_NOTARY_APPLE_ID`
- `AKI_NOTARY_TEAM_ID`
- `AKI_NOTARY_PASSWORD`

The workflow creates or updates the requested GitHub Release and uploads the DMG plus SHA-256 file, so the release notes link directly to the artifact.

## Failure Modes

If `AKI_SIGN_IDENTITY` is missing or is not a Developer ID Application identity, the script fails before creating a public release artifact.

If notarization credentials are missing, the script fails before submission. It does not print notary passwords.

If a Homebrew-linked dylib is missing during dependency vendoring, the script fails instead of creating a DMG that would break on a stock Mac.
