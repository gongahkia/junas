"""Mocked automated-corpus contracts; no provider inference or real review events."""

import copy
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest

from scripts import model_corpus as corpus

TEXT = "Mr Alex called Mr Alex.\r\n"


def config(documents=1):
    def model(name):
        return {
            "model": name,
            "reasoning_effort": "high",
            "max_input_tokens": 2000,
            "max_output_tokens": 512,
            "input_rate": "1",
            "output_rate": "2",
        }

    return {
        "schema_version": corpus.VERSION,
        "documents": documents,
        "max_candidates": documents,
        "quadrant_targets": (
            {q: documents // 4 + (i < documents % 4) for i, q in enumerate(corpus.QUADRANTS)}
            if documents >= 4
            else {q: documents if q == "pii_only" else 0 for q in corpus.QUADRANTS}
        ),
        "generator": model("fake-generator"),
        "judges": [model("fake-judge-a"), model("fake-judge-b"), model("fake-judge-c")],
        "pricing_checked_on": date.today().isoformat(),
    }


def authorization(cfg, budget="1"):
    # simulated authorization metadata for transport tests only.
    return {
        "config_sha256": corpus.identity(cfg),
        "organization": "org-test",
        "project": "proj_test",
        "budget_usd": budget,
        "available_credit_usd": "2",
        "credits_apply": True,
        "data_scope": "new_synthetic_only",
        "funding_basis": "confirmed_eligible_credits",
    }


def annotation():
    return {
        "status": "annotated",
        "coverage": "exhaustive",
        "mnpi_coverage": "exhaustive",
        "document_labels": {
            "pii": {"state": "present", "confidence": 0.8, "reason": "named fictional person"},
            "mnpi": {"state": "absent", "confidence": 0.8, "reason": "routine conversation without issuer event"},
        },
        "notes": "test-only invented scenario",
        "pii": [
            {
                "label": "PERSON_NAME",
                "start_char": start,
                "end_char": end,
                "matched_text": "Alex",
                "confidence": 0.8,
                "reason": "fictional natural person",
            }
            for start, end in [(3, 7), (18, 22)]
        ],
        "mnpi": [],
    }


@pytest.fixture(autouse=True)
def isolated_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-secret")


def transport(*, judge_b=None, status="completed", fail=False, usage=None):
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"input_tokens": 100})
        if fail:
            raise httpx.ReadTimeout("synthetic timeout")
        output = (
            {"text": TEXT}
            if body["model"] == "fake-generator"
            else (judge_b if body["model"] == "fake-judge-b" and judge_b is not None else annotation())
        )
        return httpx.Response(
            200,
            json={
                "id": "test-response",
                "model": body["model"],
                "status": status,
                "service_tier": "default",
                "usage": usage if usage is not None else {"input_tokens": 100, "output_tokens": 30},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]}],
            },
        )

    return httpx.MockTransport(handle), requests


