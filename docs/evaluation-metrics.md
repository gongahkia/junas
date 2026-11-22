# Evaluation measurement contracts

T3A adds versioned measurements without changing legacy regression calculations or locks. Historical reports remain historical evidence. No single headline accuracy score combines these tracks.

## Legacy definitions retained

| Measurement | Unit and formula | Interpretation |
|---|---|---|
| `recall_gate` per-rule recall | Expected `(rule, matched_text)` entries with any equal prediction / expected entries | Regression-label agreement. Category, offsets and occurrence identity are ignored. Duplicate expectations can share one prediction. |
| `recall_gate` per-rule precision | Expected-label hits / (expected-label hits + emitted findings matching explicitly forbidden text) | Hard-negative challenge agreement. Other unmatched predictions are ignored. Numerator and negative counts use different units; this is not general prediction precision. |
| Candidate `candidate_recall` | Matched strict rule/text entries / all strict entries | Legacy label agreement, rounded to four decimals. |
| Candidate `candidate_precision` | Matched strict entries / (matched strict entries + unexpected finding emissions) | Agreement with possibly incomplete labels; unexpected emissions are not independently adjudicated false positives. Repeated text is not occurrence-aware. |
| Candidate ideal metrics | Same calculations against `ideal_must_detect` | Coverage-gap inventory agreement, not independently established accuracy. |
| Candidate/gate independence fields | Recall after excluding historical source/reason detector-marker phrases | Historical exclusion calculation only. Missing phrases and owner approval do not establish blind independence. Legacy independent F2 mixes this recall with ordinary strict-label precision. |
| Legacy TAB exact/overlap | Greedy one-to-one matching by document/annotator; predictions replicated for each annotator | Binary DIRECT/QUASI masking agreement. Overlap requires a nonempty intersection; exact requires identical bounds. Order can affect greedy counts. Subgroup precision retains predictions outside the subgroup. |
| Legacy ai4privacy recall | Gold masks hit by any exact/overlapping prediction / gold masks | Gold-coverage recall: one prediction can credit several masks. No precision is calculated. US/GB slices use SSN/VEHICLEVRM label proxies, not observed locale. |

Legacy unexpected-finding triage buckets (including names containing `actual_detector_false_positive`) are heuristic review queues, not independent adjudications. TAB prediction-rule counts and singling-out counts describe emitted findings, QUASI annotations and per-document/annotator entity-ID groups. The QIC overlap score reuses legacy greedy span matching; it does not establish legal identifiability or group-level classification accuracy.

Where defined, F2 is `5*P*R/(4*P+R)`. Legacy zero-denominator conventions and rounding remain unchanged. `must_not_detect` is a text-based challenge list, not an exhaustive negative annotation of every document position. The numerical regression locks retain these definitions.

Document risk scores are not calibrated probabilities. This evaluation path has no qualified adjudicated document-risk truth; it does not calculate document-level accuracy, specificity, or a SAFE false-negative rate. Direct text evaluation does not measure extraction or OCR accuracy.

## Occurrence v1

`scripts/span_metrics.py` evaluates validated, half-open character spans. An observation identifies physical split, document and annotator. Category and label must match. Exact and overlap scores are reported separately.

The matcher computes a maximum-cardinality one-to-one assignment using iterative augmenting paths. Canonical sorting by observation, coordinates, category and label makes counts and tie assignment independent of input arrival order. One annotation and one prediction receive at most one credit in an observation. Duplicate predictions retain multiplicity; duplicate identical gold observations are rejected. Multiple annotators remain separate observations, with predictions explicitly replicated rather than inventing consensus labels.

For each mode:

- `matched = |maximum assignment|`.
- `labeled_span_recall = matched / gold`, unavailable when gold is empty. With partial annotations this measures supplied-positive agreement, not population recall.
- `unmatched_predictions = predictions - matched`.
- `precision_if_exhaustive = matched / predictions` only when every observation declares exhaustive coverage of the selected target; otherwise unavailable (`null`). Zero predictions also makes precision unavailable.
- `false_positives` and `f2_if_exhaustive` are unavailable without exhaustive coverage. Mixed coverage exposes unjudged predictions and false positives on explicitly exhaustive units separately, without pooling an incomplete precision denominator.

Categories filter **both** gold and predictions. Source bounds and types are validated. No offset is reconstructed by substring search. Empty evaluation datasets are unavailable rather than perfect. File hashes, document/text identities, code identities, Python/package versions and detector environment digests identify the evaluated material. Retain the actual configuration and external configuration/data artifacts separately; hashes are not a substitute for those artifacts.

