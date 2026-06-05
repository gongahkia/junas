"""Shared benchmark statistics helpers."""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class BootstrapCI:
    mean: float
    ci_low: float
    ci_high: float
    n_bootstrap: int


def bootstrap_ci(values: Sequence[float], *, seed: int, n: int = 1000) -> BootstrapCI:
    if n <= 0:
        raise ValueError("n must be positive")
    if not values:
        return BootstrapCI(mean=0.0, ci_low=0.0, ci_high=0.0, n_bootstrap=0)
    numeric_values = [float(value) for value in values]
    rng = random.Random(seed)
    means: list[float] = []
    count = len(numeric_values)
    for _ in range(n):
        sample = [numeric_values[rng.randrange(count)] for _ in range(count)]
        means.append(statistics.fmean(sample))
    means.sort()
    low_idx = int(0.025 * (n - 1))
    high_idx = int(0.975 * (n - 1))
    return BootstrapCI(
        mean=statistics.fmean(numeric_values),
        ci_low=means[low_idx],
        ci_high=means[high_idx],
        n_bootstrap=n,
    )
