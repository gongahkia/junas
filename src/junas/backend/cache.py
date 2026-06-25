from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class CacheSettings:
    size: int
    ttl_seconds: float

    @property
    def enabled(self) -> bool:
        return self.size > 0 and self.ttl_seconds > 0

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> "CacheSettings":
        payload = payload or {}
        try:
            size = max(0, int(payload.get("size", 0)))
        except (TypeError, ValueError):
            size = 0
        try:
            ttl_seconds = max(0.0, float(payload.get("ttl_seconds", 0.0)))
        except (TypeError, ValueError):
            ttl_seconds = 0.0
        return cls(size=size, ttl_seconds=ttl_seconds)


class ResponseCache:
    def __init__(self, *, size: int, ttl_seconds: float):
        self.settings = CacheSettings(size=max(0, int(size)), ttl_seconds=max(0.0, float(ttl_seconds)))
        self._entries: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.settings.enabled:
            return None

        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if now - float(entry.get("ts", 0.0)) > self.settings.ttl_seconds:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            payload = entry.get("payload")
            if isinstance(payload, dict):
                return dict(payload)
        return None

    def set(self, key: str, payload: dict[str, Any]) -> None:
        if not self.settings.enabled:
            return

        with self._lock:
            self._entries[key] = {"ts": time.monotonic(), "payload": payload}
            self._entries.move_to_end(key)
            while len(self._entries) > self.settings.size:
                self._entries.popitem(last=False)
