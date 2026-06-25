import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import junas.backend.main as main


class ConcurrencyTests(unittest.TestCase):
    def _make_response(self, request_id: str | None) -> main.ClassifyResponse:
        return main.ClassifyResponse(
            request_id=request_id,
            classification=main.Classification.SAFE,
            observability={
                "degraded": False,
                "cache_status": "disabled",
                "active_pipeline": [],
                "executed_layers": [],
                "skipped_layers": [],
                "layer_errors": [],
            },
            timings_ms={"total": 0.0},
        )

    def test_single_classify_requests_are_not_serialized(self):
        def fake_core(req: main.ClassifyRequest, request_id: str | None, endpoint: str) -> main.ClassifyResponse:
            time.sleep(0.2)
            return self._make_response(request_id)

        with patch.object(main, "_classify_core", side_effect=fake_core):
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        main._run_classify_sync,
                        main.ClassifyRequest(text=f"document-{index}"),
                        f"req-{index}",
                        "/classify",
                    )
                    for index in range(2)
                ]
                results = [future.result() for future in futures]
            elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.33)
        self.assertEqual([result.request_id for result in results], ["req-0", "req-1"])

    def test_batch_classification_runs_in_parallel_and_preserves_order(self):
        durations = {
            "first": 0.22,
            "second": 0.06,
            "third": 0.03,
        }

        def fake_core(req: main.ClassifyRequest, request_id: str | None, endpoint: str) -> main.ClassifyResponse:
            time.sleep(durations[req.text])
            return self._make_response(request_id)

        batch_request = main.BatchClassifyRequest(
            items=[
                main.ClassifyRequest(text="first"),
                main.ClassifyRequest(text="second"),
                main.ClassifyRequest(text="third"),
            ]
        )

        with (
            patch.dict(os.environ, {"JUNAS_BATCH_MAX_CONCURRENCY": "3"}, clear=False),
            patch.object(main, "_classify_core", side_effect=fake_core),
        ):
            start = time.perf_counter()
            response = main._run_batch_classify_sync(batch_request, "batch")
            elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.32)
        self.assertEqual(
            [result.request_id for result in response.results],
            ["batch:0", "batch:1", "batch:2"],
        )

    def test_slow_batch_does_not_block_unrelated_single_classify(self):
        batch_started = threading.Event()

        def fake_core(req: main.ClassifyRequest, request_id: str | None, endpoint: str) -> main.ClassifyResponse:
            if request_id == "batch:0":
                batch_started.set()
                time.sleep(0.25)
            elif request_id == "single":
                time.sleep(0.05)
            else:
                time.sleep(0.01)
            return self._make_response(request_id)

        batch_request = main.BatchClassifyRequest(
            items=[
                main.ClassifyRequest(text="slow"),
                main.ClassifyRequest(text="fast"),
            ]
        )
        batch_result: dict[str, main.BatchClassifyResponse] = {}

        def run_batch() -> None:
            batch_result["response"] = main._run_batch_classify_sync(batch_request, "batch")

        with (
            patch.dict(os.environ, {"JUNAS_BATCH_MAX_CONCURRENCY": "2"}, clear=False),
            patch.object(main, "_classify_core", side_effect=fake_core),
        ):
            batch_thread = threading.Thread(target=run_batch, daemon=True)
            batch_thread.start()
            self.assertTrue(batch_started.wait(timeout=1.0))

            start = time.perf_counter()
            single_response = main._run_classify_sync(
                main.ClassifyRequest(text="single"),
                "single",
                "/classify",
            )
            single_elapsed = time.perf_counter() - start

            batch_thread.join(timeout=1.0)

        self.assertEqual(single_response.request_id, "single")
        self.assertLess(single_elapsed, 0.16)
        self.assertFalse(batch_thread.is_alive())
        self.assertIn("response", batch_result)
        self.assertEqual(
            [result.request_id for result in batch_result["response"].results],
            ["batch:0", "batch:1"],
        )


if __name__ == "__main__":
    unittest.main()