def test_plan_and_unauthorized_cli_cannot_make_requests(tmp_path):
    cfg = config()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    with patch("httpx.Client", side_effect=AssertionError("offline only")):
        assert corpus.main(["plan", "--config", str(path), "--output", str(tmp_path / "plan.json")]) == 0
        assert corpus.main(["run", "--config", str(path), "--output", str(tmp_path / "run")]) == 2
    assert not (tmp_path / "run").exists()
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert plan["first_pass_model_calls"] == 4 and plan["model_calls"] == 7
    assert not plan["live_calls_authorized"] and not plan["human_ground_truth"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("config_sha256", "wrong"),
        ("credits_apply", False),
        ("data_scope", "private_documents"),
        ("budget_usd", "NaN"),
        ("budget_usd", "3"),
        ("organization", ""),
        ("project", ""),
    ],
)
def test_invalid_authorization_refuses_before_client_or_output(tmp_path, field, value):
    cfg = config()
    auth = authorization(cfg)
    auth[field] = value
    with patch("httpx.Client", side_effect=AssertionError("not approved")):
        with pytest.raises(ValueError):
            corpus.run(cfg, auth, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_explicit_billable_cap_does_not_invent_available_credits():
    cfg = config()
    auth = authorization(cfg, "5")
    auth.update(funding_basis="explicit_billable_cap", available_credit_usd=None, credits_apply=None)
    assert corpus.validate_authorization(auth, cfg) == Decimal(5)
    auth["credits_apply"] = True
    with pytest.raises(ValueError, match="remain null"):
        corpus.validate_authorization(auth, cfg)


def test_dotenv_loader_does_not_execute_values_or_read_other_settings(tmp_path, monkeypatch):
    import os

    path = tmp_path / ".env"
    marker = tmp_path / "never-created"
    path.write_text(f'IGNORED=$(touch {marker})\nexport OPENAI_API_KEY="test-$(literal)" # comment\n')
    monkeypatch.delenv("OPENAI_API_KEY")
    corpus.load_api_key(path)
    assert os.environ["OPENAI_API_KEY"] == "test-$(literal)"
    assert not marker.exists()
    path.write_text("OPENAI_API_KEY=one\nOPENAI_API_KEY=two\n")
    with pytest.raises(ValueError, match="duplicate"):
        corpus.load_api_key(path)


def test_model_identity_and_old_pricing_are_refused(tmp_path):
    cfg = config()
    cfg["judges"][0] = dict(cfg["generator"])
    with pytest.raises(ValueError, match="distinct"):
        corpus.validate_config(cfg)
    cfg = config()
    cfg["pricing_checked_on"] = "2000-01-01"
    with pytest.raises(ValueError, match="pricing"):
        corpus.run(cfg, authorization(cfg), tmp_path / "old")


@pytest.mark.parametrize(
    "change",
    [
        {"start_char": 0, "end_char": 0},
        {"start_char": True},
        {"end_char": 999},
        {"matched_text": "invented"},
        {"confidence": float("nan")},
        {"confidence": True},
        {"label": "not-a-label"},
        {"reason": ""},
    ],
)
def test_malformed_or_ungrounded_annotations_are_rejected(change):
    raw = annotation()
    raw["pii"][0].update(change)
    with pytest.raises(ValueError):
        corpus.validate_annotations(raw, TEXT)


def test_duplicates_abstentions_and_public_status_are_explicit():
    raw = annotation()
    raw["pii"].append(copy.deepcopy(raw["pii"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        corpus.validate_annotations(raw, TEXT)
    raw = annotation()
    raw["status"] = "abstain"
    with pytest.raises(ValueError, match="abstention"):
        corpus.validate_annotations(raw, TEXT)
    raw = annotation()
    raw["mnpi"] = [
        {k: v for k, v in raw["pii"][0].items() if k != "label"}
        | {
            "potential_materiality": "not_established",
            "public_status": "verified_public",
        }
    ]
    with pytest.raises(ValueError, match="public_status"):
        corpus.validate_annotations(raw, TEXT)


def test_disagreement_retains_occurrences_and_does_not_invent_a_confidence_probability():
    a, b = annotation(), annotation()
    b["pii"].pop()
    b["pii"][0]["confidence"] = 0.6
    c = copy.deepcopy(b)
    c["pii"][0]["confidence"] = 0.7
    result = corpus.consensus([a, b, c])
    assert len(result["pii"]) == 1 and result["pii_disputed_occurrences"] == 1
    assert result["pii"][0]["confidence_reports"] == [0.8, 0.6, 0.7]
    assert result["coverage"] == "unknown" and result["independence"] == "not_established"
    assert "uncalibrated" in result["confidence_kind"]


def test_mocked_end_to_end_is_blind_recorded_grounded_and_separate_from_human_gold(tmp_path):
    cfg = config()
    mock, requests = transport()
    output = tmp_path / "run"
    report = corpus.run(cfg, authorization(cfg), output, transport=mock)
    assert report["completed_documents"] == 1 and not report["human_annotations"] and not report["protected_holdout"]
    records = [json.loads(line) for line in (output / "records.jsonl").read_text().splitlines()]
    record = records[0]
    assert record["text"] == TEXT and record["text_sha256"] == corpus.input_identity(TEXT)
    assert len(record["consensus"]["pii"]) == 2
    completions = [body for path, body in requests if not path.endswith("input_tokens")]
    assert len(requests) == 8 and len(completions) == 4
    for body in completions[1:]:
        supplied = json.loads(body["input"])
        assert supplied["text"] == TEXT and supplied["attempt"] == 1
        assert supplied["previous_validation_error"] is None
        assert all(TEXT[start:end] == word for start, end, word in supplied["word_offsets"])
        assert "annotations" not in supplied
        assert body["store"] is False and body["text"]["format"]["strict"] is True
        assert "tools" not in body
    for path in output.iterdir():
        assert "synthetic-test-secret" not in path.read_text()
    metrics = report["evaluation"]["pii"]
    assert metrics["exact"]["matched"] == 0 and metrics["overlap"]["matched"] == 2
    assert "not independent" in report["evaluation"]["interpretation"]
    assert Decimal(report["charged_or_reserved_ceiling_usd"]) <= Decimal(report["budget_usd"])


def test_budget_stops_before_completion_not_after_spending(tmp_path):
    cfg = config(4)
    mock, requests = transport()
    report = corpus.run(cfg, authorization(cfg, "0.000001"), tmp_path / "budget", transport=mock)
    assert report["stop_reason"] == "BudgetExhausted" and report["unattempted_candidates"] == 3
    assert len(requests) == 1 and requests[0][0].endswith("input_tokens")
    assert report["charged_or_reserved_ceiling_usd"] == "0"


def test_abstention_and_disagreement_are_reported_without_exhaustive_precision(tmp_path):
    cfg = config()
    abstention = annotation()
    abstention.update(status="abstain", coverage="unknown", mnpi_coverage="unknown", pii=[], mnpi=[])
    for label in abstention["document_labels"].values():
        label["state"] = "unknown"
    mock, _ = transport(judge_b=abstention)
    report = corpus.run(cfg, authorization(cfg), tmp_path / "abstained", transport=mock)
    assert report["documents_with_abstentions"] == 1
    assert report["evaluation"]["pii"]["exact"]["precision_if_exhaustive"] is None
    disagreed = annotation()
    disagreed["pii"].pop()
    mock, _ = transport(judge_b=disagreed)
    report = corpus.run(cfg, authorization(cfg), tmp_path / "disagreed", transport=mock)
    assert report["disputed_documents"] == 1
    assert report["evaluation"]["pii"]["exact"]["precision_if_exhaustive"] is None


def test_invalid_judge_output_gets_one_bounded_indexed_correction_without_local_span_repair():
    from types import SimpleNamespace

    bad = annotation()
    bad["pii"][0]["start_char"] = 4
    responses = [bad, annotation()]
    inputs = []

    def call(model, **kwargs):
        inputs.append(kwargs["data"])
        return responses.pop(0)

    result = corpus.annotate_document(SimpleNamespace(call=call), config()["judges"][0], TEXT)
    assert result["attempts"] == 2 and len(result["validation_failures"]) == 1
    assert bad["pii"][0]["start_char"] == 4
    assert result["output"]["pii"][0]["start_char"] == 3
    assert inputs[1]["previous_validation_error"] and inputs[0]["text"] == inputs[1]["text"] == TEXT
    assert inputs[0]["word_offsets"] == inputs[1]["word_offsets"]


def test_judge_correction_attempts_are_bounded_and_unknown_transport_is_not_retried():
    from types import SimpleNamespace

    calls = []

    def bad_call(*args, **kwargs):
        calls.append(kwargs)
        return {}

    result = corpus.annotate_document(SimpleNamespace(call=bad_call), config()["judges"][0], TEXT)
    assert result["output"] is None and len(calls) == corpus.MAX_JUDGE_ATTEMPTS

    def uncertain(*args, **kwargs):
        calls.append(kwargs)
        raise corpus.UncertainRequest("uncertain test")

    before = len(calls)
    with pytest.raises(corpus.UncertainRequest):
        corpus.annotate_document(SimpleNamespace(call=uncertain), config()["judges"][0], TEXT)
    assert len(calls) == before + 1


def test_missing_key_and_repository_output_are_refused_before_network(tmp_path, monkeypatch):
    cfg = config()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        corpus.run(cfg, authorization(cfg), tmp_path / "missing-key")
    assert not (tmp_path / "missing-key").exists()
    with pytest.raises(ValueError, match="outside the repository"):
        corpus.run(cfg, authorization(cfg), corpus.ROOT / "test/fixtures/do-not-create")


def test_refusal_is_not_interpreted_as_successful_annotation(tmp_path):
    cfg = config()

    def handle(request):
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"input_tokens": 100})
        return httpx.Response(
            200,
            json={
                "id": "refusal",
                "model": "fake-generator",
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 10},
                "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "test refusal"}]}],
            },
        )

    report = corpus.run(cfg, authorization(cfg), tmp_path / "refusal", transport=httpx.MockTransport(handle))
    assert report["failed_documents"] == 1 and report["completed_documents"] == 0
    assert report["evaluation"]["pii"]["status"] == "unavailable"


def test_uncertain_completion_keeps_reserve_and_is_never_retried(tmp_path):
    cfg = config(4)
    mock, requests = transport(fail=True)
    report = corpus.run(cfg, authorization(cfg), tmp_path / "uncertain", transport=mock)
    assert report["stop_reason"] == "UncertainRequest" and len(requests) == 2
    assert Decimal(report["charged_or_reserved_ceiling_usd"]) == corpus.token_cost(cfg["generator"], 100, 512)
    events = [json.loads(line) for line in (tmp_path / "uncertain/requests.jsonl").read_text().splitlines()]
    assert [e["status"] for e in events] == ["preflight", "reserved", "uncertain"]


def test_unexpected_model_is_retained_for_audit_and_stops_the_run(tmp_path):
    cfg = config(4)
    requests = []

    def handle(request):
        requests.append(request.url.path)
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"input_tokens": 100})
        return httpx.Response(
            200,
            json={
                "id": "unexpected",
                "model": "unapproved-resolved-model",
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 10},
                "output": [],
            },
        )

    output = tmp_path / "unexpected"
    report = corpus.run(cfg, authorization(cfg), output, transport=httpx.MockTransport(handle))
    assert report["stop_reason"] == "UncertainRequest" and len(requests) == 2
    saved = json.loads((output / "response-00001.json").read_text())
    assert saved["response"]["model"] == "unapproved-resolved-model"
    assert Decimal(report["charged_or_reserved_ceiling_usd"]) == corpus.token_cost(cfg["generator"], 100, 512)


