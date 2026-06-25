import argparse
import importlib.util
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load_benchmark_module():
    path = ROOT / "scripts" / "benchmark_latency.py"
    spec = importlib.util.spec_from_file_location("test_benchmark_latency", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load benchmark module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BenchmarkLatencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_benchmark_module()

    def test_resolve_inputs_accepts_files_and_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            file_a = temp_root / "a.txt"
            file_b = temp_root / "b.txt"
            ignored = temp_root / "notes.md"
            file_a.write_text("alpha", encoding="utf-8")
            file_b.write_text("beta", encoding="utf-8")
            ignored.write_text("gamma", encoding="utf-8")

            args = argparse.Namespace(
                inputs=[str(file_a), str(temp_root)],
                glob_pattern=None,
            )
            resolved = self.mod.resolve_inputs(args)
            self.assertEqual(resolved, [file_a.resolve(), file_b.resolve()])

    def test_summarize_runs_computes_expected_statistics(self):
        runs = [
            {
                "file_name": "sample.txt",
                "file_path": "/tmp/sample.txt",
                "word_count": 10,
                "char_count": 50,
                "client_latency_ms": 10.0,
                "server_total_ms": 8.0,
            },
            {
                "file_name": "sample.txt",
                "file_path": "/tmp/sample.txt",
                "word_count": 10,
                "char_count": 50,
                "client_latency_ms": 20.0,
                "server_total_ms": 15.0,
            },
        ]
        summary = self.mod.summarize_runs(runs)
        self.assertEqual(summary["min_ms"], 10.0)
        self.assertEqual(summary["max_ms"], 20.0)
        self.assertEqual(summary["mean_ms"], 15.0)
        self.assertEqual(summary["mean_server_ms"], 11.5)

    def test_main_writes_reports_against_a_live_backend(self):
        def reserve_port() -> int:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
            sock.close()
            return port

        port = reserve_port()
        base_url = f"http://127.0.0.1:{port}"
        backend_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "test.observability_test_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(ROOT),
        )

        reports_dir = ROOT / "reports"
        existing_json = set(reports_dir.glob("latency_*.json")) if reports_dir.exists() else set()
        existing_csv = set(reports_dir.glob("latency_*.csv")) if reports_dir.exists() else set()
        existing_txt = set(reports_dir.glob("latency_*.txt")) if reports_dir.exists() else set()

        try:
            self.mod.wait_for_ready(base_url, timeout=30)

            with tempfile.TemporaryDirectory() as tmp_dir:
                sample_path = Path(tmp_dir) / "sample.txt"
                sample_path.write_text("Acme Corp merger memo", encoding="utf-8")

                argv = [
                    "benchmark_latency.py",
                    "--no-server",
                    "--url",
                    base_url,
                    "--warmups",
                    "0",
                    "--repetitions",
                    "1",
                    str(sample_path),
                ]
                with mock.patch.object(sys, "argv", argv):
                    exit_code = self.mod.main()

            self.assertEqual(exit_code, 0)

            new_json = sorted(set(reports_dir.glob("latency_*.json")) - existing_json)
            new_csv = sorted(set(reports_dir.glob("latency_*.csv")) - existing_csv)
            new_txt = sorted(set(reports_dir.glob("latency_*.txt")) - existing_txt)
            self.assertEqual(len(new_json), 1)
            self.assertEqual(len(new_csv), 1)
            self.assertEqual(len(new_txt), 1)
            report_payload = new_json[0].read_text(encoding="utf-8")
            txt_payload = new_txt[0].read_text(encoding="utf-8")
            self.assertIn("sample.txt", report_payload)
            self.assertIn("\"runs\":", report_payload)
            self.assertIn("Kaypoh Latency Benchmark Report", txt_payload)
            self.assertIn("sample.txt", txt_payload)
            self.assertIn("Detailed results:", txt_payload)
            self.assertIn("Per-run details:", txt_payload)
            self.assertIn("timings_ms:", txt_payload)
        finally:
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                backend_proc.kill()
                backend_proc.wait(timeout=10)

            time.sleep(0.1)
            for path in sorted(set(reports_dir.glob("latency_*.json")) - existing_json):
                path.unlink()
            for path in sorted(set(reports_dir.glob("latency_*.csv")) - existing_csv):
                path.unlink()
            for path in sorted(set(reports_dir.glob("latency_*.txt")) - existing_txt):
                path.unlink()


if __name__ == "__main__":
    unittest.main()
