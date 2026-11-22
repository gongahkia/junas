# Singapore development pilot — reviewer instructions

All documents in this kit are newly model-authored synthetic development examples. Names, numbers, organizations and events were invented for this task; they are not supplied as real-world personal records. These examples are unreviewed, not gold labels, and cannot establish real-world representativeness. Annotate the fictional scenario's contents using these guidelines. Do not assume that an author's assertion about identifiability or publicity is correct.

Your identity, review dates and findings have not been filled in. A blank template is not a review event. There are no predictions, detected-rule lists or proposed source-specific labels in this packet. Do not consult Junas, an LLM, existing corpus labels or another annotator's answers while independently annotating.

## Getting started

The custodian gives each reviewer a separate private copy of this kit. Do not edit the source texts, metadata or another person's submissions. Work in your own copy of `submission-templates/`. Read each complete document in `documents/`, consulting `document-metadata.json` for its ID, source/family, jurisdiction, type and exact text hash. The initial pilot is Singapore, English, canonical text only; it does not assess OCR or document extraction.

Use only your actual pseudonymous reviewer ID, actual record IDs and actual timezone-bearing timestamps when recording work. Do not invent a second reviewer, an approval or an adjudication. Set provenance fields according to what actually happened. `source_author` means author of the document, not author of the annotation. Blindness to models refers to model predictions/annotation proposals; the clearly disclosed model origin of the source text is a separate limitation.

The initial template has `stage: draft`, unknown coverage, empty annotation lists, null identity/time and null approval. It is deliberately incomplete and will be rejected if submitted unchanged. Change to `submitted` only when you actually submit your review. A custodian validates and records the completed entry using the existing review-log tool. Do not add chain hashes yourself.

## Primary track: PII occurrences

Use category `PII` and one of these labels. They define the pilot target, not all legally possible personal data:

| Label | Definition |
|---|---|
| `GOVERNMENT_ID` | Personal national/tax/passport identifier, excluding corporate registration numbers |
| `PERSON_NAME` | Name referring to a natural person in the scenario |
| `EMAIL` | Person-associated email; distinguish shared or role-only organizational contact |
| `PHONE` | Person-associated telephone number; distinguish generic company contact |
| `POSTAL_ADDRESS` | Person-associated postal address; distinguish company premises and delivery points |
| `BANK_ACCOUNT` | Person-associated account identifier, excluding amounts, bank names and organization-only accounts |
| `PERSONAL_RECORD_ID` | Person-linked employee, customer, banking, medical or insurance record identifier |
| `DATE_OF_BIRTH` | Date describing a person's birth, excluding transaction, commencement and processing dates |
| `QUASI_IDENTIFIER_COMBINATION` | Contextually identifying combination of clues, supported by a written linkage rationale |

Corporate names/registration numbers, court citations, fees/percentages, generic policy language, empty form headings and isolated age/job/locale clues are outside the narrow primary target unless the context justifies an in-scope label. Other national identifiers, standalone sensitive health/genetic/biometric information and digital identifiers are outside this pilot crosswalk. Record relevant out-of-scope observations separately; exclusion from this pilot does not mean legally safe.

Read person association from the source context. For a fictional personal identifier, assess its asserted role and plausibility; abstain with reasons if validity or placeholder treatment is ambiguous. Do not run a detector to resolve the question. Annotate all occurrences, not just the first. Different valid labels may overlap. For a contextual combination, use the smallest contiguous envelope covering the necessary clues and explain the linkage; do not invent discontiguous offsets. Mark component entities when independently in scope.

Use minimal complete entity boundaries. Exclude surrounding whitespace and labels such as `Name:`; retain punctuation belonging to the entity. If boundaries or scope are uncertain, retain `uncertain` or `abstain` and explain the problem. Do not force a doubtful case into a definite positive or negative.

A PII annotation has this shape; the null/empty fields below are field placeholders, not suggested annotations:

```json
{
  "category": "PII", "label": null,
  "start_char": null, "end_char": null, "matched_text": "",
  "certainty": null, "reason": ""
}
```

Fill `certainty` with `certain`, `uncertain` or `abstain`. Append your completed item to `pii`. Do not place this unfinished object in a submitted entry.

## Exact coordinates

Offsets are zero-based Python Unicode characters, with an exclusive end, in the exact canonical UTF-8 text. Every source-bearing item must satisfy:

```text
0 <= start_char < end_char <= len(text)
text[start_char:end_char] == matched_text
```

Select the actual occurrence in an editor that reports character offsets. Repeated text has different coordinates. Do not use substring search to repair a span or assign every occurrence the first match. Do not normalize whitespace, newlines, punctuation or Unicode, and do not edit a source to match an annotation.

You can inspect explicit coordinates locally without any model or classifier. For example, from your private kit copy:

```python
from pathlib import Path
text = Path("documents/dev-001.txt").read_bytes().decode("utf-8")
# choose start and end from your actual selection, then inspect:
print(repr(text[start:end]))
# for a character-index view of this document:
for index, character in enumerate(text):
    print(index, repr(character))
```

This is a view of canonical characters, not automatic annotation or a search for matching text.

## Secondary track: contextual MNPI review signals

This track records context requiring review; it is not a SAFE/HIGH_RISK decision. An amount, percentage, draft agreement, confidentiality marker or transaction keyword does not establish materiality or non-public status.

For a relevant signal, add an object to `mnpi` with exact `start_char`, `end_char`, `matched_text` and these fields:

- `entity`: relevant issuer/entity description, or null.
- `potential_materiality`: `potentially_material`, `not_material` or `unknown`.
- `public_status`: `public`, `non_public` or `unknown`.
- `as_of`: relevant ISO calendar date, or null.
- `evidence`: a list of supporting records with `kind` (`document`, `external` or `unknown`), `reference` and `provenance`. Document evidence also has exact offsets/text. External evidence has no invented document coordinates.
- `ambiguity`: missing entity, publication context, date, source support, disputed materiality or other uncertainty.
- `human_review_required`: true whenever relevant context or evidence is unresolved.

Do not browse or fetch outside material for this pilot unless the custodian separately authorizes it. Unsupported publicity claims stay unknown; a document's own assertion is not independent external corroboration. Supporting references may be recorded without fetching them. MNPI uncertainty must remain visible.

## Completeness, exclusions and submission

Declare `coverage.PII` and `coverage.MNPI` separately as `unknown`, `partial` or `exhaustive`. Empty lists do not establish negative examples. Declare exhaustive coverage only after reviewing the entire target and resolving in-scope uncertainties. Uncertain/abstained PII and target exclusions prohibit exhaustive PII coverage. Missing context in MNPI prohibits an exhaustive MNPI declaration; it does not prevent a separate exhaustive PII review.

An exclusion records `target` (`PII`, `MNPI` or `out_of_scope`), exact `start_char`, `end_char`, `matched_text` and a nonempty `reason`. Keep document-level concerns in `notes`; do not fabricate a source span for them.

Submit each completed entry privately to the custodian. Corrections use a new record ID, refer to your prior snapshot through `supersedes`, retain actual timestamps and explain the correction in `notes`. The custodian retains earlier versions. Blind submissions have `based_on: []` and `approval: null`. Do not inspect the merged review log until independent submission is finished.

Single-reviewer development annotation is permitted as a qualified pilot. It is not independent double annotation or adjudicated ground truth. With multiple reviewers, disagreement remains pending until a separately assigned adjudicator records a decision. Acceptance requires an explicit actual human approval event. The software cannot authenticate identities or prove independent work.
