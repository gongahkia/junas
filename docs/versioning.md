# SG-LegalBench dataset versioning

Dataset versions are task-scoped. A change to SGLB-01 does not bump SGLB-02
unless SGLB-02 data, scoring, taxonomy, or methodology also changes.

Version IDs use this form:

```text
sglb-NN-vMAJOR.MINOR.PATCH
```

Patch zero may be omitted in public prose, so `sglb-01-v0.1` means
`sglb-01-v0.1.0`.

## Bump rules

| Change type | Required bump | Example | Applies when |
|---|---:|---|---|
| Accepted label dispute or erratum | Patch | `sglb-01-v0.1.1` | A released case label, answer, citation, source URL, penalty band, case metadata field, or other case-level extraction is corrected without changing the task taxonomy, scorer semantics, split policy, or methodology. |
| Taxonomy change | Minor | `sglb-01-v0.2` | Labels are added, removed, renamed, merged, split, or redefined while the task's source class and methodology remain the same. This also covers task-contract changes caused by taxonomy updates. |
| Methodology pivot | Major | `sglb-01-v1.0` | The benchmark changes how the task's gold labels are justified, sourced, extracted, scored, or split in a way that prevents direct comparison with earlier versions. |

## Patch versions for accepted disputes

No accepted dispute may be applied to released data without a patch bump on
the affected task dataset.

If multiple accepted disputes are applied in one corrigenda PR, increment the
patch number once per accepted dispute in that PR. For example, if
`sglb-01-v0.1.0` has three accepted label disputes released together, the next
SGLB-01 dataset version is `sglb-01-v0.1.3`.

Patch releases may include clerical corrections only when they are tied to an
accepted dispute or erratum and do not alter taxonomy or methodology.

## Minor versions for taxonomy changes

Use a minor version when the label space or task contract changes but the
core methodology is still comparable. Examples:

- splitting `no_breach` into more specific no-liability labels;
- adding a new public-source category to an existing multi-label task;
- renaming a label in a way that requires dataset consumers to update code;
- changing output fields because the taxonomy changed.

If accepted label disputes are pending for the same task, apply their patch
bump first, then apply the minor bump. For example:
`sglb-01-v0.1.0` -> `sglb-01-v0.1.2` for two accepted disputes, then
`sglb-01-v0.2.0` for the taxonomy change.

## Major versions for methodology pivots

Use a major version when scores should not be compared directly with earlier
versions. Examples:

- switching the public source of truth for gold labels;
- moving from deterministic extraction to a materially different labelling
  method;
- changing scorer semantics rather than fixing an implementation bug;
- changing split construction, cutoff policy, or contamination controls;
- expanding a task beyond public-domain SG legal sources.

Methodology pivots require release notes that explain why older scores are not
directly comparable.

## Corrigenda release train

Accepted disputes are resolved through the next scheduled minor-release train,
expected every 4-8 weeks. The cadence does not change the bump rule: a pure
accepted dispute still receives a patch version, a taxonomy change receives a
minor version, and a methodology pivot receives a major version.

When a release train contains multiple change classes for one task, apply them
in this order:

1. accepted-dispute patch bumps;
2. taxonomy minor bump;
3. methodology major bump.

The public errata log for the task must identify which disputes were applied
before the broader version bump.
