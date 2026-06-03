"""Canonical-index-name regression tests.

These guarantee the region-prefixed naming convention does not drift
back to ad-hoc strings.
"""
from api.indices import ES, QDRANT, REGION, all_es_indices, all_qdrant_collections


def test_region_is_sg():
    assert REGION == "sg"


def test_es_indices_carry_region_prefix():
    for name in (ES.statutes, ES.glossary, ES.cases):
        assert name.startswith("junas_sg_"), f"{name} missing region prefix"


def test_qdrant_collections_carry_region_prefix():
    for name in (QDRANT.statutes, QDRANT.cases):
        assert name.startswith("junas_sg_"), f"{name} missing region prefix"


def test_all_es_indices_listing_complete():
    listed = set(all_es_indices())
    assert listed == {ES.statutes, ES.glossary, ES.cases}


def test_all_qdrant_collections_listing_complete():
    listed = set(all_qdrant_collections())
    assert listed == {QDRANT.statutes, QDRANT.cases}


def test_no_legacy_names_present():
    # Hard guard against accidental regression.
    for name in (
        ES.statutes,
        ES.glossary,
        ES.cases,
        QDRANT.statutes,
        QDRANT.cases,
    ):
        assert "lecard" not in name
        assert "rome" not in name
        # Reject unprefixed `junas_<doctype>` (i.e. missing region).
        assert name != "junas_statutes"
        assert name != "junas_glossary"
        assert name != "junas_cases"
