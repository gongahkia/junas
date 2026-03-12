import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

def extract_json_objects(text, decoder=json.JSONDecoder()):
    """Find and parse all JSON objects in a given block of text."""
    pos = 0
    while True:
        match = text.find('{', pos)
        if match == -1:
            break
        try:
            result, index = decoder.raw_decode(text[match:])
            yield result
            pos = match + index
        except ValueError:
            pos = match + 1

def normalise_document(doc, idx, label_map):
    """Convert mixed raw document formats into the canonical document schema."""
    doc_name = doc.get("document_name", doc.get("document_id", f"document_{idx}"))
    doc_name_str = str(doc_name)

    original_sentences = doc.get("document_sentence_array", [])
    formatted_sentences = []

    for item in original_sentences:
        if "text" in item and "label" in item:
            raw_label = str(item["label"]).strip().lower()
            norm_label = label_map.get(raw_label, raw_label)
            formatted_sentences.append({"text": item["text"], "label": norm_label})
        else:
            for _, val in item.items():
                if isinstance(val, dict) and "text" in val and "label" in val:
                    raw_label = str(val["label"]).strip().lower()
                    norm_label = label_map.get(raw_label, raw_label)
                    formatted_sentences.append({"text": val["text"], "label": norm_label})

    creation = doc.get("document_creation")
    if not creation:
        creation = datetime.now(timezone.utc).isoformat()

    return {
        "document_name": doc_name_str,
        "document_creation": creation,
        "document_sentence_array": formatted_sentences,
    }


def write_document_files(formatted_docs, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for idx, formatted_doc in enumerate(formatted_docs):
        doc_name_str = formatted_doc["document_name"]
        safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', doc_name_str.lower()).strip('_')
        safe_name = safe_name[:40]
        if not safe_name:
            safe_name = f"doc_{idx}"

        file_name = f"{safe_name}.json"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(formatted_doc, f, indent=2)

        print(f" -> Created {file_path}")


def write_batch_file(formatted_docs, output_file):
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    batch = {
        "batch_name": output_path.stem,
        "batch_creation": datetime.now(timezone.utc).isoformat(),
        "documents": formatted_docs,
    }

    output_path.write_text(json.dumps(batch, indent=2), encoding="utf-8")
    print(f" -> Created {output_path}")


def parse_and_convert(input_file, output_target="docs/json"):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    from tqdm import tqdm
    json_objects = [
        obj for obj in extract_json_objects(content)
        if isinstance(obj, dict) and "document_sentence_array" in obj
    ]
    print(f"Found {len(json_objects)} document JSON object(s) in {input_file}.")

    label_map = {
        "non": "non",
        "non-sensitive": "non",
        "non sensitive": "non",
        "low": "low",
        "low sensitivity": "low",
        "low-risk": "low",
        "low risk": "low",
        "high": "high",
        "high sensitivity": "high",
        "high-risk": "high",
        "high risk": "high",
    }
    
    formatted_docs = []
    for idx, doc in enumerate(tqdm(json_objects, desc="Ingesting Documents", unit="doc")):
        formatted_docs.append(normalise_document(doc, idx, label_map))

    output_path = Path(output_target)
    if output_path.suffix.lower() == ".json":
        write_batch_file(formatted_docs, output_path)
        return

    write_document_files(formatted_docs, output_target)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_docs.py <input_text_file> [output_dir_or_batch.json]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_target = sys.argv[2] if len(sys.argv) > 2 else "docs/json"
    parse_and_convert(input_file, output_target)
