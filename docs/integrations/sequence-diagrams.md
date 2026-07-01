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
