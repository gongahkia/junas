# Legal-contract fixture corpus

Hand-labelled synthetic SG legal documents used by the recall gate (`scripts/recall_gate.py`)
and by `test/test_legal_corpus_recall.py`.

## Layout

- `<doc_id>.txt` — synthetic document text.
- `<doc_id>.labels.json` — `must_detect` (rule + matched_text) and `must_not_detect` (matched_text + reason) labels.
- `recall.lock.json` — locked per-rule recall baseline. Regressions fail the gate.

## Labels

`must_detect` entries are matched by `(rule, matched_text)` tuple. Recall is
`true_positives / total_must_detect` per rule. `must_not_detect` entries fail the gate
if any finding's matched_text contains or equals the forbidden text.

## Updating

After a deliberate accuracy improvement, regenerate the baseline:

```sh
python3 scripts/recall_gate.py --update
```

CI invokes `scripts/recall_gate.py` (no flag) and fails on per-rule regression.
