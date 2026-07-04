from __future__ import annotations

import contextlib
import io
import re
import unittest
from unittest import mock

from junas.cli import DoctorResult, build_parser, main, render_demo, render_doctor


class AkiCliTests(unittest.TestCase):
    def test_demo_output_is_deterministic_and_fake_labeled(self):
        first = render_demo()
        second = render_demo()

        self.assertEqual(first, second)
        self.assertIn("Aki fake-secret demo", first)
        self.assertIn("synthetic FAKE/DEMO fixtures", first)
        self.assertIn("AKIA-FAKE-DEMO-0000", first)
        self.assertIn("ghp_FAKE_DEMO_TOKEN_0000", first)
        self.assertIn("sk-fake-demo", first)
        self.assertIn("xoxb-fake-demo", first)
        self.assertIn("jane.demo@example.test", first)
        self.assertIn("demo_completed: true", first)

    def test_demo_values_avoid_real_secret_shapes(self):
        output = render_demo()

        self.assertIsNone(re.search(r"\bAKIA[0-9A-Z]{16}\b", output))
        self.assertIsNone(re.search(r"\bgh[opsu]_[A-Za-z0-9_]{30,}\b", output))
        self.assertIsNone(re.search(r"\bsk-[A-Za-z0-9_-]{20,}\b", output))
        self.assertIsNone(re.search(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b", output))

    def test_demo_case_limits_output_to_selected_case(self):
        output = render_demo(case="outlook-send", frames=1)

        self.assertIn("frame 01/01 | outlook-send", output)
        self.assertIn("GITHUB_TOKEN=ghp_FAKE_DEMO_TOKEN_0000", output)
        self.assertNotIn("browser-prompt", output)

    def test_main_runs_demo(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            code = main(["demo", "--frames", "2"])

        self.assertEqual(code, 0)
        self.assertIn("frame 01/02", stdout.getvalue())
        self.assertIn("frame 02/02", stdout.getvalue())

    def test_help_lists_demo_command(self):
        help_text = build_parser().format_help()

        self.assertIn("demo", help_text)
        self.assertIn("doctor", help_text)
        self.assertIn("Junas local helper CLI", help_text)

    def test_doctor_output_reports_status_and_remediation_without_telemetry(self):
        output = render_doctor(
            (
                DoctorResult(
                    status="pass",
                    name="CoreMediaIO DAL state",
                    detail="DAL plugin directory exists.",
                    remediation="No action needed.",
                ),
                DoctorResult(
                    status="warn",
                    name="OBS reachability",
                    detail="OBS websocket URL is not configured; reachability check skipped.",
                    remediation="Set AKI_OBS_WEBSOCKET_URL=ws://127.0.0.1:4455 when OBS integration is relevant.",
                ),
            )
        )

        self.assertIn("Aki doctor", output)
        self.assertIn("telemetry: disabled", output)
        self.assertIn("pass: CoreMediaIO DAL state", output)
        self.assertIn("warn: OBS reachability", output)
        self.assertIn("fix: Set AKI_OBS_WEBSOCKET_URL", output)
        self.assertIn("summary: pass=1 warn=1 fail=0", output)

    def test_main_runs_doctor_and_returns_failure_on_failed_check(self):
        stdout = io.StringIO()
        result = DoctorResult(
            status="fail",
            name="OBS reachability",
            detail="Could not connect.",
            remediation="Start OBS.",
        )

        with mock.patch("junas.cli.run_doctor_checks", return_value=(result,)):
            with contextlib.redirect_stdout(stdout):
                code = main(["doctor", "--obs-url", "ws://127.0.0.1:4455"])

        self.assertEqual(code, 1)
        self.assertIn("fail: OBS reachability", stdout.getvalue())

    def test_main_runs_doctor_json_without_raw_text_or_telemetry(self):
        stdout = io.StringIO()
        result = DoctorResult(
            status="pass",
            name="Tesseract data path",
            detail="tesseract is installed with languages: eng.",
            remediation="No action needed.",
        )

        with mock.patch("junas.cli.run_doctor_checks", return_value=(result,)):
            with contextlib.redirect_stdout(stdout):
                code = main(["doctor", "--json"])

        self.assertEqual(code, 0)
        self.assertIn('"telemetry": "disabled"', stdout.getvalue())
        self.assertIn('"name": "Tesseract data path"', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
