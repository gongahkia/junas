# Contributing

Thanks for helping improve Aki. This project is macOS-first and local-first, so contributor work should keep the privacy boundary explicit: screenshots, OCR text, logs, fixtures, and diagnostics must stay local unless the user deliberately exports them.

## Local Setup

Install the Rust stable toolchain and native OCR/video dependencies.

On macOS:

```console
$ brew install rust tesseract ffmpeg
```

On Ubuntu or Debian:

```console
$ sudo apt-get update
$ sudo apt-get install -y pkg-config clang libclang-dev libtesseract-dev libleptonica-dev tesseract-ocr ffmpeg libxcb1-dev libpipewire-0.3-dev libspa-0.2-dev
```

Clone and build the workspace:

```console
$ git clone https://github.com/gongahkia/aki
$ cd aki
$ cargo build --all
$ cargo run -p privacy-tui -- doctor
```

The optional macOS menu-bar shell is a Swift package under `macos/AkiMenuBar`:

```console
$ cargo build -p privacy-tui
$ AKI_BINARY="$PWD/target/debug/aki" swift build --package-path macos/AkiMenuBar
```

## Validation

Run the same Rust checks used by CI before opening a pull request:

```console
$ cargo fmt --all -- --check
$ cargo clippy --all-targets -- -D warnings
$ cargo build --all
$ cargo test --all
```

Use targeted tests while iterating:

```console
$ cargo test -p privacy-core detection::scanner::tests::synthetic_fixture_corpus_recall_is_tracked
$ cargo test -p privacy-core detection::external_rules::tests::imports_community_rule_pack_sample
$ cargo test -p privacy-tui doctor
$ cargo test -p privacy-tui demo
```

Run `aki doctor` before filing setup bugs. Its output is local-only and should show `PASS`, `WARN`, or `FAIL` with remediation text for each check.

## Detector And Fixture Work

Detector changes should include fake, reserved, or project-specific fixture values. Do not paste real access tokens, customer data, private keys, screenshots, or OCR text into issues, tests, or docs.

Good detector pull requests usually include:

- A fixture string under the relevant crate or rule-pack fixture directory.
- A unit test proving the detector matches the fixture and avoids an obvious false positive.
- A quick manual check with `aki test-patterns`.

Example:

```console
$ cargo run -p privacy-tui -- test-patterns "DEMO_API_TOKEN=aki_fixture_ABCDEF123456"
```

For community rule-pack work, follow [`docs/community-rule-packs.md`](./docs/community-rule-packs.md).

## Pull Requests

- Keep each pull request scoped to one issue or one clearly described improvement.
- Link the issue in the PR body with `Closes #123` when the PR fully resolves it.
- Include the validation commands you ran.
- Call out skipped checks and the reason.
- Prefer docs, tests, and small examples that future contributors can reuse.

## Good First Issues

Start with issues that have tight scope and low coupling to the capture pipeline:

- [#31 Add SECURITY.md reporting path](https://github.com/gongahkia/aki/issues/31)
- [#32 Tag releases with changelogs](https://github.com/gongahkia/aki/issues/32)
- [#33 Draft companion engineering blog post](https://github.com/gongahkia/aki/issues/33)
- [#35 Prepare platform-specific launch copy](https://github.com/gongahkia/aki/issues/35)
- [#37 Create logo, favicon, and social card assets](https://github.com/gongahkia/aki/issues/37)
- [#40 Document anti-goals and stretch backlog](https://github.com/gongahkia/aki/issues/40)

The broader Now/Next/Later order is tracked in [`docs/roadmap.md`](./docs/roadmap.md).
