# Software Bill Of Materials

Junas emits CycloneDX 1.5 JSON SBOMs from the locked Python dependency graph. Generate
SBOMs for both shipped application surfaces before release:

- `junas-server`: FastAPI backend with the `server` optional extra.
- `junas-local-desktop`: local desktop/PyInstaller surface with `local` and `packaging`
  optional extras.

References:

- uv `export` supports CycloneDX 1.5 JSON: <https://docs.astral.sh/uv/reference/cli/#uv-export>
- CycloneDX overview: <https://cyclonedx.org/specification/overview/>
- CycloneDX integrity verification: <https://cyclonedx.org/use-cases/integrity-verification/>

## Generate Dependency SBOMs

Use the checked-in lockfile only:

```sh
uv run python scripts/generate_sbom.py --target all --out-dir reports/sbom
```

Outputs:

- `reports/sbom/junas-server.cdx.json`
- `reports/sbom/junas-local-desktop.cdx.json`

Each SBOM contains Junas metadata properties:

- `junas:sbom_target`
- `junas:artifact`
- `junas:dependency_source=uv.lock`
- `junas:generator=scripts/generate_sbom.py`

## Server Artifact

The server SBOM is generated with:

```sh
uv export --locked --extra server --format cyclonedx1.5 --preview-features sbom-export
```

This covers the backend dependency graph intended for hosted deterministic review plus
opt-in public evidence and LLM provider integrations. Attach this SBOM to server image
or deployment release evidence.

## Local Desktop Artifact

The desktop dependency SBOM is generated with:

```sh
uv export --locked --extra local --extra packaging --format cyclonedx1.5 --preview-features sbom-export
```

After building the PyInstaller bundle, regenerate the desktop SBOM with file hashes
required:

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
uv run pyinstaller packaging/junas-local.spec
uv run python scripts/generate_sbom.py \
  --target desktop \
  --out-dir reports/sbom \
  --require-desktop-artifact
```

When `dist/junas-local/` exists, the desktop SBOM includes one CycloneDX `file`
component per bundled file with a SHA-256 hash and `junas:artifact_surface=pyinstaller`.
If the artifact directory is missing and `--require-desktop-artifact` is not set, the
dependency SBOM is still generated with `junas:desktop_artifact_status=missing`.

## Release Gate

Release evidence must include:

- Current dependency scan output from `docs/security/dependency-scanning.md`.
- `reports/sbom/junas-server.cdx.json` for server releases.
- `reports/sbom/junas-local-desktop.cdx.json` for local desktop releases.
- A rebuilt SBOM after every dependency update, PyInstaller spec change, or desktop
  bundle rebuild.
- No manual edits to files inside `dist/junas-local/`; rebuild and regenerate instead.
