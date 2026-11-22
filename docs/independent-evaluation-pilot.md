# Independent evaluation pilot — preparation protocol v1

Status: **proposal awaiting human approval**. Protocol ID: `junas.legal-pilot.v1`.
Implementation validation is separate from annotation readiness, independent ground-truth readiness and protected-holdout readiness. No pilot documents have been collected by this tranche. No actual human annotations, gold labels or protected-holdout results are supplied. The synthetic unit-test records simulate review events; they are not human-review evidence.

## Domain and measurement tracks

Primary domain: short English legal and transaction-document excerpts, including engagement/onboarding, employment, financing, transaction, disclosure and compliance correspondence. Proposed jurisdictions: SG, US, UK and AU, with SG as the majority. This is a deliberately narrow pilot, not national, multilingual or general-document representativeness.

Primary target: PII **occurrences** in exact canonical text, using `junas.occurrence.v1`. Secondary target: contextual MNPI review signals with separately recorded uncertainty and evidence. No document SAFE/HIGH_RISK ground truth is inferred from either track. Text annotation does not measure file extraction, OCR or original-layout accuracy; those need separate source-grounded studies.

### Proposed PII taxonomy and rule crosswalk

Every primary label has category `PII`. These proposed target labels are annotations, not detector rules reviewers must reproduce. Reviewers use the definitions below without seeing rule names or predictions. The custodian retains the crosswalk for a later approved comparison.

| Label | Annotation target | Existing Junas rule candidates |
|---|---|---|
| `GOVERNMENT_ID` | Personal national/tax/passport identifier; not corporate registration numbers | `sg_nric_fin`, `us_ssn`, `uk_nin`, `au_tfn`, `passport_number` |
| `PERSON_NAME` | Name referring to a natural person, including a fictional person within a synthetic scenario | `named_person` |
| `EMAIL` | Person-associated email address; role-only/shared organizational contact is a hard negative | `email_address` |
| `PHONE` | Person-associated phone number, excluding generic organizational contact | `phone_number` |
| `POSTAL_ADDRESS` | Person-associated postal address; initial mapped forms are SG/AU | `sg_postal_address`, `au_postal_address` |
| `BANK_ACCOUNT` | Person-associated account identifier, not an amount, bank name or organization-only account | `bank_account` |
| `PERSONAL_RECORD_ID` | Person-linked employment/customer/banking/medical/insurance record identifier | `employee_id`, `customer_account_number`, `bank_customer_reference`, `medical_record_number`, `insurance_member_id` |
| `DATE_OF_BIRTH` | Date explicitly describing a person's birth, excluding execution/settlement dates | `date_of_birth` |
| `QUASI_IDENTIFIER_COMBINATION` | Contextually identifying combination with a written linkage rationale | `quasi_identifier_combination` |

The map is deliberately narrower than `scripts/fixture_taxonomy.py`, which also inventories corporate identifiers, administrative references and policy markers. Corporate UEN/ABN/EIN, company names, court citations, licence references, financial amounts/percentages, generic privacy language and consent markers are not automatically personal-data occurrences. Other national identifiers, isolated age/job/locale clues, special-category health/genetic/biometric content, digital identifiers, unsupported languages and unmapped address forms are outside this pilot's primary crosswalk. Record relevant exclusions and uncertainty rather than deleting them from the document. Out-of-scope does not mean legally non-personal or safe.

A rule name alone does not establish semantic equivalence: generic email, account and address findings may refer to organizations. Review person association from source context. US/UK address coverage has no justified rule-specific mapping here. A future evaluator must declare which rule outputs map to which target, filter both sides consistently, disclose unmapped outputs and freeze any boundary/crosswalk decision before seeing holdout predictions. No prediction adapter or model comparison is implemented in this tranche.

### Boundary and ambiguity guidelines

Use zero-based Python Unicode character offsets, half-open `[start_char,end_char)`, into the exact canonical UTF-8 text. Byte offsets and UTF-16 code-unit offsets are different and must not be substituted. Do not normalize newline, whitespace, punctuation, Unicode or OCR text after freezing. Each record repeats the text hash; `text[start:end] == matched_text` is mandatory. Choose coordinates from the actual occurrence using an editor's explicit selection/character-count facility; do not repair offsets by searching for the first occurrence.

Mark minimal complete entity boundaries, excluding surrounding whitespace and labels such as `Name:`. Preserve punctuation that belongs to the identifier or name. Mark each repeated occurrence separately. Different justified labels may overlap; identical same-label/same-span duplicates are invalid. A contextual combination may use a minimal contiguous envelope containing its necessary clues, with the linkage rationale in `reason`; do not fabricate a discontiguous span. Annotate component entities independently when in scope. Boundary uncertainty becomes `uncertain` or `abstain`, not detector-guided boundary adjustment.

