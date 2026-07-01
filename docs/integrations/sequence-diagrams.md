# Integration Sequence Diagrams

These diagrams show adapter control flow at the backend contract boundary. They are operational flow docs, not a claim that adapters cover every vendor client or UI variant.

## Outlook Smart Alerts Send Review

Outlook Smart Alerts calls `/review` from the `OnMessageSend` launch event, receives a backend policy decision, then completes the send event according to the decision and Outlook send-mode support.

```mermaid
sequenceDiagram
    participant User
    participant Outlook
    participant Runtime as Outlook add-in launch event
    participant API as FastAPI /review
    participant Policy as Review + policy engine
    participant Journal as Audit journal / SIEM

    User->>Outlook: Select Send
    Outlook->>Runtime: OnMessageSend event
    Runtime->>Runtime: Collect subject, body, recipient domains, attachment count
    Runtime->>API: POST /review surface="outlook" workflow="email_send" degraded_policy="block_send"
    API->>Policy: Validate auth, extract text, run deterministic review, evaluate policy
    Policy-->>API: Findings + policy_decision
    API->>Journal: Append hashes, counts, policy id/version, decision
    API-->>Runtime: Review response with review_id and policy_decision
    alt allow
        Runtime-->>Outlook: event.completed({allowEvent: true})
        Outlook-->>User: Send continues
    else warn
        Runtime-->>Outlook: event.completed({allowEvent: false, sendModeOverride: promptUser})
        Outlook-->>User: Smart Alert prompt lets user confirm or cancel
    else block / rewrite_required / approval_required / degraded
        Runtime-->>Outlook: event.completed({allowEvent: false, errorMessage})
        Outlook-->>User: Smart Alert blocks current send attempt
    end
```

The add-in sends message text only inside the `/review` request. Journal and SIEM records must contain hashes, counts, policy metadata, and decision metadata only; no message body, subject, recipient address, attachment name, or matched text belongs in those records.

## Browser GenAI Prompt Review And Safe Rewrite

This is the target sequence for a managed browser adapter when submit interception and safe rewrite are enabled. If the content script cannot resolve the prompt composer and submit control, this sequence does not run and the adapter must not silently block submit because no policy decision was evaluated.

```mermaid
sequenceDiagram
    participant User
    participant Page as GenAI page
    participant Content as Content script
    participant Worker as MV3 service worker
    participant Review as FastAPI /review
    participant Rewrite as FastAPI /safe-rewrite

    User->>Page: Click submit or press Enter
    Content->>Content: Resolve prompt composer and submit control
    Content->>Worker: Review prompt text
    Worker->>Review: POST /review surface="browser_genai" workflow="prompt_submit"
    Review-->>Worker: review_id, findings, policy_decision, action_catalog
    Worker-->>Content: Policy result
    alt allow
        Content->>Page: Let submit continue
    else warn
        Content->>User: Prompt user to proceed or cancel
        User-->>Content: Confirm proceed
        Content->>Page: Submit only after confirmation
    else rewrite_required and safe_rewrite offered
        Content->>User: Offer safe rewrite or cancel
        User-->>Content: Choose safe rewrite
        Content->>Worker: Request safe_rewrite for allowed finding ids
        Worker->>Rewrite: POST /safe-rewrite surface="browser_genai" workflow="prompt_submit"
        Rewrite-->>Worker: rewritten_text, replacements, skipped_findings
        Worker-->>Content: Safe rewrite result
        Content->>Page: Replace composer text with rewritten_text
        Content->>User: Show rewrite applied; user may review and submit
    else block / degraded / backend failure
        Content->>User: Show policy block or review unavailable message
        Content-->>Page: Do not trigger submit
    end
```

The browser adapter may hold prompt text in memory long enough to review or rewrite it. It must not save prompt text, rewritten text, matched spans, auth tokens, or endpoint secrets in extension storage or console logs.

## DMS Upload Check-In Review

This sequence is for a service-side DMS hook that reviews a document before upload, check-in, external share, or version promotion completes. The DMS stores audit evidence from the backend response, not raw reviewed content.

```mermaid
sequenceDiagram
    participant User
    participant DMS as DMS repository
    participant Hook as DMS review hook
    participant API as FastAPI /review
    participant Policy as Review + policy engine
    participant Audit as DMS audit fields
    participant Journal as Junas journal / SIEM

    User->>DMS: Upload or check in document
    DMS->>Hook: Pre-commit event with document_id, matter_id, actor, version
    Hook->>Hook: Extract text or prepare supported document_base64 payload
    Hook->>API: POST /review surface="dms" workflow="document_upload" matter_id document_id
    API->>Policy: Validate auth, extract, review, evaluate policy
    Policy-->>API: Findings + policy_decision
    API->>Journal: Append hashes, counts, policy id/version, decision
    API-->>Hook: review_id, request_id, review_expires_at, policy_decision
    Hook->>Audit: Store review id, decision, actions, policy version, scores, counts, idempotency key hash
    alt allow or warn
        Hook-->>DMS: Permit check-in and attach audit metadata
        DMS-->>User: Upload/check-in completes
    else approval_required
        Hook-->>DMS: Hold version pending reviewer approval
        DMS-->>User: Show approval-required state
    else rewrite_required
        Hook-->>DMS: Hold original and request safe rewrite or redaction workflow
        DMS-->>User: Show rewrite-required state
    else block / degraded / backend failure
        Hook-->>DMS: Stop or quarantine check-in per tenant failure policy
        DMS-->>User: Show policy block or review unavailable state
    end
```

DMS-side audit fields may include `review_id`, `request_id`, `policy_decision.decision`, required and recommended actions, policy id/version, `review_expires_at`, risk scores, finding count, matter id, document id, actor id, DMS version id, and idempotency key hash. They must not include raw document text, matched text, reviewer rationale containing sensitive content, auth headers, or reversible mapping values.

## Reviewer Approval And Adapter Retry

This sequence covers a workflow adapter that receives a blocking policy decision, records a pending approval request, waits for an authorized reviewer decision in the journal, then retries completion without treating the adapter as the approval authority.

```mermaid
sequenceDiagram
    participant Adapter
    participant Review as FastAPI /review
    participant Approval as FastAPI /request-approval
    participant Reviewer
    participant Decision as FastAPI /review/{review_id}/decision
    participant State as FastAPI /review/{review_id}
    participant Journal as Review journal

    Adapter->>Review: POST /review with surface, workflow, content, destination context
    Review-->>Adapter: policy_decision.decision=block or approval_required, review_id, required_actions
    Adapter->>Approval: POST /request-approval review_id finding_ids reason_code="policy_block"
    Approval->>Journal: approval_requested with roles, finding ids, requester, seq, hmac
    Approval-->>Adapter: approval_status="pending", required_reviewer_roles
    Adapter-->>Adapter: Stop send/share/check-in and show pending approval state
    Reviewer->>Decision: POST /review/{review_id}/decision action="approve" or "policy_exception"
    Decision->>Journal: decision_recorded with reviewer identity, action, seq, hmac
    Decision-->>Reviewer: Recorded decision response
    Adapter->>State: GET /review/{review_id}
    State-->>Adapter: Replayed findings with latest reviewer decision
    Adapter-->>Adapter: Retry workflow completion only when approval satisfies policy
```

If text, recipients, destination, attachments, matter context, or policy version changed after the original review, the adapter must start a new `/review` instead of relying on the old approval. Approval journal events must use finding ids, role metadata, reviewer identity, reason codes, sequence numbers, and HMACs; they must not include raw prompt, email, document, matched text, or sensitive reviewer rationale.
