"""Read-side DMS batch scanner substrate for iManage / NetDocuments exports.

The first supported shape is a neutral JSON manifest exported by the DMS layer.
This avoids writing back to customer systems until each pilot validates its own
API credentials, matter identifiers, and write-back approvals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kaypoh.review.engine import PreSendReviewEngine


@dataclass(frozen=True)
class DmsDocument:
    dms: str
    matter_id: str
    document_id: str
    path: Path
    source_jurisdiction: str = "SG"
    destination_jurisdiction: str = "SG"
    document_type: str = "generic"


def load_manifest(path: Path) -> list[DmsDocument]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_documents = payload.get("documents", payload if isinstance(payload, list) else [])
    if not isinstance(raw_documents, list):
        raise ValueError("DMS manifest must be a list or an object with documents=[]")
    base = path.parent
    documents: list[DmsDocument] = []
    for item in raw_documents:
        if not isinstance(item, dict):
            raise ValueError("DMS manifest entries must be objects")
        document_path = Path(str(item.get("path") or ""))
        if not document_path.is_absolute():
            document_path = base / document_path
        documents.append(
            DmsDocument(
                dms=str(item.get("dms") or payload.get("dms") or "unknown"),
                matter_id=str(item.get("matter_id") or payload.get("matter_id") or ""),
                document_id=str(item.get("document_id") or document_path.stem),
                path=document_path,
                source_jurisdiction=str(item.get("source_jurisdiction") or "SG"),
                destination_jurisdiction=str(item.get("destination_jurisdiction") or "SG"),
                document_type=str(item.get("document_type") or "generic"),
            )
        )
    return documents


def scan_manifest(path: Path, *, review_profile: str = "strict") -> dict[str, Any]:
    engine = PreSendReviewEngine()
    results: list[dict[str, Any]] = []
    for document in load_manifest(path):
        text = document.path.read_text(encoding="utf-8")
        review = engine.review(
            text=text,
            source_jurisdiction=document.source_jurisdiction,
            destination_jurisdiction=document.destination_jurisdiction,
            entity_id=None,
            include_suggestions=False,
            document_type=document.document_type,
            matter_id=document.matter_id or None,
            review_profile=review_profile,
        )
        results.append(
            {
                "dms": document.dms,
                "matter_id": document.matter_id,
                "document_id": document.document_id,
                "path": str(document.path),
                "findings": len(review.findings),
                "pii_score": review.pii_score,
                "mnpi_score": review.mnpi_score,
                "degraded_modes": review.degraded_modes,
                "rules": sorted({finding.rule for finding in review.findings}),
            }
        )
    return {"documents": results, "count": len(results), "review_profile": review_profile}
