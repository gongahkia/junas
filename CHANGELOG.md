# Changelog

Customer-facing releases use `vMAJOR.MINOR.PATCH` tags that match the Python
package version in `pyproject.toml`. Demo-asset tags such as
`readme-demo-assets-YYYY-MM-DD` are media-only releases, not install releases.

## v0.1.0 - 2026-07-04

Audience: local evaluators and portfolio reviewers.
Deployment mode: local-only backend/API package.
Action required: none for existing checkouts; use the attached package artifacts
only when validating the packaged Python install path.
Rollback: use the previous checkout or remove the installed wheel with
`python -m pip uninstall junas`.

### Install Artifacts

- Wheel: [`junas-0.1.0-py3-none-any.whl`](https://github.com/gongahkia/junas/releases/download/v0.1.0/junas-0.1.0-py3-none-any.whl)
- Source distribution: [`junas-0.1.0.tar.gz`](https://github.com/gongahkia/junas/releases/download/v0.1.0/junas-0.1.0.tar.gz)
- Source tag: [`v0.1.0`](https://github.com/gongahkia/junas/releases/tag/v0.1.0)

No signed macOS DMG, Homebrew formula, Nix package, or Cargo artifact is part of
`v0.1.0`.

### Detector Accuracy Changes

- Change: initial public package baseline for the deterministic PII/MNPI review
  engine already documented in README and benchmark artifacts.
- Impact: no new detector behavior beyond the tagged repository state.
- Evidence: CI workflow, benchmark reports, and README-linked evaluation docs.
- Customer action: none.

### Policy Behavior Changes

- Change: initial policy decision contract package baseline.
- Impact: no migration from a prior Junas install release.
- Evidence: policy contract tests and API examples in `docs/api/`.
- Customer action: none.

### Adapter Behavior Changes

- Change: adapter source and docs are included for evaluation, but no production
  adapter package is shipped as a release artifact.
- Impact: Outlook/browser/Word/DMS/local watcher surfaces remain bounded by their
  documented maturity and deployment notes.
- Evidence: adapter smoke tests and integration docs.
- Customer action: none.

### Security Fixes

- Change: initial release includes existing auth, rate-limit, log privacy, tenant
  isolation, local daemon, and SBOM guidance.
- Impact: no credential rotation from a prior Junas install release.
- Evidence: security tests, `SECURITY.md`, and `docs/security/`.
- Customer action: review deployment docs before any non-local pilot.
