"""CLI: ``python -m benchmark.cli run --workflow ... --dataset ...``."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from benchmark.evaluators import EVALUATORS, EvaluatorStrength
from benchmark.registry import TASKS
from benchmark.runner import run, write_summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark", description="SG-LegalBench harness")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run a workflow against a dataset")
    run_p.add_argument("--workflow", required=True, help="registered task name")
    run_p.add_argument("--dataset", required=True, help="path to YAML dataset")
    run_p.add_argument(
        "--evaluator",
        action="append",
        required=True,
        help="evaluator name; pass multiple times to score with several",
    )
    run_p.add_argument("--max-concurrency", type=int, default=5)
    run_p.add_argument("--output", default="", help="optional path to write JSON receipt")
    run_p.add_argument(
        "--strict",
        action="store_true",
        help="reject weak-tier evaluators (publication mode; see docs/coverage-matrix.md §4.2)",
    )

    list_p = sub.add_parser("list", help="List registered tasks and evaluators")
    list_p.add_argument(
        "--kind",
        choices=("tasks", "evaluators", "all"),
        default="all",
    )

    return parser


def _cmd_list(args: argparse.Namespace) -> int:
    if args.kind in ("tasks", "all"):
        print("Tasks:")
        for name in sorted(TASKS):
            print(f"  - {name}")
    if args.kind in ("evaluators", "all"):
        print("Evaluators:")
        for name in sorted(EVALUATORS):
            tier = EVALUATORS[name].strength.value
            print(f"  - {name} [{tier}]")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    summary = asyncio.run(
        run(
            workflow=args.workflow,
            dataset_path=args.dataset,
            evaluators=args.evaluator,
            max_concurrency=args.max_concurrency,
            strict=args.strict,
        )
    )

    means = summary.per_evaluator_mean()
    print(json.dumps({"per_evaluator_mean": means, "total_cases": summary.total_cases}, indent=2))

    if args.output:
        write_summary(summary, args.output)
        print(f"Receipt written to {args.output}")

    if any(r.error for r in summary.results):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "run":
            return _cmd_run(args)
        if args.cmd == "list":
            return _cmd_list(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
