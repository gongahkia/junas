import tempfile
import unittest
from pathlib import Path

from scripts.build_frequency_tables import main


class FrequencyTableBuilderTests(unittest.TestCase):
    def test_builds_uk_postal_population_from_local_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "uk.csv"
            out = root / "out"
            source.write_text(
                "postcode,population\nSW1A 1AA,2\nSW1A 1AB,3\nBT1 1AA,999\n",
                encoding="utf-8",
            )
            code = main([
                "--jurisdiction", "UK",
                "--source", f"UK={source}",
                "--out", str(out),
                "--retrieved-date", "2026-06-08",
            ])
            self.assertEqual(code, 0)
            table = (out / "UK" / "postal_population.csv").read_text(encoding="utf-8")
            self.assertIn("SW1A 1,5\n", table)
            self.assertNotIn("BT1", table)
            manifest = (out / "MANIFEST.generated.toml").read_text(encoding="utf-8")
            self.assertIn("[UK.postal_population]", manifest)
            self.assertIn("Northern Ireland BT postcodes excluded", manifest)

    def test_builds_jp_area_population_from_local_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "jp.csv"
            out = root / "out"
            source.write_text("area,population\nTokyo,14000000\nOsaka,8800000\n", encoding="utf-8")
            code = main([
                "--jurisdiction", "JP",
                "--source", f"JP={source}",
                "--out", str(out),
                "--retrieved-date", "2026-06-08",
            ])
            self.assertEqual(code, 0)
            table = (out / "JP" / "area_population.csv").read_text(encoding="utf-8")
            self.assertIn("Tokyo,14000000\n", table)
            self.assertIn("[JP.area_population]", (out / "MANIFEST.generated.toml").read_text(encoding="utf-8"))

    def test_missing_source_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--jurisdiction", "AU", "--out", tmp])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