@pytest.mark.parametrize(
    "usage", [None, {"input_tokens": 101, "output_tokens": 30}, {"input_tokens": True, "output_tokens": 30}]
)
def test_invalid_usage_or_incomplete_response_never_creates_consensus(tmp_path, usage):
    cfg = config()
    mock, _ = transport(status="incomplete", usage=usage)
    report = corpus.run(cfg, authorization(cfg), tmp_path / "invalid", transport=mock)
    assert report["failed_documents"] == 1 and report["completed_documents"] == 0
    assert report["evaluation"]["pii"]["status"] == "unavailable"


def test_existing_runs_are_not_overwritten_and_duplicates_are_disclosed(tmp_path):
    cfg = config(2)
    mock, requests = transport()
    output = tmp_path / "run"
    report = corpus.run(cfg, authorization(cfg), output, transport=mock)
    assert report["completed_documents"] == 1 and report["failed_documents"] == 1
    assert "duplicate" in (output / "records.jsonl").read_text()
    before = (output / "report.json").read_bytes()
    count = len(requests)
    with pytest.raises(FileExistsError):
        corpus.run(cfg, authorization(cfg), output, transport=mock)
    assert (output / "report.json").read_bytes() == before and len(requests) == count


def abstaining_annotation():
    raw = annotation()
    raw.update(status="abstain", coverage="unknown", mnpi_coverage="unknown", pii=[], mnpi=[])
    for label in raw["document_labels"].values():
        label["state"] = "unknown"
    return raw


