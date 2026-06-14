from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from api.models.batch import BatchCreateRequest, BatchJob, BatchResult


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BatchService:
    def __init__(self, classifier: Any, tos_scanner: Any) -> None:
        self.classifier = classifier
        self.tos_scanner = tos_scanner
        self.jobs: dict[str, BatchJob] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    def create_job(self, payload: BatchCreateRequest) -> BatchJob:
        batch_id = str(uuid4())
        now = _now()
        results = [
            BatchResult(document_id=doc.id, file_name=doc.file_name, status="pending")
            for doc in payload.documents
        ]
        job = BatchJob(id=batch_id, status="queued", total=len(payload.documents), created_at=now, updated_at=now, results=results)
        self.jobs[batch_id] = job
        self.events[batch_id] = []
        self.subscribers[batch_id] = set()
        self._emit(batch_id, "queued", {"batch": job.model_dump(mode="json")})
        self.tasks[batch_id] = asyncio.create_task(self._run_job(batch_id, payload))
        return job

    def get_job(self, batch_id: str) -> BatchJob | None:
        return self.jobs.get(batch_id)

    async def cancel_job(self, batch_id: str) -> BatchJob | None:
        job = self.jobs.get(batch_id)
        if job is None:
            return None
        job.cancelled = True
        job.status = "cancelled"
        job.updated_at = _now()
        task = self.tasks.get(batch_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._mark_pending_cancelled(job)
        self._emit(batch_id, "cancelled", {"batch": job.model_dump(mode="json")})
        return job

    async def iter_events(self, batch_id: str):
        if batch_id not in self.jobs:
            return
        for event in self.events.get(batch_id, []):
            yield event
            if event.get("type") in {"completed", "cancelled", "error"}:
                return
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.subscribers.setdefault(batch_id, set()).add(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event.get("type") in {"completed", "cancelled", "error"}:
                    break
        finally:
            self.subscribers.get(batch_id, set()).discard(queue)

    async def _run_job(self, batch_id: str, payload: BatchCreateRequest) -> None:
        job = self.jobs[batch_id]
        job.status = "running"
        job.updated_at = _now()
        self._emit(batch_id, "started", {"batch": job.model_dump(mode="json")})
        try:
            for index, doc in enumerate(payload.documents):
                await asyncio.sleep(0)
                if job.cancelled:
                    raise asyncio.CancelledError()
                result = job.results[index]
                result.status = "running"
                result.started_at = _now()
                job.updated_at = _now()
                self._emit(batch_id, "document_started", {"document_id": doc.id, "batch": job.model_dump(mode="json")})
                try:
                    clauses = await self._maybe_await(self.classifier.classify_contract(doc.text, top_k_types=payload.top_k_types))
                    tos = await self._maybe_await(self.tos_scanner.scan_tos(doc.text, threshold=payload.threshold))
                    flagged = [row for row in tos.get("sentences", []) if row.get("is_unfair")]
                    result.status = "done"
                    result.clauses = clauses
                    result.flagged_clauses = flagged
                    result.summary = self._summary(clauses, flagged)
                    result.reasoning = self._reasoning(clauses, tos)
                    result.finished_at = _now()
                    job.completed += 1
                    job.updated_at = _now()
                    self._emit(batch_id, "document_completed", {"document_id": doc.id, "result": result.model_dump(mode="json"), "batch": job.model_dump(mode="json")})
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    result.status = "error"
                    result.error = str(exc)
                    result.finished_at = _now()
                    job.completed += 1
                    job.updated_at = _now()
                    self._emit(batch_id, "document_error", {"document_id": doc.id, "result": result.model_dump(mode="json"), "batch": job.model_dump(mode="json")})
            job.status = "completed"
            job.updated_at = _now()
            self._emit(batch_id, "completed", {"batch": job.model_dump(mode="json")})
        except asyncio.CancelledError:
            job.status = "cancelled"
            job.cancelled = True
            job.updated_at = _now()
            self._mark_pending_cancelled(job)
            self._emit(batch_id, "cancelled", {"batch": job.model_dump(mode="json")})
            raise

    def _emit(self, batch_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, **payload}
        self.events.setdefault(batch_id, []).append(event)
        for queue in self.subscribers.get(batch_id, set()):
            queue.put_nowait(event)

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _mark_pending_cancelled(job: BatchJob) -> None:
        for result in job.results:
            if result.status in {"pending", "running"}:
                result.status = "cancelled"
                result.finished_at = _now()

    @staticmethod
    def _summary(clauses: list[dict[str, Any]], flagged: list[dict[str, Any]]) -> str:
        return f"{len(clauses)} clauses classified; {len(flagged)} flagged clause sentence(s)."

    @staticmethod
    def _reasoning(clauses: list[dict[str, Any]], tos: dict[str, Any]) -> str:
        distribution: dict[str, int] = {}
        for clause in clauses:
            clause_type = str(clause.get("clause_type") or "Unknown")
            distribution[clause_type] = distribution.get(clause_type, 0) + 1
        return "\n".join([
            f"Clause distribution: {json.dumps(distribution, sort_keys=True)}",
            f"Unfair ToS summary: {json.dumps(tos.get('summary', {}), sort_keys=True)}",
            f"Severity score: {tos.get('severity_score', 0)}",
        ])
