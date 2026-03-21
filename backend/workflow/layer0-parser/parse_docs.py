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


def extract_document_blocks(text):
    """Extract top-level document blocks from text files with 'Document N:' headers."""
    header_matches = list(re.finditer(r"(?m)^Document\s+\d+.*$", text))
    if not header_matches:
        return []

    blocks = []
    for idx, match in enumerate(header_matches):
        block_end = header_matches[idx + 1].start() if idx + 1 < len(header_matches) else len(text)
        chunk = text[match.end():block_end]
        brace_index = chunk.find("{")
        if brace_index == -1:
            continue
        blocks.append(chunk[brace_index:].strip())
    return blocks


def repair_text_field_quotes(raw_block):
    """Escape interior quotes inside text-field values in otherwise JSON-like blocks."""
    output = []
    i = 0
    inside_text_value = False
    escaped = False

    while i < len(raw_block):
        if not inside_text_value:
            if raw_block.startswith('"text"', i):
                output.append('"text"')
                i += len('"text"')
                continue

            if raw_block.startswith(': "', i) and ''.join(output).endswith('"text"'):
                output.append(': "')
                i += 3
                inside_text_value = True
                escaped = False
                continue

            output.append(raw_block[i])
            i += 1
            continue

        char = raw_block[i]
        if escaped:
            output.append(char)
            escaped = False
            i += 1
            continue

        if char == "\\":
            output.append(char)
            escaped = True
            i += 1
            continue

        if char == '"':
            j = i + 1
            while j < len(raw_block) and raw_block[j].isspace():
                j += 1
            if j < len(raw_block) and raw_block[j] == ",":
                output.append(char)
                inside_text_value = False
            else:
                output.append('\\"')
            i += 1
            continue

        output.append(char)
        i += 1

    return ''.join(output)


def parse_document_objects(content):
    """Parse canonical document objects from raw text."""
    document_blocks = extract_document_blocks(content)
    parsed_documents = []

    if document_blocks:
        for idx, block in enumerate(document_blocks):
            try:
                parsed_documents.append(json.loads(block))
                continue
            except json.JSONDecodeError:
                repaired = repair_text_field_quotes(block)
                try:
                    parsed_documents.append(json.loads(repaired))
                    print(f"[WARN] Repaired malformed quotes in document block {idx + 1}.")
                    continue
                except json.JSONDecodeError as exc:
                    print(f"[WARN] Skipping malformed document block {idx + 1}: {exc}")
        return parsed_documents

    return [
        obj for obj in extract_json_objects(content)
        if isinstance(obj, dict) and "document_sentence_array" in obj
    ]

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
    json_objects = parse_document_objects(content)
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
