"""Canonical-index-name regression tests.

These guarantee the region-prefixed naming convention does not drift
back to ad-hoc strings.
"""
import pytest

from api.indices import (
    ES,
    LEGIS_ID_COLLAPSE,
    LEGIS_ID_FIELD,
    LEGAL_SEARCH_SORT,
    QDRANT,
    REGION,
    SORT_DATE_FIELD,
    PaginationCursor,
    all_es_indices,
    all_qdrant_collections,
)


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


def test_legal_search_sort_uses_a_stable_search_after_key():
    assert LEGAL_SEARCH_SORT == [
        {SORT_DATE_FIELD: {"order": "desc", "missing": "_last", "unmapped_type": "date"}},
        {LEGIS_ID_FIELD: {"order": "asc", "missing": "_last", "unmapped_type": "keyword"}},
    ]
    assert LEGIS_ID_COLLAPSE == {"field": LEGIS_ID_FIELD}


def test_pagination_cursor_round_trips_search_after_values():
    cursor = PaginationCursor(sort_values=["2026-06-01", "PDPA2012:13"])
    token = cursor.to_token()
    assert PaginationCursor.from_token(token) == cursor


def test_pagination_cursor_rejects_invalid_tokens():
    with pytest.raises(ValueError):
        PaginationCursor.from_token("not-json")
