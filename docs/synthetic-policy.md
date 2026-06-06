# Synthetic Promotion Policy

Synthetic benchmark rows may be generated only for SGLB-08, SGLB-12, and
SGLB-15. Candidate YAML files stay under `backend/benchmark/datasets/*_candidates/`
until a human review marks the row as approved and the promotion command moves
it into the matching `*_reviewed/` directory.

## Promotion Gate

CI runs:

```sh
cd backend
python -m benchmark.synthetic.validator
```

The guard scans every `*_candidates/*.yaml` row and every reviewed-tier YAML
file under `*_reviewed/`, including aggregate `dataset.yaml` files. A candidate
row fails the gate when:

- its `metadata.review_status` is not `approved`; and
- it is referenced by reviewed-tier YAML through the same case name, the same
  fixture filename, or `_promotion.source_fixture` metadata.

This blocks accidental copies of pending, rejected, needs-edit, or missing-status
candidates into the reviewed corpus.

## Correct Promotion Flow

Use the review and promotion commands instead of manually copying YAML:

```sh
python -m benchmark.synthetic review --task sglb_08 --fixture <slug> --decision approve --reviewer <name>
python -m benchmark.synthetic promote --task sglb_08
```

`promote` moves approved fixtures out of `*_candidates/`, writes
`promotion_audit.jsonl`, stamps `_promotion` metadata, and refreshes the
reviewed `dataset.yaml`.

## Edge Cases

- Approved candidates left in `*_candidates/` do not trip this specific CI gate,
  but they should still be promoted with the promoter so the audit log and
  aggregate dataset stay consistent.
- A stale reviewed `dataset.yaml` can fail the gate if it still references a
  non-approved candidate.
- Malformed YAML in synthetic candidate or reviewed directories fails the gate
  because CI cannot reliably determine review status.
- The guard matches by case name, fixture filename, and recorded promotion
  source path. If someone manually rewrites all lineage fields and changes the
  case name, this guard cannot infer provenance from content alone.
