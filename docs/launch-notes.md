# Launch Notes

Launch gate: do not post this externally until the hosted demo URL is live, the
README hero links to it, and the demo cold-start/sleep note is visible near the
link.

## One-line Value Proposition

Junas is a deterministic pre-send reviewer for GenAI prompts, email, and
document sharing that returns statute-cited findings, policy actions, and audit
evidence before content leaves the trusted boundary.

## Lead Screenshot / Verdict

Lead with the README `60-second verdict` artifact and the same generated
Project Raven verdict:

- input: SG NRIC plus pre-announcement acquisition terms in a GenAI/email-style
  draft;
- verdict: `send_allowed: false`, `policy_decision: block`,
  `overall_risk: HIGH_RISK`;
- actions: `hold_until_public`, `redact_pii`, `request_approval`,
  `safe_rewrite`;
- proof: generated from a real local `/review` response in
  `docs/api/review_hero_response.json`.

Use one visual only: the README verdict table or the existing terminal GIF.
Do not lead with badge rows or broad procurement claims.

## Show HN Draft

Title: Show HN: Junas - deterministic pre-send review for GenAI and email

Post:

I built Junas, a pre-send review backend for cases where people paste prompts,
send external email, or share legal/workflow drafts that may contain personal
data or MNPI.

Demo: [hosted demo URL]

The fastest example is a Project Raven draft containing an SG NRIC and
pre-announcement acquisition terms. Junas returns `send_allowed: false`, blocks
the send, and surfaces required actions such as hold-until-public, PII
redaction, approval, and safe rewrite. The response also includes legal-basis
codes and generated citation text, so a reviewer can inspect why it fired.

This is intentionally deterministic-first. The public demo runs the strict
offline profile: no LLM adjudication, no public-evidence retrieval, no secrets,
and no persistence. It is not legal advice, not a DLP replacement, and not
production hardened; the repo is explicit about those limits.

The part I wanted to make inspectable is the backend contract: adapters and
workflow tools can call `/review`, get a policy decision plus evidence, then
redact, hold, route for approval, or proceed.

## r/programming Draft

Title: Junas: deterministic pre-send review for risky prompts, email, and
document text

Post:

Junas is a Python/FastAPI project for checking text before it leaves a trusted
workflow boundary. It detects PII and MNPI signals, returns a policy decision,
and exposes follow-on actions such as redaction, pseudonymization, approval, and
hold-until-public.

Demo: [hosted demo URL]

The public demo is deliberately narrow: strict deterministic profile only, no
LLM calls, no public-evidence lookup, no stored input. The example to try first
is the Project Raven draft in the README: an SG NRIC plus pre-announcement deal
terms should produce `send_allowed: false` with policy actions and citation
context.

Repo focus: inspectable rules, legal-basis citations, adapter contracts, audit
evidence, and explicit non-goals. Useful feedback would be on the API contract,
policy-decision shape, and where deterministic checks are too brittle or too
broad.

## r/legaltech Draft

Title: Deterministic pre-send review demo for GenAI/email legal-risk workflows

Post:

Junas reviews text before a user pastes into a GenAI tool, sends external email,
or shares matter documents. It is aimed at surfacing personal data and MNPI risk
early enough for redaction, hold, approval, or safe rewrite.

Demo: [hosted demo URL]

The demo runs strict deterministic review only. It does not persist submitted
text, call LLMs, or retrieve public evidence. The lead example combines an SG
NRIC with pre-announcement acquisition terms and returns a block decision,
required remediation actions, and citation context.

This is pre-production and should be read as an inspectable legal-tech
prototype, not legal advice or a replacement for DLP, eDiscovery, or counsel
review. The repo includes the threat model, limitations, policy decision
contract, and generated review artifacts so reviewers can inspect the claims.

## Candidate Venues

- Hacker News `Show HN`: one post only after the public demo is live.
- r/programming: only if the post leads with implementation/API details.
- r/legaltech: only if the post leads with workflow fit and limitations.
- GitHub social preview / pinned repo: after README hero links to the live demo.
- Personal site or portfolio: after cold-start behavior is documented near the
  demo link.

Do not cross-post the same day. Post once, answer questions, then decide whether
another venue needs a materially different angle.
