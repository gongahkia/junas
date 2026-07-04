import json
import tempfile
import unittest
import urllib.error
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
        self.assertEqual(calls[0][2]["surface"], "desktop")
        self.assertEqual(calls[0][2]["workflow"], "desktop_watch")
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

    def test_anonymized_output_stays_under_configured_output_dir(self):
        def fake_post(_base_url, path, _payload, _timeout_seconds, _headers):
            if path == "/review":
                return {"overall_risk": "HIGH", "document_score": 80.0, "findings": [{"rule": "email_address"}]}
            return {"anonymized_text": "Email [EMAIL_ADDRESS_1]"}

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(watch, "_post_json_with_headers", side_effect=fake_post),
        ):
            root = Path(tmp)
            source = root / "watched" / "nested" / "client-note.txt"
            out = root / "approved-output"
            source.parent.mkdir(parents=True)
            source.write_text("Email jane@example.com", encoding="utf-8")

            summaries = watch.scan_paths([source], watch.WatchConfig(anonymize_output_dir=out))
            anonymized_path = Path(summaries[0].anonymized_path or "")

            self.assertEqual(anonymized_path.resolve().parent, out.resolve())
            self.assertEqual(anonymized_path.name, "client-note.txt.anonymized.txt")
            self.assertTrue(anonymized_path.exists())
            self.assertFalse((source.parent / "client-note.txt.anonymized.txt").exists())
            self.assertFalse((root / "client-note.txt.anonymized.txt").exists())

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

    def test_http_auth_error_omits_response_detail_and_payload_text(self):
        secret = "clipboard secret S1234567D"
        error = urllib.error.HTTPError(
            "http://127.0.0.1:8765/review",
            401,
            "unauthorized",
            {},
            mock.Mock(read=lambda: f"auth failed for {secret}".encode("utf-8")),
        )
        with mock.patch.object(watch.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, r"/review failed with HTTP 401") as raised:
                watch._post_json_with_headers(
                    "http://127.0.0.1:8765",
                    "/review",
                    {"text": secret},
                    10.0,
                    {"X-Junas-Local-Token": "bad-token"},
                )

        self.assertNotIn(secret, str(raised.exception))
        self.assertNotIn("bad-token", str(raised.exception))

    def test_clipboard_auth_failure_does_not_print_clipboard_content(self):
        secret = "clipboard secret jane@example.com"
        with (
            mock.patch.object(watch, "_clipboard_text", return_value=secret),
            mock.patch.object(
                watch,
                "_post_json_with_headers",
                side_effect=RuntimeError("/review failed with HTTP 401"),
            ),
            mock.patch("builtins.print") as printed,
        ):
            with self.assertRaisesRegex(RuntimeError, r"HTTP 401") as raised:
                watch.poll_clipboard_once(watch.WatchConfig(local_token="bad-token"))

        printed.assert_not_called()
        self.assertNotIn(secret, str(raised.exception))
        self.assertNotIn("bad-token", str(raised.exception))

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
                foreground_profile="off",
                timeout_seconds=10.0,
                anonymize_output_dir=None,
                local_token="",
                local_token_file=token_file,
                notify=False,
            )
            config = watch._config_from_args(args)

        self.assertEqual(config.local_token, "signed-token")

    def test_auto_foreground_profile_selects_terminal_profile(self):
        args = mock.Mock(
            base_url="http://127.0.0.1:8765",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            document_type="generic",
            review_profile="strict",
            foreground_profile="auto",
            timeout_seconds=10.0,
            anonymize_output_dir=None,
            local_token="",
            local_token_file=None,
            notify=False,
        )
        app = watch.ForegroundApp(name="Terminal", bundle_id="com.apple.Terminal")

        with mock.patch.object(watch, "_detect_foreground_app", return_value=app):
            config = watch._config_from_args(args)

        self.assertEqual(config.detector_profile, "terminal")
        self.assertEqual(config.document_type, "terminal_buffer")
        self.assertEqual(config.review_profile, "strict")
        self.assertEqual(config.surface, "desktop")
        self.assertEqual(config.workflow, "desktop_watch")
        self.assertEqual(config.foreground_app, "Terminal")

    def test_foreground_profile_override_does_not_detect_app(self):
        args = mock.Mock(
            base_url="http://127.0.0.1:8765",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            document_type="generic",
            review_profile="strict",
            foreground_profile="editor",
            timeout_seconds=10.0,
            anonymize_output_dir=None,
            local_token="",
            local_token_file=None,
            notify=False,
        )

        with mock.patch.object(watch, "_detect_foreground_app") as detect:
            config = watch._config_from_args(args)

        detect.assert_not_called()
        self.assertEqual(config.detector_profile, "editor")
        self.assertEqual(config.document_type, "source_buffer")
        self.assertEqual(config.review_profile, "audit_grade")

    def test_foreground_profile_off_preserves_user_review_profile(self):
        args = mock.Mock(
            base_url="http://127.0.0.1:8765",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            document_type="memo",
            review_profile="audit_grade",
            foreground_profile="off",
            timeout_seconds=10.0,
            anonymize_output_dir=None,
            local_token="",
            local_token_file=None,
            notify=False,
        )

        with mock.patch.object(watch, "_detect_foreground_app") as detect:
            config = watch._config_from_args(args)

        detect.assert_not_called()
        self.assertEqual(config.detector_profile, "")
        self.assertEqual(config.document_type, "memo")
        self.assertEqual(config.review_profile, "audit_grade")

    def test_auto_foreground_profile_leaves_unknown_app_unchanged(self):
        args = mock.Mock(
            base_url="http://127.0.0.1:8765",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            document_type="generic",
            review_profile="strict",
            foreground_profile="auto",
            timeout_seconds=10.0,
            anonymize_output_dir=None,
            local_token="",
            local_token_file=None,
            notify=False,
        )
        app = watch.ForegroundApp(name="Preview", bundle_id="com.apple.Preview")

        with mock.patch.object(watch, "_detect_foreground_app", return_value=app):
            config = watch._config_from_args(args)

        self.assertEqual(config.detector_profile, "")
        self.assertEqual(config.document_type, "generic")
        self.assertEqual(config.review_profile, "strict")


if __name__ == "__main__":
    unittest.main()
