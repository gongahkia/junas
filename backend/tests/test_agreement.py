from __future__ import annotations

import pytest

from benchmark.synthetic.agreement import cohen_kappa, fleiss_kappa


def test_cohen_kappa_perfect_agreement() -> None:
    result = cohen_kappa(["a", "b", "a"], ["a", "b", "a"], labels=("a", "b"))
    assert result.kappa == pytest.approx(1.0)
    assert result.observed_agreement == pytest.approx(1.0)
    assert result.n == 3


def test_cohen_kappa_known_partial_agreement() -> None:
    result = cohen_kappa(["yes", "yes", "no", "no"], ["yes", "no", "no", "no"])
    assert result.observed_agreement == pytest.approx(0.75)
    assert result.expected_agreement == pytest.approx(0.5)
    assert result.kappa == pytest.approx(0.5)


def test_cohen_kappa_requires_equal_lengths() -> None:
    with pytest.raises(ValueError, match="equal-length"):
        cohen_kappa(["a"], ["a", "b"])


def test_fleiss_kappa_perfect_agreement() -> None:
    result = fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]], labels=("a", "b"))
    assert result.kappa == pytest.approx(1.0)
    assert result.observed_agreement == pytest.approx(1.0)


def test_fleiss_kappa_known_partial_agreement() -> None:
    result = fleiss_kappa([["a", "a", "a"], ["a", "b", "b"]], labels=("a", "b"))
    assert result.observed_agreement == pytest.approx(2 / 3)
    assert result.expected_agreement == pytest.approx(5 / 9)
    assert result.kappa == pytest.approx(0.25)


def test_fleiss_kappa_rejects_ragged_rows() -> None:
    with pytest.raises(ValueError, match="same number"):
        fleiss_kappa([["a", "a"], ["a", "b", "b"]])
