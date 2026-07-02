# Junas 60-Second Demo Video

Asset: [`asset/video/junas-60s-demo.mp4`](../../../asset/video/junas-60s-demo.mp4)

Transcript:

> Junas is a deterministic pre-send reviewer for risky text before it leaves a trusted workflow. Start locally with uv sync, download the small spaCy model, then run the demo script. A user or adapter can submit a GenAI prompt, email draft, document upload, or direct API payload to `/review`. In the fake Project Raven example, the text includes a sample Singapore NRIC and pre-announcement acquisition terms. Junas detects PII and MNPI, returns `send_allowed: false`, a block policy decision, legal-basis codes, and required actions. The follow-on path can redact PII, request approval, safe rewrite, or hold the MNPI until public. The public demo profile is deterministic-only: no LLM calls, no public-evidence lookup, no provider keys, and no stored input. Junas is not legal advice, not a DLP replacement, and not endpoint enforcement.

Source notes:

- All examples are synthetic and use fake secrets/data.
- The narration avoids privacy guarantees and states the main product limits.
- The generated video is intended for README, landing page, or release-page linking.
