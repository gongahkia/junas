import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = ROOT / "docs" / "integrations" / "adapter-maturity.json"
UNSUPPORTED_MARKETING_TERMS = (
    "first-class",
    "production enforcement",
    "enterprise enforcement",
    "supported adapter",
    "supported integration",
    "supported target",
)


def _table_after_heading(path: Path, heading: str) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    start = text.index(heading)
    rows: list[list[str]] = []
    in_table = False
    for line in text[start:].splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(set(cell.replace(" ", "")) <= {"-", ":"} for cell in cells):
                continue
            rows.append(cells)
            in_table = True
            continue
        if in_table:
            break
    header, body = rows[0], rows[1:]
    return [dict(zip(header, row, strict=True)) for row in body]


def _rows_by(rows: list[dict[str, str]], column: str) -> dict[str, dict[str, str]]:
    return {row[column]: row for row in rows}


def _metadata() -> dict:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


class AdapterMaturityMetadataTests(unittest.TestCase):
    def test_maturity_metadata_labels_are_defined(self):
        metadata = _metadata()
        matrix = _rows_by(_table_after_heading(ROOT / "docs" / "integrations" / "maturity-matrix.md", "| Label |"), "Label")
        self.assertEqual(set(metadata["labels"]), {label.strip("`") for label in matrix})
        for label, details in metadata["labels"].items():
            self.assertIsInstance(details["supported_marketing"], bool)
            self.assertIn(f"`{label}`", matrix)

    def test_readme_adapter_maturity_table_matches_metadata(self):
        metadata = _metadata()
        rows = _rows_by(_table_after_heading(ROOT / "README.md", "## Adapter Maturity"), "Surface")
        expected = {
            surface["readme_surface"]: surface
            for surface in metadata["surfaces"]
            if surface["readme"]
        }
        self.assertEqual(set(rows), set(expected))
        for surface_name, surface in expected.items():
            with self.subTest(surface=surface_name):
                self.assertEqual(rows[surface_name]["Maturity"], f"`{surface['maturity']}`")

    def test_readme_does_not_market_unsupported_adapters_as_supported(self):
        metadata = _metadata()
        rows = _rows_by(_table_after_heading(ROOT / "README.md", "## Adapter Maturity"), "Surface")
        labels = metadata["labels"]
        for surface in metadata["surfaces"]:
            if not surface["readme"]:
                self.assertNotIn(surface["canonical_surface"], rows)
                continue
            if labels[surface["maturity"]]["supported_marketing"]:
                continue
            row_text = " ".join(rows[surface["readme_surface"]].values()).lower()
            with self.subTest(surface=surface["canonical_surface"]):
                for term in UNSUPPORTED_MARKETING_TERMS:
                    self.assertNotIn(term, row_text)

    def test_integration_indexes_match_maturity_metadata(self):
        metadata = _metadata()
        integrations_index = _rows_by(_table_after_heading(ROOT / "INTEGRATIONS.md", "| Surface |"), "Surface")
        source_registry = _rows_by(_table_after_heading(ROOT / "integrations" / "README.md", "| Surface |"), "Surface")

        expected_index = {
            surface["canonical_surface"]: surface
            for surface in metadata["surfaces"]
            if surface["integrations_index"]
        }
        expected_source = {
            surface["source_surface"]: surface
            for surface in metadata["surfaces"]
            if surface["source_registry"]
        }
        self.assertEqual(set(integrations_index), set(expected_index))
        self.assertEqual(set(source_registry), set(expected_source))

        for surface_name, surface in expected_index.items():
            with self.subTest(integrations_surface=surface_name):
                self.assertEqual(integrations_index[surface_name]["Maturity"], f"`{surface['maturity']}`")
        for surface_name, surface in expected_source.items():
            with self.subTest(source_surface=surface_name):
                self.assertEqual(source_registry[surface_name]["Maturity"], f"`{surface['maturity']}`")

    def test_adapter_maturity_metadata_is_linked_from_docs(self):
        for relative in ("INTEGRATIONS.md", "docs/integrations/README.md"):
            with self.subTest(path=relative):
                self.assertIn("adapter-maturity.json", (ROOT / relative).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