These are annotation-agreement measurements. Exhaustiveness is a caller declaration, not certified by a command-line flag. Independently reviewed labels, target alignment and protected sampling remain prerequisites for accuracy/generalization claims.

## Runner outputs

### Internal corpora

`annotation_audit_v1` accompanies legacy summaries without changing them. It counts available offset fields, declared splits and provenance evidence by label section. All current reviewed strict labels lack offsets; the legacy internal annotation protocol is not qualified for occurrence-level truth. Internal occurrence metrics and independently established accuracy are therefore explicitly unavailable. Offset-looking fields alone would not qualify a new protocol.

Provenance categories are overlapping evidence flags, not a disjoint population partition:

- Declared independent human annotations, requiring explicit author, blind-protocol identifier and blindness declaration. This remains `declared_not_verified`.
- Model-derived labels and recorded human review of model proposals.
- Detector-derived labels.
- File-level exposure to detector reconciliation, including structured reconciliation metadata even when an individual reason looks ordinary.
- Synthetic generated labels.
- Unknown or insufficient provenance.

Approval records are not proof of blind annotation. File reconciliation markers block an independence assertion conservatively; they do not reconstruct which individual edit came from which author. Historical metadata and provenance sidecars are preserved.

### TAB

`occurrence_v1` contains separate physical-split exact/overlap scores. It validates source offsets/text and partition declarations. Duplicate text across splits is disclosed. A test filename alone does not establish a protected holdout; the report always leaves holdout protection unestablished without an audited access/tuning history.

The new target is binary DIRECT/QUASI masking compared with PII finding spans. This deliberately does not equate Junas rule names with TAB entity types. Typed subgroup precision is unavailable without an approved prediction-to-label crosswalk. Subgroup positive recall uses the **same global one-to-one assignment**, avoiding crediting one prediction separately in every subgroup. Tie-dependent subtype allocation is diagnostic, not typed classifier accuracy. Annotator micro-averaging gives documents with more annotators more observation weight.

Known invalid/dropped predictions, mismatched offsets, missing annotation coverage or conflicting split declarations make the corrected measurement unavailable. Legacy outputs remain identifiable rather than quietly acquiring new semantics.

### ai4privacy

Each locale-proxy slice gets its own `occurrence_v1`, with binary PII finding-span exact/overlap assignment. Original `slice_results` retain legacy many-to-one coverage recall. A row present in both proxy slices is disclosed; the slices must not be pooled as independent national samples. The fixture does not supply a qualified protected split, so split/holdout status is unspecified/not established.

Synthetic upstream labels are not independently human-annotated truth. Annotation completeness defaults to unknown. Per-upstream-label positive recall is diagnostic; typed precision remains unavailable without a crosswalk. The input fixture and optional manifest are fingerprinted. Caller-supplied test/model factories are identified as unfingerprinted rather than certified by the bundled classifier hash.

## Offline use

Write new reports to an explicit location, for example:

```sh
uv run --frozen python scripts/evaluate_accuracy.py --external skip --output /tmp/junas-t3a/internal.json
uv run --frozen python scripts/run_tab_eval.py --splits dev --annotation-coverage unknown --output /tmp/junas-t3a/tab-dev.json
uv run --frozen python scripts/run_ai4privacy_eval.py --output /tmp/junas-t3a/ai4privacy.json
```

The external commands require already installed local fixtures. They do not download data. A non-default aggregate output also routes external reports beside that output, preserving historical report locations. No labels or locks are rewritten by measurement commands.

Use `--annotation-coverage exhaustive` only with an independently justified target-completeness protocol. It changes corrected conditional metrics only, not historical results or provenance. Unknown/partial annotation does not turn unmatched predictions into established false positives.

## Protected comparison requirements

Before claiming generalization, freeze a source-identified holdout that was not used for detector tuning, prompt design, label reconciliation or model selection. Separate train/dev/test access, deduplicate related documents/entities across partitions and retain an access history. Renaming previously exposed data does not create a holdout.

Use blinded annotators, explicit taxonomy/crosswalk and exhaustive positive/negative coverage for the target. Record source offsets, uncertain cases, annotator identities, protocol versions, review/adjudication events and immutable data hashes. Record actual provenance rather than fabricating missing review history. Keep PII, MNPI and document classification separate; MNPI labels need materiality and non-public-status reasoning, not merely suspicious financial language.

Freeze metric versions, output units, matching modes and configuration before comparisons. Report exact and overlap separately, sample sizes and uncertainty, and label-completeness limitations. Separate text, file-extraction and OCR holdouts. T3A does not acquire, relabel or certify such a holdout.
