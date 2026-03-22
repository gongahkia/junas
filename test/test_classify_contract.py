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
    path = ROOT / "backend/workflow/layer1-lexicon" / "filter.py"
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
            self.assertTrue(span["is_exact"])
            self.assertEqual(span["char_length"], 9)
            self.assertEqual(span["line_span"], 1)
            self.assertEqual(span["context_before"], "alpha\n")
            self.assertEqual(span["context_after"], "")
            self.assertEqual(span["score"], 5.0)
            self.assertEqual(span["score_type"], "rule_score")
            self.assertIsNone(span["window_index"])

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
                        "window_index": 1,
                        "token_count": 6,
                        "window_stride": 128,
                        "max_seq_len": 512,
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
            self.assertFalse(span["is_exact"])
            self.assertEqual(span["char_length"], 29)
            self.assertEqual(span["line_span"], 1)
            self.assertEqual(span["context_before"], "public intro\n")
            self.assertEqual(span["context_after"], "\npublic outro")
            self.assertEqual(span["score"], 0.88)
            self.assertEqual(span["score_type"], "risk_score")
            self.assertEqual(span["window_index"], 1)
            self.assertEqual(span["window_count"], 3)
            self.assertEqual(span["window_token_count"], 6)
            self.assertEqual(span["window_stride"], 128)
            self.assertEqual(span["window_max_seq_len"], 512)
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
                        "window_index": 1,
                        "token_count": 5,
                        "window_stride": 128,
                        "max_seq_len": 512,
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
                        "window_index": 1,
                        "token_count": 5,
                        "window_stride": 128,
                        "max_seq_len": 512,
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
            spans_by_layer = {item["layer"]: item for item in payload["offending_spans"]}
            self.assertIn("model1", spans_by_layer)
            self.assertIn("model2", spans_by_layer)
            self.assertEqual(spans_by_layer["model2"]["score_type"], "high_risk_score")
            self.assertEqual(spans_by_layer["model2"]["window_count"], 3)

    def test_offending_spans_support_multiline_exact_hits(self):
        text = "alpha\nAcme Corp\nProject Atlas\nomega"
        hit = SimpleNamespace(
            rule="restricted_list",
            matched_text="Acme Corp\nProject Atlas",
            severity="high",
            detail="entity=Acme Corp project=Atlas",
            score=7.0,
            start_char=6,
            end_char=29,
        )
        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=True, total_score=12.0, hits=[hit]),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify",
                json={"text": text, "include_offending_spans": True},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            span = payload["offending_spans"][0]
            self.assertEqual(span["matched_text"], "Acme Corp\nProject Atlas")
            self.assertEqual(span["start_line"], 2)
            self.assertEqual(span["start_column"], 1)
            self.assertEqual(span["end_line"], 3)
            self.assertEqual(span["end_column"], 14)
            self.assertEqual(span["line_span"], 2)
            self.assertEqual(span["context_before"], "alpha\n")
            self.assertEqual(span["context_after"], "\nomega")

    def test_cached_response_preserves_offending_spans(self):
        class CountingRiskModel:
            def __init__(self):
                self.calls = 0

            def predict(self, text: str):
                self.calls += 1
                return SimpleNamespace(
                    label="risk",
                    confidence=0.87,
                    risk_score=0.87,
                    top_window={
                        "start_char": 13,
                        "end_char": 42,
                        "text": text[13:42],
                        "risk_score": 0.87,
                        "window_index": 1,
                        "token_count": 6,
                        "window_stride": 128,
                        "max_seq_len": 512,
                    },
                    window_count=3,
                )

        model = CountingRiskModel()
        test_app.seed_test_state(
            pipeline=["lexicon", "model1"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=False),
                "model1": model,
            },
        )

        text = "public intro\nconfidential operating review\npublic outro"
        with TestClient(test_app.app) as client:
            first = client.post("/classify", json={"text": text, "include_offending_spans": True})
            second = client.post("/classify", json={"text": text, "include_offending_spans": True})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(model.calls, 1)
        self.assertEqual(first.json()["observability"]["cache_status"], "miss")
        self.assertEqual(second.json()["observability"]["cache_status"], "hit")
        self.assertEqual(first.json()["offending_spans"], second.json()["offending_spans"])

    def test_cache_key_distinguishes_include_offending_spans(self):
        class CountingRiskModel:
            def __init__(self):
                self.calls = 0

            def predict(self, text: str):
                self.calls += 1
                return SimpleNamespace(
                    label="risk",
                    confidence=0.91,
                    risk_score=0.91,
                    top_window={
                        "start_char": 8,
                        "end_char": 30,
                        "text": text[8:30],
                        "risk_score": 0.91,
                        "window_index": 0,
                        "token_count": 5,
                        "window_stride": 128,
                        "max_seq_len": 512,
                    },
                    window_count=2,
                )

        model = CountingRiskModel()
        test_app.seed_test_state(
            pipeline=["lexicon", "model1"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=False),
                "model1": model,
            },
        )

        text = "public\nsensitive roadmap\npublic"
        with TestClient(test_app.app) as client:
            no_spans = client.post("/classify", json={"text": text})
            with_spans = client.post("/classify", json={"text": text, "include_offending_spans": True})
            with_spans_cached = client.post("/classify", json={"text": text, "include_offending_spans": True})

        self.assertEqual(no_spans.status_code, 200)
        self.assertEqual(with_spans.status_code, 200)
        self.assertEqual(with_spans_cached.status_code, 200)
        self.assertEqual(model.calls, 2)
        self.assertIsNone(no_spans.json()["offending_spans"])
        self.assertEqual(with_spans.json()["observability"]["cache_status"], "miss")
        self.assertEqual(with_spans_cached.json()["observability"]["cache_status"], "hit")
        self.assertEqual(len(with_spans.json()["offending_spans"]), 1)


