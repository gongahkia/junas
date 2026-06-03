# Homebrew Cask

## Tap Decision

V1 uses the project repository as the tap:

```console
$ brew tap gongahkia/aki
```

This keeps the cask, release workflow, source code, and release docs in one repository while Aki has a single app artifact. If Aki later ships multiple tools, the tap can move to `gongahkia/tap`.

## Install

After a signed and notarized GitHub Release DMG exists for the current cask version:

```console
$ brew tap gongahkia/aki
$ brew install --cask aki
```

Equivalent one-line install:

```console
$ brew install --cask gongahkia/aki/aki
```

## Upgrade

```console
$ brew update
$ brew upgrade --cask aki
```

## Uninstall

```console
$ brew uninstall --cask aki
$ brew untap gongahkia/aki
```

## Release Coupling

The cask points at:

```text
https://github.com/gongahkia/aki/releases/download/v#{version}/Aki-#{version}-macos.dmg
```

The DMG must be signed and notarized by the macOS release workflow before the cask is advertised as a working install path for that version.

The cask currently uses `sha256 :no_check` because the release workflow creates the DMG and checksum at release time. The DMG still goes through Developer ID signing, notarization, stapling, and Gatekeeper validation in `scripts/release_macos_dmg.sh`.

## Validation

Local syntax and style checks:

```console
$ brew style --cask gongahkia/aki/aki
$ brew audit --cask --skip-style gongahkia/aki/aki
$ brew info --cask gongahkia/aki/aki
```

End-to-end install validation requires the signed/notarized GitHub Release artifact to exist:

```console
$ brew tap gongahkia/aki
$ brew install --cask aki
$ brew uninstall --cask aki
```
