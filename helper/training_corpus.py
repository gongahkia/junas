from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.schemas import TrainingBatch

BATCH_FILE_GLOB = "batch*.json"


def list_batch_files(data_dir: Path, pattern: str = BATCH_FILE_GLOB) -> list[Path]:
    return sorted(data_dir.glob(pattern))


def load_batch(batch_path: Path) -> TrainingBatch:
    raw = json.loads(batch_path.read_text(encoding="utf-8"))
    return TrainingBatch.model_validate(raw)


def load_documents_from_batches(data_dir: Path, pattern: str = BATCH_FILE_GLOB) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []

    for batch_path in list_batch_files(data_dir, pattern):
        batch = load_batch(batch_path)
        for batch_doc_index, doc in enumerate(batch.documents):
            sentences: list[dict[str, Any]] = []
            for sent_index, sent in enumerate(doc.document_sentence_array):
                sentences.append(
                    {
                        "text": sent.text,
                        "label": sent.label,
                        "sentence_index": sent_index,
                    }
                )

            documents.append(
                {
                    "path": str(batch_path),
                    "batch_name": batch.batch_name,
                    "document_name": doc.document_name,
                    "entity_id": f"{batch.batch_name}_doc_{batch_doc_index}",
                    "sentences": sentences,
                }
            )

    return documents
