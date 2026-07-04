import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ArchitectureDocTests(unittest.TestCase):
    def test_runtime_architecture_diagram_keeps_adapters_outside_core_engine(self):
        text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        for token in (
            "subgraph OptionalAdapters[Optional workflow activation surfaces]",
            "Outlook Smart Alerts",
            "Browser GenAI extension",
            "Word taskpane",
            "DMS upload hook",
            "Desktop watcher",
            "FastAPI backend<br/>trust boundary",
            "Request validation<br/>tenant/auth checks",
            "Deterministic review engine",
            "Policy engine<br/>decision + actions",
            "Adapters feed the API",
            "not part of the core deterministic engine",
            "must not call or embed the review engine directly",
        ):
            self.assertIn(token, text)

    def test_top_level_architecture_doc_is_reviewer_entry_point(self):
        path = ROOT / "ARCHITECTURE.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for token in (
            "reviewer-facing map",
            "## Core Boundary",
            "FastAPI service",
            "trust boundary",
            "request validation",
            "tenant/auth checks",
            "policy decisions",
            "audit events",
            "Adapters under [`integrations/`](./integrations/) are activation surfaces",
            "## Request Lifecycle",
            "A caller sends text or a supported document payload",
            "[`src/junas/backend/main.py`](./src/junas/backend/main.py)",
            "[`PreSendReviewEngine.review`](./src/junas/review/engine.py)",
            "[`src/junas/policy/engine.py`](./src/junas/policy/engine.py)",
            "`policy_decision`",
            "`review_expires_at`",
            "allow/warn the user",
            "## Deterministic Core",
            "The policy engine is separate from detection on purpose",
            "## Advisory Layers",
            "`strict` is deterministic",
            "## Non-Suppression Invariant",
            "Deterministic-high findings stay in the review and policy path",
            "policy softening must not erase deterministic-high",
            "[`test/test_llm_coverage_audit.py`](./test/test_llm_coverage_audit.py)",
            "[`test/test_source_verification.py`](./test/test_source_verification.py)",
            "[`test/test_policy_engine.py`](./test/test_policy_engine.py)",
            "## Primary Files",
            "docs/adr/0001-backend-first-adapters-second.md",
            "docs/threat-model.md",
            "docs/llm-governance.md",
        ):
            self.assertIn(token, text)

        lifecycle_lines = [line for line in text.splitlines() if line[:3] in {f"{idx}. " for idx in range(1, 7)}]
        self.assertEqual(len(lifecycle_lines), 6)
        self.assertIn("[`ARCHITECTURE.md`](./ARCHITECTURE.md)", readme)
        design_section = readme[readme.index("## Design Principles") : readme.index("## Adapter Maturity")]
        self.assertIn("[`ARCHITECTURE.md`](./ARCHITECTURE.md)", design_section)

    def test_top_level_architecture_doc_avoids_overclaim_language(self):
        text = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8").lower()
        for forbidden in (
            "guarantee",
            "guarantees",
            "production-ready",
            "procurement-grade",
            "universal capture",
            "eliminates",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
