import copy
import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from scripts import model_corpus as c
from scripts.corpus_recovery import recover
from test.test_model_corpus import authorization, config, transport


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")


def stopped(tmp_path, *, cap="1"):
    cfg = config(4)
    cfg["max_candidates"] = 8
    auth = authorization(cfg, cap)
    mock, requests = transport(fail=True)
    report = c.run(cfg, auth, tmp_path / "first", transport=mock)
    return cfg, auth, report, requests


def test_resume_retains_unknown_reserve_and_skips_incomplete_candidate(tmp_path):
    cfg, auth, first, _ = stopped(tmp_path)
    mock, requests = transport()
    second = c.run(cfg, auth, tmp_path / "second", transport=mock, resume_from=tmp_path / "first")
    data = [json.loads(line) for line in (tmp_path / "second/combined-records.jsonl").read_text().splitlines()]
    assert data[0]["document_id"] == "synthetic-0001" and not data[0]["accepted"]
    generations = [body for path, body in requests if path.endswith("/responses") and body["model"] == "fake-generator"]
    assert json.loads(generations[0]["input"])["variant"] == 1
    recovered = recover(cfg, auth, tmp_path / "second")
    assert recovered["charged"] == Decimal(second["charged_or_reserved_ceiling_usd"])
    assert recovered["charged"] >= Decimal(first["charged_or_reserved_ceiling_usd"])
    with pytest.raises(ValueError, match="already continued"):
        c.run(cfg, auth, tmp_path / "third", transport=mock, resume_from=tmp_path / "first")


def test_resume_never_resets_or_raises_original_cap(tmp_path):
    cfg, auth, report, _ = stopped(tmp_path, cap="0.0012")
    mock, requests = transport()
    second = c.run(cfg, auth, tmp_path / "second", transport=mock, resume_from=tmp_path / "first")
    assert second["stop_reason"] == "BudgetExhausted"
    assert not any(path.endswith("/responses") for path, _ in requests)
    assert second["charged_or_reserved_ceiling_usd"] == report["charged_or_reserved_ceiling_usd"]
    changed = dict(auth, budget_usd="2")
    with pytest.raises(ValueError, match="aggregate cap"):
        recover(cfg, changed, tmp_path / "second")


def test_hard_crash_after_response_keeps_durable_cost_and_source(tmp_path):
    cfg = config(4)
    cfg["max_candidates"] = 8
    auth = authorization(cfg)
    mock, _ = transport()
    real = c.OpenAIResearchClient.call

    def crash_after_generator(self, model, **kwargs):
        result = real(self, model, **kwargs)
        if kwargs["role"] == "generator":
            raise KeyboardInterrupt()
        return result

    with patch.object(c.OpenAIResearchClient, "call", crash_after_generator), pytest.raises(KeyboardInterrupt):
        c.run(cfg, auth, tmp_path / "crash", transport=mock)
    checkpoint = recover(cfg, auth, tmp_path / "crash")
    assert checkpoint["records"][0]["text"]
    assert not checkpoint["records"][0]["accepted"]
    assert checkpoint["charged"] > 0
    assert checkpoint["last_call"] == 1


def test_torn_journal_and_tampered_source_refuse_recovery(tmp_path):
    cfg, auth, _, _ = stopped(tmp_path)
    journal = tmp_path / "first/requests.jsonl"
    original = journal.read_text()
    journal.write_text(original + '{"partial":')
    with pytest.raises(ValueError, match="torn"):
        recover(cfg, auth, tmp_path / "first")
    journal.write_text(original)
    events = [json.loads(line) for line in original.splitlines()]
    events[1]["reserved_usd"] = "0"
    journal.write_text("".join(json.dumps(e) + "\n" for e in events))
    with pytest.raises(ValueError, match="reservation cost"):
        recover(cfg, auth, tmp_path / "first")


def test_diagnostics_exclude_exception_messages_and_secrets(tmp_path):
    cfg, auth, _, _ = stopped(tmp_path)
    diagnostic = json.loads(next((tmp_path / "first").glob("diagnostic-*.json")).read_text())
    assert diagnostic["exception_types"] == ["ReadTimeout"]
    assert diagnostic["http_status_codes"] == []
    assert "synthetic-secret" not in json.dumps(diagnostic)
    assert diagnostic["messages_headers_bodies_omitted"]


def test_completed_job_cannot_be_continued(tmp_path):
    cfg = config()
    mock, _ = transport()
    c.run(cfg, authorization(cfg), tmp_path / "done", transport=mock)
    with pytest.raises(ValueError, match="quotas already complete"):
        c.run(cfg, authorization(cfg), tmp_path / "again", transport=mock, resume_from=tmp_path / "done")


def test_source_or_consensus_edits_are_not_accepted_as_recovered_labels(tmp_path):
    cfg = config()
    mock, _ = transport()
    c.run(cfg, authorization(cfg), tmp_path / "done", transport=mock)
    snapshot = tmp_path / "done/candidate-0001.json"
    record = json.loads(snapshot.read_text())
    original = copy.deepcopy(record)
    record["text"] = "Tampered text"
    record["text_sha256"] = c.input_identity(record["text"])
    snapshot.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="source not linked"):
        recover(cfg, authorization(cfg), tmp_path / "done")
    original["consensus"]["quadrant"] = "both"
    snapshot.write_text(json.dumps(original))
    with pytest.raises(ValueError, match="modified consensus"):
        recover(cfg, authorization(cfg), tmp_path / "done")


def test_hard_crash_during_completion_keeps_reserve(tmp_path):
    cfg = config(4)
    cfg["max_candidates"] = 8
    from test.test_model_corpus import transport as working_transport

    working, _ = working_transport()

    def crash(request):
        if request.url.path.endswith("/responses"):
            raise KeyboardInterrupt()
        return working.handle_request(request)

    import httpx

    with pytest.raises(KeyboardInterrupt):
        c.run(cfg, authorization(cfg), tmp_path / "crash-reserve", transport=httpx.MockTransport(crash))
    checkpoint = recover(cfg, authorization(cfg), tmp_path / "crash-reserve")
    assert checkpoint["charged"] == c.token_cost(cfg["generator"], 100, 512)
    assert len(checkpoint["records"]) == 1 and not checkpoint["records"][0]["accepted"]


def test_active_segment_lock_refuses_concurrent_continuation(tmp_path):
    import fcntl

    cfg, auth, _, _ = stopped(tmp_path)
    with (tmp_path / "first/execution.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            c.run(cfg, auth, tmp_path / "blocked", resume_from=tmp_path / "first")
    assert not (tmp_path / "blocked").exists()


def test_changed_controller_refuses_resume_before_network(tmp_path):
    cfg, auth, _, _ = stopped(tmp_path)
    with patch.object(c, "controller_identity", return_value={"changed": "source"}):
        with pytest.raises(ValueError, match="controller changed"):
            c.run(cfg, auth, tmp_path / "changed-controller", resume_from=tmp_path / "first")
    assert not (tmp_path / "changed-controller").exists()
