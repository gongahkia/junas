# Launch Notes

Launch gate: do not post this externally until the hosted demo URL is live, the
README hero links to it, and the demo cold-start/sleep note is visible near the
link.

## One-line Value Proposition

Junas is a deterministic pre-send reviewer for GenAI prompts, email, and
document sharing that returns statute-cited findings, policy actions, and audit
evidence before content leaves the trusted boundary.

Copy rule: use "reduces review risk", "flags detected findings", and "routes to
redaction, hold, approval, or safe rewrite". Do not say Junas prevents leaks,
guarantees privacy, provides universal capture, or replaces DLP, endpoint
controls, eDiscovery, or legal review.

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

## Etiquette Guardrails

- Post only after the Show HN readiness gate at the top of this file is satisfied.
- Disclose maintainer status when posting in community spaces.
- Do not cross-post the same copy. Rewrite for the venue or skip it.
- For Reddit, check current subreddit rules and mod expectations before posting; do not ask others to submit or upvote.
- For Lobste.rs, prefer a technical writeup over a product link and post only if the account has normal non-promotional participation.
- For Bluesky and Mastodon, use short posts, descriptive link text, and a small number of relevant hashtags.

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

## r/obs Draft

Title: Pre-send text review demo for stream/admin workflows with fake secrets

Post:

I maintain Junas, a local-first FastAPI project for reviewing text before it is
pasted into GenAI tools, email, or document-sharing workflows.

Demo: [hosted demo URL]

This is not an OBS plugin and it does not blur video. The reason it may be
relevant here is narrower: streamers and production teams often have show notes,
support replies, sponsor drafts, or moderation text that can contain personal
data before it is pasted elsewhere. The demo uses fake data only and shows the
deterministic `/review` response, redaction path, and non-goals.

Useful feedback would be whether this text-review workflow is relevant to
stream production at all, not feature requests for screen capture or webcam
blur.

## r/Twitch Draft

Title: Local-first text review demo for avoiding accidental personal-data leaks

Post:

I built Junas, a deterministic pre-send reviewer for text. It checks a draft
before a user pastes it into GenAI, sends email, or shares a document, then
returns findings, policy actions, and safe rewrite/redaction options.

Demo: [hosted demo URL]

This is not a Twitch overlay, bot, or moderation product. The only Twitch-adjacent
fit is checking stream notes, replies, sponsor copy, or support snippets before
they are shared. The demo stores no input, uses fake examples, and avoids claims
about privacy guarantees.

If this does not fit the subreddit rules, skip posting.

## r/macapps Draft

Title: Junas: local-first pre-send text review demo for macOS workflows

Post:

Junas is a pre-production local-first reviewer for risky text before it leaves a
workflow. The macOS-relevant path is `junas-local`: a packaged local daemon plus
optional desktop watcher for explicit file/folder/clipboard review.

Demo: [hosted demo URL]
Repo: [repo URL]

The demo is deterministic-only, no LLM calls, no stored input, and no provider
keys. The desktop watcher is explicitly experimental local fallback, not
endpoint enforcement. Feedback wanted: install clarity, local-daemon boundaries,
and whether the macOS packaging docs make the risk model obvious.

## r/rust Draft

Title: Deterministic pre-send review backend; looking for Rust integration feedback

Post:

Junas is currently Python/FastAPI, not Rust. I am posting here only if a Rust
angle exists: CLI wrappers, local daemon clients, policy/audit tooling, or
adapter integration patterns around a deterministic `/review` API.

Demo: [hosted demo URL]
API docs: [repo docs URL]

The demo runs no LLMs and stores no input. It returns policy decisions,
required actions, and audit-friendly ids for text that may contain PII or MNPI.
I would value feedback on a possible Rust client or local packaging boundary,
not language-war feedback on rewriting the backend.

If that is off-topic for the subreddit, skip posting.

## Lobste.rs Draft

Title: Building a deterministic pre-send review contract for risky text

Post:

I wrote up the API and policy-contract side of Junas, a pre-production
deterministic reviewer for text that may contain personal data or MNPI before it
is pasted into GenAI, sent by email, or shared as a document.

Writeup: [technical writeup URL]
Demo: [hosted demo URL]

The interesting implementation piece is the contract boundary: `/review`
returns findings, policy decision, action catalog, review expiry, and audit ids;
follow-on endpoints handle redaction, pseudonymization, approval, and
hold-until-public. The public demo runs strict deterministic mode with no LLMs,
public-evidence lookup, secrets, or persistence.

I am looking for critique on the API shape, failure modes, and audit evidence,
not product-growth feedback.

## Bluesky Drafts

Rust/devtools:

> I built Junas, a deterministic pre-send review backend for risky text before
> it goes into GenAI, email, or document sharing. Strict demo: no LLM calls, no
> persistence, fake data only. Feedback wanted on API shape and local-client
> ergonomics. [hosted demo URL] [repo URL]

Privacy/legal-tech:

> Junas checks text before it leaves a trusted workflow: PII/MNPI findings,
> policy decision, required actions, and audit ids. Public demo is
> deterministic-only and stores no input. It is not legal advice or a DLP
> replacement. [hosted demo URL]

## Mastodon Drafts

Rust/devtools:

> Junas is a deterministic pre-send review backend for risky text before GenAI,
> email, or document sharing. Strict public demo: no LLM calls, no persistence,
> fake data only. Feedback welcome on API contract and local-client ergonomics.
> [hosted demo URL]
>
> #DevTools #APIs #Privacy

Privacy/legal-tech:

> I built Junas to make pre-send review inspectable: findings, policy decision,
> required actions, and audit ids before risky text leaves a workflow. Demo runs
> deterministic-only and stores no input. Not legal advice, not a DLP
> replacement. [hosted demo URL]
>
> #Privacy #LegalTech #DataProtection

## Engineering Writeup Ideas

- "Designing a deterministic `/review` contract before adapters": explain
  policy decisions, review expiry, idempotency, and why adapters stay outside
  the trust boundary.
- "Why the public demo is deterministic-only": cover no persistence, no LLMs,
  no public evidence, body caps, and rate limits.
- "Audit evidence without raw body logs": cover request ids, hashes, counts,
  SIEM-safe events, and audit-pack verification.

## Meetups And Backlink Targets

- Local Python/FastAPI meetups: lead with API contract and deterministic tests.
- Privacy engineering groups: lead with no-body logs, local-only mode, and DLP
  coexistence boundaries.
- Legal-tech communities: lead with workflow fit, statutory citation context,
  and non-goals.
- Security architecture blogs/newsletters: lead with threat model, adapter
  boundaries, and audit evidence.

## Candidate Venues

- Hacker News `Show HN`: one post only after the public demo is live.
- r/programming: only if the post leads with implementation/API details.
- r/legaltech: only if the post leads with workflow fit and limitations.
- r/obs and r/Twitch: only if rules allow self-promotion and the post stays
  honest about no stream overlay, no webcam blur, and fake examples only.
- r/macapps: only after macOS packaging and local-daemon caveats are clear.
- r/rust: only with a concrete Rust client, packaging, or API-integration angle.
- Lobste.rs: prefer a technical writeup, not a product/demo link.
- Bluesky and Mastodon: use one short post per angle; do not threadstorm.
- GitHub social preview / pinned repo: after README hero links to the live demo.
- Personal site or portfolio: after cold-start behavior is documented near the
  demo link.

Do not cross-post the same day. Post once, answer questions, then decide whether
another venue needs a materially different angle.
