# Release Process

Install releases use `vMAJOR.MINOR.PATCH` tags and must match
`project.version` in `pyproject.toml`. Media-only tags such as
`readme-demo-assets-YYYY-MM-DD` are allowed for README images and videos, but
they are not install releases.

Before tagging an install release:

1. Update `CHANGELOG.md` and any release-specific notes under `docs/releases/`.
2. Confirm `README.md` references the same version as `pyproject.toml`.
3. Build package artifacts with `uv build`.
4. Attach the matching `junas-<version>.tar.gz` and
   `junas-<version>-py3-none-any.whl` artifacts to the GitHub release.
5. Link the release artifacts from the changelog or release notes.

Do not attach signed macOS DMGs, Homebrew formulae, Nix packages, or adapter
bundles unless the matching packaging, signing, install, and rollback evidence is
also committed.
