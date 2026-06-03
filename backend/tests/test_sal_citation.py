"""SAL citation engine tests. Ports the upstream JS test suite + adds grammar."""
from api.services.sal_citation import (
    CaseFootnote,
    TextFootnote,
    compute_citation_outputs,
    parse_elitigation_url,
    validate_citation,
)


# === Ported from kevanwee/sal-citation-generator tests/citationEngine.test.js ===


def test_parse_elitigation_url_extracts_fields():
    parsed = parse_elitigation_url("https://www.elitigation.sg/gd/s/2023_SGCA_5")
    assert parsed is not None
    assert parsed.year == "2023"
    assert parsed.court == "SGCA"
    assert parsed.case_no == "5"


def test_parse_elitigation_url_returns_none_on_invalid():
    assert parse_elitigation_url("https://example.com/not-a-case") is None


def test_first_case_full_citation_with_pinpoint_range():
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
    out = compute_citation_outputs(notes)[0]
    assert out.text == "Tan Kim Seng v Victor Adam Ibrahim [2003] SGCA 49 at [10]-[12]."


def test_ibid_consecutive_same_case_same_pinpoint():
    n = CaseFootnote(case_name="Case A", year="2023", court="SGHC", case_no="9", para_start="12")
    out = compute_citation_outputs([n, n])
    assert out[1].text == "Ibid."


def test_id_consecutive_same_case_different_pinpoint():
    n1 = CaseFootnote(case_name="Case A", year="2023", court="SGHC", case_no="9", para_start="12")
    n2 = CaseFootnote(case_name="Case A", year="2023", court="SGHC", case_no="9", para_start="14")
    out = compute_citation_outputs([n1, n2])
    assert out[1].text == "Id, at [14]."


def test_supra_non_consecutive_reference():
    n1 = CaseFootnote(
        case_name="Case A", short_name="Case A", year="2023", court="SGCA", case_no="5", para_start="1"
    )
    text = TextFootnote(text="Some statute reference")
    n2 = CaseFootnote(
        case_name="Case A", short_name="Case A", year="2023", court="SGCA", case_no="5", para_start="9"
    )
    out = compute_citation_outputs([n1, text, n2])
    assert out[2].text == "Case A, supra n 1, at [9]."


def test_text_citation_trailing_period_normalisation():
    out = compute_citation_outputs([TextFootnote(text="See s 9 of the Penal Code...")])
    assert out[0].text == "See s 9 of the Penal Code."


# === New: HTML output preserves italics for case name, Ibid, Id, supra ===


def test_html_italic_wrapping_for_case_name():
    notes = [CaseFootnote(case_name="Case X", year="2024", court="SGHC", case_no="1")]
    out = compute_citation_outputs(notes)[0]
    assert "<span class=\"italic\">Case X</span>" in out.html


def test_html_ibid_is_italic():
    n = CaseFootnote(case_name="Case A", year="2023", court="SGHC", case_no="9", para_start="12")
    out = compute_citation_outputs([n, n])
    assert "<span class=\"italic\">Ibid</span>" in out[1].html


# === SLR / report-citation preference over neutral ===


def test_report_citation_takes_precedence_over_neutral():
    n = CaseFootnote(
        case_name="Gay Choon Ing v Loh Sze Ti Terence Peter",
        report_citation="[2009] 2 SLR(R) 332",
        year="2008",
        court="SGCA",
        case_no="50",
        para_start="64",
    )
    out = compute_citation_outputs([n])[0]
    assert "[2009] 2 SLR(R) 332" in out.text
    assert "SGCA 50" not in out.text


def test_short_form_groups_by_report_citation_not_neutral():
    n1 = CaseFootnote(
        case_name="Gay Choon Ing",
        short_name="Gay Choon Ing",
        report_citation="[2009] 2 SLR(R) 332",
        year="2008",
        court="SGCA",
        case_no="50",
        para_start="64",
    )
    text = TextFootnote(text="Intervening text")
    # Same case but only neutral provided — should still resolve via name fallback,
    # confirming the identity hierarchy: report > neutral > name.
    n2_neutral = CaseFootnote(
        case_name="Gay Choon Ing",
        short_name="Gay Choon Ing",
        year="2008",
        court="SGCA",
        case_no="50",
        para_start="80",
    )
    out = compute_citation_outputs([n1, text, n2_neutral])
    # n1 uses report identity; n2_neutral uses neutral identity — different keys.
    # n2 should therefore re-emit a full citation, not supra. This is documented
    # behaviour: identity comparison is conservative.
    assert "supra" not in out[2].text


# === SGLB-04 scorer: validate_citation ===


def test_validate_neutral_case_citation_well_formed():
    r = validate_citation("[2023] SGCA 5")
    assert r.valid is True
    assert r.kind == "neutral_case"
    assert r.errors == ()


def test_validate_neutral_case_rejects_unknown_court_code():
    r = validate_citation("[2023] SGZZ 5")
    assert r.valid is False
    assert r.kind == "neutral_case"
    assert any(e.code == "unknown_court" for e in r.errors)


def test_validate_neutral_case_rejects_year_out_of_range():
    r = validate_citation("[1800] SGCA 5")
    assert r.valid is False
    assert any(e.code == "year_out_of_range" for e in r.errors)


def test_validate_slr_r_form():
    r = validate_citation("[2009] 2 SLR(R) 332")
    assert r.valid is True
    assert r.kind == "slr_r_case"


def test_validate_slr_plain_form():
    r = validate_citation("[2015] 1 SLR 1116")
    assert r.valid is True
    assert r.kind == "slr_case"


def test_validate_statute_with_cap():
    r = validate_citation("Penal Code (Cap. 224, 2008 Rev Ed)")
    assert r.valid is True
    assert r.kind == "statute_cap"


def test_validate_statute_with_cap_no_rev_ed():
    r = validate_citation("Misuse of Drugs Act (Cap. 185)")
    assert r.valid is True
    assert r.kind == "statute_cap"


def test_validate_statute_section_short_form():
    r = validate_citation("s 9 of the Penal Code Act")
    assert r.valid is True
    assert r.kind == "statute_section"


def test_validate_pinpoint_alone():
    r = validate_citation("at [10]-[12]")
    assert r.valid is True
    assert r.kind == "pinpoint"


def test_validate_ibid_short_form():
    r = validate_citation("Ibid")
    assert r.valid is True
    assert r.kind == "ibid"


def test_validate_id_with_pinpoint():
    r = validate_citation("Id, at [14]")
    assert r.valid is True
    assert r.kind == "id_with_pinpoint"


def test_validate_supra_with_pinpoint():
    r = validate_citation("Gay Choon Ing, supra n 1, at [64]")
    assert r.valid is True
    assert r.kind == "supra"


def test_validate_rejects_unparseable_string():
    r = validate_citation("definitely not a citation")
    assert r.valid is False
    assert r.kind == "unknown"
    assert any(e.code == "no_grammar_match" for e in r.errors)


def test_validate_strips_trailing_period():
    r = validate_citation("[2023] SGCA 5.")
    assert r.valid is True
    assert r.kind == "neutral_case"


def test_validate_empty_string():
    r = validate_citation("   ")
    assert r.valid is False
    assert any(e.code == "empty" for e in r.errors)
