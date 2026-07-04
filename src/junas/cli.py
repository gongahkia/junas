from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True)
class DemoFrame:
    key: str
    surface: str
    fake_secret: str
    sample_text: str
    expected_signal: str


DEMO_FRAMES: tuple[DemoFrame, ...] = (
    DemoFrame(
        key="browser-prompt",
        surface="browser GenAI prompt",
        fake_secret="AWS_ACCESS_KEY_ID=AKIA-FAKE-DEMO-0000",
        sample_text=("Before pasting to GenAI, remove FAKE-SG-NRIC-S1234567D for Jane Demo <jane.demo@example.test>."),
        expected_signal="fake secret + PII-shaped text",
    ),
    DemoFrame(
        key="outlook-send",
        surface="Outlook pre-send",
        fake_secret="GITHUB_TOKEN=ghp_FAKE_DEMO_TOKEN_0000",
        sample_text=("Send the Project Raven FAKE-MNPI draft to Alex Example at +1-555-0100 after approval."),
        expected_signal="fake token + MNPI-shaped text",
    ),
    DemoFrame(
        key="dms-upload",
        surface="DMS upload",
        fake_secret="OPENAI_API_KEY=sk-fake-demo",
        sample_text=("Upload fake passport FAKE-P0000000 and demo account DEMO-0000-0000 for Taylor Example."),
        expected_signal="fake API key + identifier-shaped text",
    ),
    DemoFrame(
        key="slack-like",
        surface="internal chat",
        fake_secret="SLACK_BOT_TOKEN=xoxb-fake-demo",
        sample_text=("Post only the redacted demo note; DOB 1900-01-01 and employee id DEMO-EMP-0001 are synthetic."),
        expected_signal="fake bot token + special-category-shaped text",
    ),
)


def selected_demo_frames(case: str, frame_count: int) -> tuple[DemoFrame, ...]:
    if frame_count < 1:
        raise ValueError("--frames must be >= 1")
    frames = DEMO_FRAMES
    if case != "all":
        frames = tuple(frame for frame in DEMO_FRAMES if frame.key == case)
        if not frames:
            valid = ", ".join(frame.key for frame in DEMO_FRAMES)
            raise ValueError(f"unknown demo case {case!r}; expected one of: {valid}")
    return tuple(frames[index % len(frames)] for index in range(frame_count))


def render_demo(*, case: str = "all", frames: int | None = None) -> str:
    frame_count = frames if frames is not None else len(DEMO_FRAMES)
    selected = selected_demo_frames(case, frame_count)
    lines = [
        "Aki fake-secret demo",
        "All values below are synthetic FAKE/DEMO fixtures for screenshots and bug reports.",
        "",
    ]
    for index, frame in enumerate(selected, start=1):
        lines.extend(
            [
                f"frame {index:02d}/{len(selected):02d} | {frame.key} | {frame.surface}",
                f"  fake_secret: {frame.fake_secret}",
                f"  sample_text: {frame.sample_text}",
                f"  expected_signal: {frame.expected_signal}",
                f"  repro: aki demo --case {frame.key} --frames 1",
                "",
            ]
        )
    lines.append("demo_completed: true")
    return "\n".join(lines) + "\n"


def run_demo(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    try:
        output = render_demo(case=args.case, frames=args.frames)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.delay <= 0:
        stdout.write(output)
        return 0
    lines = output.splitlines(keepends=True)
    for line in lines:
        stdout.write(line)
        stdout.flush()
        if line.startswith("frame "):
            time.sleep(args.delay)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aki", description="Junas local helper CLI.")
    subparsers = parser.add_subparsers(dest="command")
    demo = subparsers.add_parser(
        "demo",
        help="render deterministic fake-secret and PII-shaped examples",
        description="Render deterministic fake-secret and PII-shaped examples for screenshots and bug reports.",
    )
    demo.add_argument("--case", choices=("all", *(frame.key for frame in DEMO_FRAMES)), default="all")
    demo.add_argument("--frames", type=int, default=len(DEMO_FRAMES))
    demo.add_argument("--delay", type=float, default=0.0, help="sleep seconds between rendered frames")
    demo.set_defaults(func=run_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
