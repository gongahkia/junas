"""CLI for synthetic SGLB candidate generation."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from benchmark.synthetic.generator import SyntheticGenerator, case_from_body, plan_json, write_candidate_case
from benchmark.synthetic.ops import show_fixture, status_for_task, validate_task
from benchmark.synthetic.planner import build_plan, estimate_cost_usd
from benchmark.synthetic.promoter import promote_task
from benchmark.synthetic.reviewer import record_decision, resolve_fixture, summary_json
from benchmark.synthetic.taxonomy import DATASET_ROOT, supported_tasks


def _base_dir(raw: str | None) -> Path | None:
    return Path(raw) if raw else None


def _common_plan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task", required=True, choices=supported_tasks())
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--providers", default="anthropic,openai,google")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--base-dir", default="", help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark.synthetic")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan_p = sub.add_parser("plan", help="Print deterministic generation matrix")
    _common_plan_args(plan_p)
    plan_p.add_argument("--dry-run", action="store_true")

    gen_p = sub.add_parser("generate", help="Generate synthetic candidate fixtures")
    _common_plan_args(gen_p)
    gen_p.add_argument("--dry-run", action="store_true")
    gen_p.add_argument("--max-cost-usd", type=float, default=None)
    gen_p.add_argument(
        "--no-review-gate",
        action="store_true",
        help="compatibility flag: candidates are still pending and promotion still requires approval",
    )

    review_p = sub.add_parser("review", help="Record human review decision")
    review_p.add_argument("--fixture", required=True)
    review_p.add_argument("--task", choices=supported_tasks())
    review_p.add_argument("--decision", required=True, choices=("approve", "reject", "needs_edit"))
    review_p.add_argument("--reviewer", default="")
    review_p.add_argument("--notes", default="")
    review_p.add_argument("--base-dir", default="", help=argparse.SUPPRESS)

    promote_p = sub.add_parser("promote", help="Promote approved candidates to reviewed")
    promote_p.add_argument("--task", required=True, choices=supported_tasks())
    promote_p.add_argument("--base-dir", default="", help=argparse.SUPPRESS)

    status_p = sub.add_parser("status", help="Summarise candidate and reviewed fixture counts")
    status_p.add_argument("--task", required=True, choices=supported_tasks())
    status_p.add_argument("--base-dir", default="", help=argparse.SUPPRESS)

    show_p = sub.add_parser("show", help="Show one synthetic fixture")
    show_p.add_argument("--fixture", required=True)
    show_p.add_argument("--task", choices=supported_tasks())
    show_p.add_argument("--base-dir", default="", help=argparse.SUPPRESS)

    validate_p = sub.add_parser("validate", help="Validate synthetic candidate/reviewed datasets")
    validate_p.add_argument("--task", required=True, choices=supported_tasks())
    validate_p.add_argument("--base-dir", default="", help=argparse.SUPPRESS)
    return parser


def _plan_payload(args: argparse.Namespace) -> tuple[list, float]:
    plan = build_plan(
        task=args.task,
        n=args.n,
        providers=args.providers,
        seed=args.seed,
        base_dir=_base_dir(args.base_dir),
    )
    return plan, estimate_cost_usd(plan)


def _cmd_plan(args: argparse.Namespace) -> int:
    plan, cost = _plan_payload(args)
    print(plan_json(plan, estimated_cost_usd=cost))
    return 0


async def _generate_async(args: argparse.Namespace) -> int:
    plan, cost = _plan_payload(args)
    if args.max_cost_usd is not None and cost > args.max_cost_usd:
        print(
            f"estimated cost ${cost:.6f} exceeds --max-cost-usd ${args.max_cost_usd:.6f}",
            file=sys.stderr,
        )
        return 2
    if args.dry_run:
        print(plan_json(plan, estimated_cost_usd=cost))
        return 0

    generator = SyntheticGenerator()
    written: list[str] = []
    for item in plan:
        body = await generator.generate_body(item)
        case = case_from_body(item=item, body=body, seed=args.seed)
        path = write_candidate_case(item=item, case=case)
        written.append(str(path))
    print(json.dumps({"written": written, "call_counts": generator.call_counts}, indent=2, sort_keys=True))
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    return asyncio.run(_generate_async(args))


def _cmd_review(args: argparse.Namespace) -> int:
    fixture = resolve_fixture(args.fixture, task=args.task, base_dir=_base_dir(args.base_dir) or DATASET_ROOT)
    record_decision(
        fixture_path=fixture,
        decision=args.decision,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    print(summary_json(fixture))
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    result = promote_task(task=args.task, base_dir=_base_dir(args.base_dir))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


def _cmd_status(args: argparse.Namespace) -> int:
    print(json.dumps(status_for_task(task=args.task, base_dir=_base_dir(args.base_dir)), indent=2, sort_keys=True))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            show_fixture(fixture=args.fixture, task=args.task, base_dir=_base_dir(args.base_dir)),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    result = validate_task(task=args.task, base_dir=_base_dir(args.base_dir))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "plan":
            return _cmd_plan(args)
        if args.cmd == "generate":
            return _cmd_generate(args)
        if args.cmd == "review":
            return _cmd_review(args)
        if args.cmd == "promote":
            return _cmd_promote(args)
        if args.cmd == "status":
            return _cmd_status(args)
        if args.cmd == "show":
            return _cmd_show(args)
        if args.cmd == "validate":
            return _cmd_validate(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
