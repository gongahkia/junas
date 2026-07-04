from __future__ import annotations

import argparse
import io
import json
import unittest
from pathlib import Path

from junas.cli import run_sidecar_stdio
from junas.desktop.sidecar_protocol import ERROR_METHOD_NOT_FOUND, SidecarSession

ROOT = Path(__file__).resolve().parent.parent


def _request(request_id: int, method: str, params: dict | None = None) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})


class SidecarProtocolTests(unittest.TestCase):
    def test_sidecar_session_supports_v1_capture_lifecycle(self):
        session = SidecarSession()

        initialized = session.handle(_request(1, "initialize"))
        self.assertEqual(initialized[0]["result"]["transport"], "stdio-jsonrpc")
        self.assertIn("capture.start", initialized[0]["result"]["capabilities"])

        source = session.handle(_request(2, "source.select", {"kind": "display", "id": "main"}))
        transform = session.handle(_request(3, "transform.select", {"kind": "redaction_box"}))
        output = session.handle(_request(4, "output.select", {"kind": "mp4", "path": "/tmp/out.mp4"}))
        started = session.handle(_request(5, "capture.start"))
        paused = session.handle(_request(6, "capture.pause"))
        stopped = session.handle(_request(7, "capture.stop"))

        self.assertEqual(source[1]["method"], "stats.update")
        self.assertEqual(transform[1]["method"], "stats.update")
        self.assertEqual(output[1]["method"], "stats.update")
        self.assertEqual(started[0]["result"]["state"], "running")
        self.assertEqual(started[1]["params"]["state"], "running")
        self.assertEqual(paused[0]["result"]["state"], "paused")
        self.assertEqual(stopped[0]["result"]["state"], "stopped")

    def test_sidecar_session_reports_json_rpc_errors(self):
        session = SidecarSession()

        unknown = session.handle(_request(42, "capture.rewind"))
        invalid_start = session.handle(_request(43, "capture.start"))

        self.assertEqual(unknown[0]["id"], 42)
        self.assertEqual(unknown[0]["error"]["code"], ERROR_METHOD_NOT_FOUND)
        self.assertEqual(invalid_start[0]["error"]["code"], -32000)
        self.assertNotIn("token", json.dumps(invalid_start).lower())

    def test_sidecar_stdio_cli_reads_json_lines_until_shutdown(self):
        stdin = io.StringIO(
            "\n".join(
                [
                    _request(1, "initialize"),
                    _request(2, "shutdown"),
                    _request(3, "stats.snapshot"),
                ]
            )
            + "\n"
        )
        stdout = io.StringIO()

        code = run_sidecar_stdio(argparse.Namespace(), stdin=stdin, stdout=stdout)

        self.assertEqual(code, 0)
        lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["result"]["protocol_version"], "2026-07-04")
        self.assertTrue(lines[1]["result"]["should_exit"])

    def test_sidecar_protocol_docs_cover_decision_methods_and_lifecycle(self):
        doc = (ROOT / "docs" / "integrations" / "menu-bar-sidecar-protocol.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        for token in (
            "stdio JSON-RPC 2.0",
            "Unix socket",
            "FFI",
            "source.select",
            "transform.select",
            "output.select",
            "capture.start",
            "capture.pause",
            "capture.stop",
            "stats.update",
            "Process",
            "Error Handling",
        ):
            self.assertIn(token, doc)
        self.assertIn("docs/integrations/menu-bar-sidecar-protocol.md", readme)
        self.assertIn("integrations/menu-bar-sidecar-protocol.md", docs_index)
        self.assertIn("menu-bar-sidecar-protocol.md", integrations_index)


if __name__ == "__main__":
    unittest.main()
