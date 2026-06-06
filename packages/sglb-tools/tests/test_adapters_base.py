from __future__ import annotations

from datetime import date

from sglb_tools.adapters import (
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


class PublicFixtureAdapter:
    metadata = SourceMetadata(
        source_id="fixture-public",
        display_name="Fixture Public",
        base_url="https://example.sg",
        tier=AdapterTier.PUBLIC,
        licence_summary="Fixture public source for adapter-base tests.",
    )
    doc_type = DocType.CASE.value
    extra_schema = {"court": "str"}

    def fetch_all(self):
        return iter(())

    def fetch_by_id(self, document_id: str):
        return None


class CredentialedFixtureAdapter(PublicFixtureAdapter):
    metadata = SourceMetadata(
        source_id="fixture-credentialed",
        display_name="Fixture Credentialed",
        base_url="https://example.sg",
        tier=AdapterTier.USER_CREDENTIALED,
        licence_summary="Fixture credentialed source for adapter-base tests.",
        benchmark_eligible=False,
    )


def test_adapter_protocol_and_benchmark_filter():
    public = PublicFixtureAdapter()
    credentialed = CredentialedFixtureAdapter()

    assert isinstance(public, LegalSourceAdapter)
    assert BENCHMARK_ALLOWED_TIERS == frozenset({AdapterTier.PUBLIC})
    assert benchmark_safe_adapters([public, credentialed]) == [public]


def test_source_document_provenance_and_legis_id():
    doc = SourceDocument(
        document_id="SGCA-2024-48",
        source_url="https://example.sg/SGCA-2024-48",
        title="Example case",
        body="...",
        published_date=date(2024, 11, 6),
        fetched_date=date(2026, 6, 3),
        source_metadata=PublicFixtureAdapter.metadata,
        doc_type=DocType.CASE.value,
    )

    assert doc.legis_id == "sgca-2024-48"
    assert doc.country == "SG"
    assert doc.sort_date == "2024-11-06"
    assert doc.year == 2024
    assert doc.provenance["tier"] == "public"


def test_helpers_are_stable_for_consumers():
    assert derive_legis_id(country="SG", doc_type="case", raw_identifier="unknown", title="A v B").startswith("sg-case-a-v-b")
    assert normalise_date("3 Jun 2026") == date(2026, 6, 3)
    assert normalise_date("never") is None
