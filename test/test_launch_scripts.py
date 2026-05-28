import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def reserve_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def http_get_text(url: str, timeout: float = 2.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")


def wait_for_url(url: str, proc: subprocess.Popen, timeout: float = 45.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout is not None else ""
            raise AssertionError(f"process exited before {url} became ready\n{output}")
        try:
            return http_get_text(url, timeout=2.0)
        except Exception:
            time.sleep(1.0)
    raise AssertionError(f"timed out waiting for {url}")


class LaunchScriptSmokeTests(unittest.TestCase):
    def _start_script(self, script_name: str) -> tuple[subprocess.Popen, int]:
        backend_port = reserve_port()
        env = {
            **os.environ,
            "KAYPOH_HOST": "127.0.0.1",
            "KAYPOH_PORT": str(backend_port),
            "KAYPOH_UVICORN_WORKERS": "1",
            "PIPELINE_LAYERS": "",
            "KMP_DUPLICATE_LIB_OK": "TRUE",
        }
        tmp_dir = None
        if script_name == "run_prod.sh":
            tmp_dir = tempfile.mkdtemp(prefix="kaypoh-launch-")
            manifest = Path(tmp_dir) / "retention_manifest.json"
            manifest.write_text(
                """
{
  "journal": {"retention_days": 2555},
  "mapping_store": {"retention_days": 90},
  "logs": {"policy": "launch-test-log-retention"},
  "siem": {"external_policy_ref": "launch-test-siem-retention"},
  "backups": {"retention_days": 365}
}
""".strip(),
                encoding="utf-8",
            )
            env["KAYPOH_API_KEY"] = "launch-test-api-key"
            env["KAYPOH_RETENTION_MANIFEST"] = str(manifest)
        proc = subprocess.Popen(
            ["bash", str(ROOT / "scripts" / "launch" / script_name)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        proc._kaypoh_tmp_dir = tmp_dir  # type: ignore[attr-defined]
        return proc, backend_port

    def _stop_script(self, proc: subprocess.Popen) -> None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        finally:
            tmp_dir = getattr(proc, "_kaypoh_tmp_dir", None)
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            if proc.stdout is not None:
                proc.stdout.close()

    def test_run_backend_only_starts_ready_backend(self):
        proc, backend_port = self._start_script("run_backend_only.sh")
        try:
            ready_payload = wait_for_url(f"http://127.0.0.1:{backend_port}/ready", proc)
            health_payload = http_get_text(f"http://127.0.0.1:{backend_port}/health")
            self.assertIn('"ready":true', ready_payload.replace(" ", "").lower())
            self.assertIn('"status":"ok"', health_payload.replace(" ", "").lower())
        finally:
            self._stop_script(proc)

    def test_run_dev_starts_ready_backend(self):
        proc, backend_port = self._start_script("run_dev.sh")
        try:
            ready_payload = wait_for_url(f"http://127.0.0.1:{backend_port}/ready", proc)
            health_payload = http_get_text(f"http://127.0.0.1:{backend_port}/health")
            self.assertIn('"ready":true', ready_payload.replace(" ", "").lower())
            self.assertIn('"status":"ok"', health_payload.replace(" ", "").lower())
        finally:
            self._stop_script(proc)

    def test_run_prod_starts_ready_backend(self):
        proc, backend_port = self._start_script("run_prod.sh")
        try:
            ready_payload = wait_for_url(f"http://127.0.0.1:{backend_port}/ready", proc, timeout=60.0)
            health_payload = http_get_text(f"http://127.0.0.1:{backend_port}/health")
            self.assertIn('"ready":true', ready_payload.replace(" ", "").lower())
            self.assertIn('"status":"ok"', health_payload.replace(" ", "").lower())
        finally:
            self._stop_script(proc)


if __name__ == "__main__":
    unittest.main()
