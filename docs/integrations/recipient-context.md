# Recipient Context

Status: normative for adapters. Destination context is policy input, not user-facing address book storage.

Use with `docs/integrations/adapter-protocol.md`, `docs/integrations/privacy.md`, and `docs/policy/schema.md#recipient-domain-rules`.

## Canonical Fields

| Field | Meaning | Privacy rule |
|---|---|---|
| `destination_jurisdiction` | Destination legal/regulatory jurisdiction when known. | Use tenant/workflow mapping; do not derive from raw address text in logs. |
| `external_destination` | Explicit true/false for whether the workflow leaves the trusted boundary. | Prefer this when the adapter knows the boundary. |
| `recipient_domains` | Destination domains only, lower-case, without local parts. | Never send full email addresses or user ids. |
| `recipient_count` | Count of intended recipients, including internal recipients when visible. | Count only; do not list names. |
| `sensitivity_label` | Upstream label such as confidential/restricted. | Label only; do not include label comments. |
| `requested_action` | User action after review, such as `send`, `submit`, or `upload`. | Action enum only. |

Policy semantics:

- `external_destination=true` marks the workflow external.
- When `external_destination` is absent, backend policy compares `recipient_domains` to configured `internal_domains`.
- Empty `recipient_domains=[]` is allowed and does not imply external delivery.
- Unknown context should be omitted/null, not fabricated.
- A user-editable field must not override tenant policy or validated auth tenant.

## Email / Outlook

Outlook Smart Alerts should pass:

```json
{
  "surface": "outlook",
  "workflow": "email_send",
  "document_type": "email",
  "destination_jurisdiction": "US",
  "recipient_domains": ["example.com", "outside-counsel.test"],
  "recipient_count": 3,
  "external_destination": true,
  "requested_action": "send"
}
```

Rules:

- Include To, Cc, and Bcc in `recipient_count` when the client exposes them.
- Convert addresses to domains locally and send only domains.
- Deduplicate `recipient_domains`; keep `recipient_count` as the total visible count.
- Treat a distribution list as one recipient unless the platform exposes expanded members.
- Set `external_destination=true` when any recipient is outside tenant policy, when Outlook marks external recipients, or when admin policy classifies the route external.
- Do not store recipient addresses, display names, or distribution-list members in adapter storage, logs, telemetry, SIEM, or idempotency keys.

## Browser GenAI

Browser GenAI adapters usually have no human recipient list. They should pass the target service as destination context:

```json
{
  "surface": "browser_genai",
  "workflow": "prompt_submit",
  "document_type": "prompt",
  "destination_jurisdiction": "US",
  "recipient_domains": ["chatgpt.com"],
  "recipient_count": 1,
  "external_destination": true,
  "requested_action": "submit"
}
```

Rules:

- Use the target host domain, not the full URL, page title, DOM text, conversation id, or account id.
- For ChatGPT, Claude, Gemini, or another hosted GenAI service outside tenant control, default `external_destination=true` unless tenant policy explicitly treats the endpoint as internal.
- For internal GenAI deployments, use the internal host domain and set `external_destination=false` only when tenant policy owns that classification.
- If the content script cannot identify a supported target, omit recipient fields and report selector/no-capture state rather than claiming a safe destination.

## DMS

DMS upload/check-in hooks should pass repository and share context:

```json
{
  "surface": "dms",
  "workflow": "document_upload",
  "document_type": "dms_document",
  "destination_jurisdiction": "US",
  "external_destination": false,
  "recipient_domains": [],
  "recipient_count": 0,
  "requested_action": "upload"
}
```

Rules:

- Use `destination_jurisdiction` from matter, workspace, repository, client, or destination folder policy.
- Use `external_destination=true` for external share, client portal, cross-tenant workspace, outside-counsel transfer, or export workflows.
- Use `recipient_domains` only when the DMS exposes share recipient domains; do not use matter names, client names, user display names, or full email addresses.
- For internal repository check-in with no share target, use `recipient_domains=[]` and `recipient_count=0` rather than inventing a recipient.
- Store DMS audit metadata as ids/counts/hashes, not raw recipient or matter names.

## Direct API

Direct API callers own destination mapping:

```json
{
  "surface": "api",
  "workflow": "api_review",
  "destination_jurisdiction": "HK",
  "recipient_domains": ["counterparty.example"],
  "recipient_count": 2,
  "external_destination": true,
  "requested_action": "send"
}
```

Rules:

- Pass destination context from the service workflow, not from untrusted free text.
- Use `surface="api"` only for direct service calls; use `surface="dms"`, `surface="outlook"`, or `surface="browser_genai"` when acting on behalf of that workflow.
- Set `external_destination` explicitly when the service knows boundary status.
- If only a country, region, tenant, or repository boundary is known, set `destination_jurisdiction` and omit recipient domains.
- Do not pass tenant ids, workspace ids, or matter ids as recipient domains.

## Normalization

Adapters should normalize before calling `/review`:

- lower-case domains
- strip local parts from email addresses
- strip ports, paths, query strings, fragments, and schemes from hosts
- convert internationalized domain names to a stable ASCII form when possible
- sort and deduplicate `recipient_domains`
- keep `recipient_count` as the total visible recipient/share target count, not the deduplicated domain count
- rotate the idempotency key when recipients, destination, external flag, jurisdiction, or attachment set changes

## Unknown Or Conflicting Context

| Case | Behavior |
|---|---|
| Unknown recipients | Omit `recipient_domains`; set `recipient_count` only if known. |
| Empty internal send | Use `recipient_domains=[]`, `recipient_count=0`, `external_destination=false` only when known. |
| Domains conflict with explicit `external_destination` | Explicit `external_destination` is the adapter assertion; emit telemetry for conflict if safe. |
| User edits recipients after review | Start a new review. |
| Adapter cannot inspect destination | Apply `docs/integrations/failure-semantics.md`; do not emit a clean allow signal from missing context. |

## Privacy QA

Before support claims, test:

- Outlook sends domains/counts, not full addresses or display names.
- Browser sends host domain, not URL, page title, conversation id, or DOM text.
- DMS stores recipient/matter context as ids, domains, counts, or hashes only.
- Direct API examples use `recipient_domains` and `external_destination`.
- Telemetry contains `recipient_count` and `recipient_domain_count`, not addresses.
- Idempotency keys change when destination context changes and never include raw recipients.
