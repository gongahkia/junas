# Product Usability Pass - 2026-07-04

Status: local backend/API evaluation is usable from a checkout after prerequisites;
public launch and broad adoption remain on hold.

Commit under test: `82c59d89` (`docs: document distribution path status`).
Environment: macOS, `uv`, Python 3.12, local strict/offline profile.

## Commands Run

| Command | Result | Product signal |
|---|---|---|
| `./scripts/demo.sh` | Pass. Printed three deterministic cases and `demo_completed: true`. | First-run demo is understandable and exercises GenAI prompt, email/MNPI, and clean text flows. |
| `UV_PROJECT_ENVIRONMENT=.venv-uv UV_PYTHON=3.12 ./scripts/verify_runtime.sh` | Initial fail: strict preflight could not load `en_core_web_sm`. | README prerequisite is real; users must install the spaCy model before the standard verifier. |
| `UV_PROJECT_ENVIRONMENT=.venv-uv UV_PYTHON=3.12 uv run python -m spacy download en_core_web_sm` | Pass. Installed `en-core-web-sm==3.8.0`. | Missing-model remediation is a single documented command. |
| `UV_PROJECT_ENVIRONMENT=.venv-uv UV_PYTHON=3.12 ./scripts/verify_runtime.sh` | Pass. Preflight warnings: none. Focused tests: 61 passed. Backend smoke passed. | Runtime health/readiness, core review, rewrite, redaction, metrics, and classify paths work locally. |
| `UV_PROJECT_ENVIRONMENT=.venv-uv UV_PYTHON=3.12 uv run pytest test/test_product_value_report.py -q` | Pass. 2 tests passed. | Product-value reporting path is test-covered and raw-content-free. |

## Demo Outcomes

The deterministic demo produced:

- SG NRIC in a GenAI prompt: `decision: rewrite_required`,
  `send_allowed: false`, required actions included `redact_pii`,
  `request_approval`, and `safe_rewrite`.
- M&A MNPI before announcement: `decision: block`, `send_allowed: false`,
  required actions included `hold_until_public` and `request_approval`.
- Clean internal text: `decision: allow`, `send_allowed: true`, findings `none`.

## Usable Now

- Local checkout install path is actionable after `uv sync`, spaCy model install,
  preflight, and demo commands.
- The demo output explains risk, policy decision, required actions, findings, legal
  basis, and citation snippets without requiring cloud providers.
- The standard verifier covers `/health`, `/ready`, `/diagnostics`, `/metrics`,
  `/review`, `/pseudonymize`, `/anonymize`, `/redact`, `/classify`, and related
  contract paths through focused tests plus a live backend smoke.
- Product-value metrics have a raw-free aggregation script and tests.

## Not Yet Adoptable For Public Launch

- Hosted demo work remains open in GitHub issues #84 and #85.
- No external tester has run the current install/demo path and reported results.
- Homebrew, Nix, signed DMG, and app-store-style installs are not current install
  paths.
- Adapter deployment is not yet certified in a real tenant or buyer environment.
- No pilot has measured avoided risky sends, accepted rewrites, reviewer decisions,
  false-positive fatigue, or audit-pack export rate against the pilot rubric.

## Decision

Use Junas for local evaluator walkthroughs and API-pilot preparation. Hold public launch/adoption claims until hosted demo verification, external tester evidence, and at least one pilot workflow report exist.

Allowed wording: "local backend/API evaluation works from a checkout after the
documented spaCy model prerequisite."

Forbidden wording: "launch-ready", "production-ready", "broadly adopted",
"one-click install", "verified by external testers", or "low-friction pilot"
without the missing evidence above.
