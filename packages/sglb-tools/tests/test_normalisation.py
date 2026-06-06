import pytest

from sglb_tools.normalisation import normalise_section_citation, normalise_statute_name


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("PDPA", "personal data protection act 2012"),
        ("Personal Data Protection Act 2012", "personal data protection act 2012"),
        ("Employment Act", "employment act 1968"),
        ("Penal Code 1871", "penal code 1871"),
        ("Rules of Court 2021", "rules of court 2021"),
    ],
)
def test_normalise_statute_name(raw: str, canonical: str):
    assert normalise_statute_name(raw) == canonical


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("s 13", "s 13 of the personal data protection act 2012"),
        ("section 13", "s 13 of the personal data protection act 2012"),
        ("Sec. 13 of the PDPA", "s 13 of the personal data protection act 2012"),
        (
            "Section 13 of the Personal Data Protection Act, 2012.",
            "s 13 of the personal data protection act 2012",
        ),
        ("s. 26A of the PDPA", "s 26a of the personal data protection act 2012"),
        ("s 13(1) of the Personal Data Protection Act", "s 13(1) of the personal data protection act 2012"),
    ],
)
def test_normalise_section_citation(raw: str, canonical: str):
    assert normalise_section_citation(raw) == canonical


def test_unknown_statute_or_non_citation_does_not_normalise():
    assert normalise_statute_name("Unknown Act 1900") == ""
    assert normalise_section_citation("s 1 of the Unknown Act 1900") == ""
    assert normalise_section_citation("not a section") == ""
