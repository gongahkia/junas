import argparse
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_CORPUS_CASES = {
    "outlook-short-email.txt": (45, 250),
    "browser-prompt.txt": (80, 350),
    "legal-memo.txt": (350, None),
    "dms-upload-size-document.txt": (500, None),
}


def load_benchmark_module():
    path = ROOT / "scripts" / "benchmark_latency.py"
    spec = importlib.util.spec_from_file_location("test_benchmark_corpus_benchmark", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load benchmark module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reserve_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


class BenchmarkCorpusRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_benchmark_module()

    def test_latency_corpus_includes_workflow_cases(self):
        corpus_dir = ROOT / "test" / "fixtures" / "latency-corpus"
        args = argparse.Namespace(inputs=[str(corpus_dir)], glob_pattern=None)
        resolved_names = {path.name for path in self.mod.resolve_inputs(args)}

        self.assertLessEqual(set(WORKFLOW_CORPUS_CASES), resolved_names)

        for file_name, (min_words, max_words) in WORKFLOW_CORPUS_CASES.items():
            path = corpus_dir / file_name
            text = path.read_text(encoding="utf-8")
            word_count = len(text.split())
            self.assertGreaterEqual(word_count, min_words, file_name)
            if max_words is not None:
                self.assertLessEqual(word_count, max_words, file_name)

    def test_benchmark_main_handles_1k_2k_5k_and_10k_word_documents(self):
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
                temp_root = Path(tmp_dir)
                expected_counts = {}
                for target_count in (1000, 2000, 5000, 10000):
                    path = temp_root / f"{target_count}_words.txt"
                    tokens = [f"token{index}" for index in range(target_count)]
                    path.write_text(" ".join(tokens), encoding="utf-8")
                    expected_counts[path.name] = target_count

                argv = [
                    "benchmark_latency.py",
                    "--no-server",
                    "--url",
                    base_url,
                    "--warmups",
                    "0",
                    "--repetitions",
                    "1",
                    str(temp_root),
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

            payload = json.loads(new_json[0].read_text(encoding="utf-8"))
            observed_summary_counts = {
                item["file_name"]: item["word_count"]
                for item in payload["summaries"]
            }
            observed_run_counts = {
                item["file_name"]: item["word_count"]
                for item in payload["runs"]
            }

            self.assertEqual(observed_summary_counts, expected_counts)
            self.assertEqual(observed_run_counts, expected_counts)
        finally:
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                backend_proc.kill()
                backend_proc.wait(timeout=10)

            for path in sorted(set(reports_dir.glob("latency_*.json")) - existing_json):
                path.unlink()
            for path in sorted(set(reports_dir.glob("latency_*.csv")) - existing_csv):
                path.unlink()
            for path in sorted(set(reports_dir.glob("latency_*.txt")) - existing_txt):
                path.unlink()


if __name__ == "__main__":
    unittest.main()
