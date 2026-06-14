# GenAI Browser Capture

Source: `integrations/browser_extension/`

Maturity: `supported-target`

The browser adapter is a managed Chromium MV3 extension for selected GenAI web surfaces. It is not universal browser DLP and must not promise coverage when a target app changes DOM structure, editor behavior, CSP, extension permissions, or submit flow.

## Current Target Hosts

The current manifest injects the content script on:

- `https://chatgpt.com/*`
- `https://claude.ai/*`
- `https://gemini.google.com/*`

These host matches only mean the script is present on those origins. They do not guarantee that every prompt box, compose surface, upload widget, or future UI variant is captured.

## Capture Paths

- Context menu: user selects text and chooses "Review selection with Kaypoh".
- Opt-in paste interception: when enabled in extension settings, pasted plain text in editable elements is reviewed or rewritten.
- Generic editable fallback: `textarea`, text-like `input`, and `contenteditable` elements are treated as editable targets.

The adapter does not capture keystrokes continuously, does not scrape full pages, and does not persist prompt text in extension storage.

## Target Assumptions

| Target | Assumption | Known limitation |
|---|---|---|
| ChatGPT | Text entry occurs in an editable browser element on `chatgpt.com`. | UI/editor changes can bypass generic editable detection or insertion. |
| Claude | Prompt entry exposes selected text or paste events to the extension on `claude.ai`. | File uploads, artifacts, and non-text editor state are not covered by the generic path. |
| Gemini | Prompt entry exposes selected text or paste events to the extension on `gemini.google.com`. | Multimodal upload surfaces and generated-content actions are outside current capture. |
| Generic textarea | Text is pasted into `textarea`, text-like `input`, or `contenteditable`. | Shadow DOM, canvas editors, isolated frames, and custom editors may not be visible. |

## Backend Contract

The service worker calls the configured endpoint with `review`, `pseudonymize`, `anonymize`, or `redact`. The default endpoint is `http://127.0.0.1:8765`; production pilots should use enterprise extension policy and backend/local-token auth appropriate to the deployment.

For managed GenAI review, callers should use `surface="browser_genai"` and `workflow="prompt_submit"` when the adapter has enough context to submit those fields. The current local extension keeps a minimal strict review payload and should be treated as a pilot surface until target-specific submit interception and selector tests exist.

## Failure Behavior

- Backend error or timeout: show a visible Kaypoh error panel; do not silently replace text.
- Rewrite failure: restore the original pasted text.
- Degraded review: display degraded coverage and `send_allowed` status from the response.
- Target DOM mismatch: fail as no capture rather than claiming enforcement.

## QA Requirements Before Expanding Claims

- Selector or event tests per target surface: ChatGPT, Claude, Gemini, and generic textarea.
- Manual Chrome/Edge matrix for managed install, local-token auth, context menu, paste review, and rewrite flows.
- No raw prompt text in extension storage, console logs, or telemetry.
- Explicit docs for unsupported target UI changes and degraded behavior.

## References

- [`docs/integrations/browser-extension.md`](./browser-extension.md)
- [`docs/policy/decision-contract.md`](../policy/decision-contract.md)
- [`docs/api/idempotency.md`](../api/idempotency.md)
