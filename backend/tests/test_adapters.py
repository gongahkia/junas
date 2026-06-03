"""Adapter architecture invariants — most important: benchmark gating."""
from datetime import date

import pytest

from api.adapters import (
    BENCHMARK_ALLOWED_TIERS,
    AdapterTier,
    DocType,
    LegalSourceAdapter,
    SourceDocument,
    SourceMetadata,
    benchmark_safe_adapters,
    derive_legis_id,
    normalise_date,
)
from api.adapters.public import (
    AustliiSgAdapter,
    CommonliiSgAdapter,
    ElitigationAdapter,
    HansardAdapter,
    IrasAdapter,
    MomAdapter,
    PdpcAdapter,
    PdpcGuidanceAdapter,
    SsoAdapter,
)
from api.adapters.user_credentialed import (
    LawnetAdapter,
    LexisNexisSgAdapter,
    PracticalLawSgAdapter,
)


def test_only_public_tier_is_benchmark_allowed():
    assert BENCHMARK_ALLOWED_TIERS == frozenset({AdapterTier.PUBLIC})


def test_all_public_adapters_have_public_tier():
    public_classes = [
        AustliiSgAdapter,
        CommonliiSgAdapter,
        ElitigationAdapter,
        HansardAdapter,
        IrasAdapter,
        MomAdapter,
        PdpcAdapter,
        PdpcGuidanceAdapter,
        SsoAdapter,
    ]
    for cls in public_classes:
        assert cls.metadata.tier == AdapterTier.PUBLIC, f"{cls.__name__} is not PUBLIC"


def test_all_user_credentialed_adapters_have_credentialed_tier():
    credentialed_classes = [LawnetAdapter, PracticalLawSgAdapter, LexisNexisSgAdapter]
    for cls in credentialed_classes:
        assert cls.metadata.tier == AdapterTier.USER_CREDENTIALED, (
            f"{cls.__name__} is not USER_CREDENTIALED"
        )


def test_user_credentialed_adapters_are_never_benchmark_eligible():
    for cls in [LawnetAdapter, PracticalLawSgAdapter, LexisNexisSgAdapter]:
        assert cls.metadata.benchmark_eligible is False, (
            f"{cls.__name__} must not be benchmark-eligible"
        )


def test_benchmark_safe_filter_excludes_credentialed():
    mixed = [SsoAdapter(), LawnetAdapter(), PdpcAdapter()]
    safe = benchmark_safe_adapters(mixed)
    assert LawnetAdapter() not in safe
    assert {type(a) for a in safe} == {SsoAdapter, PdpcAdapter}


def test_benchmark_safe_filter_respects_benchmark_eligible_flag():
    # ElitigationAdapter is PUBLIC tier but benchmark_eligible=False until #34.
    mixed = [SsoAdapter(), ElitigationAdapter(), PdpcAdapter()]
    safe = benchmark_safe_adapters(mixed)
    assert ElitigationAdapter not in {type(a) for a in safe}
    assert {type(a) for a in safe} == {SsoAdapter, PdpcAdapter}


def test_iras_and_hansard_excluded_pending_v0_3():
    mixed = [IrasAdapter(), HansardAdapter(), PdpcAdapter()]
    safe = benchmark_safe_adapters(mixed)
    assert {type(a) for a in safe} == {PdpcAdapter}


def test_provenance_record_includes_all_required_fields():
    md = SsoAdapter.metadata
    doc = SourceDocument(
        document_id="penal-code/s-9",
        source_url="https://sso.agc.gov.sg/Act/PC1871#pr9-",
        title="Penal Code s.9",
        body="...",
        published_date=date(2008, 12, 31),
        fetched_date=date(2026, 6, 3),
        source_metadata=md,
        doc_type=DocType.LEGISLATION.value,
    )
    p = doc.provenance
    assert p["source_id"] == "sso"
    assert p["source_url"].startswith("https://sso.agc.gov.sg")
    assert p["document_id"] == "penal-code/s-9"
    assert p["published_date"] == "2008-12-31"
    assert p["fetched_date"] == "2026-06-03"
    assert p["sort_date"] == "2008-12-31"
    assert p["year"] == 2008
    assert p["country"] == "SG"
    assert p["doc_type"] == "legislation"
    assert p["legis_id"]  # derived; never empty
    assert p["tier"] == "public"
    assert "Singapore legislation" in p["licence_summary"]


def test_legis_id_derived_when_blank():
    doc = SourceDocument(
        document_id="",
        source_url="https://www.pdpc.gov.sg/enforcement/abc",
        title="Some PDPC enforcement against XYZ Pte Ltd",
        body="",
        published_date=None,
        fetched_date=date(2026, 6, 3),
        source_metadata=PdpcAdapter.metadata,
        doc_type=DocType.ENFORCEMENT_DECISION.value,
    )
    assert doc.legis_id.startswith("sg-enforcement_decision-")


