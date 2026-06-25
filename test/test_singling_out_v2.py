import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from junas.review.engine import PreSendReviewEngine
from junas.review.singling_out.scorer import (
    _load_generated_tables,
    _load_sg_tables,
    _tables_for,
    clear_table_cache_for_tests,
)
from scripts.build_frequency_tables import main as build_frequency_tables_main


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
        license: str = "test open licence",
        refresh_due_date: str = "2027-06-08",
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
            f'license = "{license}"\n'
            'license_url = "https://example.test/licence"\n'
            'retrieved_date = "2026-06-08"\n'
            f'refresh_due_date = "{refresh_due_date}"\n'
            f'sha256 = "{digest}"\n'
        )
        (root / "MANIFEST.generated.toml").write_text(manifest, encoding="utf-8")

    def _builder_metadata_args(self, source_name: str) -> list[str]:
        return [
            "--source-name", source_name,
            "--source-url", "https://example.test/source",
            "--license", "test open licence",
            "--license-url", "https://example.test/licence",
            "--attribution", "test attribution",
            "--license-scope", "test aggregate source scope",
            "--redistribution", "operator_local_only",
        ]

    def test_sg_frequency_manifest_loads(self):
        tables = _load_sg_tables()
        self.assertGreater(tables.total_population, 4_000_000)
        self.assertIn("population_by_area_age", tables.loaded_tables)
        self.assertIn("postal_sector_population", tables.loaded_tables)
        self.assertIn("role_frequency", tables.loaded_tables)
        self.assertGreater(tables.role_population["MANAGER"], 100_000)
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

    def test_bundled_non_sg_frequency_manifests_load(self):
        clear_table_cache_for_tests()
        for code, table_name, key in [
            ("UK", "postal_population", "EC2M 5"),
            ("UK", "name_frequency", "AABAN"),
            ("AU", "postal_population", "5950"),
            ("AU", "name_frequency", "NOAH"),
            ("JP", "area_population", "東京都"),
            ("KR", "area_population", "서울 중구"),
            ("US", "surname_frequency", "SMITH"),
        ]:
            with self.subTest(code=code):
                tables = _tables_for(code)
                self.assertIsNotNone(tables)
                self.assertIn(table_name, tables.loaded_tables)
                if table_name == "postal_population":
                    self.assertGreaterEqual(tables.postal_population[key], 1)
                elif table_name == "name_frequency":
                    self.assertGreaterEqual(tables.name_population[key], 1)
                elif table_name == "surname_frequency":
                    self.assertGreater(tables.surname_population[key], 1_000_000)
                else:
                    self.assertGreater(tables.area_population[key.casefold()], 1_000)

    def test_strict_non_sg_v2_activates_from_bundled_tables_without_env(self):
        clear_table_cache_for_tests()
        with mock.patch.dict(os.environ, {}, clear=True):
            findings = self._quasi_for(
                "Dr Jane Tan; Age: 42; office 1 Liverpool Street London EC2M 5QQ.",
                "UK",
            )
        self.assertEqual(len(findings), 1)
        metadata = findings[0].metadata
        self.assertEqual(metadata["layer"], "singling_out_v2")
        self.assertEqual(metadata["k_anonymity_equivalence"], 1)
        self.assertEqual(metadata["frequency_tables_used"], ["name_frequency", "postal_population"])

    def test_strict_non_sg_v2_prefers_generated_table_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(root, "UK", "postal_population", "postal_prefix,population\nSW1A 1,3\n")
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi_for(
                    "Dr Jane Tan; Age: 42; address 10 Downing Street SW1A 1AA.",
                    "UK",
                )
            self.assertEqual(len(findings), 1)
            metadata = findings[0].metadata
            self.assertEqual(metadata["layer"], "singling_out_v2")
            self.assertEqual(metadata["k_anonymity_equivalence"], 3)
            self.assertEqual(metadata["frequency_tables_used"], ["postal_population"])

    def test_generated_us_surname_table_can_drive_named_person_k(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(root, "US", "surname_frequency", "surname,population\nRARETEST,4\n")
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi_for(
                    "Dr Jane Raretest; Age: 42; address 123 Market Street, CA 94105.",
                    "US",
                )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 4)
        self.assertEqual(findings[0].metadata["frequency_tables_used"], ["surname_frequency"])
        self.assertIn("postal_population", findings[0].metadata["frequency_tables_missing"])

    def test_generated_name_table_can_drive_named_person_k(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(root, "US", "name_frequency", "name,population\nJane Raretest,4\n")
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi_for(
                    "Dr Jane Raretest; Age: 42; address 123 Market Street, CA 94105.",
                    "US",
                )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 4)
        self.assertEqual(findings[0].metadata["frequency_tables_used"], ["name_frequency"])

    def test_bundled_uk_given_name_table_can_drive_named_person_k(self):
        clear_table_cache_for_tests()
        with mock.patch.dict(os.environ, {}, clear=True):
            findings = self._quasi_for(
                "Dr Aaban Smith is a Senior Actuary; Age: 42.",
                "UK",
            )
        self.assertEqual(len(findings), 1)
        metadata = findings[0].metadata
        self.assertEqual(metadata["k_anonymity_equivalence"], 4)
        self.assertEqual(metadata["frequency_tables_used"], ["name_frequency"])
        self.assertIn("quasi_identifier_component_spans", metadata)

    def test_generated_sg_name_table_can_override_bundled_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(root, "SG", "name_frequency", "name,population\nJane Raretest,4\n")
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi(
                    "Dr Jane Raretest; Age: 42; address 77 Shenton Way, Singapore 068810."
                )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 4)
        self.assertEqual(findings[0].metadata["frequency_tables_used"], ["name_frequency"])

    def test_builder_generated_sg_name_table_can_drive_named_person_k(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sg_names.csv"
            out = root / "out"
            source.write_text("name,population\nJane Raretest,4\n", encoding="utf-8")
            self.assertEqual(
                build_frequency_tables_main([
                    "--jurisdiction", "SG",
                    "--table", "name_frequency",
                    "--source", f"SG={source}",
                    "--out", str(out),
                    "--retrieved-date", "2026-06-10",
                    *self._builder_metadata_args("operator SG name source"),
                ]),
                0,
            )
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": str(out)}):
                findings = self._quasi(
                    "Dr Jane Raretest; Age: 42; address 77 Shenton Way, Singapore 068810."
                )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 4)
        self.assertEqual(findings[0].metadata["frequency_tables_used"], ["name_frequency"])

    def test_builder_generated_jp_kr_role_tables_can_drive_role_k(self):
        for code in ("JP", "KR"):
            with self.subTest(code=code):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    source = root / f"{code.lower()}_roles.csv"
                    out = root / "out"
                    source.write_text("occupation,population\nSenior Actuary,3\n", encoding="utf-8")
                    self.assertEqual(
                        build_frequency_tables_main([
                            "--jurisdiction", code,
                            "--table", "role_frequency",
                            "--source", f"{code}={source}",
                            "--out", str(out),
                            "--retrieved-date", "2026-06-10",
                            *self._builder_metadata_args(f"operator {code} role source"),
                        ]),
                        0,
                    )
                    clear_table_cache_for_tests()
                    with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": str(out)}):
                        findings = self._quasi_for(
                            "Dr Jane Raretest works as Senior Actuary. Age: 42.",
                            code,
                        )

                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 3)
                self.assertEqual(findings[0].metadata["frequency_tables_used"], ["role_frequency"])

    def test_generated_role_table_can_drive_personal_attribute_k(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(root, "US", "role_frequency", "role,population\nActuary,3\n")
            clear_table_cache_for_tests()
            with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi_for(
                    "Dr Jane Raretest is a Senior Actuary; Age: 42; address 123 Market Street, CA 94105.",
                    "US",
                )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 3)
        self.assertEqual(findings[0].metadata["frequency_tables_used"], ["role_frequency"])
        self.assertIn("name_density", findings[0].metadata["frequency_tables_missing"])

    def test_generated_table_with_stale_refresh_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(
                root,
                "SG",
                "name_frequency",
                "name,population\nJane Raretest,4\n",
                refresh_due_date="2020-06-08",
            )
            with self.assertRaises(RuntimeError):
                _load_generated_tables("SG", root)

    def test_generated_table_missing_license_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_generated_table(
                root,
                "SG",
                "name_frequency",
                "name,population\nJane Raretest,4\n",
                license="",
            )
            with self.assertRaises(RuntimeError):
                _load_generated_tables("SG", root)

    def test_bundled_au_postal_table_can_emit_low_k_cluster(self):
        clear_table_cache_for_tests()
        with mock.patch.dict(os.environ, {}, clear=True):
            findings = self._quasi_for(
                "Dr Jane Tan; Age: 42; address 1 Airport Drive, Adelaide Airport SA 5950.",
                "AU",
            )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 4)
        evidence = findings[0].metadata.get("locality_evidence", [])
        self.assertTrue(any(item.get("kind") == "postal_population" for item in evidence))

    def test_invalid_generated_checksum_falls_back_to_bundled_tables(self):
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
            with mock.patch.dict(os.environ, {"JUNAS_FREQUENCY_DATA_DIR": tmp}):
                findings = self._quasi_for(
                    "Dr Jane Tan; Age: 42; office 1 Liverpool Street London EC2M 5QQ.",
                    "UK",
                )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["k_anonymity_equivalence"], 1)


if __name__ == "__main__":
    unittest.main()
