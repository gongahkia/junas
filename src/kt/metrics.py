"""Minimal Prometheus-compatible metrics, no external deps.

Only tracks what the middleware actually observes: HTTP request counts and
latency histograms. Keyed by (method, route template, status_code). Exposed
as text/plain with the standard exposition format at /metrics.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

_HIST_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


@dataclass
class _Series:
    count: int = 0
    sum_: float = 0.0
    buckets: list[int] = field(default_factory=lambda: [0] * len(_HIST_BUCKETS))


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, str, str], int] = {}
        self._hist: dict[tuple[str, str, str], _Series] = {}
        self._started_at = time.time()

    def observe_http(
        self, method: str, route: str, status: int, duration: float
    ) -> None:
        key = (method.upper(), route, str(status))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1
            series = self._hist.get(key)
            if series is None:
                series = _Series()
                self._hist[key] = series
            series.count += 1
            series.sum_ += duration
            for i, b in enumerate(_HIST_BUCKETS):
                if duration <= b:
                    series.buckets[i] += 1

    def expose(self) -> str:
        lines: list[str] = []
        lines.append("# HELP kt_build_info Process start info")
        lines.append("# TYPE kt_build_info gauge")
        lines.append(f"kt_build_info {self._started_at}")
        lines.append("")
        lines.append("# HELP kt_http_requests_total HTTP requests.")
        lines.append("# TYPE kt_http_requests_total counter")
        with self._lock:
            for (method, route, status), count in self._counters.items():
                lines.append(
                    f'kt_http_requests_total{{method="{method}",route="{_esc(route)}",status="{status}"}} {count}'
                )
            lines.append("")
            lines.append("# HELP kt_http_request_duration_seconds Request latency histogram.")
            lines.append("# TYPE kt_http_request_duration_seconds histogram")
            for (method, route, status), series in self._hist.items():
                base = f'method="{method}",route="{_esc(route)}",status="{status}"'
                cumulative = 0
                for bucket, count in zip(_HIST_BUCKETS, series.buckets, strict=False):
                    cumulative += count
                    lines.append(
                        f"kt_http_request_duration_seconds_bucket{{{base},le=\"{bucket}\"}} {cumulative}"
                    )
                lines.append(
                    f'kt_http_request_duration_seconds_bucket{{{base},le="+Inf"}} {series.count}'
                )
                lines.append(
                    f"kt_http_request_duration_seconds_sum{{{base}}} {series.sum_}"
                )
                lines.append(
                    f"kt_http_request_duration_seconds_count{{{base}}} {series.count}"
                )
        return "\n".join(lines) + "\n"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')
