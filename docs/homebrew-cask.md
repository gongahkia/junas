# Homebrew Cask Release

Status: staging only; public install is blocked on a signed and notarized DMG.

## Tap Naming

Use `gongahkia/tap` for public installs. The GitHub repository for that tap is
`gongahkia/homebrew-tap`; Homebrew maps `brew tap gongahkia/tap` to that
repository name. This keeps the public command stable if Junas later adds more
formulae or casks.

The staged cask source in this repo is `packaging/homebrew/Casks/aki.rb`. Copy it
to `Casks/aki.rb` in `gongahkia/homebrew-tap` only after the signed DMG release
gate passes.

## Public Commands

Do not publish these as the README primary install path until the release gate
below passes end to end:

```sh
brew tap gongahkia/tap
brew install --cask aki
brew upgrade --cask aki
brew uninstall --cask aki
```

## Release Gate

1. Build the signed release DMG with `docs/macos-dmg-release.md`.
2. Verify notarization, stapling, `spctl`, DMG attach, app copy, launch, and
   uninstall on a stock Mac.
3. Update the staged cask from the signed DMG:

   ```sh
   uv run python scripts/update_homebrew_cask.py \
     --version 0.1.0 \
     --dmg dist/JunasMenuBar-0.1.0.dmg
   ```

4. Confirm the generated `sha256` matches
   `shasum -a 256 dist/JunasMenuBar-<version>.dmg`.
5. Confirm the cask URL points at the signed DMG release asset.
6. Before copying to the real tap, run the local tap style verifier:

   ```sh
   ./scripts/verify_homebrew_cask.sh
   ```

7. In the real tap checkout, run `brew style --cask Casks/aki.rb`.
8. In the real tap checkout, run `brew audit --cask --strict --online aki`.
9. On a clean Mac, run the public tap/install/upgrade/uninstall commands above.
10. Link the signed DMG and Homebrew install path from release notes and README.

Until those checks pass, README and release notes must keep Homebrew marked as a
planned install path.
