import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PackagingScriptTests(unittest.TestCase):
    def run_script(self, script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        merged_env.update(env)
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / script)],
            cwd=ROOT,
            env=merged_env,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def test_browser_packager_fails_clearly_when_integration_source_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_script(
                "package_browser_extension.sh",
                {
                    "JUNAS_EXTENSION_SRC": str(Path(tmp) / "missing_browser_extension"),
                    "JUNAS_EXTENSION_OUT_DIR": str(Path(tmp) / "out"),
                },
            )

        self.assertEqual(result.returncode, 64)
        self.assertIn("missing browser extension source:", result.stderr)
        self.assertIn("manifest.json", result.stderr)

    def test_macos_packager_fails_clearly_when_desktop_source_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_script(
                "package_macos_desktop.sh",
                {
                    "JUNAS_DESKTOP_SRC": str(Path(tmp) / "missing_desktop"),
                    "JUNAS_PACKAGE_OUTPUT": str(Path(tmp) / "out.zip"),
                },
            )

        self.assertEqual(result.returncode, 64)
        self.assertIn("missing desktop adapter source:", result.stderr)
        self.assertIn("watch.py", result.stderr)


if __name__ == "__main__":
    unittest.main()
