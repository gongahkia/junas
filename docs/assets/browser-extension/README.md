# Browser Extension Screenshots

These screenshots use synthetic prompt text and a Playwright-routed `https://chatgpt.com/` fixture. The real unpacked MV3 extension from `integrations/browser_extension/` calls a deterministic local Junas backend at `http://127.0.0.1:8765`.

Files:

- `browser-extension-warn-confirm.png`: warning confirm text for a low-risk named-person finding.
- `browser-extension-policy-block.png`: policy-block panel for synthetic SG NRIC plus Project Raven MNPI text.

The warn-confirm image renders the native confirm text in-page to avoid capturing the operator desktop. Treat both images as illustrative adapter screenshots, not proof of universal browser capture; coverage depends on third-party DOM stability, target editor behavior, CSP, extension permissions, and submit flow.