def test_majority_keeps_unanimity_dissent_and_minority_spans_distinct():
    a, b, c = annotation(), annotation(), annotation()
    c["pii"].pop()
    result = corpus.consensus([a, b, c])
    assert [s["judge_agreement"] for s in result["pii"]] == [3, 2]
    assert [s["agreement_level"] for s in result["pii"]] == ["unanimous", "majority"]
    assert result["pii"][1]["supporting_judges"] == [0, 1]
    assert result["pii"][1]["dissenting_judges"] == [2]
    assert result["pii_disputed_occurrences"] == 1 and result["coverage"] == "unknown"
    b["pii"].pop()
    result = corpus.consensus([a, b, c])
    assert len(result["pii"]) == 1 and len(result["pii_challenges"]) == 1
    assert result["pii_challenges"][0]["judge_agreement"] == 1


def test_abstentions_do_not_lower_the_two_of_three_threshold():
    a = annotation()
    result = corpus.consensus([a, abstaining_annotation(), abstaining_annotation()])
    assert result["pii"] == [] and result["quadrant"] == "unknown"
    assert result["document_labels"]["pii"]["agreement_level"] == "unresolved"
    result = corpus.consensus([a, annotation(), abstaining_annotation()])
    assert len(result["pii"]) == 2 and result["quadrant"] == "pii_only"
    assert result["document_labels"]["pii"]["agreement_level"] == "majority"
    assert result["coverage"] == "unknown"


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_consensus_refuses_missing_or_extra_judges(count):
    with pytest.raises(ValueError, match="exactly three"):
        corpus.consensus([annotation() for _ in range(count)])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a["document_labels"]["pii"].update(state="absent"),
        lambda a: a.update(pii=[]),
        lambda a: a["document_labels"]["mnpi"].update(state="present"),
        lambda a: a.update(mnpi_coverage="partial"),
        lambda a: a["document_labels"]["pii"].update(confidence=True),
        lambda a: a["document_labels"]["mnpi"].update(reason=""),
    ],
)
def test_document_labels_require_grounded_positive_or_exhaustive_negative_evidence(mutate):
    raw = annotation()
    mutate(raw)
    with pytest.raises(ValueError):
        corpus.validate_annotations(raw, TEXT)


