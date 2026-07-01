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