`certainty` is `certain`, `uncertain` or `abstain`. Unresolved in-scope uncertainty/exclusions prohibit `PII: exhaustive`; keep partial/unknown coverage until resolved. An exhaustive negative document has no in-scope PII spans and an explicit exhaustive declaration after full review. Empty labels alone do not establish a negative. Keep out-of-scope exclusions separately, with exact spans and reasons, and report that precision concerns the narrow target only.

### MNPI contextual fields

Each signal carries an exact source span plus:

- `entity`: natural-language relevant issuer/entity, or null when unknown.
- `potential_materiality`: `potentially_material`, `not_material` or `unknown`, supported by reasoning/evidence rather than keywords.
- `public_status`: `public`, `non_public` or `unknown`.
- `as_of`: relevant ISO calendar date, or null; explain date/publication context in evidence/ambiguity.
- `evidence`: document-local spans and/or authorized external references, each with `kind`, `reference` and `provenance`. External evidence has no invented document offsets. The tool never fetches references.
- `ambiguity`: missing context, disputed materiality, unsupported publicity assumptions or insufficient evidence.
- `human_review_required`: true whenever entity, materiality, publicity, as-of context or supporting evidence is unresolved.

A contract amount, financial keyword, confidentiality boilerplate or codename is not proof of MNPI. Unknown cases remain unknown; do not convert them to SAFE/HIGH_RISK. `MNPI` completeness is separate from `PII`; unresolved signals prohibit an exhaustive MNPI declaration. The pilot does not establish legal MNPI classification accuracy.

## Proposed sample and partition plan

Target **80 excerpts**, adjustable to 60–100 only after checking reviewer capacity. Prefer 150–600 words, at most 20,000 canonical characters. Aim for about 40 source/scenario families with two excerpts each, assigning entire families to one partition. Proposed split: 40 development, 40 protected holdout, approximately 20 families each. Do not create a training set in this pilot.

Suggested primary sampling intentions (not labels): 16 ordinary negatives, 20 clear PII-positive scenarios, 12 contextual PII, 12 hard negatives, 8 repeated-identifier cases, 6 overlapping-entity cases and 6 ambiguous MNPI scenarios. Cross-tag legal document type, jurisdiction, structure and MNPI context. Actual annotations may disagree with intended strata. Do not select/drop examples after looking at predictions. Approximately 40 SG, 16 US, 12 UK and 12 AU excerpts, balanced across partitions at family level where possible; record achieved counts rather than forcing variant leakage to meet quotas.

Use paragraph memos, correspondence, clauses, short lists and text tables. Keep all variants of one source, template or scenario together. The initial study evaluates canonical text; retaining a DOCX/PDF source does not make it an extraction benchmark.

Only newly human-authored synthetic material or explicitly authorized licence-compatible public material is eligible. Record source ownership/licence and reference before admission. Avoid real personal data in synthetic material. Public availability alone is not a licence or privacy authorization. Model-generated source text, if proposed later, remains marked `generation_origin: model` and synthetic; its sampling limitations require approval. No model generation or downloads occur here.

Existing internal detector-reconciled corpora may inform this protocol but must not become independent holdout truth. A custodian must check the prior-use registry, document lineage, template/scenario identities and near duplicates against development, historical regression and all known tuning/prompt material. Retain both original-source-byte and exact-canonical-text SHA256. The near-duplicate heuristic uses NFKC/casefolded token trigrams, numeric-token masking and Jaccard >= 0.75. It is a warning heuristic, not semantic duplicate detection; short paraphrases, renamed entities and unrecorded template relationships need human review. Similarity hashes can leak low-entropy content and belong in custodian storage, not public Git.

## Manifest schema

`junas.annotation_manifest.v1` records `protocol_id`, `dataset_id`, `purpose` (`pilot` or `tooling_toy`) and 1–100 documents. Each document requires ID, split, source/template/scenario identities, relative source/text paths, jurisdiction, type, synthetic flag, generation origin, authorization and prior-use declaration. Hashed manifests also require `source_sha256`, `canonical_text_sha256`, and `similarity_sha256`.

For an eligible **development** plan, before hashing:

```json
{
  "schema_version": "junas.annotation_manifest.v1",
  "protocol_id": "junas.legal-pilot.v1",
  "dataset_id": "pilot-pending-approval",
  "purpose": "pilot",
  "documents": [{
    "document_id": "dev-001",
    "split": "development",
    "source_id": "source-family-001",
    "template_family_id": "template-001",
    "scenario_family_id": "scenario-001",
    "source_path": "sources/dev-001.txt",
    "text_path": "canonical/dev-001.txt",
    "jurisdiction": "SG",
    "document_type": "memo",
    "synthetic": true,
    "generation_origin": "human",
    "authorization": {
      "basis": "synthetic_owned",
      "reference": "REPLACE with actual author/authorization record",
      "licence": "REPLACE with actual permission terms"
    },
    "prior_use": "none"
  }]
}
```