@pytest.mark.parametrize(
    "materiality,publicity",
    [
        ("not_established", "unknown"),
        ("potentially_material", "unknown"),
        ("not_established", "claimed_nonpublic"),
    ],
)
def test_uncertain_mnpi_cannot_become_a_negative_reference(materiality, publicity):
    raw = annotation()
    raw["mnpi"] = [
        {k: v for k, v in raw["pii"][0].items() if k != "label"}
        | {
            "potential_materiality": materiality,
            "public_status": publicity,
        }
    ]
    with pytest.raises(ValueError, match="unresolved MNPI"):
        corpus.validate_annotations(raw, TEXT)
    raw["document_labels"]["mnpi"]["state"] = "unknown"
    corpus.validate_annotations(raw, TEXT)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["judges"].pop(),
        lambda c: c.update(max_candidates=0),
        lambda c: c.update(max_candidates=1001),
        lambda c: c["quadrant_targets"].update(neither=2),
        lambda c: c["quadrant_targets"].update(neither=True),
        lambda c: c.update(quadrant_targets=dict(neither=0, pii_only=2, mnpi_only=1, both=1)),
    ],
)
def test_invalid_quadrant_and_three_judge_plans_fail_before_network(tmp_path, mutate):
    cfg = config(4)
    mutate(cfg)
    with patch("httpx.Client", side_effect=AssertionError("no network")):
        with pytest.raises(ValueError):
            corpus.run(cfg, authorization(cfg), tmp_path / "invalid-config")


QUADRANT_TEXT = {
    "neither": "Generic public policy for all companies.",
    "pii_only": "Alex joined the routine payroll register.",
    "mnpi_only": "Acme confidential acquisition is not yet announced.",
    "both": "Alex discussed Acme confidential acquisition before public announcement.",
}


def quadrant_annotation(quadrant, text):
    raw = annotation()
    raw["pii"], raw["mnpi"] = [], []
    pii, mnpi = corpus.QUADRANTS[quadrant]
    for category, state in (("pii", pii), ("mnpi", mnpi)):
        raw["document_labels"][category].update(state=state, reason="stipulated synthetic transport test")
    if pii == "present":
        raw["pii"] = [
            {
                "label": "PERSON_NAME",
                "start_char": 0,
                "end_char": 4,
                "matched_text": text[:4],
                "confidence": 0.8,
                "reason": "invented natural person",
            }
        ]
    if mnpi == "present":
        start = text.index("Acme")
        raw["mnpi"] = [
            {
                "start_char": start,
                "end_char": len(text),
                "matched_text": text[start:],
                "potential_materiality": "potentially_material",
                "public_status": "claimed_nonpublic",
                "confidence": 0.8,
                "reason": "stipulated nonpublic issuer acquisition in fictional scenario",
            }
        ]
    return corpus.validate_annotations(raw, text)


def quadrant_transport(*, force_quadrant=None, unknown=False):
    requests, sources = [], {}

    def handle(request):
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"input_tokens": 100})
        data = json.loads(body["input"])
        if body["model"] == "fake-generator":
            quadrant = force_quadrant or data["requested_quadrant"]
            text = QUADRANT_TEXT[quadrant] + f" Variant {data['variant']}."
            sources[text] = quadrant
            output = {"text": text}
        else:
            output = quadrant_annotation(sources[data["text"]], data["text"])
            if unknown:
                output["document_labels"]["mnpi"]["state"] = "unknown"
        return httpx.Response(
            200,
            json={
                "id": "quadrant-test",
                "model": body["model"],
                "status": "completed",
                "service_tier": "default",
                "usage": {"input_tokens": 100, "output_tokens": 30},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]}],
            },
        )

    return httpx.MockTransport(handle), requests


