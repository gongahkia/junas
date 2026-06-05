from __future__ import annotations

import random
import statistics

import pytest

from benchmark.stats import BootstrapCI, bootstrap_ci


def _reference_bootstrap(values: list[float], *, seed: int, n: int) -> BootstrapCI:
    rng = random.Random(seed)
    means: list[float] = []
    count = len(values)
    for _ in range(n):
        sample = [values[rng.randrange(count)] for _ in range(count)]
        means.append(statistics.fmean(sample))
    means.sort()
    low_idx = int(0.025 * (n - 1))
    high_idx = int(0.975 * (n - 1))
    return BootstrapCI(
        mean=statistics.fmean(values),
        ci_low=means[low_idx],
        ci_high=means[high_idx],
        n_bootstrap=n,
    )


def test_bootstrap_ci_matches_leaderboard_algorithm():
    values = [0.0, 1.0, 0.5, 1.0, 0.0]
    assert bootstrap_ci(values, seed=1009, n=200) == _reference_bootstrap(
        values,
        seed=1009,
        n=200,
    )


def test_bootstrap_ci_is_seed_deterministic():
    values = [0.0, 1.0, 1.0, 0.0]
    first = bootstrap_ci(values, seed=1234, n=100)
    second = bootstrap_ci(values, seed=1234, n=100)
    assert first == second


def test_bootstrap_ci_empty_values_has_zero_interval():
    ci = bootstrap_ci([], seed=1009)
    assert ci.mean == 0.0
    assert ci.ci_low == 0.0
    assert ci.ci_high == 0.0
    assert ci.n_bootstrap == 0


def test_bootstrap_ci_rejects_non_positive_n():
    with pytest.raises(ValueError, match="n must be positive"):
        bootstrap_ci([1.0], seed=1009, n=0)
