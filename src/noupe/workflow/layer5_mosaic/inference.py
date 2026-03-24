import hashlib
import json
import logging
import socket
import time
import uuid
from typing import Any

import redis

logger = logging.getLogger("noupe.mosaic")


class MosaicAggregator:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        ttl_hours: float = 24,
        threshold: int = 10,
        connect_timeout: float = 0.5,
        socket_timeout: float = 0.5,
        retry_attempts: int = 3,
        retry_backoff_ms: int = 100,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.ttl_seconds = int(ttl_hours * 3600)
        self.threshold = threshold
        self.connect_timeout = max(0.1, float(connect_timeout))
        self.socket_timeout = max(0.1, float(socket_timeout))
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_ms = max(0, int(retry_backoff_ms))
        self.redis = None
        self.connected = False

        self._connect()

    def _connect(self) -> bool:
        for attempt in range(1, self.retry_attempts + 1):
            try:
                with socket.create_connection((self.host, self.port), timeout=self.connect_timeout):
                    pass
                self.redis = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    decode_responses=True,
                    socket_connect_timeout=self.connect_timeout,
                    socket_timeout=self.socket_timeout,
                )
                self.redis.ping()
                self.connected = True
                return True
            except (OSError, redis.ConnectionError, redis.TimeoutError):
                self.redis = None
                self.connected = False
                if attempt < self.retry_attempts:
                    time.sleep((self.retry_backoff_ms * attempt) / 1000.0)

        logger.warning(
            "redis_unavailable: host=%s port=%s attempts=%s; mosaic operates as no-op",
            self.host,
            self.port,
            self.retry_attempts,
        )
        return False

    def _ensure_connection(self) -> bool:
        if self.connected and self.redis is not None:
            return True
        return self._connect()

    @staticmethod
    def _normalize_entity_id(entity_id: str) -> str:
        return " ".join(entity_id.strip().split()).lower()

    @staticmethod
    def _normalize_fragment(fragment_text: str | None) -> str:
        if not fragment_text:
            return ""
        return " ".join(fragment_text.strip().split()).lower()

    def _default_result(self, entity_id: str = "") -> dict[str, Any]:
        return {
            "entity_id": entity_id,
            "escalate_to_high_risk": False,
            "count": 0,
            "recent_event_count": 0,
            "unique_fragment_count": 0,
            "window_hours": round(self.ttl_seconds / 3600.0, 3),
            "threshold": self.threshold,
            "escalation_reason": "",
            "matched_event_ids": [],
        }

    def _entity_events_key(self, entity_id: str) -> str:
        return f"mosaic:entity:{entity_id}:events"

    def _event_key(self, event_id: str) -> str:
        return f"mosaic:event:{event_id}"

    def _trim_expired_events(self, events_key: str, min_score: float) -> None:
        if self.redis is None:
            return
        expired_ids = self.redis.zrangebyscore(events_key, 0, min_score)
        if not expired_ids:
            return

        pipeline = self.redis.pipeline()
        pipeline.zremrangebyscore(events_key, 0, min_score)
        for event_id in expired_ids:
            pipeline.delete(self._event_key(event_id))
        pipeline.execute()

    def _load_recent_events(self, events_key: str, *, now: float) -> list[dict[str, Any]]:
        if self.redis is None:
            return []

        min_score = now - self.ttl_seconds
        self._trim_expired_events(events_key, min_score)
        event_ids = self.redis.zrevrangebyscore(events_key, "+inf", min_score)
        if not event_ids:
            return []

        pipeline = self.redis.pipeline()
        for event_id in event_ids:
            pipeline.get(self._event_key(event_id))
        payloads = pipeline.execute()

        events: list[dict[str, Any]] = []
        for event_id, raw_payload in zip(event_ids, payloads):
            if not raw_payload:
                continue
            try:
                payload = json.loads(raw_payload)
            except Exception:
                continue
            payload["event_id"] = event_id
            events.append(payload)
        return events

    def _record_event(
        self,
        *,
        entity_id: str,
        fragment_hash: str,
        fragment_text: str,
        request_id: str | None,
        classification: str | None,
        model_scores: dict[str, float | None] | None,
        now: float,
    ) -> str:
        if self.redis is None:
            raise RuntimeError("redis client unavailable")

        event_id = request_id or uuid.uuid4().hex
        events_key = self._entity_events_key(entity_id)
        payload = {
            "entity_id": entity_id,
            "fragment_hash": fragment_hash,
            "fragment_preview": fragment_text[:160],
            "classification": classification or "LOW_RISK",
            "timestamp": now,
            "model_scores": model_scores or {},
        }

        pipeline = self.redis.pipeline()
        pipeline.zadd(events_key, {event_id: now})
        pipeline.set(self._event_key(event_id), json.dumps(payload, sort_keys=True))
        pipeline.expire(events_key, self.ttl_seconds)
        pipeline.expire(self._event_key(event_id), self.ttl_seconds)
        pipeline.execute()
        return event_id

    def _result_from_events(self, entity_id: str, events: list[dict[str, Any]], *, is_low_risk: bool) -> dict[str, Any]:
        fragment_hashes = {
            str(event.get("fragment_hash"))
            for event in events
            if event.get("fragment_hash")
        }
        unique_fragment_count = len(fragment_hashes)
        recent_event_count = len(events)
        escalate = bool(is_low_risk and unique_fragment_count >= self.threshold)
        reason = ""
        if escalate:
            reason = (
                f"{unique_fragment_count} unique low-risk fragments observed "
                f"within {round(self.ttl_seconds / 3600.0, 3)} hours"
            )
        return {
            "entity_id": entity_id,
            "escalate_to_high_risk": escalate,
            "count": unique_fragment_count,
            "recent_event_count": recent_event_count,
            "unique_fragment_count": unique_fragment_count,
            "window_hours": round(self.ttl_seconds / 3600.0, 3),
            "threshold": self.threshold,
            "escalation_reason": reason,
            "matched_event_ids": [str(event.get("event_id", "")) for event in events if event.get("event_id")],
        }

    def aggregate(
        self,
        entity_id: str,
        is_low_risk: bool,
        *,
        fragment_text: str | None = None,
        request_id: str | None = None,
        classification: str | None = None,
        model_scores: dict[str, float | None] | None = None,
    ) -> dict[str, Any]:
        if not entity_id:
            return self._default_result()

        normalized_entity_id = self._normalize_entity_id(entity_id)
        if not normalized_entity_id:
            return self._default_result()

        if not self._ensure_connection():
            return self._default_result(normalized_entity_id)

        fragment_hash = hashlib.sha256(
            self._normalize_fragment(fragment_text).encode("utf-8")
        ).hexdigest()
        events_key = self._entity_events_key(normalized_entity_id)

        for _ in range(2):
            try:
                now = time.time()
                if is_low_risk:
                    self._record_event(
                        entity_id=normalized_entity_id,
                        fragment_hash=fragment_hash,
                        fragment_text=self._normalize_fragment(fragment_text),
                        request_id=request_id,
                        classification=classification,
                        model_scores=model_scores,
                        now=now,
                    )
                events = self._load_recent_events(events_key, now=now)
                return self._result_from_events(normalized_entity_id, events, is_low_risk=is_low_risk)
            except redis.RedisError:
                self.connected = False
                self.redis = None
                if not self._ensure_connection():
                    return self._default_result(normalized_entity_id)

        return self._default_result(normalized_entity_id)

    @classmethod
    def load(cls):
        from noupe.configs.runtime import get_runtime_settings

        settings = get_runtime_settings().mosaic

        return cls(
            host=settings.redis_host,
            port=settings.redis_port,
            ttl_hours=settings.ttl_hours,
            threshold=settings.threshold,
            connect_timeout=settings.connect_timeout_seconds,
            socket_timeout=settings.socket_timeout_seconds,
            retry_attempts=settings.retry_attempts,
            retry_backoff_ms=settings.retry_backoff_ms,
        )
