# Procurement FAQ

This FAQ is for security, legal, and procurement conversations. It keeps accuracy claims tied to committed evidence and separates product scope from unsupported claims.

Use `docs/faq/buyer-objections.md` for objection-specific answers covering accuracy
proof, legal liability, data residency, admin deployment, user friction, false
positives, and existing DLP interoperability.
Use `docs/product/claim-review-checklist.md` before turning any answer into public
marketing, security, or procurement copy.

## Accuracy Claim Rule

Use only promoted corpus locks and committed evaluation reports for accuracy statements:

- Generated detector disclosure: [`docs/accuracy.md`](../accuracy.md)
- Promoted reviewed-candidate lock: [`test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json`](../../test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json)
- Promoted strict candidate report: [`reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json`](../../reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json)
- Candidate status page: [`docs/candidate_corpus_status.md`](../candidate_corpus_status.md)

Before claiming improved detection, verify that fixture text plus `.labels.json`
sidecars are committed, labels are human-approved, the promoted recall lock was
refreshed with `--require-human-reviewed`, precision evidence is committed, and
`docs/accuracy.md` was regenerated from those locks.

Current promoted strict evidence: 1,428 approved legal/cross-jurisdiction documents, 17,552 strict expected labels, strict recall `1.0000`, and strict precision `0.9269` in `20260608-strict-item70v2_strict_candidate_eval.json`.

Treat this as an in-repo legal fixture benchmark and regression gate, not an independent market benchmark.

## What Can We Say About Accuracy?

Say: Junas has deterministic in-domain regression evidence over committed, human-approved legal fixtures. The evidence is detector-level span evidence and policy-contract evidence, not a statement about every possible customer document or workflow surface.

Do not use screenshots, demo flows, unpromoted candidate sidecars, synthetic examples, or roadmap notes as accuracy evidence.

## What Independent Benchmarks Exist?

No Junas score on TAB or ai4privacy is claimed until an eval report is committed. Those datasets are future comparison targets only.

There is no public MNPI benchmark in this repo comparable to TAB or ai4privacy. Current MNPI evidence is in-domain legal fixture evidence plus statutory coverage docs and review examples.

## Can Junas Replace Legal Advice Or DLP?

No. Junas is not legal advice and does not replace Microsoft Purview, Google Workspace DLP, Slack DLP, CASB, endpoint control, IdP policy, or customer counsel review. Use [`docs/product/non-goals.md`](../product/non-goals.md) and [`docs/known-limitations.md`](../known-limitations.md) for scope boundaries.

## What Should A Buyer Validate In Pilot?

Run a customer pilot validation corpus before relying on Junas in production. Include representative Outlook sends, GenAI prompts, DMS uploads, legal memos, safe rewrites, reviewer approvals, and audit exports.

Record false positives, false negatives found by reviewers, accepted findings, override rate, rewrite acceptance, blocked-risk outcomes, adapter failures, and audit-pack exports. Tie every pilot claim back to the specific corpus, policy profile, adapter, and commit used for the run.
