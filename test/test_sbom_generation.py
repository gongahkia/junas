import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_sbom_module():
    path = ROOT / "scripts" / "generate_sbom.py"
    spec = importlib.util.spec_from_file_location("test_generate_sbom_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load SBOM generator from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SbomGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_sbom_module()

    def test_generate_server_and_desktop_sboms_from_locked_graph(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir:
            out_dir = Path(tmp_dir) / "sbom"

            result = self.mod.main(["--target", "all", "--out-dir", str(out_dir)])

            self.assertEqual(result, 0)
            server = json.loads((out_dir / "junas-server.cdx.json").read_text(encoding="utf-8"))
            desktop = json.loads((out_dir / "junas-local-desktop.cdx.json").read_text(encoding="utf-8"))

        for sbom, target in ((server, "server"), (desktop, "desktop")):
            self.assertEqual(sbom["bomFormat"], "CycloneDX")
            self.assertEqual(sbom["specVersion"], "1.5")
            properties = {item["name"]: item["value"] for item in sbom["metadata"]["properties"]}
            self.assertEqual(properties["junas:sbom_target"], target)
            self.assertEqual(properties["junas:dependency_source"], "uv.lock")
            self.assertEqual(properties["junas:generator"], "scripts/generate_sbom.py")

        server_names = {component["name"] for component in server["components"]}
        desktop_names = {component["name"] for component in desktop["components"]}
        self.assertIn("boto3", server_names)
        self.assertIn("pyinstaller", desktop_names)

    def test_desktop_artifact_components_include_sha256_hashes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir:
            artifact_dir = Path(tmp_dir) / "dist" / "junas-local"
            artifact_dir.mkdir(parents=True)
            binary = artifact_dir / "junas-local"
            binary.write_bytes(b"desktop bundle")

            components = self.mod.desktop_artifact_components(artifact_dir)

        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], "file")
        self.assertEqual(components[0]["name"], "junas-local")
        self.assertEqual(components[0]["hashes"][0]["alg"], "SHA-256")
        self.assertEqual(components[0]["hashes"][0]["content"], hashlib.sha256(b"desktop bundle").hexdigest())

    def test_sbom_doc_is_indexed_and_covers_release_artifacts(self):
        text = (ROOT / "docs" / "security" / "sbom.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/sbom.md", docs_index)
        for token in (
            "scripts/generate_sbom.py --target all",
            "reports/sbom/junas-server.cdx.json",
            "reports/sbom/junas-local-desktop.cdx.json",
            "uv export --locked --extra server",
            "uv export --locked --extra local --extra packaging",
            "--require-desktop-artifact",
            "SHA-256",
            "CycloneDX 1.5",
            "https://docs.astral.sh/uv/reference/cli/#uv-export",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
