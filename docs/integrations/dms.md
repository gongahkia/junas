# DMS Integration

Source: `src/junas/integrations/dms.py`, `scripts/scan_dms_manifest.py`

Maturity: `experimental`

DMS integration is a service-side upload/check-in review flow. The backend remains the policy and audit boundary; the DMS adapter should collect document text or a supported document payload plus matter metadata, call `/review`, then allow, warn, block, request approval, or store audit fields according to `policy_decision`.

The shipped code is a read-side neutral JSON manifest scanner for exports from systems such as iManage or NetDocuments. It does not write back to a customer repository and does not ship vendor SDK credentials.

## Upload / Check-In Flow

Start the backend before running service-side upload/check-in hooks:

```sh
./scripts/launch/run_backend_only.sh
```

1. User uploads or checks in a document to the DMS.
2. DMS hook extracts text or sends a supported `document_base64` payload.
3. Hook calls `POST /review` with `surface="dms"` and `workflow="document_upload"`.
4. Backend returns findings, scores, `policy_decision`, `request_id`, and `review_expires_at`.
5. Hook applies the decision before check-in completes, or records a pending approval/rewrite requirement.
6. Optional follow-on actions run only when allowed by `action_catalog`.

Sequence diagram: `docs/integrations/sequence-diagrams.md#dms-upload-check-in-review`.

## Required Metadata

Production DMS hooks should provide:

- `dms`: vendor or repository family, for example `imanage` or `netdocuments`.
- `matter_id`: matter/workspace id, preferably namespaced as `{dms}:{matter_id}`.
- `document_id`: DMS document id or stable pre-check-in draft id.
- `document_filename` and `document_mime_type` when using `document_base64`.
- `source_jurisdiction`, `destination_jurisdiction`, and `document_type`.
- `surface="dms"`, `workflow="document_upload"`, and `actor_role="service_account"` or the authenticated user role.
- `external_destination`, `recipient_domains`, `attachment_count`, and `sensitivity_label` when the DMS exposes them.

The current manifest scanner accepts a JSON list or an object with `documents=[]`. Each entry should include `path`, `document_id`, `matter_id`, `dms`, `source_jurisdiction`, `destination_jurisdiction`, and `document_type`. Missing optional fields default to `unknown`, empty string, `SG`, or `generic`; production hooks should avoid relying on those defaults.

Example manifest:

```json
{
  "dms": "imanage",
  "matter_id": "imanage:M123",
  "documents": [
    {
      "document_id": "D1",
      "path": "draft.txt",
      "source_jurisdiction": "SG",
      "destination_jurisdiction": "US",
      "document_type": "memo"
    }
  ]
}
```

Run the scanner:

```sh
uv run python scripts/scan_dms_manifest.py manifest.json --output dms-review.json
```

## Failure Behavior

- Backend timeout: hold check-in or mark it pending review according to tenant policy; retry with the same `Idempotency-Key` only if document content and metadata are unchanged.
- Auth failure: fail closed for controlled repositories and do not store raw text in error logs.
- Validation failure: stop check-in and surface the invalid metadata field to the service operator.
- Missing text extraction: use the DMS extraction fallback if approved; otherwise return a degraded review state and apply tenant policy.
- `block`, `approval_required`, or `rewrite_required`: do not commit the original document as an approved external/shareable version.
- User edits the document after review: require a fresh `/review`.

## Audit Fields To Store

Store DMS-side audit metadata without raw document text:

- `request_id` / review id.
- `policy_decision.decision`, `send_allowed`, `required_actions`, and `recommended_actions`.
- `policy_id`, `policy_version`, `review_expires_at`, and `degraded_modes`.
- `overall_risk`, `pii_score`, `mnpi_score`, finding count, and rule names.
- `matter_id`, `document_id`, DMS version/check-in id, actor id, timestamp, and idempotency key hash.
- `text_hash` from `/review/{review_id}` when session persistence is enabled, or `document_hash` from rewrite responses when a follow-on action changes content.

Do not store raw prompts, document bodies, matched text, auth headers, reversible mapping values, or reviewer rationale containing sensitive content in DMS-visible audit fields.

## References

- [`docs/product/workflows.md#dms-upload`](../product/workflows.md#dms-upload)
- [`docs/integrations/direct-api.md`](./direct-api.md)
- [`docs/policy/decision-contract.md`](../policy/decision-contract.md)
- [`docs/api/idempotency.md`](../api/idempotency.md)
