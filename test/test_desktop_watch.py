import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from junas.desktop import watch


class DesktopWatchTests(unittest.TestCase):
    def test_scan_paths_reviews_file_and_writes_anonymized_copy_only_when_requested(self):
        calls = []

        def fake_post(base_url, path, payload, timeout_seconds, headers):
            calls.append((base_url, path, payload, timeout_seconds, headers))
            if path == "/review":
                return {"overall_risk": "HIGH", "document_score": 90.0, "findings": [{"rule": "sg_nric_fin"}]}
            return {"anonymized_text": "Send [NRIC_FIN_1]"}

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(watch, "_post_json_with_headers", side_effect=fake_post),
        ):
            root = Path(tmp)
            source = root / "note.txt"
            out = root / "out"
            source.write_text("Send S1234567D", encoding="utf-8")
            config = watch.WatchConfig(anonymize_output_dir=out, local_token="signed-token")

            summaries = watch.scan_paths([source], config)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].finding_count, 1)
        self.assertTrue(str(summaries[0].anonymized_path).endswith("note.txt.anonymized.txt"))
        self.assertEqual(calls[0][1], "/review")
        self.assertEqual(calls[1][1], "/anonymize")
        self.assertEqual(calls[0][2]["text"], "Send S1234567D")
        self.assertEqual(calls[0][4]["X-Junas-Local-Token"], "signed-token")

    def test_scan_paths_does_not_call_anonymize_without_explicit_output_dir(self):
        def fake_post(_base_url, path, _payload, _timeout_seconds, _headers):
            self.assertEqual(path, "/review")
            return {"overall_risk": "HIGH", "document_score": 80.0, "findings": [{"rule": "email_address"}]}

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(watch, "_post_json_with_headers", side_effect=fake_post),
        ):
            source = Path(tmp) / "note.txt"
            source.write_text("Email jane@example.com", encoding="utf-8")
            summaries = watch.scan_paths([source], watch.WatchConfig())

        self.assertEqual(summaries[0].anonymized_path, None)

    def test_changed_files_tracks_new_and_modified_text_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracked = root / "drop.txt"
            ignored = root / "drop.bin"
            tracked.write_text("v1", encoding="utf-8")
            ignored.write_bytes(b"v1")
            seen: dict[Path, float] = {}

            first = watch.changed_files(root, seen)
            second = watch.changed_files(root, seen)
            tracked.write_text("v2", encoding="utf-8")
            third = watch.changed_files(root, seen)

        self.assertEqual(first, [tracked])
        self.assertEqual(second, [])
        self.assertEqual(third, [tracked])

    def test_main_requires_explicit_surface(self):
        with self.assertRaises(SystemExit):
            watch.main([])

    def test_emit_summary_is_json_line(self):
        summary = watch.ReviewSummary(source="clipboard", overall_risk="LOW", finding_count=0, document_score=0.0)
        with mock.patch("builtins.print") as printed:
            watch._emit_summary(summary, watch.WatchConfig())
        payload = json.loads(printed.call_args.args[0])

        self.assertEqual(payload["source"], "clipboard")
        self.assertEqual(payload["finding_count"], 0)

    def test_config_reads_local_token_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "token"
            token_file.write_text("signed-token\n", encoding="utf-8")
            args = mock.Mock(
                base_url="http://127.0.0.1:8765",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                document_type="generic",
                review_profile="strict",
                timeout_seconds=10.0,
                anonymize_output_dir=None,
                local_token="",
                local_token_file=token_file,
                notify=False,
            )
            config = watch._config_from_args(args)

        self.assertEqual(config.local_token, "signed-token")


if __name__ == "__main__":
    unittest.main()
