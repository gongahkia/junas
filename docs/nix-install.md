# Nix Install

The Nix path builds the Rust CLI binary named `aki` from source. It is useful for Nix users and CI-style development shells, but it is not the signed macOS app bundle. The primary macOS app install path remains the Homebrew cask after a signed and notarized DMG exists.

## Run Without Installing

From this repository:

```console
$ nix run .#aki -- doctor
```

From GitHub:

```console
$ nix run github:gongahkia/aki#aki -- doctor
```

Pin a specific revision for repeatable installs:

```console
$ nix run github:gongahkia/aki/<commit-sha>#aki -- --help
```

## Install To A Profile

```console
$ nix profile install github:gongahkia/aki#aki
$ aki doctor
```

## Developer Shell

```console
$ nix develop
$ cargo fmt --all -- --check
$ cargo clippy --all-targets -- -D warnings
$ cargo test --all
```

The flake shell includes Rust, Tesseract, ffmpeg, libclang, pkg-config, and the Linux or macOS native libraries needed by the workspace.

## Validation

When Nix is available, validate the package and app outputs with:

```console
$ nix flake check
$ nix build .#aki
$ result/bin/aki doctor
```
