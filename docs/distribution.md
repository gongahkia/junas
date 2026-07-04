# Distribution Paths

Status: 2026-07-04.

Junas currently ships as a Python/FastAPI package and source checkout. The
current install release is [`v0.1.0`](https://github.com/gongahkia/junas/releases/tag/v0.1.0)
with a wheel and source distribution:

- [`junas-0.1.0-py3-none-any.whl`](https://github.com/gongahkia/junas/releases/download/v0.1.0/junas-0.1.0-py3-none-any.whl)
- [`junas-0.1.0.tar.gz`](https://github.com/gongahkia/junas/releases/download/v0.1.0/junas-0.1.0.tar.gz)

The checkout-first path in `README.md#install-locally` remains the primary local
evaluation path until packaged app installers are signed and tested.

## Cargo

`cargo install aki` is not available for this repository.

Reasons:

- The current product is Junas, implemented as Python/FastAPI.
- There is no `Cargo.toml` in this repo.
- No `aki` or `junas` crate is published from this repo.
- Legacy Aki/Rust distribution language is not current Junas release guidance.

Do not document `cargo install` as an install path unless a Rust crate is added,
published, versioned, and wired into CI/release artifacts.

## Nix

No Nix flake or package expression is committed yet.

Implementation plan:

1. Add a `flake.nix` that packages `pyproject.toml`/`uv.lock` with Python 3.12.
2. Expose `packages.<system>.junas` and `apps.<system>.junas`.
3. Add a dev shell with `uv`, Python 3.12, and test dependencies.
4. Run `nix flake check` in CI before advertising `nix run`.
5. Document the exact command only after the flake installs and starts the local backend from a clean checkout.

Expected command shape after implementation:

```sh
nix run github:gongahkia/junas#junas
```

This is a plan, not a current install path.

## Homebrew And DMG

No public Homebrew formula/cask or signed macOS DMG is published for Junas
v0.1.0. README and release notes must not present either as a current install
path until the packaging, signing, notarization, rollback, and install QA
evidence exists. Signing credential custody and the project-level Developer ID
decision are defined in `docs/macos-signing-credentials.md`. The DMG packaging
pipeline and stock-Mac verification gate are defined in
`docs/macos-dmg-release.md`.

The chosen public Homebrew tap is `gongahkia/tap`; its GitHub repository is
`gongahkia/homebrew-tap`. A staged, non-release cask draft lives at
`packaging/homebrew/Casks/aki.rb`. Homebrew release gates and install commands
are defined in `docs/homebrew-cask.md`.

The local macOS daemon can still be built from source with
`./scripts/package_macos_desktop.sh`; see `docs/install.md` and
`docs/deployment-local-only.md`.
