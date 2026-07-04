import os
import tempfile
import unittest
from pathlib import Path

from junas.backend.schemas import Classification
from junas.review.engine import PreSendReviewEngine
from junas.review.secret_rulepacks import (
    DEFAULT_GITLEAKS_MAX_MATCHES,
    DEFAULT_GITLEAKS_MAX_RULES,
    DEFAULT_GITLEAKS_RULE_PACK_MAX_BYTES,
    ENV_GITLEAKS_MAX_MATCHES,
    ENV_GITLEAKS_RULE_PACKS,
    SecretRulePackError,
    clear_secret_rule_pack_cache_for_tests,
    load_gitleaks_rule_pack,
)

FIXTURE = Path(__file__).parent / "fixtures" / "external" / "gitleaks-custom.toml"
TOKEN = "a1b2c3d4e5f6g7h8i9j0"
ALLOWLISTED_TOKEN = "clientexampletokenx7y8z9"
ENV_KEYS = (
    ENV_GITLEAKS_RULE_PACKS,
    ENV_GITLEAKS_MAX_MATCHES,
    "JUNAS_GITLEAKS_MAX_RULES",
    "JUNAS_GITLEAKS_RULE_PACK_MAX_BYTES",
)


class SecretRulePackTests(unittest.TestCase):
    def setUp(self):
        self._env = {key: os.environ.get(key) for key in ENV_KEYS}
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        clear_secret_rule_pack_cache_for_tests()

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        clear_secret_rule_pack_cache_for_tests()

    def test_loads_gitleaks_toml_rule_pack(self):
        pack = load_gitleaks_rule_pack(FIXTURE)

        self.assertEqual(pack.title, "Junas test Gitleaks pack")
        self.assertEqual(len(pack.rules), 1)
        rule = pack.rules[0]
        self.assertEqual(rule.rule_id, "acme-api-token")
        self.assertEqual(rule.secret_group, 1)
        self.assertEqual(rule.entropy, 3.0)
        self.assertEqual(rule.keywords, ("acme", "api"))

    def test_default_engine_does_not_load_secret_rules(self):
        engine = PreSendReviewEngine()

        result = self._review(engine, f"ACME_API_KEY = {TOKEN}")

        self.assertNotIn("external_secret_acme-api-token", {finding.rule for finding in result.findings})

    def test_env_opt_in_flags_gitleaks_secret_as_high_risk_pii(self):
        os.environ[ENV_GITLEAKS_RULE_PACKS] = str(FIXTURE)
        engine = PreSendReviewEngine()

        result = self._review(engine, f"Send this credential to support: ACME_API_KEY = {TOKEN}")

        finding = self._secret_finding(result)
        self.assertEqual(finding.category, "PII")
        self.assertEqual(finding.severity, "high")
        self.assertEqual(finding.matched_text, TOKEN)
        self.assertEqual(finding.legal_basis, "EXTERNAL_SECRET_RULE_PACK")
        self.assertEqual(finding.metadata["detector_source"], "gitleaks")
        self.assertEqual(finding.metadata["rule_id"], "acme-api-token")
        self.assertEqual(result.overall_risk, Classification.HIGH_RISK)
        self.assertGreaterEqual(result.pii_score, 85.0)
        self.assertTrue(any(suggestion.finding_id == finding.id for suggestion in result.suggestions))

    def test_gitleaks_allowlists_suppress_matches(self):
        os.environ[ENV_GITLEAKS_RULE_PACKS] = str(FIXTURE)
        engine = PreSendReviewEngine()

        global_result = self._review(engine, f"allowlisted demo key ACME_API_KEY = {TOKEN}")
        rule_result = self._review(engine, f"ACME_API_KEY = {ALLOWLISTED_TOKEN}")

        self.assertIsNone(self._maybe_secret_finding(global_result))
        self.assertIsNone(self._maybe_secret_finding(rule_result))

    def test_match_limit_bounds_secret_rule_pack_findings(self):
        os.environ[ENV_GITLEAKS_RULE_PACKS] = str(FIXTURE)
        os.environ[ENV_GITLEAKS_MAX_MATCHES] = "2"
        engine = PreSendReviewEngine()
        text = "\n".join(f"ACME_API_KEY = {TOKEN}{suffix:02d}" for suffix in range(5))

        result = self._review(engine, text)

        self.assertEqual(
            2,
            len([finding for finding in result.findings if finding.rule == "external_secret_acme-api-token"]),
        )

    def test_invalid_extend_pack_fails_fast(self):
        with self.subTest("extend useDefault"):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "gitleaks-extend-invalid.toml"
                path.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")

                with self.assertRaises(SecretRulePackError):
                    load_gitleaks_rule_pack(path)

    def test_default_bounds_are_explicit(self):
        self.assertEqual(DEFAULT_GITLEAKS_MAX_RULES, 512)
        self.assertEqual(DEFAULT_GITLEAKS_MAX_MATCHES, 64)
        self.assertEqual(DEFAULT_GITLEAKS_RULE_PACK_MAX_BYTES, 2 * 1024 * 1024)

    def test_readme_and_docs_explain_optional_local_import(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        doc = (root / "docs" / "secret-rule-packs.md").read_text(encoding="utf-8")
        docs_index = (root / "docs" / "README.md").read_text(encoding="utf-8")

        for token in (
            "Optional Secret Rule Packs",
            "JUNAS_GITLEAKS_RULE_PACKS",
            "no cloud dependency",
            "EXTERNAL_SECRET_RULE_PACK",
            "docs/secret-rule-packs.md",
        ):
            self.assertIn(token, readme)
        for token in (
            "Supported Gitleaks Subset",
            "TruffleHog Evaluation",
            "JUNAS_GITLEAKS_MAX_RULES",
            "JUNAS_GITLEAKS_MAX_MATCHES",
            "`[extend]` is not resolved",
            "not a cloud dependency",
        ):
            self.assertIn(token, doc)
        self.assertIn("secret-rule-packs.md", docs_index)

    def _review(self, engine: PreSendReviewEngine, text: str):
        return engine.review(
            text=text,
            source_jurisdiction="US",
            destination_jurisdiction="US",
            entity_id=None,
            include_suggestions=True,
        )

    def _secret_finding(self, result):
        finding = self._maybe_secret_finding(result)
        self.assertIsNotNone(finding)
        return finding

    def _maybe_secret_finding(self, result):
        return next(
            (finding for finding in result.findings if finding.rule == "external_secret_acme-api-token"),
            None,
        )


if __name__ == "__main__":
    unittest.main()
