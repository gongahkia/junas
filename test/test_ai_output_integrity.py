"""Mocked AI evidence/privacy regressions; no accuracy or real-model claims."""

import copy
import hashlib
import json
from dataclasses import asdict
from types import SimpleNamespace as N
from unittest.mock import patch

import pytest

from junas.advisory.llm_adjudicator.helpers import RuntimeLLMCoverageAuditor, RuntimeLLMDefinedTermExtractor
from junas.advisory.llm_adjudicator.inference import LocalLLMAdjudicator
from junas.advisory.llm_adjudicator.structured_query import build_structured_query
from junas.review.engine import PreSendReviewEngine, ReviewLayerError
from junas.review.llm_defined_terms import LLMDefinedTermError, extract_with_cache

TEXT = "Acme acquisition for $2.5 billion is pending."
PAYLOAD = {
    "risk_label": "SAFE",
    "public_status": "public",
    "confidence": 0.9,
    "materiality_reason": "public_source_match",
    "matched_public_sources": [],
    "unverified_claims": [],
    "review_recommendation": "ok",
}


def settings(**overrides):
    return N(
        **dict(
            {
                "enabled": True,
                "provider": "vllm",
                "model": "fake-model",
                "base_url": "http://127.0.0.1:8001/v1",
                "llm_input_mode": "structured_tokens",
                "allow_remote_base_url": False,
                "allow_remote_raw_text": False,
            },
            **overrides,
        )
    )


def review(engine, text=TEXT, profile="audit_grade"):
    return engine.review(
        text=text,
        source_jurisdiction="SG",
        destination_jurisdiction="SG",
        entity_id=None,
        include_suggestions=False,
        review_profile=profile,
        document_type="memo",
    )


class Auditor:
    provider, model, prompt_version = "fake", "fake-model", "test-v1"

    def __init__(self, warnings=None):
        self.warnings = (
            warnings
            if warnings is not None
            else [{"rule_guess": "missing_signal", "why": "unverified hypothesis", "confidence": 0.5}]
        )
        self.calls = 0

    def audit(self, **kwargs):
        self.calls += 1
        return copy.deepcopy(self.warnings)


class Adjudicator:
    def __init__(self, payload=None):
        self.payload = (
            payload if payload is not None else dict(PAYLOAD, status="adjudicated", provider="fake", model="fake-model")
        )
        self.calls = 0

    def adjudicate(self, **kwargs):
        self.calls += 1
        return copy.deepcopy(self.payload)


class Terms:
    def __init__(self, terms=("Seller",), model="fake-model", version="v1"):
        self.terms, self.model, self.version, self.calls = list(terms), model, version, 0

    def extract(self, preamble):
        self.calls += 1
        return self.terms

    def cache_identity(self):
        return {
            "provider": "fake",
            "model": self.model,
            "prompt_version": self.version,
            "prompt_sha256": hashlib.sha256(self.version.encode()).hexdigest(),
        }


@pytest.fixture(autouse=True)
def private_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("JUNAS_CACHE_DIR", str(tmp_path))


@pytest.mark.parametrize("count", [1, 20])
def test_coverage_advice_never_changes_evidence_scores_or_risk(count):
    baseline = review(PreSendReviewEngine())
    auditor = Auditor(Auditor().warnings * count)
    result = review(PreSendReviewEngine(llm_coverage_auditor=auditor))
    assert [asdict(f) for f in result.findings] == [asdict(f) for f in baseline.findings]
    assert (result.document_score, result.pii_score, result.mnpi_score, result.overall_risk) == (
        baseline.document_score,
        baseline.pii_score,
        baseline.mnpi_score,
        baseline.overall_risk,
    )
    assert len(result.coverage_warnings) == 1
    w = result.coverage_warnings[0]
    assert w["advisory_only"] and w["evidence_status"] == "unverified"
    assert w["provider"] == "fake" and w["model"] == "fake-model"
    assert not {"matched_text", "start_char", "end_char"} & w.keys()


