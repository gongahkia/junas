"""The production launcher uses multiple worker processes, not only threads."""

import json
import multiprocessing
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


def _writer(kind, worker, barrier):
    from junas.anonymize import mapping_store
    from junas.review import journal, subject_index

    barrier.wait(timeout=20)
    for number in range(20):
        identity = f"synthetic-{worker}-{number}"
        if kind == "journal":
            journal.append_event(event_type="synthetic", review_id=identity, payload={"padding": "x" * 4000})
        elif kind == "index":
            subject_index._add_entries({"synthetic-subject": [{"entry_type": "review", "review_id": identity}]})
        else:
            mapping_store.save_mapping(
                document_hash="a" * 64,
                mapping=[
                    {
                        "placeholder": f"[EMAIL_{i}]",
                        "entity_type": "EMAIL",
                        "occurrence_count": 1,
                        "original_text": f"synthetic-{i}@example.test",
                    }
                    for i in range(30)
                ],
            )


def _hold_lock(path, ready):
    from junas.helper.file_lock import interprocess_lock

    with interprocess_lock(Path(path)):
        ready.set()
        time.sleep(30)


class StorageProcessSafetyTests(unittest.TestCase):
    def test_lock_timeout_and_worker_termination_leave_no_stale_lock(self):
        from junas.helper.file_lock import interprocess_lock

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.lock"
            context = multiprocessing.get_context("spawn")
            ready = context.Event()
            child = context.Process(target=_hold_lock, args=(str(path), ready))
            child.start()
            try:
                self.assertTrue(ready.wait(timeout=10))
                with self.assertRaises(TimeoutError):
                    with interprocess_lock(path, timeout_seconds=0.05):
                        self.fail("another process still owns the lock")
            finally:
                child.terminate()
                child.join(timeout=3)
                if child.is_alive():
                    child.kill()
                    child.join(timeout=3)
            with interprocess_lock(path, timeout_seconds=0.1):
                pass

    def _exercise(self, kind, verify):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(
                os.environ,
                {
                    "JUNAS_JOURNAL_DIR": tmp,
                    "JUNAS_JOURNAL_KEY": "synthetic-process-key",
                    "JUNAS_SUBJECT_INDEX_KEY": "synthetic-subject-key",
                    "JUNAS_MAPPING_STORE_KEY": "q5cVCBcQ0PHsgxBpwoXOrp0tGSgZBz7oBfZmuZBFLJk=",
                },
            ),
        ):
            context = multiprocessing.get_context("spawn")
            barrier = context.Barrier(4)
            children = [context.Process(target=_writer, args=(kind, i, barrier)) for i in range(4)]
            try:
                for child in children:
                    child.start()
                deadline = time.monotonic() + 35
                for child in children:
                    child.join(timeout=max(0, deadline - time.monotonic()))
                self.assertEqual([child.exitcode for child in children], [0] * 4)
                verify(Path(tmp))
            finally:
                for child in children:
                    if child.is_alive():
                        child.terminate()
                    child.join(timeout=3)
                    if child.is_alive():
                        child.kill()
                        child.join(timeout=3)

    def test_journal_keeps_every_sequence_and_valid_hmac_across_processes(self):
        def verify(_):
            from junas.review import journal

            entries = journal.read_journal()
            self.assertEqual(len(entries), 80)
            self.assertEqual(len({entry.review_id for entry in entries}), 80)
            self.assertEqual([entry.seq for entry in entries], list(range(80)))
            self.assertEqual(journal.verify_chain(entries), (True, []))

        self._exercise("journal", verify)

    def test_subject_index_does_not_lose_concurrent_process_updates(self):
        def verify(tmp):
            payload = json.loads((tmp / "subject_index/index.json").read_text())
            self.assertEqual(len(payload["entries"]["synthetic-subject"]), 80)

        self._exercise("index", verify)

    def test_mapping_atomic_writes_do_not_share_a_temporary_file_between_processes(self):
        def verify(_):
            from junas.anonymize import mapping_store

            entries = mapping_store.load_mapping("a" * 64)
            self.assertEqual(len(entries), 30)
            self.assertEqual(entries[0]["original_text"], "synthetic-0@example.test")

        self._exercise("mapping", verify)
