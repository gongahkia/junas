import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ManagedLLMDeploymentDocsTests(unittest.TestCase):
    def test_managed_llm_doc_separates_default_public_evidence_and_llm(self):
        text = (ROOT / "docs" / "deployment-managed-llm.md").read_text(encoding="utf-8")

        for token in (
            "## Default: Deterministic-Only",
            "JUNAS_PUBLIC_EVIDENCE_ENABLED=0",
            "JUNAS_LLM_ENABLED=0",
            "## Opt-In: Public Evidence Only",
            "Public evidence retrieval is for audit-grade public-source checks. It is not LLM adjudication.",
            "PIPELINE_LAYERS=public_evidence",
            "## Opt-In: LLM Adjudication",
            "JUNAS_LLM_INPUT_MODE=structured_tokens",
            "JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT=0",
            "JUNAS_LLM_TENANT_OPT_IN_OPENAI=1",
            "## Exceptional: Remote Raw Text",
            "JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT=1",
            "docker-compose.managed-llm.yml",
            "deterministic policy decision path",
        ):
            self.assertIn(token, text)

    def test_compose_overlay_keeps_remote_raw_text_opt_in_explicit(self):
        text = (ROOT / "docker-compose.managed-llm.yml").read_text(encoding="utf-8")

        self.assertIn("JUNAS_PUBLIC_EVIDENCE_ENABLED", text)
        self.assertIn('JUNAS_LLM_ENABLED: "1"', text)
        self.assertIn("JUNAS_LLM_INPUT_MODE", text)
        self.assertIn("JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT", text)
        self.assertIn("JUNAS_LLM_TENANT_OPT_IN_OPENAI:?set to 1 only after tenant opt-in", text)

    def test_docs_index_links_managed_llm_deployment_doc(self):
        text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("deployment-managed-llm.md", text)


if __name__ == "__main__":
    unittest.main()
