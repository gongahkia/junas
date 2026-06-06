# sglb-tools

`sglb-tools` is the reusable utility package extracted from SG-LegalBench. It
contains only stable, dependency-light APIs that Singapore legal-tech engineers
can use without installing the full Junas backend.

## Install

From this monorepo:

```sh
cd packages/sglb-tools
python -m pip install -e .
```

From PyPI, after release:

```sh
python -m pip install sglb-tools
```

## Citation grammar

```python
from sglb_tools.citation import validate_citation

result = validate_citation("[2023] SGCA 5")
assert result.valid
assert result.kind == "neutral_case"
```

The citation module also exposes the sequence formatter used by the main repo:

```python
from sglb_tools.citation import CaseFootnote, compute_citation_outputs

notes = [
    CaseFootnote(
        case_name="Tan Kim Seng v Victor Adam Ibrahim",
        year="2003",
        court="SGCA",
        case_no="49",
        para_start="10",
        para_end="12",
    )
]
print(compute_citation_outputs(notes)[0].text)
```

## Normalisation

```python
from sglb_tools.normalisation import normalise_section_citation

assert normalise_section_citation("Sec. 13 of the PDPA") == (
    "s 13 of the personal data protection act 2012"
)
```

Normalisers are mechanical comparison helpers. They do not decide whether a
case exists, whether a statutory provision is current, or whether a legal
answer is correct.

## Adapter base

```python
from datetime import date

from sglb_tools.adapters import AdapterTier, SourceDocument, SourceMetadata

metadata = SourceMetadata(
    source_id="example",
    display_name="Example Public Source",
    base_url="https://example.sg",
    tier=AdapterTier.PUBLIC,
    licence_summary="Public source; confirm attribution requirements before redistribution.",
)

doc = SourceDocument(
    document_id="example-1",
    source_url="https://example.sg/example-1",
    title="Example",
    body="...",
    published_date=None,
    fetched_date=date.today(),
    source_metadata=metadata,
    doc_type="case",
)
print(doc.provenance)
```

## Development

```sh
cd packages/sglb-tools
python -m pip install -e .
python -m pytest
```

The package is MIT-licensed, matching the main repository code licence.
