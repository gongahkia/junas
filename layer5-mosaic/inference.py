import redis
import os

class MosaicAggregator:
    def __init__(self, host='localhost', port=6379, db=0, ttl_hours=24, threshold=10):
        self.ttl_seconds = ttl_hours * 3600
        self.threshold = threshold
        try:
            self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.redis.ping()
            self.connected = True
        except redis.ConnectionError:
            self.redis = None
            self.connected = False
            print("Warning: Redis not connected. Mosaic layer will be a no-op.")

    @staticmethod
    def _normalize_entity_id(entity_id: str) -> str:
        # Normalize whitespace/casing to avoid fragmented counters for semantically identical IDs.
        normalized = " ".join(entity_id.strip().split()).lower()
        return normalized
            
    def aggregate(self, entity_id: str, is_low_risk: bool):
        if not self.connected or not entity_id:
            return {"escalate_to_high_risk": False, "count": 0}

        entity_id = self._normalize_entity_id(entity_id)
        if not entity_id:
            return {"escalate_to_high_risk": False, "count": 0}
            
        key = f"mosaic:entity:{entity_id}"
        
        if is_low_risk:
            current_count = self.redis.incr(key)
            if current_count == 1:
                # Set TTL only on creation to track within a fixed window
                self.redis.expire(key, self.ttl_seconds)
        else:
            hit = self.redis.get(key)
            current_count = int(hit) if hit else 0
            
        escalate = current_count >= self.threshold
        return {"escalate_to_high_risk": bool(escalate), "count": current_count}

    @classmethod
    def load(cls):
        from config import get_config_val
        ttl_hours = get_config_val("mosaic", "ttl_hours", "MOSAIC_TTL_HOURS", "24", float)
        threshold = get_config_val("mosaic", "threshold", "MOSAIC_THRESHOLD", "10", int)
        redis_host = get_config_val("mosaic", "redis_host", "REDIS_HOST", "localhost", str)
        redis_port = get_config_val("mosaic", "redis_port", "REDIS_PORT", "6379", int)
        return cls(host=redis_host, port=redis_port, ttl_hours=ttl_hours, threshold=threshold)