def test_all_four_quadrants_have_judged_quotas_and_blind_three_judge_requests(tmp_path):
    cfg = config(4)
    mock, requests = quadrant_transport()
    output = tmp_path / "balanced"
    report = corpus.run(cfg, authorization(cfg), output, transport=mock)
    assert report["status"] == "completed" and report["accepted_documents"] == 4
    coverage = report["quadrant_coverage"]
    assert coverage["all_quadrants_covered"] and coverage["coverage_passed"]
    assert coverage["accepted"] == dict.fromkeys(corpus.QUADRANTS, 1)
    assert coverage["shortfall"] == dict.fromkeys(corpus.QUADRANTS, 0)
    records = [json.loads(x) for x in (output / "records.jsonl").read_text().splitlines()]
    assert {r["consensus"]["quadrant"] for r in records} == set(corpus.QUADRANTS)
    for category in ("pii", "mnpi"):
        assert sum(report["evaluation"]["document_presence"]["counts"][category].values()) == 4
    judges = [body for path, body in requests if path.endswith("/responses") and body["model"] != "fake-generator"]
    assert len(judges) == 12
    for body in judges:
        data = json.loads(body["input"])
        assert "requested_quadrant" not in data and "document_labels" not in data and "sampling_instruction" not in data


def test_generation_intent_does_not_fill_a_judged_quadrant_and_refill_is_bounded(tmp_path):
    cfg = config(4)
    cfg["max_candidates"] = 6
    mock, requests = quadrant_transport(force_quadrant="pii_only")
    report = corpus.run(cfg, authorization(cfg), tmp_path / "mismatch", transport=mock)
    assert report["status"] == "coverage_shortfall" and report["accepted_documents"] == 1
    assert report["attempted_candidates"] == 6 and report["unattempted_candidates"] == 0
    assert report["quadrant_coverage"]["accepted"] == dict(neither=0, pii_only=1, mnpi_only=0, both=0)
    assert report["quadrant_coverage"]["observed_including_excess"]["pii_only"] == 6
    assert len([p for p, b in requests if p.endswith("/responses")]) == 24


def test_unknown_document_votes_are_retained_without_negative_quadrant_credit(tmp_path):
    cfg = config(4)
    mock, _ = quadrant_transport(unknown=True)
    output = tmp_path / "unknown"
    report = corpus.run(cfg, authorization(cfg), output, transport=mock)
    assert report["accepted_documents"] == 0 and report["status"] == "coverage_shortfall"
    assert report["quadrant_coverage"]["observed_including_excess"]["unknown"] == 4
    assert report["evaluation"]["pii"]["status"] == "unavailable"
    assert all(not json.loads(line)["accepted"] for line in (output / "records.jsonl").read_text().splitlines())


def test_document_confusion_counts_cover_tp_fp_tn_fn_for_each_target(tmp_path):
    from types import SimpleNamespace

    cfg = config(4)
    mock, _ = quadrant_transport()

    def review(*, text, **kwargs):
        categories = (
            []
            if text.startswith("Generic")
            else ["MNPI"]
            if text.startswith("Alex joined")
            else ["PII"]
            if text.startswith("Acme")
            else ["PII", "MNPI"]
        )
        return SimpleNamespace(
            findings=[SimpleNamespace(category=c, rule="email", start_char=0, end_char=4) for c in categories],
            sensitivity={
                c.lower(): {"state": "present" if c in categories else "not_detected"} for c in ("PII", "MNPI")
            },
        )

    with patch("junas.review.engine.PreSendReviewEngine.review", side_effect=review):
        report = corpus.run(cfg, authorization(cfg), tmp_path / "confusion", transport=mock)
    assert report["evaluation"]["document_presence"]["counts"] == {
        category: dict(tp=1, fp=1, tn=1, fn=1, unknown=0) for category in ("pii", "mnpi")
    }


def test_prepared_200_document_plan_is_offline_and_prices_all_allowed_attempts():
    cfg = corpus.validate_config(json.loads((corpus.ROOT / "config/model_corpus.200.json").read_text()))
    with patch("httpx.Client", side_effect=AssertionError("offline only")):
        report = corpus.plan(cfg)
    assert report["documents"] == 200 and report["max_candidates"] == 300
    assert report["quadrant_targets"] == dict.fromkeys(corpus.QUADRANTS, 50)
    assert report["first_pass_model_calls"] == 800 and report["model_calls"] == 2100
    assert Decimal(report["target_first_pass_token_cost_ceiling_usd"]) == Decimal("92.536")
    assert Decimal(report["configured_token_cost_ceiling_usd"]) == Decimal("236.832")
    assert not report["live_calls_authorized"]


