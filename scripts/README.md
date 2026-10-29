# Evaluation and corpus tools

Start with `uv run python scripts/evaluate_accuracy.py`. It writes a source/corpus-fingerprinted report and executes the existing locks without updating them.

- `recall_gate.py`: per-rule regression checks.
- `evaluate_candidate_corpus.py`: detailed matched, missed, unexpected and ideal-label results.
- `run_tab_eval.py`, `run_ai4privacy_eval.py`, `run_singling_out_pack_eval.py`: external breadth checks.
- `fetch_tab_fixture.sh`, `fetch_ai4privacy_fixture.py`: explicit external dataset acquisition.
- `run_layer_attribution_eval.py`, `bucket_candidate_misses.py`, `miss_concentration.py`: gap analysis.
- `candidate_review.py`, `review_candidate_fixture.py`, `check_candidate_stage_gate.py`, `promote_candidate_fixtures.py`: label review and promotion.
- `check_fixture_scrub.py`, `check_mnpi_conjunctive_provenance.py`: fixture/privacy and provenance checks.
- `generate_accuracy_doc.py`, `generate_defensibility_reports.py`: generated research documentation.

Generation and autolabelling scripts create candidates, not independent ground truth. Run each tool with `--help` before changing corpus labels. Never lower a lock simply to pass a test.
