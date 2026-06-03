# Show HN Readiness Gate

Do not submit a Show HN post until every required gate below is checked, dated, and backed by evidence. This checklist is a release gate, not a status report. Unchecked items mean the Show HN launch is not ready.

## Required Gates

| Gate | Pass condition | Evidence to record |
|------|----------------|--------------------|
| Signed DMG launches on a stock Mac | A signed and notarized `Aki-<version>-macos.dmg` downloads from the GitHub Release, mounts, installs, and launches on a Mac without local developer state. | Version, release URL, macOS version, architecture, `spctl` result, tester/date. |
| Homebrew cask install works end to end | `brew tap gongahkia/aki && brew install --cask aki` installs the same signed DMG, launches `Aki.app`, and uninstalls cleanly. | Commands run, cask version, macOS version, architecture, tester/date. |
| Hero GIF is in the README | `README.md` embeds `asset/demo/hero-ascii-redaction.gif`, and the file exists in the repository. | Commit SHA containing both README link and GIF file. |
| External user has installed successfully | At least one person outside the maintainer's machine installs through the public path and confirms launch. | Tester name or handle, install path, macOS version, architecture, date, notes. |
| Known limitations are published | `README.md` includes a `Known limitations` section that explains leak-risk boundaries and operational fallback. | Commit SHA or README permalink. |
| Version numbers are consistent | Workspace version, README badge, cask version, release tag, and DMG filename all refer to the same version. | Version string, release tag, command output or permalinks. |

## Tracking Checklist

Write the evidence link, tester, and date next to each item before checking it off.

- [ ] Signed DMG downloads, installs, and launches on a stock Mac:
- [ ] Homebrew cask installs, launches, and uninstalls end to end:
- [ ] README hero GIF is present and visible:
- [ ] External user install is confirmed:
- [ ] Known limitations section is published:
- [ ] Cargo, README badge, cask, release tag, and DMG versions match:

## Verification Commands

Run these before marking the gate complete:

```console
$ rg -n "Version [0-9]|version-[0-9]|version \"|version = \"" README.md Cargo.toml Casks/aki.rb
$ test -f asset/demo/hero-ascii-redaction.gif
$ gh release view v0.1.0 --json tagName,name,assets
$ xcrun stapler validate /Volumes/Aki/Aki.app
$ spctl --assess --type open --verbose /Volumes/Aki/Aki.app
$ brew tap gongahkia/aki
$ brew install --cask aki
$ brew uninstall --cask aki
```

Replace `v0.1.0` with the release being launched. Run the install checks on a machine that did not build the app locally.

## Launch Copy Rule

Draft launch copy may describe the intended product and current local-first behavior, but it must not claim the Show HN gate has passed until every required gate above is complete. Avoid wording like "ready for public launch" or "install now with Homebrew" while the signed DMG, cask install, and external-user install evidence are still missing.

## Evidence Template

Copy this block into the release notes or launch tracker when the gate is complete:

```text
Show HN gate for v<version>

- Signed DMG:
  - Release URL:
  - macOS:
  - Architecture:
  - Tester/date:
  - spctl/stapler result:
- Homebrew cask:
  - Commands:
  - Cask version:
  - Tester/date:
- Hero GIF:
  - README permalink:
  - GIF permalink:
- External install:
  - Tester:
  - Install path:
  - macOS/architecture:
  - Result:
- Known limitations:
  - README permalink:
- Version consistency:
  - Workspace:
  - Badge:
  - Cask:
  - Release tag:
  - DMG:
```
