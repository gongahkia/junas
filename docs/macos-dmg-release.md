# macOS DMG Release

Status: release pipeline scaffold; public signed artifact is still blocked on project Developer ID and notary credentials.

## Artifact Shape

The release DMG contains:

- `JunasMenuBar.app`, built from `apps/macos-menu-bar/`
- bundled stdio sidecar at `JunasMenuBar.app/Contents/Resources/aki-sidecar/aki-sidecar`
- `/Applications` symlink for drag install

The menu-bar app uses the bundled sidecar first. Development can still override it:

```sh
JUNAS_SIDECAR_COMMAND="uv run aki sidecar stdio" ./script/build_and_run.sh
```

## Local Unsigned DMG

For development-only packaging checks:

```sh
uv sync --extra packaging
./scripts/package_macos_dmg.sh
```

This creates `dist/JunasMenuBar.dmg`. Unsigned output is not a release artifact, not a Homebrew cask input, and not expected to pass Gatekeeper on a stock Mac.

## Signed Release DMG

Release maintainers must follow `docs/macos-signing-credentials.md`, import the project-level Developer ID certificate into a temporary or release keychain, and create the notary profile:

```sh
xcrun notarytool store-credentials junas-notary
JUNAS_CODESIGN_IDENTITY="Developer ID Application: <release owner> (<TEAMID>)" \
JUNAS_NOTARYTOOL_PROFILE=junas-notary \
JUNAS_RELEASE_SIGNING_REQUIRED=1 \
JUNAS_DMG_OUTPUT=dist/JunasMenuBar-0.1.0.dmg \
./scripts/package_macos_dmg.sh
```

The script:

1. builds `JunasMenuBar.app` through `script/build_and_run.sh --bundle-only`
2. builds the bundled `aki-sidecar` through `packaging/aki-sidecar.spec`
3. signs the sidecar and app bundle when `JUNAS_CODESIGN_IDENTITY` is set
4. creates a compressed DMG with `hdiutil`
5. signs the DMG when `JUNAS_CODESIGN_IDENTITY` is set
6. submits, waits, staples, and assesses the DMG when `JUNAS_NOTARYTOOL_PROFILE` is set
7. prints the SHA-256 hash for release notes and Homebrew cask updates

`JUNAS_RELEASE_SIGNING_REQUIRED=1` fails before building if signing identity or notary profile configuration is missing.

## Stock-Mac Verification

Before release notes or Homebrew cask publication:

```sh
spctl -a -t open --context context:primary-signature -v dist/JunasMenuBar-0.1.0.dmg
hdiutil attach dist/JunasMenuBar-0.1.0.dmg
cp -R /Volumes/Junas/JunasMenuBar.app /Applications/
spctl -a -t exec -vv /Applications/JunasMenuBar.app
open /Applications/JunasMenuBar.app
```

Verify the menu-bar app opens, start/pause/stop controls work, `Open TUI` launches `aki --tui`, and no Gatekeeper dialog blocks launch.

## Release Notes Gate

Do not link a DMG from release notes until:

- `JUNAS_RELEASE_SIGNING_REQUIRED=1 ./scripts/package_macos_dmg.sh` completes
- notarization and stapling complete without error
- the stock-Mac verification above passes
- the SHA-256 hash is recorded for the Homebrew cask
