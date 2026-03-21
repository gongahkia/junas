import importlib.util
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import ValidationError

import backend.main as main
from backend.schemas import ClassifyRequest, MAX_CLASSIFY_TEXT_LENGTH
from test import observability_test_app as test_app


ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


def load_lexicon_module():
    path = ROOT / "layer1-lexicon" / "filter.py"
    spec = importlib.util.spec_from_file_location("test_lexicon_filter", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load lexicon module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClassifySchemaTests(unittest.TestCase):
    def test_text_limit_accepts_maximum_length(self):
        payload = ClassifyRequest(text="a" * MAX_CLASSIFY_TEXT_LENGTH)
        self.assertEqual(len(payload.text), MAX_CLASSIFY_TEXT_LENGTH)

    def test_text_limit_rejects_over_maximum_length(self):
        with self.assertRaises(ValidationError):
            ClassifyRequest(text="a" * (MAX_CLASSIFY_TEXT_LENGTH + 1))


class OffendingSpanApiTests(unittest.TestCase):
    def test_offending_spans_absent_by_default(self):
        hit = SimpleNamespace(
            rule="restricted_list",
            matched_text="Acme Corp",
            severity="high",
            detail="entity=Acme Corp ticker=ACME",
            score=5.0,
            start_char=0,
            end_char=9,
        )
        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=True, total_score=12.0, hits=[hit]),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post("/classify", json={"text": "Acme Corp"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["classification"], "LOW_RISK")
            self.assertIsNone(payload["offending_spans"])

    def test_offending_spans_present_when_requested(self):
        text = "alpha\nAcme Corp"
        hit = SimpleNamespace(
            rule="restricted_list",
            matched_text="Acme Corp",
            severity="high",
            detail="entity=Acme Corp ticker=ACME",
            score=5.0,
            start_char=6,
            end_char=15,
        )
        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=True, total_score=12.0, hits=[hit]),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post("/classify", json={"text": text, "include_offending_spans": True})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["classification"], "LOW_RISK")
            self.assertEqual(len(payload["offending_spans"]), 1)
            span = payload["offending_spans"][0]
            self.assertEqual(span["matched_text"], "Acme Corp")
            self.assertEqual(span["start_char"], 6)
            self.assertEqual(span["end_char"], 15)
            self.assertEqual(span["start_line"], 2)
            self.assertEqual(span["start_column"], 1)
            self.assertEqual(span["end_line"], 2)
            self.assertEqual(span["end_column"], 10)

    def test_offending_spans_include_classifier_window_for_model_only_risk(self):
        text = "public intro\nconfidential operating review\npublic outro"
        test_app.seed_test_state(
            pipeline=["lexicon", "model1"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=False),
                "model1": test_app.DummyModel1(
                    label="risk",
                    confidence=0.82,
                    risk_score=0.88,
                    top_window={
                        "start_char": 13,
                        "end_char": 42,
                        "text": "confidential operating review",
                        "risk_score": 0.88,
                    },
                    window_count=3,
                ),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify",
                json={"text": text, "include_offending_spans": True},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["classification"], "LOW_RISK")
            self.assertEqual(len(payload["offending_spans"]), 1)
            span = payload["offending_spans"][0]
            self.assertEqual(span["layer"], "model1")
            self.assertEqual(span["rule"], "sliding_window")
            self.assertEqual(span["matched_text"], "confidential operating review")
            self.assertEqual(span["start_char"], 13)
            self.assertEqual(span["end_char"], 42)
            self.assertIn("windows=3", span["detail"])

    def test_offending_spans_include_model2_window_for_high_risk(self):
        text = "public intro\nsensitive merger plans\npublic outro"
        test_app.seed_test_state(
            pipeline=["lexicon", "model1", "model2"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=False),
                "model1": test_app.DummyModel1(
                    label="risk",
                    confidence=0.91,
                    risk_score=0.91,
                    top_window={
                        "start_char": 13,
                        "end_char": 35,
                        "text": "sensitive merger plans",
                        "risk_score": 0.91,
                    },
                    window_count=3,
                ),
                "model2": test_app.DummyModel2(
                    label="high_risk",
                    confidence=0.84,
                    high_risk_score=0.84,
                    top_window={
                        "start_char": 13,
                        "end_char": 35,
                        "text": "sensitive merger plans",
                        "high_risk_score": 0.84,
                    },
                    window_count=3,
                ),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify",
                json={"text": text, "include_offending_spans": True},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["classification"], "HIGH_RISK")
            layers = [item["layer"] for item in payload["offending_spans"]]
            self.assertIn("model1", layers)
            self.assertIn("model2", layers)


class LexiconSpanExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex_mod = load_lexicon_module()
        cls.filter = cls.lex_mod.LexiconFilter()

    def test_money_threshold_hit_includes_offsets(self):
        text = "The deal is worth $2.5 billion."
        result = self.filter.run(text)
        hit = next(h for h in result.hits if h.rule == "money_threshold")
        self.assertEqual(text[hit.start_char:hit.end_char], "$2.5 billion")

    def test_restricted_list_hit_includes_offsets(self):
        text = "Acme Corp shared updated revenue guidance."
        result = self.filter.run(text)
        hit = next(h for h in result.hits if h.rule == "restricted_list")
        self.assertEqual(text[hit.start_char:hit.end_char], "Acme Corp")

    def test_presidio_email_hit_includes_offsets(self):
        text = "Contact jane@example.com for the internal memo."
        result = self.filter.run(text)
        hit = next(h for h in result.hits if h.rule == "presidio_email_address")
        self.assertEqual(text[hit.start_char:hit.end_char], "jane@example.com")

    def test_sentence_correlation_hit_includes_offsets(self):
        text = "Acme Corp is planning an acquisition of GlobalTech next quarter."
        result = self.filter.run(text)
        hit = next(h for h in result.hits if h.rule == "ner_event_entity_correlation")
        self.assertEqual(text[hit.start_char:hit.end_char], hit.matched_text)


if __name__ == "__main__":
    unittest.main()
