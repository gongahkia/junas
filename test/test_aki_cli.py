from __future__ import annotations

import contextlib
import io
import json
import re
import unittest
from pathlib import Path
from unittest import mock

import httpx

from junas.advisory.local_ocr_llm import (
    LocalOcrLLMSettings,
    LocalOcrRegionClassifier,
    low_confidence_region_candidates,
)
from junas.cli import DoctorResult, build_parser, main, render_demo, render_doctor
from junas.desktop.displays import (
    DisplaySelectionError,
    build_capture_plan,
    parse_system_profiler_displays,
    raw_frame_bandwidth_mbps,
    select_displays,
)

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent


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
        self.assertIn("rules", help_text)
        self.assertIn("ocr", help_text)
        self.assertIn("displays", help_text)
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

    def test_rules_test_consumes_local_gitleaks_pack(self):
        stdout = io.StringIO()
        pack = ROOT / "rules" / "community" / "gitleaks-acme-demo.toml"
        fixture = ROOT / "rules" / "community" / "fixtures" / "acme-api-token.txt"

        with contextlib.redirect_stdout(stdout):
            code = main(["rules", "test", "--gitleaks", str(pack), "--text-file", str(fixture)])

        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("Aki rules test", output)
        self.assertIn("external_secret_acme-api-token", output)
        self.assertIn("a1b2c3d4e5f6g7h8i9j0", output)

    def test_rules_test_json_emits_findings(self):
        stdout = io.StringIO()
        pack = ROOT / "rules" / "community" / "gitleaks-acme-demo.toml"

        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "rules",
                    "test",
                    "--gitleaks",
                    str(pack),
                    "--text",
                    "ACME_API_KEY = a1b2c3d4e5f6g7h8i9j0",
                    "--json",
                ]
            )

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["findings"][0]["rule"], "external_secret_acme-api-token")
        self.assertEqual(payload["findings"][0]["matched_text"], "a1b2c3d4e5f6g7h8i9j0")

    def test_ocr_classify_region_is_disabled_by_default(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            code = main(["ocr", "classify-region", "--text", "AK1A0CRNO1SE", "--confidence", "0.41", "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "disabled")
        self.assertEqual(payload["label"], "ambiguous")
        self.assertNotIn("AK1A0CRNO1SE", stdout.getvalue())

    def test_local_ocr_classifier_refuses_non_loopback_base_url(self):
        classifier = LocalOcrRegionClassifier(
            LocalOcrLLMSettings(
                enabled=True,
                model="local-test",
                base_url="https://llm.example.com",
            )
        )

        result = classifier.classify_text("AK1A0CRNO1SE", confidence=0.4)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "non_loopback_base_url")

    def test_local_ocr_classifier_calls_ollama_loopback_and_clamps_output(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "response": json.dumps(
                        {
                            "label": "secret_shaped",
                            "confidence": 1.7,
                            "reason": "token_syntax",
                        }
                    )
                },
            )

        classifier = LocalOcrRegionClassifier(
            LocalOcrLLMSettings(enabled=True, model="local-test", base_url="http://127.0.0.1:11434"),
            transport=httpx.MockTransport(handler),
        )

        result = classifier.classify_text("ghp_0crN0ise", confidence=0.38)

        self.assertEqual(result.status, "classified")
        self.assertEqual(result.label, "secret_shaped")
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.reason, "token_syntax")
        self.assertIn("/api/generate", captured["url"])
        self.assertEqual(captured["body"]["model"], "local-test")

    def test_low_confidence_region_candidate_filter(self):
        low = mock.Mock(text="sk-ocrnoise", confidence=0.42, start_char=3, end_char=14)
        high = mock.Mock(text="ordinary text", confidence=0.95, start_char=20, end_char=33)

        candidates = low_confidence_region_candidates([low, high], threshold=0.72)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].text, "sk-ocrnoise")
        self.assertEqual(candidates[0].confidence, 0.42)

    def test_local_ocr_llm_docs_preserve_default_footprint_and_positioning(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        doc = (ROOT / "docs" / "local-ocr-llm.md").read_text(encoding="utf-8")
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        deps = "\n".join(pyproject["project"]["dependencies"])

        self.assertNotIn("AI-powered", readme)
        self.assertIn("docs/local-ocr-llm.md", readme)
        for token in (
            "disabled by default",
            "loopback-only",
            "no added default dependencies",
            "Accuracy And Latency Tradeoffs",
            "JUNAS_LOCAL_OCR_LLM_ENABLED",
        ):
            self.assertIn(token, doc)
        for package in ("ollama", "llama-cpp-python", "torch", "transformers"):
            self.assertNotIn(package, deps)

    def test_display_inventory_parses_main_display_first(self):
        payload = {
            "SPDisplaysDataType": [
                {
                    "spdisplays_ndrvs": [
                        {
                            "_name": "Studio Display",
                            "_spdisplays_displayID": "2",
                            "_spdisplays_pixels": "5120 x 2880",
                            "_spdisplays_resolution": "2560 x 1440 @ 60.00Hz",
                            "spdisplays_online": "spdisplays_yes",
                        },
                        {
                            "_name": "Color LCD",
                            "_spdisplays_displayID": "1",
                            "_spdisplays_pixels": "2940 x 1912",
                            "_spdisplays_resolution": "1470 x 956 @ 60.00Hz",
                            "spdisplays_main": "spdisplays_yes",
                            "spdisplays_online": "spdisplays_yes",
                        },
                    ]
                }
            ]
        }

        displays = parse_system_profiler_displays(payload)

        self.assertEqual([display.name for display in displays], ["Color LCD", "Studio Display"])
        self.assertEqual([display.capture_index for display in displays], [1, 2])
        self.assertEqual(displays[0].pixels, (2940, 1912))

    def test_display_capture_plan_validates_missing_displays(self):
        displays = parse_system_profiler_displays(
            {
                "SPDisplaysDataType": [
                    {"spdisplays_ndrvs": [{"_name": "Color LCD", "spdisplays_main": "spdisplays_yes"}]}
                ]
            }
        )

        with self.assertRaises(DisplaySelectionError):
            select_displays(displays, [2])

        self.assertEqual(select_displays(displays, [2], ignore_missing=True), ())

    def test_display_capture_plan_builds_multi_display_commands(self):
        payload = {
            "SPDisplaysDataType": [
                {
                    "spdisplays_ndrvs": [
                        {"_name": "Color LCD", "spdisplays_main": "spdisplays_yes"},
                        {"_name": "Projector"},
                    ]
                }
            ]
        }
        displays = parse_system_profiler_displays(payload)

        plan = build_capture_plan(
            displays,
            selected_indexes=[1, 2],
            output_dir=Path("/tmp/captures"),
            video_seconds=30,
            timestamp="20260704T000000",
        )

        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0].argv[:5], ("screencapture", "-x", "-v", "-V", "30"))
        self.assertIn("-D", plan[0].argv)
        self.assertTrue(str(plan[0].output_path).endswith("display-1-20260704T000000.mov"))
        self.assertTrue(str(plan[1].output_path).endswith("display-2-20260704T000000.mov"))

    def test_displays_cli_lists_mocked_inventory_without_capture(self):
        stdout = io.StringIO()
        displays = parse_system_profiler_displays(
            {
                "SPDisplaysDataType": [
                    {"spdisplays_ndrvs": [{"_name": "Color LCD", "spdisplays_main": "spdisplays_yes"}]}
                ]
            }
        )

        with mock.patch("junas.desktop.displays.list_displays", return_value=displays):
            with contextlib.redirect_stdout(stdout):
                code = main(["displays", "list", "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["displays"][0]["name"], "Color LCD")

    def test_multi_display_docs_cover_removal_and_performance(self):
        doc = (ROOT / "docs" / "integrations" / "multi-display-capture.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for token in (
            "Select Displays",
            "Connected Or Removed Displays",
            "Performance Impact",
            "display index not available",
            "--ignore-missing",
            "3840 x 2160",
        ):
            self.assertIn(token, doc)
        self.assertEqual(raw_frame_bandwidth_mbps(3840, 2160), 995.3)
        self.assertIn("docs/integrations/multi-display-capture.md", readme)


if __name__ == "__main__":
    unittest.main()
