# Procurement Demo Scripts

Use these demo scripts for buyer walkthroughs. They are talk tracks plus commands and
fixtures; they are not proof of customer validation. Use synthetic content only.

## Demo Guardrails

- State the deployment mode and commit before each demo.
- Use synthetic prompts, emails, documents, and DMS manifests.
- Do not paste buyer confidential text into a demo.
- State whether the demo is backend-only, local-only, hosted, or customer-managed.
- Tie every claim to `docs/product/claim-review-checklist.md`.

## Backend API Only

Goal: show the backend policy contract without UI adapters.

1. Start the backend or use an already running pilot endpoint.
2. Check readiness:

```sh
curl -fsS http://127.0.0.1:8000/ready
```

3. Submit a synthetic `/review` request with `surface="api"` and
   `workflow="gateway_review"`.
4. Show `policy_decision.decision`, `send_allowed`, `required_actions`,
   `recommended_actions`, `policy_id`, `policy_version`, `review_id`, and timings.
5. Explain that direct API integration is the baseline path when the customer owns the
   service-side workflow.

Do not claim Outlook, browser, Word, DMS, Slack, or Google Workspace coverage from this
demo.

## Outlook Pre-Send

Goal: show Outlook Smart Alerts pre-send behavior for email.

1. Render and validate the manifest:

```sh
uv run python scripts/render_outlook_manifest.py --profile production --origin https://outlook-addin.example.com
uv run python scripts/validate_outlook_manifest.py dist/outlook-addin/production/manifest.xml --profile production
```

2. Use the synthetic Smart Alert fixtures or a scoped test tenant.
3. Show allow, warn, block, and approval-required states.
4. Explain that Outlook support depends on Microsoft 365 admin assignment, client
   version, Smart Alerts support, hosted runtime origin, CORS, and well-known URI setup.
5. Show failure behavior for backend unavailable or timeout.

Do not claim mobile Outlook send-time enforcement or tenant-wide email coverage until
client-family QA has been completed for assigned users.

## Browser GenAI Prompt

Goal: show prompt review for managed browser GenAI surfaces.

1. Package or load `integrations/browser_extension/` in a managed test profile.
2. Confirm backend mode, auth mode, endpoint health, and prompt-submit review setting.
3. Use a synthetic prompt in a local fixture or approved test profile.
4. Show warning confirmation, block panel, safe rewrite/redaction action, and connection
   health.
5. Explain that coverage depends on browser/extension policy, target host permissions,
   DOM selectors, CSP, frames, and target editor behavior.

Do not claim universal browser DLP, native app coverage, mobile app coverage, or
coverage for arbitrary SaaS UIs.

## DMS Upload

Goal: show service-side document upload/check-in review.

1. Prepare a synthetic DMS manifest with document id, matter id, path, document type,
   source jurisdiction, destination jurisdiction, and requested action.
2. Run the scanner or customer hook equivalent:

```sh
uv run python scripts/scan_dms_manifest.py manifest.json --output dms-review.json
```

3. Show how the DMS path passes `surface="dms"` and `workflow="document_upload"` to
   `/review`.
4. Show allow, warn, block, approval, and audit metadata fields.
5. Explain that the shipped scanner is vendor-neutral and does not write back to a
   repository without a customer hook.

Do not claim iManage, NetDocuments, Google Drive, SharePoint, or other DMS write-back
unless a certified customer hook exists.

## Audit Export

Goal: show evidence generation and verification.

1. Use a review id created from a synthetic demo.
2. Export an audit pack:

```sh
uv run python scripts/export_audit_pack.py --review-id <review-id> --output audit-pack.zip
```

3. Verify the audit pack and journal:

```sh
uv run python scripts/verify_audit_pack.py audit-pack.zip
uv run python scripts/verify_journal.py
```

4. Show manifest, policy id/version, decision metadata, hashes, counts, and verification
   result.
5. Explain that audit packs must not be treated as universal deletion or legal-hold
   automation; retention and subject erasure remain operator-owned.

Do not attach raw customer content to procurement follow-ups. Share only sanitized
metadata, hashes, screenshots, and reports approved by the claim-review checklist.
