from collections import Counter
from pathlib import Path

import yaml

from api.services.sal_citation import validate_citation


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sal_style_guide" / "examples.yaml"


def _examples() -> list[dict[str, object]]:
    payload = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    return list(payload["examples"])


def test_published_style_guide_fixture_has_required_coverage():
    examples = _examples()
    counts = Counter(str(row["source_guide"]) for row in examples)
    assert counts["SAL_Style_Guide_Quick_Reference_2007_Ed.pdf"] >= 30
    assert counts["SLR_Style_Guide_2021.pdf"] >= 30
    for row in examples:
        assert row["example_text"]
        assert row["expected_kind"]
        assert isinstance(row["expected_components"], dict)
        assert row["source_section_in_guide"]


def test_published_style_guide_examples_validate_against_sal_grammar():
    for row in _examples():
        result = validate_citation(str(row["example_text"]))
        assert result.valid is True, row
        assert result.kind == row["expected_kind"], row
        for key, value in dict(row["expected_components"]).items():
            assert result.components.get(key) == str(value), row
