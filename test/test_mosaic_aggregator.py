import unittest
from unittest.mock import patch

from kaypoh.workflow.layer5_mosaic import inference as mosaic_inference


class FakeRedisPipeline:
    def __init__(self, client: "FakeRedis"):
        self.client = client
        self.ops: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        def recorder(*args, **kwargs):
            self.ops.append((name, args, kwargs))
            return self

        return recorder

    def execute(self):
        results = []
        for name, args, kwargs in self.ops:
            results.append(getattr(self.client, name)(*args, **kwargs))
        self.ops.clear()
        return results


class FakeRedis:
    def __init__(self, now_fn):
        self.now_fn = now_fn
        self.values: dict[str, str] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.expirations: dict[str, float] = {}

    def _current_time(self) -> float:
        return float(self.now_fn())

    def _purge_expired(self) -> None:
        now = self._current_time()
        expired = [key for key, expiry in self.expirations.items() if now >= expiry]
        for key in expired:
            self.values.pop(key, None)
            self.zsets.pop(key, None)
            self.expirations.pop(key, None)

    @staticmethod
    def _score(value):
        if isinstance(value, str):
            if value == "+inf":
                return float("inf")
            if value == "-inf":
                return float("-inf")
        return float(value)

    def ping(self):
        return True

    def pipeline(self):
        return FakeRedisPipeline(self)

    def zadd(self, key: str, mapping: dict[str, float]):
        self._purge_expired()
        bucket = self.zsets.setdefault(key, {})
        for member, score in mapping.items():
            bucket[str(member)] = float(score)
        return len(mapping)

    def zrangebyscore(self, key: str, min_score, max_score):
        self._purge_expired()
        minimum = self._score(min_score)
        maximum = self._score(max_score)
        members = [
            member
            for member, score in self.zsets.get(key, {}).items()
            if minimum <= score <= maximum
        ]
        return sorted(members, key=lambda item: self.zsets[key][item])

    def zrevrangebyscore(self, key: str, max_score, min_score):
        self._purge_expired()
        minimum = self._score(min_score)
        maximum = self._score(max_score)
        members = [
            member
            for member, score in self.zsets.get(key, {}).items()
            if minimum <= score <= maximum
        ]
        return sorted(members, key=lambda item: self.zsets[key][item], reverse=True)

    def zremrangebyscore(self, key: str, min_score, max_score):
        self._purge_expired()
        minimum = self._score(min_score)
        maximum = self._score(max_score)
        bucket = self.zsets.get(key, {})
        expired = [member for member, score in bucket.items() if minimum <= score <= maximum]
        for member in expired:
            bucket.pop(member, None)
        if not bucket:
            self.zsets.pop(key, None)
        return len(expired)

    def set(self, key: str, value: str):
        self._purge_expired()
        self.values[key] = value
        return True

    def get(self, key: str):
        self._purge_expired()
        return self.values.get(key)

    def expire(self, key: str, ttl_seconds: int):
        self._purge_expired()
        if key in self.values or key in self.zsets:
            self.expirations[key] = self._current_time() + float(ttl_seconds)
            return True
        return False

    def delete(self, key: str):
        self.values.pop(key, None)
        self.zsets.pop(key, None)
        self.expirations.pop(key, None)
        return 1


class MosaicAggregatorTests(unittest.TestCase):
    def setUp(self):
        self.now = [1000.0]

        def _now():
            return self.now[0]

        self.now_fn = _now

    def _aggregator(self, *, ttl_hours: float = 1.0, threshold: int = 2) -> mosaic_inference.MosaicAggregator:
        with patch.object(mosaic_inference.MosaicAggregator, "_connect", return_value=False):
            aggregator = mosaic_inference.MosaicAggregator(
                host="localhost",
                port=6379,
                ttl_hours=ttl_hours,
                threshold=threshold,
            )
        aggregator.redis = FakeRedis(self.now_fn)
        aggregator.connected = True
        return aggregator

    def test_unique_fragment_threshold_ignores_duplicate_content(self):
        aggregator = self._aggregator()

        with patch.object(mosaic_inference.time, "time", side_effect=self.now_fn):
            first = aggregator.aggregate(
                entity_id="Acme Corp",
                is_low_risk=True,
                fragment_text="Repeated low risk fragment",
                request_id="req-1",
            )
            second = aggregator.aggregate(
                entity_id="Acme Corp",
                is_low_risk=True,
                fragment_text="Repeated   low risk   fragment",
                request_id="req-2",
            )
            third = aggregator.aggregate(
                entity_id="Acme Corp",
                is_low_risk=True,
                fragment_text="Second distinct fragment",
                request_id="req-3",
            )

        self.assertFalse(first["escalate_to_high_risk"])
        self.assertEqual(first["recent_event_count"], 1)
        self.assertEqual(first["unique_fragment_count"], 1)

        self.assertFalse(second["escalate_to_high_risk"])
        self.assertEqual(second["recent_event_count"], 2)
        self.assertEqual(second["unique_fragment_count"], 1)
        self.assertEqual(second["count"], 1)

        self.assertTrue(third["escalate_to_high_risk"])
        self.assertEqual(third["recent_event_count"], 3)
        self.assertEqual(third["unique_fragment_count"], 2)
        self.assertCountEqual(third["matched_event_ids"], ["req-1", "req-2", "req-3"])

    def test_expired_events_are_trimmed_from_window(self):
        aggregator = self._aggregator(ttl_hours=1.0, threshold=2)

        with patch.object(mosaic_inference.time, "time", side_effect=self.now_fn):
            first = aggregator.aggregate(
                entity_id="Beta Corp",
                is_low_risk=True,
                fragment_text="First fragment",
                request_id="req-1",
            )
            self.now[0] += 3601.0
            second = aggregator.aggregate(
                entity_id="Beta Corp",
                is_low_risk=True,
                fragment_text="Second fragment",
                request_id="req-2",
            )

        self.assertEqual(first["recent_event_count"], 1)
        self.assertEqual(first["unique_fragment_count"], 1)
        self.assertEqual(second["recent_event_count"], 1)
        self.assertEqual(second["unique_fragment_count"], 1)
        self.assertEqual(second["matched_event_ids"], ["req-2"])


if __name__ == "__main__":
    unittest.main()