def test_legis_id_uses_raw_identifier_when_present():
    doc = SourceDocument(
        document_id="pdpa-decision-2024-04-29",
        source_url="https://www.pdpc.gov.sg/x",
        title="",
        body="",
        published_date=None,
        fetched_date=date(2026, 6, 3),
        source_metadata=PdpcAdapter.metadata,
        doc_type=DocType.ENFORCEMENT_DECISION.value,
    )
    assert doc.legis_id == "pdpa-decision-2024-04-29"


def test_derive_legis_id_unknown_marker_treated_as_blank():
    assert derive_legis_id(
        country="SG",
        doc_type="case",
        raw_identifier="unknown-doc",
        title="Quoth v Raven",
    ).startswith("sg-case-")


def test_derive_legis_id_hashes_when_no_signal():
    out = derive_legis_id(country="SG", doc_type="case", extra={"x": 1})
    assert out.startswith("sg-case-")
    assert len(out) > len("sg-case-")


def test_normalise_date_handles_iso():
    assert normalise_date("2026-06-03") == date(2026, 6, 3)


def test_normalise_date_handles_common_sg_format():
    assert normalise_date("3 Jun 2026") == date(2026, 6, 3)


def test_normalise_date_handles_unix_seconds():
    assert normalise_date(1_717_372_800) == date(2024, 6, 3)


def test_normalise_date_handles_unix_milliseconds():
    # Same instant in ms
    assert normalise_date(1_717_372_800_000) == date(2024, 6, 3)


def test_normalise_date_returns_none_on_garbage():
    assert normalise_date("never") is None
    assert normalise_date(None) is None


def test_sort_date_falls_back_to_fetched_when_published_missing():
    doc = SourceDocument(
        document_id="x",
        source_url="https://x",
        title="x",
        body="",
        published_date=None,
        fetched_date=date(2026, 6, 3),
        source_metadata=PdpcAdapter.metadata,
        doc_type=DocType.ENFORCEMENT_DECISION.value,
    )
    assert doc.sort_date == "2026-06-03"
    assert doc.year == 2026


def test_country_is_sg_for_all_public_adapters():
    for cls in [
        AustliiSgAdapter,
        CommonliiSgAdapter,
        ElitigationAdapter,
        HansardAdapter,
        IrasAdapter,
        MomAdapter,
        PdpcAdapter,
        PdpcGuidanceAdapter,
        SsoAdapter,
    ]:
        assert cls.metadata.country == "SG", f"{cls.__name__} country is not SG"


def test_each_adapter_declares_doc_type():
    for cls in [
        AustliiSgAdapter,
        CommonliiSgAdapter,
        ElitigationAdapter,
        HansardAdapter,
        IrasAdapter,
        MomAdapter,
        PdpcAdapter,
        PdpcGuidanceAdapter,
        SsoAdapter,
    ]:
        dt = getattr(cls, "doc_type", "")
        assert dt, f"{cls.__name__} has no doc_type"
        # must be a canonical value from DocType
        assert dt in {d.value for d in DocType}, f"{cls.__name__} doc_type {dt!r} not in DocType"


def test_each_adapter_declares_non_empty_extra_schema():
    for cls in [
        ElitigationAdapter,
        HansardAdapter,
        IrasAdapter,
        MomAdapter,
        PdpcAdapter,
        PdpcGuidanceAdapter,
        SsoAdapter,
    ]:
        schema = getattr(cls, "extra_schema", {})
        assert schema and isinstance(schema, dict), f"{cls.__name__} extra_schema empty/invalid"


def test_all_public_adapters_have_licence_summary():
    for cls in [
        AustliiSgAdapter,
        CommonliiSgAdapter,
        ElitigationAdapter,
        HansardAdapter,
        IrasAdapter,
        MomAdapter,
        PdpcAdapter,
        PdpcGuidanceAdapter,
        SsoAdapter,
    ]:
        summary = cls.metadata.licence_summary
        assert summary and len(summary) >= 50, (
            f"{cls.__name__} licence_summary too short or empty"
        )


def test_all_adapters_satisfy_protocol():
    for cls in [
        SsoAdapter, PdpcAdapter, PdpcGuidanceAdapter, ElitigationAdapter,
        CommonliiSgAdapter, AustliiSgAdapter, MomAdapter, IrasAdapter, HansardAdapter,
        LawnetAdapter, PracticalLawSgAdapter, LexisNexisSgAdapter,
    ]:
        instance = cls()
        assert isinstance(instance, LegalSourceAdapter), f"{cls.__name__} does not satisfy protocol"


def test_unimplemented_fetches_raise_not_silently_return_empty():
    """A benchmark build against a not-yet-implemented adapter must fail loudly."""
    from api.adapters.base import SourceAdapterError

    with pytest.raises(SourceAdapterError):
        list(SsoAdapter().fetch_all())
    with pytest.raises(SourceAdapterError):
        list(PdpcAdapter().fetch_all())
    with pytest.raises(SourceAdapterError):
        list(ElitigationAdapter().fetch_all())
