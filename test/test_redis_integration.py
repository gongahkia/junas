import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as main
import test.observability_test_app as test_app
from kaypoh.workflow.layer5_mosaic import inference as mosaic_inference
from test.integration_helpers import TemporaryRedisServer, load_json_fixture, require_env_flag


class RedisMosaicIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_env_flag(
            "KAYPOH_RUN_REDIS_INTEGRATION",
            reason="set KAYPOH_RUN_REDIS_INTEGRATION=1 to run live Redis-backed mosaic tests",
        )
        cls.redis_server = TemporaryRedisServer().start()
        cls.fixture = load_json_fixture("runtime_golden_corpus.json")

    @classmethod
    def tearDownClass(cls):
        cls.redis_server.stop()

    def setUp(self):
        self.redis_server.client.flushdb()

    def _aggregator(self, *, ttl_hours: float = 1.0, threshold: int = 2) -> mosaic_inference.MosaicAggregator:
        aggregator = mosaic_inference.MosaicAggregator(
            host=self.redis_server.host,
            port=self.redis_server.port,
            ttl_hours=ttl_hours,
            threshold=threshold,
            connect_timeout=0.2,
            socket_timeout=0.2,
            retry_attempts=1,
            retry_backoff_ms=0,
        )
        self.assertTrue(aggregator.connected)
        return aggregator

    def test_live_redis_dedupes_and_escalates_on_unique_fragments(self):
        aggregator = self._aggregator(threshold=self.fixture["mosaic_scenario"]["threshold"])
        entity_id = self.fixture["mosaic_scenario"]["entity_id"]
        events = self.fixture["mosaic_scenario"]["events"]

        first = aggregator.aggregate(
            entity_id=entity_id,
            is_low_risk=True,
            fragment_text=events[0]["text"],
            request_id=events[0]["request_id"],
            classification="LOW_RISK",
            model_scores={"model1": 0.95, "model2": 0.01},
        )
        duplicate = aggregator.aggregate(
            entity_id=entity_id,
            is_low_risk=True,
            fragment_text=events[1]["text"],
            request_id=events[1]["request_id"],
            classification="LOW_RISK",
            model_scores={"model1": 0.96, "model2": 0.01},
        )
        escalated = aggregator.aggregate(
            entity_id=entity_id,
            is_low_risk=True,
            fragment_text=events[2]["text"],
            request_id=events[2]["request_id"],
            classification="LOW_RISK",
            model_scores={"model1": 0.98, "model2": 0.02},
        )

        self.assertFalse(first["escalate_to_high_risk"])
        self.assertEqual(first["recent_event_count"], 1)
        self.assertEqual(first["unique_fragment_count"], 1)

        self.assertFalse(duplicate["escalate_to_high_risk"])
        self.assertEqual(duplicate["recent_event_count"], 2)
        self.assertEqual(duplicate["unique_fragment_count"], 1)

        self.assertTrue(escalated["escalate_to_high_risk"])
        self.assertEqual(escalated["recent_event_count"], 3)
        self.assertEqual(escalated["unique_fragment_count"], 2)
        self.assertCountEqual(
            escalated["matched_event_ids"],
            [event["request_id"] for event in events],
        )

    def test_live_redis_trims_expired_events(self):
        aggregator = self._aggregator(ttl_hours=(1.0 / 3600.0), threshold=2)
        entity_id = "trimmed-entity"

        with patch.object(mosaic_inference.time, "time", side_effect=[1000.0, 1002.5]):
            first = aggregator.aggregate(
                entity_id=entity_id,
                is_low_risk=True,
                fragment_text="First fragment",
                request_id="trim-1",
                classification="LOW_RISK",
                model_scores=None,
            )
            second = aggregator.aggregate(
                entity_id=entity_id,
                is_low_risk=True,
                fragment_text="Second fragment",
                request_id="trim-2",
                classification="LOW_RISK",
                model_scores=None,
            )

        self.assertEqual(first["recent_event_count"], 1)
        self.assertEqual(first["unique_fragment_count"], 1)
        self.assertEqual(second["recent_event_count"], 1)
        self.assertEqual(second["unique_fragment_count"], 1)
        self.assertEqual(second["matched_event_ids"], ["trim-2"])

    def test_redis_outage_only_degrades_mosaic_dependency(self):
        aggregator = mosaic_inference.MosaicAggregator(
            host="127.0.0.1",
            port=self.redis_server.port + 1000,
            ttl_hours=1.0,
            threshold=2,
            connect_timeout=0.1,
            socket_timeout=0.1,
            retry_attempts=1,
            retry_backoff_ms=0,
        )
        self.assertFalse(aggregator.connected)

        test_app.seed_test_state(
            pipeline=["model1", "model2", "mosaic"],
            optional_layers=["mosaic"],
            models={
                "model1": test_app.DummyModel1(label="risk", risk_score=0.92),
                "model2": test_app.DummyModel2(label="low_risk", high_risk_score=0.02),
                "mosaic": aggregator,
            },
        )

        with TestClient(main.app) as client:
            response = client.post(
                "/classify",
                json={
                    "text": self.fixture["mosaic_scenario"]["events"][0]["text"],
                    "entity_id": self.fixture["mosaic_scenario"]["entity_id"],
                },
            )

        payload = response.json()
        dependency_status = main.get_dependency_status()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["classification"], "LOW_RISK")
        self.assertFalse(payload["observability"]["degraded"])
        self.assertEqual(payload["mosaic"]["recent_event_count"], 0)
        self.assertEqual(payload["mosaic"]["unique_fragment_count"], 0)
        self.assertFalse(payload["mosaic"]["escalated"])
        self.assertIn("redis", dependency_status)
        self.assertFalse(dependency_status["redis"].healthy)


if __name__ == "__main__":
    unittest.main()