@pytest.mark.parametrize(
    "extra",
    [
        {"matched_text": "fabricated", "start_char": 0, "end_char": 0},
        {"confidence": float("nan")},
        {"confidence": True},
        {"why": 42},
        {"rule_guess": None},
    ],
)
def test_invalid_coverage_outputs_fail_closed(extra):
    warning = dict(Auditor().warnings[0], **extra)
    with pytest.raises(ReviewLayerError) as exc:
        review(PreSendReviewEngine(llm_coverage_auditor=Auditor([warning])))
    assert exc.value.layer == "llm_coverage_audit"


def test_adjudication_is_explicit_advice_not_a_scoreless_override():
    baseline = review(PreSendReviewEngine())
    result = review(PreSendReviewEngine(llm_adjudicator=Adjudicator()))
    assert result.overall_risk == baseline.overall_risk and result.document_score == baseline.document_score
    advice = result.llm_adjudication
    assert advice["risk_label"] == "SAFE" and advice["classification_applied"] is False
    assert advice["evidence_status"] == "unverified" and advice["origin"] == "llm"
    assert advice["public_status"] == "not_checked" and advice["proposed_public_status"] == "public"


def test_in_band_advice_cannot_clear_deterministic_high_pii():
    adj = Adjudicator()
    text = TEXT + " Client NRIC S1234567D."
    baseline = review(PreSendReviewEngine(), text)
    result = review(PreSendReviewEngine(llm_adjudicator=adj), text)
    assert adj.calls == 1 and baseline.overall_risk.value == "HIGH_RISK"
    assert result.overall_risk == baseline.overall_risk and result.document_score == baseline.document_score


@pytest.mark.parametrize("output", [None, [], {}, {"status": "adjudicated", "risk_label": "invalid"}])
def test_malformed_injected_adjudicator_fails_explicitly(output):
    adj = Adjudicator()
    adj.payload = output
    with pytest.raises(ReviewLayerError) as exc:
        review(PreSendReviewEngine(llm_adjudicator=adj))
    assert exc.value.layer == "llm_adjudicator"


def test_internal_type_error_does_not_retry_outbound_adjudication():
    class Bad(Adjudicator):
        def adjudicate(self, **kwargs):
            self.calls += 1
            raise TypeError("malformed provider output")

    adj = Bad()
    with pytest.raises(ReviewLayerError):
        review(PreSendReviewEngine(llm_adjudicator=adj))
    assert adj.calls == 1


def test_defined_terms_cannot_suppress_an_ungrounded_person():
    text = "Mr Seller shall execute the contract."
    baseline = review(PreSendReviewEngine(), text)
    result = review(PreSendReviewEngine(llm_defined_term_extractor=Terms()), text)
    assert [asdict(f) for f in result.findings] == [asdict(f) for f in baseline.findings]
    advice = next(w for w in result.coverage_warnings if w.get("source") == "llm_defined_terms")
    assert advice["terms"] == ["seller"] and advice["advisory_only"]


def test_strict_calls_no_optional_provider_and_preserves_high_floor():
    adj, auditor, extractor = Adjudicator(), Auditor(), Terms()
    engine = PreSendReviewEngine(
        llm_adjudicator=adj, llm_coverage_auditor=auditor, llm_defined_term_extractor=extractor
    )
    with patch("httpx.Client", side_effect=AssertionError("no outbound calls")):
        result = review(engine, "Confidential acquisition. NRIC S1234567D.", "strict")
    assert result.overall_risk.value == "HIGH_RISK"
    assert adj.calls == auditor.calls == extractor.calls == 0


def test_pii_only_and_above_band_documents_keep_existing_router():
    for text in (
        "Client NRIC S1234567D.",
        "Confidential pre-announcement acquisition. Material non-public information.",
    ):
        adj, auditor = Adjudicator(), Auditor()
        review(PreSendReviewEngine(llm_adjudicator=adj, llm_coverage_auditor=auditor), text)
        assert adj.calls == auditor.calls == 0


