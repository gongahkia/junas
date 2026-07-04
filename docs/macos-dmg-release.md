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

## Protected CI Release

Use `.github/workflows/release-macos-dmg.yml` for public release artifacts after
the `macos-release` environment has the secrets listed in
`docs/macos-signing-credentials.md`.

The manual workflow:

1. imports the project Developer ID certificate into a temporary keychain
2. stores the `junas-notary` notarytool profile
3. runs `scripts/package_macos_dmg.sh` with `JUNAS_RELEASE_SIGNING_REQUIRED=1`
4. verifies the stapled DMG with `spctl`
5. mounts the DMG and checks `JunasMenuBar.app`
6. copies the app to a runner-local path and checks executable assessment
7. uploads the signed DMG and `.sha256` file as GitHub Actions artifacts
8. optionally uploads both files to an existing GitHub release when
   `upload_to_release=true`

## Stock-Mac Verification

Before release notes or Homebrew cask publication:

```sh
JUNAS_VERIFY_OPEN=1 ./scripts/verify_macos_dmg_release.sh dist/JunasMenuBar-0.1.0.dmg
```

Verify the menu-bar app opens, start/pause/stop controls work, `Open TUI` launches `aki --tui`, and no Gatekeeper dialog blocks launch.

The verifier prints the SHA-256 hash, checks the DMG assessment with
`spctl -a -t open --context context:primary-signature`, mounts the DMG, copies
`JunasMenuBar.app` to `${JUNAS_VERIFY_INSTALL_DIR:-/Applications}`, checks the
bundled sidecar is executable, and assesses the installed app with
`spctl -a -t exec -vv`. It refuses to overwrite an existing app unless
`JUNAS_VERIFY_OVERWRITE=1` is set.

## Release Notes Gate

Do not link a DMG from release notes until:

- `JUNAS_RELEASE_SIGNING_REQUIRED=1 ./scripts/package_macos_dmg.sh` completes
- `.github/workflows/release-macos-dmg.yml` completes for the same version or an
  equivalent protected release job captures the same evidence
- notarization and stapling complete without error
- the stock-Mac verification above passes
- the SHA-256 hash is recorded for the Homebrew cask
