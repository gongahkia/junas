import os
import time

import redis


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
        self.ttl_seconds = ttl_hours * 3600
        self.threshold = threshold
        self.connect_timeout = max(0.1, float(connect_timeout))
        self.socket_timeout = max(0.1, float(socket_timeout))
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_ms = max(0, int(retry_backoff_ms))
        self.redis = None
        self.connected = False

        for attempt in range(1, self.retry_attempts + 1):
            try:
                self.redis = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    decode_responses=True,
                    socket_connect_timeout=self.connect_timeout,
                    socket_timeout=self.socket_timeout,
                )
                self.redis.ping()
                self.connected = True
                break
            except (redis.ConnectionError, redis.TimeoutError):
                self.redis = None
                if attempt < self.retry_attempts:
                    time.sleep((self.retry_backoff_ms * attempt) / 1000.0)

        if not self.connected:
            print("Warning: Redis not connected. Mosaic layer will be a no-op.")

    @staticmethod
    def _normalize_entity_id(entity_id: str) -> str:
        # Normalize whitespace/casing to avoid fragmented counters for semantically identical IDs.
        normalized = " ".join(entity_id.strip().split()).lower()
        return normalized

    def aggregate(self, entity_id: str, is_low_risk: bool):
        if not self.connected or not entity_id or self.redis is None:
            return {"escalate_to_high_risk": False, "count": 0}

        entity_id = self._normalize_entity_id(entity_id)
        if not entity_id:
            return {"escalate_to_high_risk": False, "count": 0}

        key = f"mosaic:entity:{entity_id}"

        try:
            if is_low_risk:
                current_count = self.redis.incr(key)
                if current_count == 1:
                    # Set TTL only on creation to track within a fixed window
                    self.redis.expire(key, self.ttl_seconds)
            else:
                hit = self.redis.get(key)
                current_count = int(hit) if hit else 0
        except redis.RedisError:
            # Fail open: keep classification flow alive if Redis has transient issues.
            self.connected = False
            return {"escalate_to_high_risk": False, "count": 0}

        escalate = current_count >= self.threshold
        return {"escalate_to_high_risk": bool(escalate), "count": current_count}

    @classmethod
    def load(cls):
        from config import get_config_val

        ttl_hours = get_config_val("mosaic", "ttl_hours", "MOSAIC_TTL_HOURS", "24", float)
        threshold = get_config_val("mosaic", "threshold", "MOSAIC_THRESHOLD", "10", int)
        redis_host = get_config_val("mosaic", "redis_host", "REDIS_HOST", "localhost", str)
        redis_port = get_config_val("mosaic", "redis_port", "REDIS_PORT", "6379", int)
        connect_timeout = get_config_val(
            "mosaic", "connect_timeout_seconds", "MOSAIC_CONNECT_TIMEOUT_SECONDS", "0.5", float
        )
        socket_timeout = get_config_val(
            "mosaic", "socket_timeout_seconds", "MOSAIC_SOCKET_TIMEOUT_SECONDS", "0.5", float
        )
        retry_attempts = get_config_val(
            "mosaic", "retry_attempts", "MOSAIC_RETRY_ATTEMPTS", "3", int
        )
        retry_backoff_ms = get_config_val(
            "mosaic", "retry_backoff_ms", "MOSAIC_RETRY_BACKOFF_MS", "100", int
        )

        return cls(
            host=redis_host,
            port=redis_port,
            ttl_hours=ttl_hours,
            threshold=threshold,
            connect_timeout=connect_timeout,
            socket_timeout=socket_timeout,
            retry_attempts=retry_attempts,
            retry_backoff_ms=retry_backoff_ms,
        )
