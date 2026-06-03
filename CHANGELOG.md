# Changelog

All notable release changes are tracked here. Release sections use the Git tag as the heading so the macOS release workflow can publish the matching section as GitHub Release notes.

## v0.1.0 - Next release

Tag: `v0.1.0`
Version: `0.1.0`

Install artifacts, published by the protected macOS release workflow:

- [Aki-0.1.0-macos.dmg](https://github.com/gongahkia/aki/releases/download/v0.1.0/Aki-0.1.0-macos.dmg)
- [Aki-0.1.0-macos.dmg.sha256](https://github.com/gongahkia/aki/releases/download/v0.1.0/Aki-0.1.0-macos.dmg.sha256)

### Added

- Local-first screen privacy filter with OCR and pattern-based secret/PII detection.
- TUI and headless CLI modes with virtual camera, MJPEG, OBS prototype, and direct MP4 recording outputs.
- Offline video redaction through `aki redact`.
- Menu-bar sidecar shell with AppleScript and Shortcuts automation intents.
- Local-only `aki doctor`, fake-secret demo, redaction log, foreground-app profiles, external rule-pack import, and opt-in local LLM detector.
- Architecture, benchmark, release, cask, contributing, security, and roadmap documentation.

### Release Notes

- The public release tag is `v0.1.0`.
- The README version badge, workspace version, cask version, release tag, and DMG filename must all stay on `0.1.0` for this release.
- Do not advertise the Homebrew cask as install-ready until the signed and notarized DMG plus checksum are attached to the GitHub Release.