class BatchClassifyApiTests(unittest.TestCase):
    def test_batch_classify_preserves_per_item_contracts(self):
        class RoutingLexicon:
            def run(self, text: str):
                if "Acme Corp" in text:
                    return SimpleNamespace(
                        flagged=True,
                        high_risk_short_circuit=False,
                        total_score=12.0,
                        score_threshold=10.0,
                        score_threshold_exceeded=True,
                        hits=[
                            SimpleNamespace(
                                rule="restricted_list",
                                matched_text="Acme Corp",
                                severity="high",
                                detail="entity=Acme Corp ticker=ACME",
                                score=5.0,
                                start_char=text.index("Acme Corp"),
                                end_char=text.index("Acme Corp") + len("Acme Corp"),
                            )
                        ],
                        restricted_entities_found=[{"name": "Acme Corp", "ticker": "ACME"}],
                    )
                return SimpleNamespace(
                    flagged=False,
                    high_risk_short_circuit=False,
                    total_score=0.0,
                    score_threshold=10.0,
                    score_threshold_exceeded=False,
                    hits=[],
                    restricted_entities_found=[],
                )

        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={"lexicon": RoutingLexicon()},
        )

        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify/batch",
                json={
                    "items": [
                        {"text": "Memo: Acme Corp is buying GlobalTech.", "include_offending_spans": True},
                        {"text": "Public earnings call next week."},
                    ]
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 2)
        first, second = payload["results"]
        self.assertEqual(first["classification"], "LOW_RISK")
        self.assertEqual(second["classification"], "SAFE")
        self.assertTrue(first["request_id"].endswith(":0"))
        self.assertTrue(second["request_id"].endswith(":1"))
        self.assertEqual(first["offending_spans"][0]["matched_text"], "Acme Corp")
        self.assertIsNone(second["offending_spans"])

    def test_batch_classify_rejects_more_than_32_items(self):
        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={"lexicon": test_app.DummyLexiconFilter(flagged=False)},
        )

        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify/batch",
                json={"items": [{"text": f"sample {index}"} for index in range(33)]},
            )

        self.assertEqual(response.status_code, 422)


class LexiconSpanExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex_mod = load_lexicon_module()
        cls.filter = cls.lex_mod.LexiconFilter()

    def test_dynamic_score_threshold_increases_with_text_length(self):
        original_mode = self.lex_mod.LEXICON_SCORE_THRESHOLD_MODE
        original_chars_per_point = self.lex_mod.LEXICON_DYNAMIC_CHARS_PER_POINT
        original_increment = self.lex_mod.LEXICON_DYNAMIC_THRESHOLD_INCREMENT
        try:
            self.lex_mod.LEXICON_SCORE_THRESHOLD_MODE = "dynamic"
            self.lex_mod.LEXICON_DYNAMIC_CHARS_PER_POINT = 10.0
            self.lex_mod.LEXICON_DYNAMIC_THRESHOLD_INCREMENT = 2.0

            short_result = self.filter.run("abcde")
            long_result = self.filter.run("a" * 25)

            self.assertEqual(short_result.score_threshold, 11.0)
            self.assertEqual(long_result.score_threshold, 15.0)
            self.assertGreater(long_result.score_threshold, short_result.score_threshold)
        finally:
            self.lex_mod.LEXICON_SCORE_THRESHOLD_MODE = original_mode
            self.lex_mod.LEXICON_DYNAMIC_CHARS_PER_POINT = original_chars_per_point
            self.lex_mod.LEXICON_DYNAMIC_THRESHOLD_INCREMENT = original_increment

    def test_dynamic_score_threshold_can_prevent_info_only_flag_on_longer_text(self):
        original_mode = self.lex_mod.LEXICON_SCORE_THRESHOLD_MODE
        original_chars_per_point = self.lex_mod.LEXICON_DYNAMIC_CHARS_PER_POINT
        original_increment = self.lex_mod.LEXICON_DYNAMIC_THRESHOLD_INCREMENT
        original_money = self.filter._check_money_threshold
        original_pct = self.filter._check_pct_threshold
        original_restricted = self.filter._check_restricted_list
        original_ner = self.filter._check_ner
        original_presidio = self.filter._check_presidio
        try:
            self.lex_mod.LEXICON_SCORE_THRESHOLD_MODE = "dynamic"
            self.lex_mod.LEXICON_DYNAMIC_CHARS_PER_POINT = 10.0
            self.lex_mod.LEXICON_DYNAMIC_THRESHOLD_INCREMENT = 1.0

            self.filter._check_money_threshold = lambda text: []
            self.filter._check_pct_threshold = lambda text: []
            self.filter._check_restricted_list = lambda text: ([], [])
            self.filter._check_ner = lambda text: [
                self.lex_mod.LexiconHit(rule="ner_org", matched_text="alpha", severity="info")
                for _ in range(22)
            ]
            self.filter._check_presidio = lambda text: []

            short_result = self.filter.run("short")
            long_result = self.filter.run("a" * 30)

            self.assertEqual(short_result.total_score, 11.0)
            self.assertTrue(short_result.score_threshold_exceeded)
            self.assertTrue(short_result.flagged)

            self.assertEqual(long_result.total_score, 11.0)
            self.assertFalse(long_result.score_threshold_exceeded)
            self.assertFalse(long_result.flagged)
        finally:
            self.lex_mod.LEXICON_SCORE_THRESHOLD_MODE = original_mode
            self.lex_mod.LEXICON_DYNAMIC_CHARS_PER_POINT = original_chars_per_point
            self.lex_mod.LEXICON_DYNAMIC_THRESHOLD_INCREMENT = original_increment
            self.filter._check_money_threshold = original_money
            self.filter._check_pct_threshold = original_pct
            self.filter._check_restricted_list = original_restricted
            self.filter._check_ner = original_ner
            self.filter._check_presidio = original_presidio

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
