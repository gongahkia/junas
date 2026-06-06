from sglb_tools.citation import (
    CaseFootnote,
    TextFootnote,
    compute_citation_outputs,
    parse_elitigation_url,
    validate_citation,
)


def test_consumer_import_validate_citation():
    result = validate_citation("[2023] SGCA 5")
    assert result.valid is True
    assert result.kind == "neutral_case"


def test_parse_elitigation_url_extracts_fields():
    parsed = parse_elitigation_url("https://www.elitigation.sg/gd/s/2023_SGCA_005")
    assert parsed is not None
    assert parsed.year == "2023"
    assert parsed.court == "SGCA"
    assert parsed.case_no == "5"


def test_citation_sequence_short_forms():
    first = CaseFootnote(case_name="Case A", year="2023", court="SGHC", case_no="9", para_start="12")
    second = CaseFootnote(case_name="Case A", year="2023", court="SGHC", case_no="9", para_start="14")
    text = TextFootnote(text="Some statute reference...")
    third = CaseFootnote(
        case_name="Case A",
        short_name="Case A",
        year="2023",
        court="SGHC",
        case_no="9",
        para_start="20",
    )

    output = compute_citation_outputs([first, second, text, third])

    assert output[0].text == "Case A [2023] SGHC 9 at [12]."
    assert output[1].text == "Id, at [14]."
    assert output[2].text == "Some statute reference."
    assert output[3].text == "Case A, supra n 1, at [20]."


def test_validate_sal_forms_and_rejects_unknown():
    assert validate_citation("[2009] 2 SLR(R) 332").kind == "slr_r_case"
    assert validate_citation("Penal Code (Cap. 224, 2008 Rev Ed)").kind == "statute_cap"
    assert validate_citation("s 9 of the Penal Code Act").kind == "statute_section"
    assert validate_citation("definitely not a citation").valid is False
