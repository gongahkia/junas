import json
import logging
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as main
from test import observability_test_app as test_app


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


@contextmanager
def capture_backend_logs():
    handler = _CaptureHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    main.logger.addHandler(handler)
    try:
        yield handler.messages
    finally:
        main.logger.removeHandler(handler)


class BackendLoggingTests(unittest.TestCase):
    def setUp(self):
        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={"lexicon": test_app.DummyLexiconFilter(flagged=False)},
        )

    def test_render_backend_log_pretty_by_default(self):
        payload = {"event": "request", "path": "/classify", "status_code": 200}

        with patch.dict(os.environ, {}, clear=True):
            rendered = main.render_backend_log(payload)

        self.assertTrue(rendered.startswith("{\n"))
        self.assertIn('\n  "event"', rendered)
        self.assertEqual(json.loads(rendered), payload)

    def test_render_backend_log_compact_when_disabled(self):
        payload = {"event": "request", "path": "/classify", "status_code": 200}

        with patch.dict(os.environ, {"NOUPE_PRETTY_LOGS": "0"}, clear=False):
            rendered = main.render_backend_log(payload)

        self.assertNotIn("\n", rendered)
        self.assertEqual(json.loads(rendered), payload)

    def test_classify_and_request_logs_use_shared_formatter(self):
        with patch.dict(os.environ, {"NOUPE_PRETTY_LOGS": "1"}, clear=False):
            with capture_backend_logs() as messages:
                with TestClient(test_app.app) as client:
                    response = client.post("/classify", json={"text": "public update"})

        self.assertEqual(response.status_code, 200)

        event_messages: dict[str, str] = {}
        for message in messages:
            payload = json.loads(message)
            event_messages[payload["event"]] = message

        self.assertIn("classify_summary", event_messages)
        self.assertIn("request", event_messages)

        for event in ("classify_summary", "request"):
            payload = json.loads(event_messages[event])
            self.assertEqual(event_messages[event], main.render_backend_log(payload))
            self.assertTrue(event_messages[event].startswith("{\n"))


if __name__ == "__main__":
    unittest.main()
