# DMS Matter IDs

Status: normative for DMS adapter pilots. Junas accepts opaque matter ids; it does not depend on iManage, NetDocuments, or any other vendor SDK.

Use with `docs/integrations/dms.md`, `docs/integrations/document-context.md`, and `docs/integrations/auth.md`.

## Contract Boundary

The backend `/review` schema has only one DMS matter field:

| Field | Backend role | Rule |
|---|---|---|
| `matter_id` | Matter-scoped defined-term inheritance across sessions. | Optional `[A-Za-z0-9_-:]{1,128}`; tenant-scoped; not an auth grant. |

DMS adapters may keep extra fields in adapter audit metadata:

| Adapter field | Meaning | Backend behavior |
|---|---|---|
| `dms` | Repository family such as `imanage`, `netdocuments`, or another tenant-defined slug. | Not a `/review` field. Use only to build namespaced ids or audit metadata. |
| `document_id` | DMS document id or stable pre-check-in draft id. | Not a `/review` field. Store in DMS-side audit metadata. |
| `workspace_id` / `cabinet_id` / `folder_id` | Repository locator used by the hook. | Do not send unless mapped into an opaque `matter_id` or kept in private audit metadata. |

Tenant identity comes from validated backend credentials. Never treat `matter_id` as proof that the caller can read or write that matter.

## ID Construction

Preferred format:

```text
{dms}:{source_matter_id}
```

Examples:

```json
{
  "surface": "dms",
  "workflow": "document_upload",
  "matter_id": "imanage:M123",
  "session_id": "upload-M123-001"
}
```

```json
{
  "surface": "dms",
  "workflow": "document_upload",
  "matter_id": "netdocuments:456789",
  "session_id": "nd-upload-456789-001"
}
```

Rules:

- Use a stable id from the DMS matter, workspace, cabinet, profile, or repository layer.
- Use lower-case vendor slugs such as `imanage` or `netdocuments` when composing ids.
- Keep the source id opaque. Do not encode matter names, client names, deal names, user names, folder paths, workspace display names, or free-text descriptions.
- If the source id contains unsupported characters, map it to a stable slug or keyed hash before sending it to Junas.
- Keep the mapping from source id to Junas-safe id in tenant-controlled adapter storage.
- Do not include raw `matter_id` values in telemetry; use `matter_id_hash` when correlation is needed.

## iManage-Style Mapping

For iManage-style repositories, the adapter should map the stable workspace/matter identifier it already receives from the DMS hook or export manifest:

```json
{
  "dms": "imanage",
  "matter_id": "imanage:M123",
  "document_id": "D456",
  "path": "draft.txt"
}
```

Rules:

- The `M123` value is illustrative, not a required iManage format.
- Do not require an iManage SDK in the Junas backend.
- A hook, webhook worker, export job, or JSON manifest scanner may supply the same `matter_id` contract.
- Keep iManage library, database, workspace, profile, version, and ACL details in the DMS integration layer unless tenant audit policy explicitly stores them.

## NetDocuments-Style Mapping

For NetDocuments-style repositories, the adapter should map the stable cabinet/matter/profile identifier available to the hook:

```json
{
  "dms": "netdocuments",
  "matter_id": "netdocuments:456789",
  "document_id": "ND-1001",
  "path": "memo.txt"
}
```

Rules:

- The `456789` value is illustrative, not a required NetDocuments format.
- Do not require a NetDocuments SDK in the Junas backend.
- Keep cabinet, workspace, profile attributes, version labels, and ACL details in the DMS integration layer unless tenant audit policy explicitly stores them.
- If a tenant has multiple NetDocuments cabinets with overlapping ids, namespace before sending, for example `netdocuments-cabinetA:456789`.

## Manifest Scanner Shape

The shipped scanner remains vendor-neutral. It accepts JSON manifests, not vendor SDK credentials:

```json
{
  "dms": "imanage",
  "matter_id": "imanage:M123",
  "documents": [
    {
      "document_id": "D1",
      "path": "draft.txt",
      "document_type": "memo"
    }
  ]
}
```

Production hooks can produce the same shape from any DMS, export job, queue worker, or webhook. The backend contract remains `POST /review` with `surface="dms"` and `workflow="document_upload"`.

## Failure Behavior

| Case | Behavior |
|---|---|
| Missing `matter_id` | Review can continue, but no matter-level defined terms are inherited. |
| Invalid `matter_id` pattern | Backend validation fails; stop check-in or hold the upload according to tenant policy. |
| Matter id changes after review | Start a new `/review` and rotate the idempotency key. |
| Potential id collision | Fail closed in the adapter and require operator mapping repair. |
| DMS hook cannot read matter metadata | Apply DMS failure semantics; do not invent a matter id from names or paths. |
| Tenant mismatch | Reject through auth/tenant boundary; do not use `matter_id` to select tenant. |

## Privacy And Audit

Allowed DMS-side audit metadata:

- `matter_id` when tenant policy permits raw DMS ids in repository audit fields
- `matter_id_hash` for telemetry and SIEM
- `document_id`, DMS version/check-in id, actor id, policy id/version, decision, action names, and idempotency key hash

Prohibited in Junas telemetry, SIEM details, support logs, and idempotency keys:

- matter names, client names, deal names, folder paths, workspace display names, document titles, auth tokens, raw document text, matched text, reviewer free text, or vendor SDK credentials

## QA Checklist

Before claiming a DMS matter-id integration:

- iManage-style manifest maps stable ids to `imanage:{id}` without SDK dependencies.
- NetDocuments-style manifest maps stable ids to `netdocuments:{id}` without SDK dependencies.
- Invalid spaces, slashes, paths, and display names are rejected or mapped before `/review`.
- Two sessions with the same `matter_id` inherit matter-defined terms.
- Two tenants with the same source DMS id do not share matter-defined terms.
- Telemetry emits `matter_id_hash`, not raw matter names or ids.
- Idempotency keys rotate when `matter_id`, document content, attachments, or destination context changes.
