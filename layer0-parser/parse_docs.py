import json
import os
import re
import sys
from datetime import datetime, timezone

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

def parse_and_convert(input_file, output_dir="docs/json"):
    os.makedirs(output_dir, exist_ok=True)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    from tqdm import tqdm
    json_objects = list(extract_json_objects(content))
    print(f"Found {len(json_objects)} JSON object(s) in {input_file}.")

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
    
    for idx, doc in enumerate(tqdm(json_objects, desc="Ingesting Documents", unit="doc")):
        # 1. Handle document_name vs document_id
        doc_name = doc.get("document_name", doc.get("document_id", f"document_{idx}"))
        doc_name_str = str(doc_name)
        
        # Create a file name based on the document name
        safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', doc_name_str.lower()).strip('_')
        safe_name = safe_name[:40]  # Truncate
        if not safe_name: 
            safe_name = f"doc_{idx}"
        
        file_name = f"{safe_name}.json"
        
        # 2. Extract and format sentences
        original_sentences = doc.get("document_sentence_array", [])
        formatted_sentences = []
        
        for item in original_sentences:
            # Matches existing schema: {"text": "...", "label": "..."}
            if "text" in item and "label" in item:
                raw_label = str(item["label"]).strip().lower()
                norm_label = label_map.get(raw_label, raw_label)
                formatted_sentences.append({"text": item["text"], "label": norm_label})
            else:
                # Matches your input format: {"sentence 1": {"text": "...", "label": "..."}}
                for key, val in item.items():
                    if isinstance(val, dict) and "text" in val and "label" in val:
                        raw_label = str(val["label"]).strip().lower()
                        norm_label = label_map.get(raw_label, raw_label)
                        formatted_sentences.append({"text": val["text"], "label": norm_label})
        
        creation = doc.get("document_creation")
        if not creation:
            creation = datetime.now(timezone.utc).isoformat()

        # Construct formatted document matching the schema
        formatted_doc = {
            "document_name": doc_name_str,
            "document_creation": creation,
            "document_sentence_array": formatted_sentences
        }
        
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(formatted_doc, f, indent=2)
        
        print(f" -> Created {file_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_docs.py <input_text_file> [output_dir]")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "docs/json"
    parse_and_convert(input_file, output_dir)
