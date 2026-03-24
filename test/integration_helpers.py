from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import redis

from noupe.configs.artifacts import artifact_manifest_path, verify_artifact_manifest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "test" / "fixtures"


def require_env_flag(flag: str, *, reason: str) -> None:
    if os.environ.get(flag) != "1":
        raise unittest.SkipTest(reason)


def load_json_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def ensure_real_artifacts_available() -> None:
    errors = verify_artifact_manifest(artifact_manifest_path())
    if errors:
        preview = "; ".join(errors[:2])
        raise unittest.SkipTest(f"real-artifact integration unavailable: {preview}")


def find_free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class TemporaryRedisServer:
    def __init__(self) -> None:
        self.host = os.environ.get("NOUPE_TEST_REDIS_HOST", "127.0.0.1")
        env_port = os.environ.get("NOUPE_TEST_REDIS_PORT")
        self.port = int(env_port) if env_port else find_free_tcp_port()
        self._managed = env_port is None
        self._process: subprocess.Popen | None = None
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self.client = redis.Redis(host=self.host, port=self.port)

    def start(self) -> "TemporaryRedisServer":
        if self._managed:
            binary = shutil.which("redis-server")
            if binary is None:
                raise unittest.SkipTest("redis integration requested but redis-server is unavailable")
            self._tmpdir = tempfile.TemporaryDirectory()
            self._process = subprocess.Popen(
                [
                    binary,
                    "--save",
                    "",
                    "--appendonly",
                    "no",
                    "--bind",
                    self.host,
                    "--port",
                    str(self.port),
                    "--dir",
                    self._tmpdir.name,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        deadline = time.time() + 10.0
        last_exc: Exception | None = None
        while time.time() < deadline:
            try:
                self.client.ping()
                self.client.flushdb()
                return self
            except Exception as exc:  # pragma: no cover - exercised in integration environments
                last_exc = exc
                time.sleep(0.1)

        raise RuntimeError(f"redis server did not become ready on {self.host}:{self.port}: {last_exc}")

    def stop(self) -> None:
        try:
            self.client.flushdb()
        except Exception:
            pass

        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
                self._process.kill()
                self._process.wait(timeout=5.0)

        if self._tmpdir is not None:
            self._tmpdir.cleanup()
