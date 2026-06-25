import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.policy import PolicyConfigError, load_policy_profile


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


if __name__ == "__main__":
    unittest.main()
