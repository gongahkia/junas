import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.policy import PolicyConfigError, load_policy_profile

POLICY_DOCS = (
    ROOT / "docs" / "policy" / "schema.md",
    ROOT / "docs" / "policy" / "examples.md",
)


def _toml_blocks(path: Path) -> list[str]:
    blocks = []
    lines: list[str] = []
    in_toml = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "```toml":
            in_toml = True
            lines = []
            continue
        if in_toml and line == "```":
            blocks.append("\n".join(lines) + "\n")
            in_toml = False
            continue
        if in_toml:
            lines.append(line)
    return blocks


class PolicyConfigTests(unittest.TestCase):
    def _write_config(self, content: str) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        path = Path(tempdir.name) / "policy.toml"
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return path

    def test_loads_base_policy_profile(self):
        path = self._write_config(
            """
            [policy]
            policy_id = "enterprise-soft"
            policy_version = "2026-06-14.1"
            internal_domains = ["Example.COM."]
            high_pii_required_actions = ["safe_rewrite", "request_approval"]
            """
        )

        profile = load_policy_profile(path, production=True)

        self.assertEqual(profile.policy_id, "enterprise-soft")
        self.assertEqual(profile.policy_version, "2026-06-14.1")
        self.assertEqual(profile.internal_domains, ("example.com",))
        self.assertEqual(profile.high_pii_required_actions, ("safe_rewrite", "request_approval"))

    def test_tenant_override_merges_with_base_policy(self):
        path = self._write_config(
            """
            [policy]
            policy_id = "default"
            policy_version = "2026-06-14"
            high_pii_required_actions = ["safe_rewrite", "request_approval"]

            [tenants.law-firm]
            policy_id = "law-firm-strict"
            policy_version = "2026-06-14-law"
            high_mnpi_external_actions = ["hold_until_public"]
            """
        )

        profile = load_policy_profile(path, tenant_id="law-firm", production=True)

        self.assertEqual(profile.policy_id, "law-firm-strict")
        self.assertEqual(profile.policy_version, "2026-06-14-law")
        self.assertEqual(profile.high_pii_required_actions, ("safe_rewrite", "request_approval"))
        self.assertEqual(profile.high_mnpi_external_actions, ("hold_until_public",))

    def test_unknown_section_fails_validation(self):
        path = self._write_config(
            """
            [policy]
            policy_version = "2026-06-14"

            [other]
            enabled = true
            """
        )

        with self.assertRaises(PolicyConfigError) as ctx:
            load_policy_profile(path)

        self.assertIn("unknown policy config sections", str(ctx.exception))

    def test_invalid_action_fails_validation(self):
        path = self._write_config(
            """
            [policy]
            policy_version = "2026-06-14"
            high_pii_required_actions = ["dump_raw_text"]
            """
        )

        with self.assertRaises(PolicyConfigError) as ctx:
            load_policy_profile(path)

        self.assertIn("unsupported action", str(ctx.exception))

    def test_production_policy_requires_explicit_version(self):
        path = self._write_config(
            """
            [policy]
            policy_id = "missing-version"
            """
        )

        with self.assertRaises(PolicyConfigError) as ctx:
            load_policy_profile(path, production=True)

        self.assertIn("policy.policy_version", str(ctx.exception))

    def test_production_tenant_override_requires_explicit_version(self):
        path = self._write_config(
            """
            [policy]
            policy_id = "default"
            policy_version = "2026-06-14"

            [tenants.tenant-a]
            policy_id = "tenant-a-policy"
            """
        )

        with self.assertRaises(PolicyConfigError) as ctx:
            load_policy_profile(path, tenant_id="tenant-a", production=True)

        self.assertIn("tenants.tenant-a.policy_version", str(ctx.exception))

    def test_docs_policy_config_examples_validate_in_production(self):
        seen_blocks = 0
        for doc in POLICY_DOCS:
            blocks = _toml_blocks(doc)
            self.assertTrue(blocks, f"missing TOML policy examples in {doc}")
            for index, block in enumerate(blocks):
                with self.subTest(doc=doc.name, block=index):
                    raw = tomllib.loads(block)
                    self.assertIn("policy", raw)
                    path = self._write_config(block)
                    profile = load_policy_profile(path, production=True)
                    self.assertTrue(profile.policy_id)
                    self.assertTrue(profile.policy_version)
                    for tenant_id in raw.get("tenants", {}):
                        tenant_profile = load_policy_profile(path, tenant_id=tenant_id, production=True)
                        self.assertTrue(tenant_profile.policy_id)
                        self.assertTrue(tenant_profile.policy_version)
                    seen_blocks += 1
        self.assertGreaterEqual(seen_blocks, 6)


if __name__ == "__main__":
    unittest.main()
