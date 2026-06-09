"""junas-mcp server entry. F1 scaffold: stdio + http transports, health tool only."""
from __future__ import annotations
import argparse
import asyncio
import signal
import subprocess
import sys
from importlib import metadata as _metadata
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from .tools import register_tools

SERVER_NAME = "junas-mcp"
HTTP_PORT = 3344  # F1 default per issue #48

server = FastMCP(SERVER_NAME, host="127.0.0.1", port=HTTP_PORT)  # tools registered below

def _repo_version() -> str:
    try:
        return _metadata.version("junas")  # from backend/pyproject.toml
    except _metadata.PackageNotFoundError:
        return "unknown"

def _git_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[2]  # worktree root
        out = subprocess.run(  # noqa: S603 — fixed argv
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"

def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

@server.tool(description="Report repo version, git SHA, and Python version for setup verification.")
def health() -> dict:
    return {
        "server": SERVER_NAME,
        "repo_version": _repo_version(),
        "git_sha": _git_sha(),
        "python_version": _python_version(),
    }


register_tools(server)

def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    def _handler() -> None:
        stop.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handler)
        except NotImplementedError:
            signal.signal(sig, lambda *_: stop.set())  # windows fallback

async def _run_stdio() -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    _install_signal_handlers(loop, stop)
    serve = asyncio.create_task(server.run_stdio_async())
    halt = asyncio.create_task(stop.wait())
    done, pending = await asyncio.wait({serve, halt}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in done:
        exc = t.exception()
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            raise exc

async def _run_http() -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    _install_signal_handlers(loop, stop)
    serve = asyncio.create_task(server.run_streamable_http_async())
    halt = asyncio.create_task(stop.wait())
    done, pending = await asyncio.wait({serve, halt}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in done:
        exc = t.exception()
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            raise exc

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="junas-mcp", description="Junas MCP server (F1 scaffold).")
    p.add_argument("--http", action="store_true", help=f"serve streamable HTTP on :{HTTP_PORT} (default: stdio)")
    args = p.parse_args(argv)
    coro = _run_http() if args.http else _run_stdio()
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        return 130
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
