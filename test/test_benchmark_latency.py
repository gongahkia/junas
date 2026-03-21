import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
