from types import SimpleNamespace

from scripts.measure_external_surfaces import ContextualPiiEngine


def test_context_adapter_preserves_offsets_and_degradation_without_legacy_findings():
    adapter = ContextualPiiEngine()
    evidence = {"rule": "email", "start_char": 2, "end_char": 5, "matched_text": "a@b"}
    source = SimpleNamespace(
        sensitivity={"pii": {"evidence": [evidence]}},
        findings=[SimpleNamespace(rule="legacy-only")],
        degraded_modes=["source limit"],
    )
    adapter.engine = SimpleNamespace(review=lambda **kwargs: source)
    result = adapter.review(text="x a@b")
    assert vars(result.findings[0]) == {"category": "PII", **evidence}
    assert len(result.findings) == 1 and result.degraded_modes == source.degraded_modes
    assert source.sensitivity["pii"]["evidence"] == [evidence]
