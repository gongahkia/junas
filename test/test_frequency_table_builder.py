import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

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
            self.assertIn("attribution", manifest)
            self.assertIn("license_scope", manifest)
            self.assertIn("redistribution", manifest)
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

    def test_builds_au_postal_population_from_poa_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "au.csv"
            out = root / "out"
            source.write_text("POA_CODE_2021,Tot_P_P\nPOA5950,4\nPOA2000,27936\n", encoding="utf-8")
            code = main([
                "--jurisdiction", "AU",
                "--source", f"AU={source}",
                "--out", str(out),
                "--retrieved-date", "2026-06-09",
            ])
            self.assertEqual(code, 0)
            table = (out / "AU" / "postal_population.csv").read_text(encoding="utf-8")
            self.assertIn("5950,4\n", table)
            self.assertIn("2000,27936\n", table)

    def test_builds_kr_area_population_from_cp949_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "kr.csv"
            out = root / "out"
            source.write_bytes("시도명,시군구명,계\n서울특별시,중구,10\n서울특별시,중구,7\n".encode("cp949"))
            code = main([
                "--jurisdiction", "KR",
                "--source", f"KR={source}",
                "--out", str(out),
                "--retrieved-date", "2026-06-09",
            ])
            self.assertEqual(code, 0)
            table = (out / "KR" / "area_population.csv").read_text(encoding="utf-8")
            self.assertIn("서울 중구,17\n", table)

    def test_builds_us_surname_frequency_from_census_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "names.zip"
            out = root / "out"
            csv_payload = (
                "name,rank,count,prop100k\n"
                "SMITH,1,2442977,828.19\n"
                "RARETEST,2,4,0.00\n"
                "ALL OTHER NAMES,0,29312001,9936.97\n"
            )
            with zipfile.ZipFile(source, "w") as zf:
                zf.writestr("Names_2010Census.csv", csv_payload)
            code = main([
                "--jurisdiction", "US",
                "--source", f"US={source}",
                "--out", str(out),
                "--retrieved-date", "2026-06-09",
            ])
            self.assertEqual(code, 0)
            table = (out / "US" / "surname_frequency.csv").read_text(encoding="utf-8")
            self.assertIn("SMITH,2442977\n", table)
            self.assertIn("RARETEST,4\n", table)
            self.assertNotIn("ALLOTHERNAMES", table)
            manifest = (out / "MANIFEST.generated.toml").read_text(encoding="utf-8")
            self.assertIn("[US.surname_frequency]", manifest)
            self.assertIn("U.S. Census Bureau", manifest)

    def test_missing_source_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--jurisdiction", "AU", "--out", tmp])
        self.assertEqual(code, 2)

    def test_list_sources_does_not_require_output_or_source(self):
        with mock.patch("sys.stdout") as stdout:
            code = main(["--list-sources"])
        self.assertEqual(code, 0)
        rendered = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertIn("Open Government Licence v3.0", rendered)
        self.assertIn("Creative Commons Attribution 4.0 International", rendered)
        self.assertIn("e-Stat Terms of Use", rendered)
        self.assertIn("Open Government Data Portal scope of use: limitless", rendered)
        self.assertIn("U.S. Census Bureau", rendered)


if __name__ == "__main__":
    unittest.main()
