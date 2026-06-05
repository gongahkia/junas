"""Agreement metrics for LLM judge ensembles."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence


INVALID_LABEL = "__invalid__"


@dataclass(frozen=True)
class KappaResult:
    kappa: float | None
    n: int
    observed_agreement: float | None
    expected_agreement: float | None
    labels: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "kappa": self.kappa,
            "n": self.n,
            "observed_agreement": self.observed_agreement,
            "expected_agreement": self.expected_agreement,
            "labels": list(self.labels),
        }


def cohen_kappa(
    rater_a: Sequence[str],
    rater_b: Sequence[str],
    *,
    labels: Iterable[str] | None = None,
) -> KappaResult:
    if len(rater_a) != len(rater_b):
        raise ValueError("cohen_kappa requires equal-length rating sequences")
    n = len(rater_a)
    label_order = _labels(labels, rater_a, rater_b)
    if n == 0:
        return KappaResult(
            kappa=None,
            n=0,
            observed_agreement=None,
            expected_agreement=None,
            labels=label_order,
        )

    observed = sum(1 for left, right in zip(rater_a, rater_b) if left == right) / n
    counts_a = Counter(rater_a)
    counts_b = Counter(rater_b)
    expected = sum((counts_a[label] / n) * (counts_b[label] / n) for label in label_order)
    denominator = 1.0 - expected
    if abs(denominator) < 1e-12:
        kappa = 1.0 if abs(observed - 1.0) < 1e-12 else 0.0
    else:
        kappa = (observed - expected) / denominator
    return KappaResult(
        kappa=float(kappa),
        n=n,
        observed_agreement=float(observed),
        expected_agreement=float(expected),
        labels=label_order,
    )


def fleiss_kappa(
    ratings_by_item: Sequence[Sequence[str]],
    *,
    labels: Iterable[str] | None = None,
) -> KappaResult:
    rows = [tuple(row) for row in ratings_by_item]
    label_order = _labels(labels, *(rows or [()]))
    if not rows:
        return KappaResult(
            kappa=None,
            n=0,
            observed_agreement=None,
            expected_agreement=None,
            labels=label_order,
        )

    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError("fleiss_kappa requires the same number of ratings for every item")
    ratings_per_item = widths.pop()
    if ratings_per_item < 2:
        raise ValueError("fleiss_kappa requires at least two ratings per item")

    item_agreements: list[float] = []
    category_totals = Counter()
    for row in rows:
        counts = Counter(row)
        category_totals.update(counts)
        numerator = sum(count * count for count in counts.values()) - ratings_per_item
        denominator = ratings_per_item * (ratings_per_item - 1)
        item_agreements.append(numerator / denominator)

    n_items = len(rows)
    observed = sum(item_agreements) / n_items
    total_ratings = n_items * ratings_per_item
    expected = sum((category_totals[label] / total_ratings) ** 2 for label in label_order)
    denominator = 1.0 - expected
    if abs(denominator) < 1e-12:
        kappa = 1.0 if abs(observed - 1.0) < 1e-12 else 0.0
    else:
        kappa = (observed - expected) / denominator
    return KappaResult(
        kappa=float(kappa),
        n=n_items,
        observed_agreement=float(observed),
        expected_agreement=float(expected),
        labels=label_order,
    )


def agreement_rate(rater_a: Sequence[str], rater_b: Sequence[str]) -> float | None:
    if len(rater_a) != len(rater_b):
        raise ValueError("agreement_rate requires equal-length rating sequences")
    if not rater_a:
        return None
    return sum(1 for left, right in zip(rater_a, rater_b) if left == right) / len(rater_a)


def _labels(labels: Iterable[str] | None, *rating_sets: Sequence[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for label in labels or ():
        if label not in seen:
            ordered.append(str(label))
            seen.add(str(label))
    for ratings in rating_sets:
        for label in ratings:
            if label not in seen:
                ordered.append(str(label))
                seen.add(str(label))
    return tuple(ordered)
