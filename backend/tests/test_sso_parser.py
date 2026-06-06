"""SSO parser + ingestion tests using the PDPA 2012 fixture."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.services.statute_lookup import (
    load_sso_jsonl,
    resolve_citation_offline,
)
from data.ingestion.sso import parse_html_file, write_jsonl
from data.parsers.sso_parser import parse_sso_html, parse_toc

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sso"
TOC_HTML = FIXTURE_DIR / "pdpa_toc.html"
FULL_HTML = FIXTURE_DIR / "pdpa_full.html"


@pytest.fixture(scope="module")
def parsed_act():
    toc = TOC_HTML.read_text(encoding="utf-8")
    body = FULL_HTML.read_text(encoding="utf-8")
    return parse_sso_html(
        body,
        "PDPA2012",
        "https://sso.agc.gov.sg/Act/PDPA2012?WholeDoc=1",
        toc_html=toc,
    )


def test_parse_toc_yields_section_to_part_map() -> None:
    toc = TOC_HTML.read_text(encoding="utf-8")
    section_to_part, section_to_division, ordered = parse_toc(toc)
    assert len(ordered) >= 90  # PDPA has ~95 sections
    assert section_to_part["pr1-"].lower().startswith("part 1")
    assert section_to_part["pr13-"].lower().startswith("part 4")


def test_parse_full_act_extracts_metadata(parsed_act) -> None:
    assert parsed_act.act_title.startswith("Personal Data Protection Act")
    assert parsed_act.edition == 2020
    assert parsed_act.kind == "act"
    assert parsed_act.version_id == "PDPA2012@2020"
    assert parsed_act.valid_start_date == "2021-12-31"


def test_parse_full_act_yields_all_sections_including_repealed(parsed_act) -> None:
    nums = {s.number for s in parsed_act.sections}
    # active sections in every part
    assert "1" in nums and "13" in nums and "26A" in nums and "68" in nums
    # repealed Part 7/8 sections must still be present
    assert "27" in nums and "30" in nums


def test_section_has_part_and_division_metadata(parsed_act) -> None:
    s13 = next(s for s in parsed_act.sections if s.number == "13")
    assert s13.part.lower().startswith("part 4")
    assert s13.name == "Consent required"
    assert s13.chapter_number == "PDPA2012"
    assert s13.text_plain.startswith("13.")


def test_repealed_section_has_amendment_label(parsed_act) -> None:
    s27 = next(s for s in parsed_act.sections if s.number == "27")
    assert s27.name == "[Repealed]"
    assert "repealed" in s27.text_plain.lower()


def test_parse_html_file_helper_round_trip(tmp_path) -> None:
    act = parse_html_file(FULL_HTML, "PDPA2012")
    # without toc, part/division will be empty but sections still extract
    assert len(act.sections) >= 80
    assert act.sections[0].number == "1"


def test_write_jsonl_is_idempotent(parsed_act, tmp_path) -> None:
    out = tmp_path / "sso.jsonl"
    n1 = write_jsonl([parsed_act], out)
    n2 = write_jsonl([parsed_act], out, append=True)
    assert n1 == len(parsed_act.sections)
    assert n2 == 0  # nothing new on the second pass


def test_jsonl_row_carries_required_fields(parsed_act, tmp_path) -> None:
    out = tmp_path / "sso.jsonl"
    write_jsonl([parsed_act], out)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    s13_row = next(r for r in rows if r["number"] == "13" and r["chapter_number"] == "PDPA2012")
    for field in (
        "number", "name", "chapter_number", "act_title", "part", "edition",
        "kind", "text_html", "text_plain", "source_url", "version_id",
        "valid_start_date", "section_id", "legis_id", "sort_date",
        "extraction_rule_sha",
    ):
        assert field in s13_row, f"missing {field}"
    assert s13_row["section_id"] == "PDPA2012@2020:13"
    assert s13_row["legis_id"] == "PDPA2012:13"
    assert s13_row["sort_date"] == "2021-12-31"
    assert len(s13_row["extraction_rule_sha"]) == 7
    assert "Personal Data Protection Act" in s13_row["act_title"]


def test_statute_lookup_resolves_citation_against_jsonl(parsed_act, tmp_path) -> None:
    """End-to-end: ingest -> write JSONL -> resolve a citation."""
    out = tmp_path / "sso.jsonl"
    write_jsonl([parsed_act], out)
    rows = load_sso_jsonl(out)
    assert len(rows) >= 90

    # SAL-style "s 13 PDPA" must resolve to PDPA2012 s 13.
    row = resolve_citation_offline("s 13 of the Personal Data Protection Act 2012", rows)
    assert row is not None
    assert row["number"] == "13"
    assert row["chapter_number"] == "PDPA2012"
    assert row["name"] == "Consent required"

    # short form also resolves
    row2 = resolve_citation_offline("section 13 PDPA", rows)
    assert row2 is not None and row2["number"] == "13"

    # unknown act → None
    assert resolve_citation_offline("s 13 of the Mythical Act 2099", rows) is None
