import json
import tempfile
import unittest
from pathlib import Path

from junas.backend.schemas import ReviewResponse
from scripts import export_openapi_examples

ROOT = Path(__file__).resolve().parent.parent
DEMO_ASSET_TAG = "readme-demo-assets-2026-06-30"
DEMO_GIF_URL = f"https://github.com/gongahkia/junas/releases/download/{DEMO_ASSET_TAG}/junas-demo.gif"
DEMO_FALLBACK_URL = f"https://github.com/gongahkia/junas/releases/download/{DEMO_ASSET_TAG}/junas-demo-fallback.png"


def _markdown_table_rows(markdown: str) -> list[list[str]]:
    rows = []
    for line in markdown.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    return rows


class ReadmeHeroArtifactTests(unittest.TestCase):
    def test_committed_hero_artifact_is_valid_review_response(self):
        request_path = ROOT / "docs" / "api" / "review_hero_request.json"
        response_path = ROOT / "docs" / "api" / "review_hero_response.json"
        markdown_path = ROOT / "docs" / "api" / "review_hero.md"
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertTrue(request_path.exists())
        self.assertTrue(response_path.exists())
        self.assertTrue(markdown_path.exists())
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))
        ReviewResponse.model_validate(response_payload)

        self.assertEqual(request_payload["source_jurisdiction"], "SG")
        self.assertEqual(request_payload["destination_jurisdiction"], "US")
        self.assertFalse(response_payload["send_allowed"])
        self.assertEqual(response_payload["policy_decision"]["decision"], "block")
        self.assertFalse(response_payload["policy_decision"]["send_allowed"])
        self.assertTrue(
            any(
                finding_id.startswith("pii:sg_nric_fin")
                for finding_id in response_payload["policy_decision"]["blocking_findings"]
            )
        )
        categories = {finding["category"] for finding in response_payload["findings"]}
        self.assertIn("PII", categories)
        self.assertIn("MNPI", categories)
        self.assertTrue(all(finding["legal_basis"] for finding in response_payload["findings"]))

        rationales = "\n".join(suggestion["rationale"] for suggestion in response_payload["suggestions"])
        self.assertIn("Personal Data Protection Act 2012", rationales)
        self.assertIn("Securities and Futures Act 2001", rationales)

        self.assertIn(export_openapi_examples.HERO_MARKER_START, readme)
        self.assertIn(export_openapi_examples.HERO_MARKER_END, readme)
        self.assertIn("./docs/api/review_hero_request.json", readme)
        self.assertIn("./docs/api/review_hero_response.json", readme)
        self.assertIn("send_allowed: false", readme)
        self.assertIn("policy_decision: block", readme)
        self.assertIn("SG_PDPA_PERSONAL_DATA", readme)
        self.assertIn("SG_SFA_INSIDE_INFORMATION", readme)

    def test_demo_capture_is_embedded_near_hero_and_regenerable(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        capture_doc = (ROOT / "docs" / "assets" / "demo" / "README.md")
        tape = ROOT / "docs" / "assets" / "demo" / "junas-demo.tape"
        self.assertTrue(capture_doc.exists())
        self.assertTrue(tape.exists())

        hero_end = readme.index(export_openapi_examples.HERO_MARKER_END)
        toc_start = readme.index("## Table of Contents")
        capture_section = readme[hero_end:toc_start]
        self.assertIn(DEMO_GIF_URL, capture_section)
        self.assertIn(DEMO_FALLBACK_URL, capture_section)
        self.assertIn("./docs/assets/demo/README.md", capture_section)
        self.assertIn("Terminal recording of ./scripts/demo.sh producing three Junas review verdicts", capture_section)
        self.assertIn("Static fallback PNG", capture_section)

        doc_text = capture_doc.read_text(encoding="utf-8")
        tape_text = tape.read_text(encoding="utf-8")
        self.assertIn("vhs docs/assets/demo/junas-demo.tape", doc_text)
        self.assertIn("magick /tmp/junas-demo.gif -coalesce", doc_text)
        self.assertIn("Do not commit generated GIF/PNG binaries", doc_text)
        self.assertIn(DEMO_GIF_URL, doc_text)
        self.assertIn(DEMO_FALLBACK_URL, doc_text)
        self.assertIn('Output "/tmp/junas-demo.gif"', tape_text)
        self.assertIn('Type "./scripts/demo.sh"', tape_text)
        self.assertNotIn(".gif", {path.suffix for path in (ROOT / "docs" / "assets" / "demo").iterdir()})
        self.assertNotIn(".png", {path.suffix for path in (ROOT / "docs" / "assets" / "demo").iterdir()})

    def test_exporter_regenerates_hero_artifacts_from_backend_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_openapi_examples.write_review_hero_artifacts(Path(tmp))
            response_payload = json.loads(paths["response"].read_text(encoding="utf-8"))
            markdown = paths["markdown"].read_text(encoding="utf-8")

        ReviewResponse.model_validate(response_payload)
        self.assertFalse(response_payload["send_allowed"])
        self.assertEqual(response_payload["policy_decision"]["decision"], "block")
        self.assertIn("Generated by `python3 scripts/export_openapi_examples.py`", markdown)
        self.assertIn("send_allowed: false", markdown)

    def test_why_junas_story_is_near_top_and_scoped(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        why_start = readme.index("## Why Junas")
        design_start = readme.index("## Design Principles")
        demo_start = readme.index("## Demo")
        quick_start = readme.index("## Quick Start")
        self.assertLess(why_start, design_start)
        self.assertLess(design_start, demo_start)
        self.assertLess(why_start, demo_start)
        self.assertLess(demo_start, quick_start)

        why_section = readme[why_start:demo_start]
        for token in (
            "public GenAI tool",
            "Project Raven",
            "SG NRIC",
            "deal codename",
            "acquisition price",
            "`/review`",
            "docs/product/positioning.md",
        ):
            self.assertIn(token, why_section)
        for forbidden in ("accuracy", "recall", "precision", "procurement-grade"):
            self.assertNotIn(forbidden, why_section.lower())

    def test_project_status_banner_is_near_top_and_honest(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        status_start = readme.index("Project status:")
        hero_start = readme.index(export_openapi_examples.HERO_MARKER_START)
        toc_start = readme.index("## Table of Contents")
        self.assertLess(status_start, hero_start)
        self.assertLess(status_start, toc_start)

        status_end = readme.index("\n\n", status_start)
        status = readme[status_start:status_end]
        for token in (
            "pre-production / portfolio-stage",
            "deterministic core",
            "policy contract",
            "demo artifacts",
            "supported-target adapter evidence",
            "production hardening",
            "independent eval expansion",
            "hosted demo",
            "[`TODO.md`](./TODO.md)",
        ):
            self.assertIn(token, status)
        for forbidden in ("production-ready", "complete", "guarantee", "guarantees", "procurement-grade"):
            self.assertNotIn(forbidden, status.lower())

    def test_design_principles_are_near_top_and_proven(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        why_start = readme.index("## Why Junas")
        design_start = readme.index("## Design Principles")
        scope_start = readme.index("## What This Is / What This Is NOT")
        demo_start = readme.index("## Demo")
        quick_start = readme.index("## Quick Start")
        self.assertLess(why_start, design_start)
        self.assertLess(design_start, scope_start)
        self.assertLess(scope_start, demo_start)
        self.assertLess(demo_start, quick_start)

        design_section = readme[design_start:scope_start]
        principles = [line for line in design_section.splitlines() if line.startswith("- **")]
        self.assertEqual(len(principles), 7)
        for token in (
            "Deterministic first",
            "Backend trust boundary",
            "LLM strictly advisory and gated",
            "Deterministic-high non-suppression",
            "Statute-cited findings",
            "Privacy-gated external calls",
            "Audit evidence by default",
        ):
            self.assertIn(token, design_section)

        for proof_link in (
            "./docs/architecture.md",
            "./src/junas/review/engine.py",
            "./docs/adr/0001-backend-first-adapters-second.md",
            "./docs/threat-model.md",
            "./docs/llm-governance.md",
            "./docs/running.md",
            "./test/test_llm_coverage_audit.py",
            "./src/junas/review/engine.py#L4317",
            "./test/test_source_verification.py",
            "./test/test_policy_engine.py",
            "./docs/statutory-coverage.md",
            "./test/test_citations.py",
            "./src/junas/external/privacy_guard.py",
            "./test/test_siem_export.py",
            "./docs/admin-security.md",
            "./test/test_audit_pack_smoke.py",
        ):
            self.assertIn(proof_link, design_section)

        self.assertIn("- [Design Principles](#design-principles)", readme)
        for forbidden in ("procurement-grade", "guarantee", "guarantees"):
            self.assertNotIn(forbidden, design_section.lower())

    def test_design_section_has_compact_architecture_diagram(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        design_start = readme.index("## Design Principles")
        scope_start = readme.index("## What This Is / What This Is NOT")
        design_section = readme[design_start:scope_start]

        for token in (
            "Compact runtime spine",
            "```mermaid",
            "flowchart LR",
            "Adapters / direct API<br/>Outlook, browser, DMS, clients",
            "FastAPI backend<br/>trust boundary",
            "Deterministic review engine<br/>PII + MNPI + citations",
            "Policy decision<br/>allow / warn / block / approval / rewrite",
            "Actions + audit evidence<br/>redact / hold / approval / SIEM",
            "Optional public evidence",
            "Optional LLM helpers",
            "privacy-gated opt-in",
            "tenant + deployer gated",
            "advisory only",
            "./docs/architecture.md",
        ):
            self.assertIn(token, design_section)
        self.assertGreaterEqual(design_section.count("-."), 4)

    def test_what_this_is_not_block_matches_non_goals_doc(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        non_goals = (ROOT / "docs" / "product" / "non-goals.md").read_text(encoding="utf-8")
        design_start = readme.index("## Design Principles")
        scope_start = readme.index("## What This Is / What This Is NOT")
        demo_start = readme.index("## Demo")
        self.assertLess(design_start, scope_start)
        self.assertLess(scope_start, demo_start)

        scope_section = readme[scope_start:demo_start]
        readme_rows = _markdown_table_rows(scope_section)
        non_goal_rows = _markdown_table_rows(non_goals)
        self.assertEqual(readme_rows[0], ["What this is", "What this is NOT"])
        self.assertEqual(non_goal_rows[0], ["Area", "Non-goal", "Junas boundary"])

        readme_pairs = [(row[0], row[1]) for row in readme_rows[1:]]
        doc_pairs = [(row[2], row[1]) for row in non_goal_rows[1:]]
        self.assertEqual(readme_pairs, doc_pairs)
        self.assertIn("./docs/product/non-goals.md", scope_section)
        self.assertIn("- [What This Is / What This Is NOT](#what-this-is--what-this-is-not)", readme)

    def test_accuracy_evaluation_section_is_scoped_and_sourced(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section_start = readme.index("## Accuracy & Evaluation")
        runtime_start = readme.index("## Runtime Modes")
        section = readme[section_start:runtime_start]

        self.assertIn("- [Accuracy & Evaluation](#accuracy--evaluation)", readme)
        for token in (
            "in-domain regression evidence over committed fixtures",
            "not a claim about general-world accuracy",
            "./docs/accuracy.md",
            "detector-level span evidence",
            "F-beta=2",
            "https://microsoft.github.io/presidio/evaluation/",
            "https://github.com/microsoft/presidio-research",
            "./reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json",
            "1,428 approved legal/cross-jurisdiction documents",
            "17,552 strict expected labels",
            "strict recall `1.0000`",
            "strict precision `0.9269`",
            "not an independent market benchmark",
            "./docs/candidate_corpus_status.md",
            "https://aclanthology.org/2022.cl-4.19/",
            "https://huggingface.co/datasets/ai4privacy/pii-masking-300k",
            "future comparison targets only",
            "no Junas score on those datasets is claimed",
            "There is no public MNPI benchmark",
            "Public-evidence matching and LLM adjudication accuracy are outside",
        ):
            self.assertIn(token, section)
        for forbidden in (
            "procurement-grade",
            "population-level",
            "production-ready",
            "guarantee",
            "guarantees",
            "state of the art",
            "sota",
        ):
            self.assertNotIn(forbidden, section.lower())


if __name__ == "__main__":
    unittest.main()
