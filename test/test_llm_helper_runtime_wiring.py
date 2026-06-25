import os
import tempfile
import textwrap
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import junas.backend.main as main
from junas.configs import runtime
from junas.review.engine import PreSendReviewEngine


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class LedgerExtractor:
    def __init__(self):
        self.calls = 0
        self._events = []

    def extract(self, preamble: str) -> list[str]:
        self.calls += 1
        self._events.append(
            {
                "destination": "test_llm",
                "operation": "llm_defined_terms",
                "allowed": True,
                "reason": "test helper approved",
                "query": "",
                "redactions": [],
                "input_mode": "raw_preamble",
                "content_sha256": "a" * 64,
                "content_type": "text/plain",
            }
        )
        return ["Seller"]

    def pop_privacy_ledger_events(self) -> list[dict]:
        events = list(self._events)
        self._events.clear()
        return events


class LedgerAuditor:
    def __init__(self):
        self.calls = 0
        self._events = []

    def audit(self, *, findings, body_hash, document_type):
        self.calls += 1
        self._events.append(
            {
                "destination": "test_llm",
                "operation": "llm_coverage_audit",
                "allowed": True,
                "reason": "test helper approved",
                "query": "",
                "redactions": [],
                "input_mode": "structured_summary",
                "content_sha256": body_hash,
                "content_type": "application/json",
            }
        )
        return [{"rule_guess": "embargo_marker", "why": "possible missing embargo", "confidence": 0.4}]

    def pop_privacy_ledger_events(self) -> list[dict]:
        events = list(self._events)
        self._events.clear()
        return events


class LLMHelperRuntimeWiringTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        os.environ["JUNAS_JOURNAL_DIR"] = self._tmpdir.name
        self.addCleanup(lambda: os.environ.pop("JUNAS_JOURNAL_DIR", None))
        main.app.router.lifespan_context = _noop_lifespan
        main.app.openapi_schema = None
        main._state.clear()

    def _settings_from_config(self, content: str):
        path = Path(self._tmpdir.name) / "config.toml"
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return runtime.load_runtime_settings(cli_overrides={"config_path": str(path)})

    def test_defined_term_helper_privacy_ledger_is_returned_under_audit_grade(self):
        extractor = LedgerExtractor()
        engine = PreSendReviewEngine(llm_defined_term_extractor=extractor)

        result = engine.review(
            text="Mr Seller shall execute the contract.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="SPA",
            review_profile="audit_grade",
        )

        self.assertEqual(extractor.calls, 1)
        self.assertEqual(result.privacy_ledger[0]["operation"], "llm_defined_terms")
        self.assertEqual(result.privacy_ledger[0]["input_mode"], "raw_preamble")

    def test_strict_profile_does_not_emit_helper_privacy_ledger(self):
        extractor = LedgerExtractor()
        engine = PreSendReviewEngine(llm_defined_term_extractor=extractor)

        result = engine.review(
            text="Mr Seller shall execute the contract.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="SPA",
            review_profile="strict",
        )

        self.assertEqual(extractor.calls, 0)
        self.assertEqual(result.privacy_ledger, [])

    def test_coverage_audit_helper_privacy_ledger_is_returned_under_audit_grade(self):
        auditor = LedgerAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)

        result = engine.review(
            text="Acme acquisition for $2.5 billion is pending.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
            review_profile="audit_grade",
        )

        self.assertEqual(auditor.calls, 1)
        operations = [entry["operation"] for entry in result.privacy_ledger]
        self.assertIn("llm_coverage_audit", operations)
        self.assertEqual(result.coverage_warnings[0]["rule_guess"], "embargo_marker")

    def test_diagnostics_and_readiness_surface_configured_helper_dependency(self):
        settings = self._settings_from_config(
            """
            [pipeline]
            layers = []

            [llm_helpers]
            defined_terms_enabled = true
            """
        )
        main._state["settings"] = settings
        main._state["pipeline"] = []
        main._state["models"] = {}
        main._state["lazy_loaders"] = {}
        main._state["warming_required_layers"] = []
        main._state["load_errors"] = []
        main._state["startup_timings_ms"] = {}
        main._state["runtime_layer_errors"] = {}

        with TestClient(main.app) as client:
            diagnostics = client.get("/diagnostics")
            ready = client.get("/ready")

        self.assertEqual(diagnostics.status_code, 200)
        helper_status = diagnostics.json()["dependency_status"]["llm_defined_term_extractor"]
        self.assertTrue(helper_status["configured"])
        self.assertFalse(helper_status["healthy"])
        self.assertIn("requires llm.enabled=true", helper_status["detail"])
        self.assertEqual(ready.status_code, 200)
        self.assertFalse(ready.json()["ready"])
        self.assertIn("llm_defined_term_extractor unavailable", " ".join(ready.json()["reasons"]))


if __name__ == "__main__":
    unittest.main()
