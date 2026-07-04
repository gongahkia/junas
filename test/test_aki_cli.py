from __future__ import annotations

import contextlib
import io
import re
import unittest

from junas.cli import build_parser, main, render_demo


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
        self.assertIn("Junas local helper CLI", help_text)


if __name__ == "__main__":
    unittest.main()
