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

## P1/Credibility — Independent signals a reviewer can verify quickly

## P2/Reach — Distribution, once the surface is strong (do NOT start before P0/Surface is done)

---

### Note on what was deliberately NOT added

I did not add more product/security/eval items: those already dominate TODO.md and serve goal (d) — becoming a deployable product for regulated buyers — which you ranked lowest. The open P0/Security and P0/Eval items there *do* matter for credibility in one specific way: the README must not claim guarantees those items show are not yet true (unconditional mapping encryption, append-only journals, procurement-grade accuracy). The P1/Credibility items above are written to stay honest about exactly those gaps rather than to close them.
