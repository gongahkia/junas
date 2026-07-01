# Dependency And Artifact Security Scanning

Junas release and security review must scan every dependency surface that can ship code
or executable assets. This is a required gate for changes touching `pyproject.toml`,
`uv.lock`, `integrations/`, `packaging/`, `scripts/package_*`, or Office/browser
manifests.

## Evidence Directory

Write local scan evidence under `reports/security/`. Do not commit raw scan output from
private builds unless it has been reviewed for hostnames, usernames, paths, tokens, and
raw document text.

```sh
mkdir -p reports/security
```

## Python Packages

Junas uses `uv.lock` as the Python dependency source of truth. Audit the locked graph,
including optional extras, before merging dependency changes or cutting a release.

```sh
uv export --locked --all-extras --format requirements-txt --output-file reports/security/requirements-all.txt
uvx pip-audit -r reports/security/requirements-all.txt --progress-spinner off
```

Expected handling:

- High or critical findings block release until upgraded, removed, or documented with a
  time-bound exception.
- Exceptions must name the package, CVE/advisory id, affected version, reason the code
  path is unreachable or accepted, owner, expiry date, and replacement plan.
- Do not rely on an unlocked environment audit; the checked-in lockfile is the artifact
  under review.

References: `pip-audit` official docs: <https://pypa.github.io/pip-audit/>.

## Browser Extension JS

Current browser extension assets are static MV3 files under
`integrations/browser_extension/`; there is no `package.json` or npm lockfile in the
repo. For the current static shape, review these files on every extension release:

- `integrations/browser_extension/manifest.json`
- `integrations/browser_extension/adapters.js`
- `integrations/browser_extension/content.js`
- `integrations/browser_extension/options.js`
- `integrations/browser_extension/service_worker.js`
- `scripts/package_browser_extension.sh`

Required checks:

```sh
uv run ruff check test/test_browser_extension*.py test/test_deployment_docs.py
uv run pytest test/test_browser_extension*.py test/test_deployment_docs.py
./scripts/package_browser_extension.sh
```

If extension dependencies are introduced later, add a committed lockfile and run npm
audit from that adapter directory:

```sh
npm ci
npm audit --audit-level=high
```

Do not add vendored, minified, or remote-loaded third-party JS without a lockfile,
license source, and documented reason. Manifest permission additions must explain the
minimum required host and extension permissions in the same PR.

Reference: npm audit official docs: <https://docs.npmjs.com/cli/v11/commands/npm-audit>.

## Office Assets

Outlook and Word add-ins ship static HTML, JS, and XML manifests under
`integrations/outlook_addin/` and `integrations/word_addin/`. They currently have no
npm dependency graph, so scan scope is manifest validation, static source review, and
adapter privacy tests.

Outlook manifest rendering and validation:

```sh
uv run python scripts/render_outlook_manifest.py \
  --profile staging \
  --origin https://junas.example.invalid \
  --output dist/outlook-addin/staging/manifest.xml
uv run python scripts/validate_outlook_manifest.py \
  dist/outlook-addin/staging/manifest.xml \
  --profile staging
```

Office source regression tests:

```sh
uv run pytest test/test_outlook*.py test/test_deployment_docs.py
```

If Office assets later gain npm dependencies, require `package-lock.json`, `npm ci`, and
`npm audit --audit-level=high` for that add-in directory before release.

## PyInstaller Output

The desktop bundle is a second security surface because PyInstaller freezes Python
packages into `dist/junas-local/`. Audit the packaging dependency set before building,
then inventory the exact output.

```sh
uv export --locked --extra packaging --format requirements-txt --output-file reports/security/requirements-packaging.txt
uvx pip-audit -r reports/security/requirements-packaging.txt --progress-spinner off
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
uv run pyinstaller packaging/junas-local.spec
find dist/junas-local -type f -print0 | sort -z | xargs -0 shasum -a 256 > reports/security/junas-local.sha256
```

After a dependency fix, rebuild the PyInstaller output from a clean environment. Do not
patch files inside `dist/junas-local/` in place.

## Pull Request Gate

For GitHub-hosted review, enable Dependency Review on PRs that modify dependency or
lock files and treat it as advisory evidence alongside the commands above. Dependency
Review is not a replacement for scanning the PyInstaller bundle or static adapter
assets.

Reference: GitHub Dependency Review docs:
<https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review>.
