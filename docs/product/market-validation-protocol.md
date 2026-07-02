# Market Validation Protocol

Status: protocol only. No participant evidence is present in this repository.

This protocol prepares the two open market-validation TODOs without satisfying
them. Do not mark either TODO complete until participant records are added and
`docs/product/personas.md` plus `docs/product/value-metrics.md` are updated with
validated findings.

## Source Basis

Web check performed 2026-07-02.

- Nielsen Norman Group describes user interviews as a discovery method for
  learning user needs, experiences, and pain points:
  <https://www.nngroup.com/articles/user-interviews/>.
- Nielsen Norman Group describes qualitative usability testing as direct
  observation of task behavior and notes that five participants can uncover
  common issues for one user group:
  <https://www.nngroup.com/articles/usability-testing-101/>.
- Nielsen Norman Group guidance for task scenarios says tasks should be
  realistic, action-oriented, and avoid giving away the interface path:
  <https://www.nngroup.com/articles/task-scenarios-usability-testing/>.

Use the five-participant TODO as qualitative evidence only. It is not a
statistical proof of adoption rate, task time, or conversion.

## Recruiting Quotas

Minimum participant mix for the interview TODO:

| Segment | Minimum | Screening criteria |
|---|---:|---|
| Legal reviewer | 2 | Reviews external communications, deal docs, filings, or privilege-sensitive material. |
| Compliance/admin | 2 | Owns policy, escalation, audit, DLP, or regulated-data review workflows. |
| Security/platform | 1 | Owns integration, endpoint, browser, email, DMS, SIEM, or API rollout decisions. |

Reject participants who only have generic consumer privacy opinions and no
workflow ownership or direct review burden.

## Interview Guide

Record only notes, role, segment, workflow, and coded findings. Do not commit
raw transcripts, names, employers, email addresses, deal names, client names, or
document excerpts.

Required prompts:

1. Walk me through the last time sensitive content had to be checked before an
   email, GenAI paste, DMS upload, or external share.
2. What made that workflow slow, risky, or easy to bypass?
3. Which tools did you use, and where did the review evidence end up?
4. What would make an inline Junas warning trusted or ignored?
5. What approval, audit, SIEM, or policy evidence would be required for rollout?
6. Where would a standalone copy-paste redactor fit or fail in the same day?

Followups:

- When did this happen?
- How often does this happen?
- Who owns the final decision?
- What information must not leave the tenant boundary?
- What would block a pilot even if detection accuracy looked good?

## Manual Task Study

Run a within-participant qualitative study with the same synthetic content set
across two flows:

| Flow | Start state | Success condition |
|---|---|---|
| Standalone copy-paste redaction | Participant has text in an external workflow and must manually switch to a separate redaction/review surface. | Participant completes review and applies the required safe action before simulated send/share/paste. |
| In-workflow review | Participant starts in Outlook/browser-style surface where Junas warning appears before completion. | Participant completes review and applies the required safe action before simulated send/share/paste. |

Task scenarios:

1. PII: send a short update containing an SG NRIC and named person.
2. MNPI: prepare an external investor message with an unannounced acquisition
   price and project codename.
3. Clean text: share a benign internal note.

Capture coded evidence only:

- completion status: `completed_safe`, `completed_risky`, `abandoned`,
  `facilitator_rescued`;
- friction code: `context_switch`, `unclear_action`, `trust_gap`,
  `false_positive_concern`, `approval_unclear`, `slow_response`,
  `copy_paste_error`, `none`;
- observed bypass: `none`, `sent_without_review`, `ignored_warning`,
  `manual_redaction_skipped`, `used_unapproved_tool`;
- participant segment and flow order;
- optional time buckets: `<30s`, `30-60s`, `1-3m`, `3-5m`, `>5m`.

Do not record raw task text beyond the synthetic fixtures already committed in
the repo.

## Evidence File Shape

When real sessions exist, add one redacted JSON file under
`reports/market-validation/`:

```json
{
  "schema_version": "junas.market_validation.v1",
  "participant_count": 5,
  "segments": {"legal": 2, "compliance": 2, "security_platform": 1},
  "interview_status": "complete",
  "task_study_status": "complete",
  "raw_text_committed": false,
  "findings": [
    {
      "finding_id": "mv-001",
      "segment": "legal",
      "workflow": "genai_paste",
      "pain_point": "context_switch",
      "evidence_count": 3,
      "doc_update": "docs/product/personas.md"
    }
  ],
  "task_summary": {
    "standalone_copy_paste": {"completed_safe": 0, "abandoned": 0},
    "in_workflow": {"completed_safe": 0, "abandoned": 0}
  }
}
```

Only after that evidence exists should the open TODOs be removed.
