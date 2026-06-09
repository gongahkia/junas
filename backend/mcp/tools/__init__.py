"""Tool registration for the junas MCP server."""
from __future__ import annotations

from typing import Any

from .check_compliance import check_compliance
from .lookup_statute import lookup_statute
from .retrieve_cases import retrieve_cases
from .run_benchmark import run_benchmark
from .verify_citation import verify_citation


def register_tools(server: Any) -> None:
    """Register junas tools on a FastMCP server instance."""
    server.tool(description="Run a local SG-LegalBench task with the oracle harness.")(
        run_benchmark
    )
    server.tool(description="Validate a Singapore legal citation against the SAL grammar.")(
        verify_citation
    )
    server.tool(description="Look up a Singapore statute section from local SSO data.")(
        lookup_statute
    )
    server.tool(description="Retrieve related cases from the local case-retrieval corpus.")(
        retrieve_cases
    )
    server.tool(description="Check text against local SG compliance rules.")(
        check_compliance
    )


__all__ = [
    "check_compliance",
    "lookup_statute",
    "register_tools",
    "retrieve_cases",
    "run_benchmark",
    "verify_citation",
]
