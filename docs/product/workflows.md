# Product Workflows

These workflows define how Junas should appear in daily work. Each path uses the backend review contract as the control point and treats adapters as optional activation surfaces.

## Outlook Send

1. User composes an email and clicks send.
2. Outlook Smart Alerts adapter collects subject, body text, recipients, attachment metadata, surface `outlook`, workflow `email_send`, and destination context.
3. Adapter calls `/review` before completing send.
4. Backend returns findings, policy decision, required actions, review id, and audit metadata.
5. Adapter allows send, warns with proceed tracking, blocks, requests approval, or offers safe rewrite based on the decision contract.

## GenAI Browser Paste

1. User drafts or pastes a prompt into a managed GenAI surface.
2. Browser adapter captures prompt text at submit time, target domain, surface `browser_genai`, workflow `prompt_submit`, and tenant policy context.
3. Adapter calls `/review` before prompt submission where supported by the target UI.
4. Backend returns policy decision and action catalog.
5. Adapter lets the user proceed, cancel, safe-rewrite, redact PII, or request approval according to tenant policy.

## DMS Upload

1. User uploads or checks in a document to a document-management system.
2. DMS integration sends extracted text or supported document payload, matter id, document filename, MIME type, destination repository, surface `dms`, and workflow `document_upload`.
3. Backend reviews content and metadata, then returns findings, policy decision, document hash, and audit evidence.
4. DMS integration accepts the upload, blocks check-in, requests legal review, or stores audit fields alongside the matter record.
5. Metadata scrub can run as a follow-on action when the decision allows document transformation.

## API Gateway Review

1. Internal workflow, gateway, or service prepares content for external sharing.
2. Service calls `/review` directly with text or document payload plus surface `api`, workflow `gateway_review`, actor role, recipient domains, and requested action.
3. Backend enforces tenant auth, evaluates policy, and returns deterministic decision metadata.
4. Caller applies allow, warn, block, rewrite, or approval behavior without requiring a UI adapter.
5. Caller uses review id and idempotency guidance to prevent duplicate review sessions.

## Legal Reviewer Override

1. A policy decision returns `approval_required`, `rewrite_required`, or a blocked state eligible for reviewer action.
2. Reviewer opens the review session without raw body exposure by default.
3. Reviewer inspects findings, rationale, policy reasons, public evidence where enabled, and allowed override controls.
4. Reviewer records approve, reject, rewrite request, policy exception, or hold decision with taxonomy and rationale.
5. Backend journals the action and allows adapters to retry or complete the workflow using the same review id.

## Auditor Export

1. Auditor requests evidence for a review id, time range, tenant, matter id, or policy version.
2. Backend exports hashes, counts, findings metadata, policy id/version, decisions, reviewer actions, timestamps, and SIEM-safe event data.
3. Export omits raw prompts, email bodies, document text, reversible mapping values, and authorization headers.
4. Auditor verifies journal integrity and compares exported evidence against policy/version requirements.
5. Compliance team uses aggregate metrics to measure adoption, override rates, rewrite usage, and blocked-send outcomes.
