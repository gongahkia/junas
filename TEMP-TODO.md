# TODO Additions — Surface, Demonstrability, and Credibility

> Purpose: the existing TODO.md is almost entirely product/security/eval hardening (goal: become a deployable product for regulated buyers). These additions target a different, currently-unaddressed goal set: make the project's real depth *legible and demonstrable to a visitor in under 60 seconds*, for GitHub stars and portfolio/legal-tech credibility. These are purely additive; they do not modify or supersede any existing item.
>
> Ordering principle: leverage-per-hour toward "a stranger lands on the repo, immediately sees something impressive, and stars/respects it." The single highest-leverage cluster is P0/Surface. Do that before anything below it.
>
> Guardrail for all tasks here: the repo's edge is *substance* (deterministic-first review, statute-cited findings, an audit-grade trust boundary). Surface work must *showcase real depth*, never decorate over it. No vanity-badge rows, no auto-playing banner GIFs, no marketing claims unbacked by tests/eval. Every demonstrated capability must come from a real `/review` response the code actually produces.

## P0/Surface — Make the hero artifact visible (highest leverage)

## P1/Surface — Visual proof of the workflow surfaces

## P1/Demo — A hosted, clickable playground (highest single conversion lever, higher effort)

- [ ] P1/Demo: Stand up a free hosted demo of the deterministic-only profile so visitors can try Junas without cloning, since a public link in the README is the single highest-converting surface for a tool whose output is visually legible (done when: a public URL runs the offline/deterministic local profile on a free tier suitable for a FastAPI app — e.g. Hugging Face Spaces via Docker, or Render/Railway free tier — and is linked from the README hero; the deployment uses the local SKU that excludes public-evidence and LLM-adjudicator modules; cold-start/sleep behavior of the free tier is documented so the link is not perceived as broken; no secrets, provider keys, or persistence are required).

- [ ] P1/Demo: Build a minimal single-page playground UI in front of the hosted demo that lets a visitor paste text, pick a jurisdiction/profile, and see findings + citations + policy decision rendered, since raw JSON undersells a tool whose strength is human-legible verdicts (done when: a single static page calls `/review` and renders findings with their legal-basis citations, the policy decision, required actions, and `send_allowed`; it ships a few one-click example inputs covering PII, MNPI, and clean text; it visibly states it is a deterministic-only demo and does not persist input; it is the page served at the hosted demo URL).

- [ ] P1/Demo: Add abuse and safety guards appropriate to a public, unauthenticated demo endpoint, since the hosted playground is the one place untrusted users hit a live backend (done when: the demo profile enforces a low request-body cap and basic rate limiting, runs deterministic-only with all external/LLM paths hard-disabled, persists nothing to disk beyond ephemeral runtime, and documents that submitted text should be synthetic/non-confidential).

## P1/Credibility — Independent signals a reviewer can verify quickly

- [ ] P1/Credibility: Write a short, honest "Accuracy & evaluation" README section that links the promoted eval evidence and states the methodology, since procurement-grade-sounding numbers without framing read as a red flag to knowledgeable reviewers, while disclosed methodology reads as rigor (done when: the section states that recall is reported span-level with F-beta=2 per Presidio-Research conventions, distinguishes in-domain corpus results from independent benchmarks [TAB, ai4privacy] once those eval items land, explicitly notes the no-public-MNPI-benchmark limitation, and links `docs/accuracy.md`; it makes no population-level or procurement-grade claim; this section's claims are gated on the corresponding P0/Eval items being complete and must not overstate them beforehand).

- [ ] P1/Credibility: Add a top-level `ARCHITECTURE.md` (or promote the existing architecture doc to a linked, reviewer-friendly entry point) aimed at the technical reviewer who reads code to assess the author, since this audience [goal a/c] rewards seeing invariants and design decisions made explicit (done when: the doc walks the request lifecycle, names the trust boundary, explains the deterministic-vs-advisory split and why, points to the key modules [`review/engine.py`, `policy/engine.py`, `backend/main.py`], and states the non-suppression invariant with its test; the README links it from the design-principles section).

- [ ] P1/Credibility: Add a `CONTRIBUTING.md` and a small set of `good first issue`-labeled issues drawn from the existing TODO's lower-risk items, since a contribution on-ramp is a standard star/credibility signal and converts interested visitors into stargazers/contributors (done when: `CONTRIBUTING.md` documents the `uv`-based dev setup, the test/lint commands, and the deterministic-local invariant contributors must preserve; at least 5 genuinely scoped good-first-issues exist that do not touch the security-sensitive core).

- [ ] P1/Credibility: Add a one-paragraph "Project status" honesty banner to the README stating this is pre-production / portfolio-stage with deterministic core complete and specific hardening tracked in TODO, since a stale or over-claiming README erodes trust faster than an honest one and reviewers respect calibrated self-assessment (done when: a short status line near the top states the maturity accurately, links TODO.md, and avoids both under-selling the real depth and implying production-readiness that the open P0/Security items contradict).

## P2/Reach — Distribution, once the surface is strong (do NOT start before P0/Surface is done)

- [ ] P2/Reach: Write a launch-ready project description and a short "show HN / r/programming / r/legaltech"-style post draft that leads with the demo link and one striking verdict, since stars [goal b] require the strong surface to actually be seen, but distribution before the surface exists wastes the one-shot attention (done when: a `docs/launch-notes.md` drafts the post, the one-line value proposition, and the single screenshot/verdict to lead with; it is explicitly gated on the hosted demo and README hero being live; it lists candidate venues without committing to spammy cross-posting).

- [ ] P2/Reach: Add `topics`/tags and a precise repo description optimized for discovery by the legal-tech/privacy/GenAI-governance audience, since GitHub topic search and the repo's one-liner are passive discovery surfaces (done when: the repo description matches the README hook, and relevant topics — e.g. pii, mnpi, dlp, genai-security, compliance, fastapi, presidio — are set; none overstate scope).

---

### Note on what was deliberately NOT added

I did not add more product/security/eval items: those already dominate TODO.md and serve goal (d) — becoming a deployable product for regulated buyers — which you ranked lowest. The open P0/Security and P0/Eval items there *do* matter for credibility in one specific way: the README must not claim guarantees those items show are not yet true (unconditional mapping encryption, append-only journals, procurement-grade accuracy). The P1/Credibility items above are written to stay honest about exactly those gaps rather than to close them.