@pytest.mark.parametrize("entity", ["S1234567D", "alice@example.test", "private client name", "opaque-client-1"])
def test_structured_entity_identifiers_are_hashed_not_forwarded(entity):
    q = build_structured_query(
        text="x", findings=[], entity_id=entity, current_classification="LOW_RISK", public_evidence=None
    )
    assert entity not in json.dumps(q)
    assert q["entity_id"] == "sha256:" + hashlib.sha256(entity.encode()).hexdigest()


@pytest.mark.parametrize("entity", [[], {}, 23])
def test_non_string_entity_identifiers_are_rejected(entity):
    with pytest.raises(ValueError):
        build_structured_query(
            text="x", findings=[], entity_id=entity, current_classification="LOW_RISK", public_evidence=None
        )


@pytest.mark.parametrize("start,end,matched", [(0, 0, "x"), (0, 1, "wrong"), (-1, 1, "x")])
def test_structured_fabricated_evidence_refused_before_transport(start, end, matched):
    finding = N(
        rule="named_person",
        category="PII",
        severity="low",
        jurisdiction="SG",
        start_char=start,
        end_char=end,
        matched_text=matched,
    )
    adj = LocalLLMAdjudicator(settings())
    with patch.object(adj, "_call_openai_compatible", side_effect=AssertionError("no request")):
        result = adj.adjudicate(text="x", current_classification="LOW_RISK", findings=[finding])
    assert result["status"] == "error"


@pytest.mark.parametrize(
    "field,value",
    [
        ("confidence", float("nan")),
        ("confidence", float("inf")),
        ("confidence", True),
        ("confidence", "0.9"),
        ("public_status", "unknown-enum"),
        ("risk_label", ["SAFE"]),
        ("matched_public_sources", "https://example.test"),
        ("unverified_claims", [12]),
        ("materiality_reason", {}),
    ],
)
def test_malformed_model_payloads_are_not_normalized_into_success(field, value):
    adj = LocalLLMAdjudicator(settings())
    with patch.object(adj, "_call_openai_compatible", return_value=dict(PAYLOAD, **{field: value})):
        result = adj.adjudicate(text="x", current_classification="LOW_RISK")
    assert result["status"] == "error" and result["risk_label"] is None


def test_structured_metadata_does_not_forward_free_form_fields():
    private = "alice@example.test"
    finding = N(
        rule=private,
        reason=private,
        category="PII",
        severity="high",
        jurisdiction=private,
        matched_text="x",
        start_char=0,
        end_char=1,
    )
    auditor = RuntimeLLMCoverageAuditor(settings())
    with patch.object(auditor, "_call_json", return_value={"warnings": []}) as call:
        from junas.review.llm_coverage_audit import run_coverage_audit

        run_coverage_audit(text="x", findings=[finding], document_type=private, auditor=auditor, fail_closed=True)
    assert private not in json.dumps(call.call_args.args)


def test_cache_identity_separates_model_and_prompt_and_does_not_cache_unknown_extractors():
    first, second, third = Terms(("Seller",), "one"), Terms(("Buyer",), "two"), Terms(("Vendor",), "one", "v2")
    assert extract_with_cache(text="same text", extractor=first, fail_closed=True) == {"seller"}
    assert extract_with_cache(text="same text", extractor=second, fail_closed=True) == {"buyer"}
    assert extract_with_cache(text="same text", extractor=third, fail_closed=True) == {"vendor"}
    assert first.calls == second.calls == third.calls == 1
    extract_with_cache(text="same text", extractor=first, fail_closed=True)
    assert first.calls == 1

    class Unattributed:
        calls = 0

        def extract(self, preamble):
            self.calls += 1
            return []

    unknown = Unattributed()
    for _ in range(2):
        extract_with_cache(text="another text", extractor=unknown, fail_closed=True)
    assert unknown.calls == 2


def test_disabled_runtime_helper_cannot_reuse_a_prior_cached_result():
    extractor = RuntimeLLMDefinedTermExtractor(settings())
    with patch.object(extractor, "_call_json", return_value={"terms": ["Seller"]}) as call:
        extract_with_cache(text="same text", extractor=extractor, fail_closed=True)
        extractor.enabled = False
        with pytest.raises(LLMDefinedTermError):
            extract_with_cache(text="same text", extractor=extractor, fail_closed=True)
        assert call.call_count == 1


