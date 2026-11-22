# Classifier reliability tuning — 22 November 2026

Both synthetic development sets now pass all predeclared engineering targets. These are tuned model-reference agreements, not independently established detection accuracy. No paid inference was used.

| Development measure | Before | After |
| --- | --- | --- |
| 72 docs: PII exact spans | 46/129 (35.7%) | 122/129 (94.6%) |
| 72 docs: PII overlap spans | 55/129 (42.6%) | 124/129 (96.1%) |
| 72 docs: PII positive documents detected | 28/36 | 36/36 |
| 72 docs: MNPI positive documents detected | 13/36 | 36/36 |
| 72 docs: PII-negative documents flagged | 14/36 | 0/36 |
| 200 docs: PII exact spans | 329/531 (62.0%) | 472/531 (88.9%) |
| 200 docs: PII overlap spans | 340/531 (64.0%) | 476/531 (89.6%) |
| 200 docs: PII positive documents detected | 99/100 | 99/100 |
| 200 docs: MNPI positive documents detected | 28/100 | 87/100 |
| 200 docs: PII-negative documents flagged | 22/100 | 0/100 |

Positive document detection counts abstentions against detection. Both targets have zero negative-document flags and zero negative-document abstentions after tuning. The older set has 13 positive MNPI abstentions and one missed PII-positive document. Each dataset contains all four PII/MNPI quadrants, with 18 or 50 documents per quadrant.

Changes ground names, aliases and personal-record fields in person-specific context; distinguish personal contacts from corporate/shared channels; and link issuer events, materiality evidence and disclosure claims within bounded context. Unrelated topics, hypothetical events and conflicting public/private assertions do not establish a positive contextual result. Contextual output is versioned `junas.sensitivity.v2`; broad findings, scores and risk classifications retain their existing behavior.

The development evaluator checks immutable source identity and recomputed consensus, refuses holdout inputs and duplicate document IDs, and counts abstentions explicitly. Targets were committed before tuning. Reference labels and historical reports were not changed.

Verification: 1,744 tests plus 254 subtests pass on each of Python 3.11 and 3.12. All eight changed Python files pass Ruff lint/format; the five changed runtime/evaluation sources pass scoped mypy. All nine locked corpus gates pass. A network-denied replay of 1,722 documents and 27,034 findings finds no changed legacy result, invalid span or duplicate finding. The sdist and wheel build; an isolated wheel installation passes three classifier smoke cases and CLI execution, and matches the frozen runtime hash. The initial offline dependency installation failed for an empty cache; installation using downloaded locked direct dependencies passed.

Important limits: quasi-identifiers remain weak (4/7 exact matches on the 72-document set; 0/1 on the older set). The older set has no bank-account examples. Exact unmatched predictions on declared exhaustive units remain 4 and 11. Some annotations have unknown coverage, so pooled precision and F2 remain unavailable. Full-project mypy was not run; imported dependencies are silent in the scoped check. Model judges can share errors, scores remain uncalibrated, and legal materiality/public status are unverified.

The consumed 40-document holdout was excluded from tuning and retesting. Fresh unseen validation remains necessary. For planning, the previous 40-document generation/judging stage cost US$1.75; a new run could use a separately approved US$3 cap, with automatic budget stopping. This is a historical estimate, not a live quote; new scenario families, exclusions and a frozen classifier are required. No new run is authorized or started.

All pre-existing uncommitted changes, including README, remain unchanged. The two paid-run archives retain all 1,079 and 971 recorded file hashes. Commits apply only to this reliability work. Validation describes the current workspace, which includes earlier uncommitted work.

Implementation HEAD: `fc8072ddd7db03be1d1a6c82fe3394b7604373cc`. Runtime SHA-256: `9e28c87ad7acb888b7506ad9e061abd8d7b6f3773b1089cb29040a6a7aaf3c62`.

Commands: `python -m pytest -q`; `python scripts/evaluate_sensitivity.py --records <development-jsonl> --output <new-json>`; `python scripts/evaluate_accuracy.py --external skip --output <new-json>`; `uv build`. Full metrics and source identities are recorded in [the machine-readable report](../reports/current/classifier_reliability_tuning.json). Raw development sources and iteration reports remain in the private research directory.
