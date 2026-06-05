# SG-LegalBench dispute and errata process

This process gives vendors, benchmark users, and labelled-case subjects a
public path to dispute released SG-LegalBench labels or raise concerns about
the benchmark methodology.

GitHub issues are the operational record. Do not include confidential,
privileged, sealed, or paywalled evidence in an issue. Benchmark labels must be
verifiable from public sources.

## What to file

Use the label-dispute issue form when the concern is about one released case:

- wrong gold label, answer, outcome, citation, penalty band, or extracted
  field;
- malformed citation or source URL;
- case metadata that changes how the example should be scored.

File it here: <https://github.com/gongahkia/junas/issues/new?template=label_dispute.yml>

The form requires:

- task ID and case ID;
- dataset version observed;
- disputed label or field;
- public evidence URL and evidence summary;
- suggested correction;
- filer relationship to the case, if any.

Use the methodology-concern issue form for systematic concerns:

- taxonomy categories are incomplete, overlapping, or misleading;
- an extraction rule is systematically wrong;
- a scorer, normaliser, split policy, or source-provenance rule is flawed;
- the dispute would affect multiple cases or a task contract.

File it here: <https://github.com/gongahkia/junas/issues/new?template=methodology_concern.yml>

## What happens next

1. The issue receives a pending triage label.
2. Within 14 calendar days of filing, maintainers add exactly one triage
   outcome label: `accepted`, `rejected`, or `needs-evidence`.
3. If a maintainer was involved in labelling the disputed case, authoring the
   disputed extraction row, or reviewing the disputed label before release,
   that maintainer discloses the conflict and recuses from triage.
4. `accepted` means the public evidence supports a correction. The correction
   is queued for the next corrigenda release.
5. `needs-evidence` means the issue is missing required public evidence. When
   the filer supplies the missing evidence, maintainers re-triage within 14
   calendar days of that update.
6. `rejected` means maintainers do not think the public evidence supports a
   correction. The issue remains public with a short rationale and may be
   reopened if new public evidence is added.

Triage is not legal advice and does not decide the underlying legal dispute.
It only decides whether the benchmark record should change.

## Corrigenda cadence

Accepted label disputes are batched into the next scheduled minor-release
train, expected every 4-8 weeks. Corrections are not hot-patched directly into
released dataset YAML from the issue; they land through a follow-up PR that:

- updates the affected task data;
- records each accepted correction in the public errata log;
- bumps the affected dataset version under the versioning policy.

If a correction misses the release freeze for a train, it moves to the next
train and remains labelled `accepted`.

## Public errata log

Each task keeps a public errata log at `data/sglb_NN/errata.md`, replacing
`NN` with the two-digit task number. For example:
[`data/sglb_01/errata.md`](../data/sglb_01/errata.md).

Every accepted dispute should be traceable from the issue to the errata row
and the release that applied it. Errata rows should identify the issue, case
ID, affected label or field, accepted correction, public evidence URL, release
version, and attribution.

## Versioning

Accepted label disputes require a dataset patch version bump on the affected
task, such as `sglb-01-v0.1.1`. Taxonomy changes require a minor version bump,
such as `sglb-01-v0.2`. Methodology pivots require a major version bump, such
as `sglb-01-v1.0`.

The full policy is in [Dataset versioning](versioning.md).

## Out of scope

This process does not cover confidential takedown demands, private settlement
communications, security disclosures, or disputes that depend on non-public
evidence. It also does not provide a private legal complaint channel for
vendors or labelled-case subjects.
