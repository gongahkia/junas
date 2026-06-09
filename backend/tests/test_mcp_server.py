from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

try:
    from mcp.tools import register_tools
except ModuleNotFoundError:
    from backend.mcp.tools import register_tools


class FakeServer:
    def __init__(self) -> None:
        self.tools: dict[str, str] = {}

    def tool(self, description: str = ""):
        def _decorator(fn):
            self.tools[fn.__name__] = description
            return fn

        return _decorator


def test_register_tools_adds_five_wrappers():
    fake = FakeServer()
    register_tools(fake)
    assert set(fake.tools) == {
        "run_benchmark",
        "verify_citation",
        "lookup_statute",
        "retrieve_cases",
        "check_compliance",
    }


def test_server_subprocess_lists_registered_tools_when_sdk_available():
    repo_root = Path(__file__).resolve().parents[2]
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "from mcp.server.fastmcp import FastMCP; print('ok')",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if probe.returncode != 0:
        pytest.skip("MCP SDK is not installed in this Python environment")

    script = """
import asyncio, json
from backend.mcp.server import server
tools = asyncio.run(server.list_tools())
print(json.dumps(sorted(tool.name for tool in tools)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    names = set(json.loads(result.stdout))
    assert {
        "health",
        "run_benchmark",
        "verify_citation",
        "lookup_statute",
        "retrieve_cases",
        "check_compliance",
    } <= names