@pytest.mark.parametrize(
    "materiality,publicity,state",
    [
        ("potentially_material", "claimed_nonpublic", "present"),
        ("potentially_material", "claimed_public", "absent"),
        ("not_material", "claimed_nonpublic", "absent"),
        ("not_material", "claimed_public", "absent"),
    ],
)
def test_mnpi_materiality_publicity_truth_table(materiality, publicity, state):
    raw = annotation()
    raw["mnpi"] = [
        {k: v for k, v in raw["pii"][0].items() if k != "label"}
        | {
            "potential_materiality": materiality,
            "public_status": publicity,
        }
    ]
    raw["document_labels"]["mnpi"]["state"] = state
    corpus.validate_annotations(raw, TEXT)
    result = corpus.consensus([raw, copy.deepcopy(raw), copy.deepcopy(raw)])
    assert result["document_labels"]["mnpi"]["state"] == state
    assert result["quadrant"] == ("both" if state == "present" else "pii_only")


def test_prepared_size_mock_run_stops_at_200_accepted_not_300_candidates(tmp_path):
    cfg = config(200)
    cfg["max_candidates"] = 300
    mock, requests = quadrant_transport()
    report = corpus.run(cfg, authorization(cfg), tmp_path / "two-hundred-mocked", transport=mock)
    assert report["accepted_documents"] == report["attempted_candidates"] == 200
    assert report["unattempted_candidates"] == 100 and report["status"] == "completed"
    assert report["quadrant_coverage"]["accepted"] == dict.fromkeys(corpus.QUADRANTS, 50)
    assert report["accepted_reference_tiers"] == {"unanimous": 200}
    assert len(requests) == 1600


def test_document_dissent_is_reported_even_when_spans_match(tmp_path):
    raw = annotation()
    raw["document_labels"]["mnpi"]["state"] = "unknown"
    mock, _ = transport(judge_b=raw)
    cfg = config()
    report = corpus.run(cfg, authorization(cfg), tmp_path / "document-dissent", transport=mock)
    assert report["disputed_documents"] == 1 and report["unresolved_documents"] == 0
    assert report["accepted_reference_tiers"] == {"majority": 1}


def test_cli_returns_failure_for_coverage_shortfall(tmp_path):
    cfg = config(4)
    conf = tmp_path / "config.json"
    auth = tmp_path / "auth.json"
    conf.write_text(json.dumps(cfg))
    auth.write_text(json.dumps(authorization(cfg)))
    with patch.object(corpus, "run", return_value={"status": "coverage_shortfall"}):
        assert (
            corpus.main(["run", "--config", str(conf), "--authorization", str(auth), "--output", str(tmp_path / "out")])
            == 1
        )


def spending_limit():
    cfg = json.loads((corpus.ROOT / "config/model_corpus.200.json").read_text())
    limit = copy.deepcopy(cfg["spending_limit"])
    limit["fx_checked_on"] = date.today().isoformat()
    return limit


def test_same_model_repeats_is_explicit_and_each_sample_is_attributable(tmp_path):
    cfg = config()
    cfg["judge_mode"] = "same_model_repeats"
    cfg["judges"] = [copy.deepcopy(cfg["judges"][0]) for _ in range(3)]
    corpus.validate_config(cfg)
    mock, requests = transport()
    output = tmp_path / "repeated-model"
    report = corpus.run(cfg, authorization(cfg), output, transport=mock)
    assert report["judge_mode"] == "same_model_repeats" and report["unique_judge_models"] == 1
    plan = corpus.plan(cfg)
    assert "not cross-model" in plan["voting_interpretation"]
    record = json.loads((output / "records.jsonl").read_text())
    assert [a["judge_pass"] for a in record["annotations"]] == [1, 2, 3]
    assert len({a["model"] for a in record["annotations"]}) == 1
    judge_inputs = [
        json.loads(body["input"])
        for path, body in requests
        if path.endswith("/responses") and body["model"] != "fake-generator"
    ]
    assert [x["judge_pass"] for x in judge_inputs] == [1, 2, 3]
    assert all("annotations" not in x and x["text"] == TEXT for x in judge_inputs)
    assert record["consensus"]["independence"] == "not_established"


