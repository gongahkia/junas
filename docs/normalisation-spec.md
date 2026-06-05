# Citation and Statute Normalisation Spec

This document defines the canonical strings used by SG-LegalBench citation
and statute normalisers. It is for vendors who want to audit exact-match
scores without reading the implementation.

The executable corpus is
`backend/tests/fixtures/normalisation/corpus.yaml`; the contract test is
`backend/tests/test_normalisation_spec.py`.

## Scope

The spec covers four kinds:

1. Section citations used by SGLB-02 citation exact match.
2. Statute short names and long-form statute titles used when section
   citations name a statute.
3. Singapore neutral case citations.
4. Singapore Law Reports citations: SLR and SLR(R).

The normalisers are mechanical string rules. They do not decide whether a
case exists, whether a statutory provision is current, or whether a legal
answer is correct.

## Section Citations

Accepted input forms include:

- `s 13`
- `section 13`
- `s. 13`
- `Sec. 13 of the PDPA`
- `Section 13 of the Personal Data Protection Act 2012`

Canonical form:

```text
s <section> of the <canonical statute long name>
```

For example:

```text
s 13 of the personal data protection act 2012
```

Rules:

- Prefixes `s`, `s.`, `section`, `Section`, `sec`, and `Sec.` canonicalise
  to `s`.
- Section numbers may include an alpha suffix or bracketed subsections, e.g.
  `26A`, `13(1)`.
- Output is lowercase.
- Terminal full stops are removed.
- `Act, 2012` is treated as `Act 2012`.
- Known statute aliases are expanded to the canonical long-form title.
- If a section citation names an unknown statute, it does not normalise.
- Bare section references are resolved against the SGLB-02 v0.1 statute
  context. That context is PDPA, so `s 13` canonicalises to
  `s 13 of the personal data protection act 2012`.

Rationale: models should not lose exact-match credit for harmless style
variants, but the comparison string should make the statute identity explicit.

## Statute Short Names

Canonical statute identity is the lowercase long-form title. The supported
short names and aliases are:

| Short name | Accepted aliases | Canonical long form |
| --- | --- | --- |
| `PDPA` | `PDPA`, `PDPA2012`, `Personal Data Protection Act`, `Personal Data Protection Act 2012` | `personal data protection act 2012` |
| `EmA` | `EmA`, `EmA1968`, `Employment Act`, `Employment Act 1968` | `employment act 1968` |
| `PC` | `PC`, `PC1871`, `Penal Code`, `Penal Code 1871` | `penal code 1871` |
| `ROC2021` | `ROC2021`, `Rules of Court`, `Rules of Court 2021` | `rules of court 2021` |

Precedence rules:

- Strip case, punctuation, extra whitespace, and a leading `the` before
  matching.
- Year-bearing aliases map to the statute with that year.
- Unyear-labeled long forms map only when the corpus table makes them
  unambiguous.
- Unknown names do not normalise; add them to the corpus and implementation
  together in a PR.

## Neutral Case Citations

Canonical form:

```text
[YYYY] <COURT> <case_no>
```

Example:

```text
[2023] SGCA 5
```

Rules:

- `YYYY` must be in the implemented range `1965` to `2100`, inclusive.
- `<COURT>` must be one of:
  `SGCA`, `SGHC`, `SGHCR`, `SGDC`, `SGMC`, `SGFC`, `SGCFI`, `SGIA`,
  `SGHCF`, `SGSAC`.
- `<case_no>` must be a positive integer.
- Canonical case numbers do not include leading zeroes.
- eLitigation URL/path fragments containing `YYYY_COURT_NNN` normalise to
  the same canonical form, e.g. `2023_SGCA_005` to `[2023] SGCA 5`.

The validator checks grammar only. A syntactically valid citation may still
refer to no real judgment.

## SLR and SLR(R) Citations

Canonical forms:

```text
[YYYY] <volume> SLR <page>
[YYYY] <volume> SLR(R) <page>
```

Examples:

```text
[2015] 1 SLR 1116
[2009] 2 SLR(R) 332
```

Rules:

- `YYYY` uses the same implemented range as neutral citations: `1965` to
  `2100`, inclusive.
- Volume and page must be positive integers.
- Canonical volume and page numbers do not include leading zeroes.
- A terminal full stop is tolerated in footnote text but is not part of the
  canonical form.
- `SLR` and `SLR(R)` are distinct reporters.
- Forms such as `SLRR`, zero volume/page, missing volume, or out-of-range
  years do not normalise.

## Test Corpus

The corpus lives at:

```text
backend/tests/fixtures/normalisation/corpus.yaml
```

Each kind has:

- `positive`: raw/canonical pairs.
- `negative`: raw forms that must not normalise.

Every kind must have at least 10 positive pairs and 3 negative cases. Run:

```sh
cd backend
../.venv/bin/python -m pytest tests/test_normalisation_spec.py -q
```

To add coverage in a PR:

1. Add the new row under the right kind in `corpus.yaml`.
2. If the row is a positive case, include `raw_form` and `canonical_form`.
3. If the row should be rejected, add only `raw_form` under `negative`.
4. Run the contract test above.
5. If the corpus reveals implementation divergence, update the normaliser in
   the same PR and mention the divergence in the PR description.
