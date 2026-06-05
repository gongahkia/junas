# Reference PDFs (not in repo)

This directory holds upstream style guides and reference documents used as the source for SG-LegalBench's mechanical extraction (chiefly the SAL citation grammar tests under `backend/tests/test_sal_citation_published_examples.py`).

The PDFs themselves are **not** committed. They are copyrighted publications and redistribution may not be permitted. Download them yourself; gitignore is set to skip `*.pdf` files in this directory.

## Required files

| Filename | Source | Used by |
|---|---|---|
| `SAL_Style_Guide_Quick_Reference_2007_Ed.pdf` | Singapore Academy of Law — Style Guide Quick Reference (2007 Ed.). Available via `sal.org.sg`. | `NEW-SAL-VALIDATION` test fixture extraction (closes GAP-05). |
| `SLR_Style_Guide_2021.pdf` | Singapore Law Reports — Style Guide (2021). Available via `sal.org.sg` / SAL Press. | Same as above. |

## Optional files (used during grammar extension, not required for tests)

| Filename | Source | Notes |
|---|---|---|
| `FinalOnlinePDF-2012Reprint.pdf` | SLR consolidated reprint reference. | Used as cross-check for older bill-form and Cap-less revised-legislation patterns added to the grammar. |
| `silo.tips_aall-universal-citation-guide-version-21.pdf` | AALL Universal Citation Guide (v2.1) mirror. | Used for cross-jurisdiction (US/UK/EU) citation patterns referenced in the grammar's source-specific ordering. |

## Why these aren't in the repo

1. **Licensing.** SAL and SLR style guides are SAL Press publications; redistribution without permission may breach copyright.
2. **Reproducibility is preserved.** The extracted worked-citation examples live in `backend/tests/fixtures/sal_style_guide/examples.yaml` (committed). The test suite validates the SAL citation grammar against those examples, so contributors who only want to run the tests do not need the PDFs.

## Verification path for contributors

If you change the SAL citation grammar in `backend/api/services/sal_citation.py`:

1. Download the two required PDFs into this directory.
2. Re-run the grammar against the fixture: `pytest backend/tests/test_sal_citation_published_examples.py -q`.
3. If you need to add new examples from the guides, extract them into `examples.yaml` with the existing schema (`example_text`, `expected_kind`, `expected_components`, `source_section_in_guide`). Cite page + section.

## Disputes

If a worked example was extracted incorrectly or the guide has been updated, file a label dispute per `docs/dispute-process.md` (lands separately via `NEW-DISPUTE-PROCESS`).