This example is a structural handoff, not a collected document or an authorization event. Paths resolve within the manifest directory, including symlink checks. Exact UTF-8 text is hashed without universal-newline conversion. `fingerprint` emits a new manifest; it does not certify licence declarations or copy/approve a source. After a text correction, produce a new version and reannotate; never transfer old spans silently.

## Review schema and blind workflow

`junas.annotation_review.v1` is an immutable-snapshot JSONL log. Each record identifies protocol, document, split, canonical hash, reviewer pseudonym, stage and timezone-bearing timestamp. It includes separate PII/MNPI coverage, PII occurrences, contextual MNPI signals, exclusions, notes, provenance, earlier `supersedes`/`based_on` references and explicit approval when accepted. Provenance records human/model-reviewed/detector-derived/unknown origin; blindness to Junas, models and other annotations; source authorship; and synthetic status. Unknown declarations are null. No independence is inferred from a missing marker.

A reviewer edits a single entry JSON without chain hashes. Initial draft skeleton:

```json
{
  "schema_version": "junas.annotation_review.v1",
  "protocol_id": "junas.legal-pilot.v1",
  "record_id": "review-dev001-a-v1",
  "document_id": "dev-001",
  "split": "development",
  "canonical_text_sha256": "REPLACE from the frozen manifest",
  "reviewer_id": "REPLACE with actual pseudonymous reviewer ID",
  "stage": "draft",
  "timestamp": "REPLACE with actual timezone-bearing timestamp",
  "provenance": {
    "label_origin": "unknown",
    "blinded_to_junas": null,
    "blinded_to_models": null,
    "blinded_to_other_annotations": null,
    "source_author": null,
    "synthetic": true
  },
  "coverage": {"PII": "unknown", "MNPI": "unknown"},
  "pii": [],
  "mnpi": [],
  "exclusions": [],
  "notes": "",
  "supersedes": null,
  "based_on": [],
  "approval": null
}
```

A PII item requires `category`, one target `label`, `start_char`, `end_char`, `matched_text`, `certainty` and nonempty `reason`. An exclusion requires `target` (`PII`, `MNPI` or `out_of_scope`), exact span/text and reason. MNPI items require all fields listed above; document evidence also requires exact span/text. Unknown fields are rejected to catch misspellings, not silently ignored.

1. A human custodian approves source use and partition allocation before annotation and keeps holdout materials outside the repository. Reviewers receive only their assigned canonical document, opaque document ID/hash, these guidelines with the detector crosswalk omitted, and their own blank/draft entry. Do not give them candidate labels, engine logs, Junas output, LLM proposals or another reviewer's annotations. Do not use `review_candidate_fixture.py`: it displays detector comparisons.
2. Assign two independently working annotators per document. A writer/source author may help clarify context but their own annotations are not blind non-author evidence. Use the development subset to pilot instructions and resolve taxonomy ambiguities before freezing the holdout protocol. Record conflicts and changes.
3. Each reviewer records actual identity/pseudonym and timestamps, marks every in-scope occurrence and uncertainty, and submits their own full snapshot. The custodian receives entries separately; reviewers must not inspect the merged JSONL history. The validator never generates missing labels.
4. The custodian retains original submissions and combines them into an ordered log. A correction has a new record ID, explicit `supersedes` link to that reviewer's prior snapshot and a correction rationale in `notes`; retain the old version. `based_on` remains empty for blind submissions.
5. For two or more active submissions, a separate adjudicator records an `adjudicated` snapshot referencing **all** active submissions and explaining agreement/disagreement resolution. Even agreement is documented. The original disagreements remain visible. No automatic consensus or majority-vote gold is created.
6. Acceptance is an explicit human event: `stage: accepted`, `based_on: [reviewed_snapshot_id]`, `approval: {reviewer_id, timestamp, reason}` and identical annotation contents to the reviewed snapshot. It cannot accept an unsubmitted draft. A later correction revokes prior active acceptance. Acceptance does not erase model/detector exposure in the correction/review lineage.
7. With only one annotator, explicit acceptance may be recorded, but it remains **single-annotator**, not independently adjudicated multi-annotator ground truth. Missing reviewers and uncertain/blindness declarations remain qualifications. Independent status never exceeds `declared_not_verified`; the validator cannot authenticate humans or attestations.