@pytest.mark.parametrize(
    "mode,mutation",
    [
        ("distinct_models", "duplicates"),
        ("same_model_repeats", "mixed_models"),
        ("same_model_repeats", "mixed_limits"),
        ("same_model_repeats", "generator_overlap"),
        ("unsupported", "duplicates"),
    ],
)
def test_invalid_repeat_modes_do_not_silently_change_the_experiment(mode, mutation):
    cfg = config()
    cfg["judge_mode"] = mode
    if mutation != "mixed_models":
        cfg["judges"] = [copy.deepcopy(cfg["judges"][0]) for _ in range(3)]
    if mutation == "mixed_limits":
        cfg["judges"][1]["max_output_tokens"] += 1
    if mutation == "generator_overlap":
        cfg["generator"] = copy.deepcopy(cfg["judges"][0])
    with pytest.raises(ValueError):
        corpus.validate_config(cfg)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cap_sgd", "40"),
        ("provider_cap_usd", "30"),
        ("sgd_per_usd_ceiling", "NaN"),
        ("extra_charge_multiplier", "0.9"),
        ("prior_cost_reserve_usd", "0"),
        ("currency", "USD"),
    ],
)
def test_sgd_allowance_rejects_invalid_or_excessive_conversion_scenarios(field, value):
    limit = spending_limit()
    limit[field] = value
    with pytest.raises(ValueError):
        corpus.validate_spending_limit(limit)


def test_sgd_plan_limits_provider_budget_and_includes_prior_cost_and_fee_reserves():
    cfg = config()
    cfg["spending_limit"] = spending_limit()
    plan = corpus.plan(cfg)
    assert plan["spending_limit"]["sgd_scenario_ceiling"] == "46.80"
    assert Decimal(plan["spending_limit"]["provider_cap_usd"]) == Decimal("25")
    assert Decimal(plan["effective_run_token_cost_ceiling_usd"]) <= Decimal("25")
    auth = authorization(cfg, "25")
    auth.update(funding_basis="explicit_billable_cap", available_credit_usd=None, credits_apply=None)
    assert corpus.validate_authorization(auth, cfg) == Decimal("25")
    auth["budget_usd"] = "25.01"
    with pytest.raises(ValueError, match="USD spending limit"):
        corpus.validate_authorization(auth, cfg)


def test_over_limit_authorization_fails_before_transport_or_output(tmp_path):
    cfg = config()
    cfg["spending_limit"] = spending_limit()
    auth = authorization(cfg, "26")
    with patch("httpx.Client", side_effect=AssertionError("no provider requests")):
        with pytest.raises(ValueError, match="USD spending limit"):
            corpus.run(cfg, auth, tmp_path / "over-budget")
    assert not (tmp_path / "over-budget").exists()


def test_budget_limited_repeated_model_run_stops_without_forcing_quadrants(tmp_path):
    cfg = config(4)
    cfg["judge_mode"] = "same_model_repeats"
    cfg["judges"] = [copy.deepcopy(cfg["judges"][0]) for _ in range(3)]
    cfg["spending_limit"] = spending_limit() | {"provider_cap_usd": "0.0007"}
    mock, requests = transport()
    report = corpus.run(cfg, authorization(cfg, "0.0007"), tmp_path / "budget-shortfall", transport=mock)
    assert report["stop_reason"] == "BudgetExhausted" and report["accepted_documents"] == 0
    assert not report["quadrant_coverage"]["coverage_passed"]
    assert report["charged_or_reserved_ceiling_usd"] == "0" and len(requests) == 1


def test_currency_and_model_revision_invalidates_the_prior_run_authorization():
    old = corpus.validate_config(json.loads((corpus.ROOT / "config/model_corpus.200.distinct.json").read_text()))
    current = corpus.validate_config(json.loads((corpus.ROOT / "config/model_corpus.200.json").read_text()))
    assert old.get("judge_mode", "distinct_models") == "distinct_models"
    assert current["judge_mode"] == "same_model_repeats"
    assert corpus.identity(old) != corpus.identity(current)
    with pytest.raises(ValueError, match="does not match"):
        corpus.validate_authorization(authorization(old), current)


def test_stale_fx_assumptions_refuse_live_spending():
    cfg = config()
    cfg["spending_limit"] = spending_limit() | {"fx_checked_on": "2000-01-01"}
    with pytest.raises(ValueError, match="recheck FX"):
        corpus.validate_authorization(authorization(cfg), cfg)


def test_entity_coverage_does_not_infer_bank_accounts_from_quadrants():
    cfg = config(4)
    cfg["entity_targets"] = dict.fromkeys(corpus.PII_RULE_MAP, 1)
    corpus.validate_config(cfg)
    assert corpus.entity_coverage([], cfg)["shortfall"]["BANK_ACCOUNT"] == 1
    records = [{"status": "completed", "accepted": True, "consensus": {"pii": [{"label": "BANK_ACCOUNT"}]}}]
    assert corpus.entity_coverage(records, cfg)["shortfall"]["BANK_ACCOUNT"] == 0
    records[0]["accepted"] = False
    assert corpus.entity_coverage(records, cfg)["shortfall"]["BANK_ACCOUNT"] == 1
