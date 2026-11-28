#!/usr/bin/env python3
"""Retired risk-label agreement evaluator; retained only to reject old invocations."""

import sys


def main() -> int:
    print(
        "Risk-label agreement evaluation was retired with legacy scoring. "
        "Use scripts/evaluate_sensitivity.py with contextual references; "
        "a model must supply validated PII/MNPI evidence before comparison.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