def test_unrelated_retrieved_sources_do_not_verify_each_claim():
    class Retriever:
        def retrieve(self, **kwargs):
            return {"status": "queried", "sources": [{"url": "https://example.test/unrelated"}], "privacy_ledger": []}

    result = review(PreSendReviewEngine(public_evidence_retriever=Retriever()))
    assert all(f.source_verification != "public_source_matched" for f in result.findings if f.category == "MNPI")


def test_existing_distilled_runtime_adapter_uses_advisory_validation_without_loading_weights(tmp_path):
    from training.distillation.student_provider import LocalDistilledAdjudicator

    student = LocalDistilledAdjudicator(adapter_path=tmp_path, base_model="fake", input_mode="structured_tokens")
    with pytest.raises(ValueError):
        student._normalize_payload(dict(PAYLOAD, confidence=float("nan")))
    result = student._normalize_payload(PAYLOAD)
    assert result["advisory_only"] and result["public_status"] == "not_checked"
    assert result["provenance"]["model"] == "fake"


@pytest.mark.parametrize(
    "overrides",
    [
        {"base_url": "https://provider.example/v1"},
        {"base_url": "https://provider.example/v1", "allow_remote_base_url": True, "llm_input_mode": "raw_text"},
        {"base_url": "https://provider.example/v1", "allow_remote_base_url": True, "provider": "openai"},
    ],
)
def test_existing_remote_consent_gates_refuse_before_transport(overrides):
    adj = LocalLLMAdjudicator(settings(**overrides))
    with patch("httpx.Client", side_effect=AssertionError("no consent, no request")):
        result = adj.adjudicate(text="synthetic text", current_classification="LOW_RISK")
    assert result["status"] == "error"


def test_runtime_cache_identity_changes_with_endpoint_and_prompt_and_rejects_old_entries(tmp_path):
    from junas.review.llm_defined_terms import document_hash

    legacy = tmp_path / "llm_defined_terms" / (document_hash("same text") + ".json")
    legacy.parent.mkdir()
    legacy.write_text(json.dumps({"terms": ["legacy-unattributed"]}))
    a = RuntimeLLMDefinedTermExtractor(settings())
    b = RuntimeLLMDefinedTermExtractor(settings(base_url="http://127.0.0.1:8002/v1"))
    with (
        patch.object(a, "_call_json", return_value={"terms": ["Seller"]}) as ca,
        patch.object(b, "_call_json", return_value={"terms": ["Buyer"]}) as cb,
    ):
        assert extract_with_cache(text="same text", extractor=a, fail_closed=True) == {"seller"}
        assert extract_with_cache(text="same text", extractor=b, fail_closed=True) == {"buyer"}
        assert ca.call_count == cb.call_count == 1
    assert json.loads(legacy.read_text())["terms"] == ["legacy-unattributed"]
    entries = [json.loads(p.read_text()) for p in (legacy.parent / "v2").glob("*.json")]
    assert len(entries) == 2 and all(p["identity"]["prompt_version"] == a.prompt_version for p in entries)
    assert all(p["evidence_status"] == "unverified" for p in entries)


def test_no_provider_audit_grade_retains_its_existing_deterministic_profile_difference():
    text = (
        "Dr Jane Tan (NRIC S1234567A, mobile +65 9123 4567, email jane.tan@example.sg) "
        "lives at 1 Address Lane Singapore 123456."
    )
    strict = review(PreSendReviewEngine(), text, "strict")
    audit = review(PreSendReviewEngine(), text, "audit_grade")
    assert (
        next(f for f in strict.findings if f.rule == "quasi_identifier_combination").metadata["layer"]
        == "singling_out_v2"
    )
    assert (
        next(f for f in audit.findings if f.rule == "quasi_identifier_combination").metadata["layer"]
        == "quasi_identifier_seed"
    )