The custodian archives each version and its log-head hash in separately controlled, preferably immutable storage. A hash chain detects changes relative to a trusted prior anchor; it cannot detect replacement of the whole log if the anchor is also replaced. Pseudonyms need a custodian-controlled identity/role registry. Timestamps and approval records must describe actual events; do not backfill fabricated review history.

## Offline preparation commands

All paths below are hypothetical **development** material outside the repository. Use new output names; existing output files are never overwritten. Preparation commands do not invoke a classifier, model, network provider or score function.

```sh
uv run --frozen python scripts/prepare_evaluation_dataset.py fingerprint /private/dev/plan.json --output /private/dev/manifest-v1.json
uv run --frozen python scripts/prepare_evaluation_dataset.py append /private/dev/manifest-v1.json --entry /private/dev/entry-a-v1.json --output /private/dev/reviews-v1.jsonl
uv run --frozen python scripts/prepare_evaluation_dataset.py append /private/dev/manifest-v1.json --reviews /private/dev/reviews-v1.jsonl --entry /private/dev/entry-a-v2.json --output /private/dev/reviews-v2.jsonl
uv run --frozen python scripts/prepare_evaluation_dataset.py validate /private/dev/manifest-v1.json --reviews /private/dev/reviews-v2.jsonl --output /private/dev/validation-v2.json
```

`append` creates a **new complete log**, preserving the previous file and adding chain hashes only after validating the new state. It does not submit, adjudicate or accept a draft automatically. `validate` reports schema integrity, origins, uncertainty, declared blindness, disagreements, acceptance and qualifications; it reports no accuracy. Exit 0 means valid preparation, not independent dataset readiness; exit 1 means detected partition contamination; exit 2 means invalid/unreadable input or output collision.

`occurrence_inputs` converts explicitly accepted **development** PII annotations to T3A `Span`, text and coverage inputs without computing metrics. Uncertain/abstained spans remain in review history and are excluded from supplied-positive spans; their target coverage cannot be exhaustive. MNPI signals remain a separate contextual track. There is no benchmark command in this tool.

## Protected-holdout freeze and access boundary

A split name or Git directory is not an access control. The holdout's source text **and labels** must remain outside the checkout, under a human custodian account/storage inaccessible to tuning/prompt agents and ordinary development processes. Use actual filesystem/account/encryption controls and an access log; do not mount protected storage into the development runtime. Keep authorized reviewers' access limited to their assigned material. Do not expose low-entropy fingerprints publicly.

The current tool refuses **all** content-bearing operations on manifests containing `protected_holdout`, before source/text/review files are opened. Do not relabel holdout material as development to bypass this boundary. A later explicitly authorized custodian validation/freeze process must operate in the protected environment; this tranche does not implement an authentication or access-control service. The pure record schema supports matching split identity, but the public preparation loader admits development only.

A metadata-only custodian check can compare previously generated fingerprints without opening referenced source/label files:

```sh
uv run --frozen python scripts/prepare_evaluation_dataset.py partitions /private/custodian/dev-metadata.json /private/custodian/holdout-metadata.json --excluded-hashes /private/custodian/prior-use-sha256.json --output /private/custodian/partition-check-v1.json
```

`prior-use-sha256.json` is a custodian-owned JSON array of source/canonical SHA256 values for historical regression, development and known tuning material. The tool does not generate or certify a complete registry. Group IDs, prior-use declarations, exact hashes and token similarity checks expose recorded leakage; absence of a warning does not prove no contamination. The command always leaves protected readiness **NOT READY**. Only synthetic metadata is exercised in this tranche, not an actual protected manifest.

Before an actual freeze, require: approved source permissions; group-level partition and exclusion-registry review; two blind annotations; separately recorded adjudication/acceptance; canonical/source/annotation hashes and immutable log anchors; justified target completeness; documented custodian/reviewer approval; audited access history; and a frozen taxonomy, evaluation protocol, candidate code/configuration/dependency hashes and release decision. One future final comparison must be approved after candidate and protocol freeze. Subsequent inspection consumes protection for future tuning; record that exposure and refresh the holdout when needed.

No actual holdout is accessed, displayed, predicted or scored here. No sources, annotations, reviewer approvals, protected access controls or final evaluation have been established. All remain pending. A validated toy fixture does not change that status.

## Human decisions before collection

Approve or amend the target definitions/crosswalk, four-jurisdiction English scope, approximately 80-document/family-level split plan, source authorizations and reuse exclusions. Appoint a custodian, two independent annotators and a separate adjudicator, with actual capacity and access controls. Approve the versioned annotation/boundary guidelines after a development-only calibration exercise. If these prerequisites are unavailable, keep independent ground truth and protected holdout **NOT READY** and reduce the pilot rather than inventing annotations or reviewers.
