"""Adapter architecture invariants — most important: benchmark gating."""
from datetime import date

import pytest

from api.adapters import (
    BENCHMARK_ALLOWED_TIERS,
    AdapterTier,
    LegalSourceAdapter,
    SourceDocument,
    SourceMetadata,
    benchmark_safe_adapters,
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
    )
    p = doc.provenance
    assert p["source_id"] == "sso"
    assert p["source_url"].startswith("https://sso.agc.gov.sg")
    assert p["document_id"] == "penal-code/s-9"
    assert p["published_date"] == "2008-12-31"
    assert p["fetched_date"] == "2026-06-03"
    assert p["tier"] == "public"
    assert "Singapore legislation" in p["licence_summary"]


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
