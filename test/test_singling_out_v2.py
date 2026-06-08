import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kaypoh.review.engine import PreSendReviewEngine
from kaypoh.review.singling_out.scorer import (
    _load_generated_tables,
    _load_sg_tables,
    clear_table_cache_for_tests,
)


class SinglingOutV2Tests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _quasi(self, text: str):
        result = self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        return [f for f in result.findings if f.rule == "quasi_identifier_combination"]

    def _quasi_for(self, text: str, jurisdiction: str):
        result = self.engine.review(
            text=text,
            source_jurisdiction=jurisdiction,
            destination_jurisdiction=jurisdiction,
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        return [f for f in result.findings if f.rule == "quasi_identifier_combination"]

    def _write_generated_table(
        self,
        root: Path,
        jurisdiction: str,
        table: str,
        csv_text: str,
        *,
        sha256: str | None = None,
    ):
        table_dir = root / jurisdiction
        table_dir.mkdir(parents=True, exist_ok=True)
        (table_dir / f"{table}.csv").write_text(csv_text, encoding="utf-8")
        digest = sha256 or hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
        manifest = (
            'schema_version = 1\n'
            'generated_by = "test"\n\n'
            f"[{jurisdiction}.{table}]\n"
            f'path = "{jurisdiction}/{table}.csv"\n'
            'source_name = "test source"\n'
            'source_url = "https://example.test/source"\n'
            'license = "test open licence"\n'
            'license_url = "https://example.test/licence"\n'
            'retrieved_date = "2026-06-08"\n'
            'refresh_due_date = "2027-06-08"\n'
            f'sha256 = "{digest}"\n'
        )
        (root / "MANIFEST.generated.toml").write_text(manifest, encoding="utf-8")

    def test_sg_frequency_manifest_loads(self):
        tables = _load_sg_tables()
        self.assertGreater(tables.total_population, 4_000_000)
        self.assertIn("population_by_area_age", tables.loaded_tables)
        self.assertIn("postal_sector_population", tables.loaded_tables)
        for prefix in ("12", "46", "54", "61", "65"):
            with self.subTest(prefix=prefix):
                self.assertIn(prefix, tables.postal_population)

    def test_strict_sg_v2_emits_k_metadata_for_unique_contact_cluster(self):
        findings = self._quasi(
            "Dr Jane Tan can be reached at +65 9123 4567 or jane.tan@example.sg."
        )
        self.assertEqual(len(findings), 1)
        metadata = findings[0].metadata
        self.assertEqual(metadata["layer"], "singling_out_v2")
        self.assertEqual(metadata["k_anonymity_equivalence"], 1)
        self.assertEqual(metadata["re_identification_estimate"], 1.0)
        self.assertEqual(metadata["singling_out_scope"], "paragraph")

    def test_identifiers_in_separate_paragraphs_do_not_aggregate(self):
        text = "Dr Jane Tan leads the team.\n\nPhone: +65 9123 4567.\n\nEmail: jane.tan@example.sg."
        self.assertEqual(self._quasi(text), [])

    def test_generated_uk_frequency_manifest_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(root, "UK", "postal_population", "postal_prefix,population\nSW1A 1,3\n")
            tables = _load_generated_tables("UK", root)
            self.assertIsNotNone(tables)
            self.assertEqual(tables.jurisdiction, "UK")
            self.assertEqual(tables.postal_population["SW1A 1"], 3)
            self.assertIn("postal_population", tables.loaded_tables)

    def test_strict_non_sg_v2_activates_when_generated_table_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(root, "UK", "postal_population", "postal_prefix,population\nSW1A 1,3\n")
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"KAYPOH_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi_for(
                    "Dr Jane Tan; Age: 42; address 10 Downing Street SW1A 1AA.",
                    "UK",
                )
            self.assertEqual(len(findings), 1)
            metadata = findings[0].metadata
            self.assertEqual(metadata["layer"], "singling_out_v2")
            self.assertEqual(metadata["k_anonymity_equivalence"], 3)
            self.assertEqual(metadata["frequency_tables_used"], ["postal_population"])

    def test_strict_non_sg_v2_stays_silent_without_generated_table(self):
        clear_table_cache_for_tests()
        with mock.patch.dict(os.environ, {}, clear=True):
            findings = self._quasi_for(
                "Dr Jane Tan; Age: 42; address 10 Downing Street SW1A 1AA.",
                "UK",
            )
        self.assertEqual(findings, [])

    def test_invalid_generated_checksum_stays_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(
                root,
                "UK",
                "postal_population",
                "postal_prefix,population\nSW1A 1,3\n",
                sha256="bad",
            )
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"KAYPOH_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi_for(
                    "Dr Jane Tan; Age: 42; address 10 Downing Street SW1A 1AA.",
                    "UK",
                )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
