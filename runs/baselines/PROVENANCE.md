# Baseline Receipt Provenance Audit

Audit date: 2026-06-05

Scope: GAP-03 closure audit for commit messages claiming Anthropic and Gemini
baselines across SGLB-01, SGLB-02, and SGLB-04.

## Claims Checked

- `9beb0867257d2c552fe5fc7053313242db8bd7f1`:
  `feat(baselines): Anthropic baselines across SGLB-01/02/04 (advances #36)`
- `414bb4bb7ad46ef77ee41c34f958adc0e134831a`:
  `feat(baselines): Gemini baselines across SGLB-01/02/04 (advances #36)`

## What The Commits Added

- `git show 9beb086 --stat` shows only
  `backend/benchmark/scripts/run_baselines_anthropic.py` added.
- `git show 414bb4b --stat` shows only
  `backend/benchmark/scripts/run_baselines_gemini.py` added.
- Neither commit added any `runs/baselines/<provider>/<task>/*.json` receipt.
- The added runners intended to write:
  - `runs/baselines/anthropic/sglb_01.json`
  - `runs/baselines/anthropic/sglb_02.json`
  - `runs/baselines/anthropic/sglb_04.json`
  - `runs/baselines/gemini/sglb_01.json`
  - `runs/baselines/gemini/sglb_02.json`
  - `runs/baselines/gemini/sglb_04.json`

## Recovery Search

Searches performed:

- Current disk search under `runs/baselines/`, including ignored files.
- Filename search for `anthropic`, `gemini`, `claude`, and `google` JSON files
  under the repository and registered worktree area.
- JSON content search for Anthropic/Gemini provider labels.
- Git object search via `git rev-list --all --objects -- runs/baselines`.
- Git reflog search via `git rev-list --reflog --objects -- runs/baselines`.
- Stash search; no stashes exist.
- Unreachable commit search via `git fsck --no-reflogs --unreachable`.
- Unreachable blob content search for Anthropic/Gemini provider labels.

Result:

- No Anthropic receipt JSON was found on disk, in tracked history, in reflog
  history, in stashes, or in unreachable objects.
- No Gemini receipt JSON was found on disk, in tracked history, in reflog
  history, in stashes, or in unreachable objects.
- Ignored Azure receipts and tracked Ollama receipts exist, but they are outside
  this GAP-03 claim and are not substitutes for Anthropic/Gemini receipts.
- No receipt JSON was recovered or created during this audit.

## Provider Task Status

| Provider | Task | Status |
|---|---|---|
| anthropic | sglb_01 | receipt-missing-rerun-via-BATCH-D |
| anthropic | sglb_02 | receipt-missing-rerun-via-BATCH-D |
| anthropic | sglb_04 | receipt-missing-rerun-via-BATCH-D |
| gemini | sglb_01 | receipt-missing-rerun-via-BATCH-D |
| gemini | sglb_02 | receipt-missing-rerun-via-BATCH-D |
| gemini | sglb_04 | receipt-missing-rerun-via-BATCH-D |

## NEW-BATCH-D Queue

Rerun required; see NEW-BATCH-D.

Queue these missing receipts for NEW-BATCH-D:

- Anthropic x SGLB-01
- Anthropic x SGLB-02
- Anthropic x SGLB-04
- Gemini x SGLB-01
- Gemini x SGLB-02
- Gemini x SGLB-04
