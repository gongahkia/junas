import json
import urllib.request
import urllib.error
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def run_tests():
    try:
        with open(ROOT / "test.json", "r", encoding="utf-8") as f:
            tests = json.load(f)
    except Exception as e:
        print(f"Failed to load test.json: {e}")
        return

    url = "http://127.0.0.1:8000/classify"
    headers = {"Content-Type": "application/json"}

    for item in tests:
        text = item.get("text", "")
        test_id = item.get("id", "unknown")
        
        req = urllib.request.Request(
            url, 
            data=json.dumps({"text": text}).encode('utf-8'),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                classification = resp_data.get("classification")
                print(f"[{test_id}] Text: {text[:50]}... => {classification}")
                print(f"      Lexicon flagged: {resp_data['lexicon']['flagged']}")
                if resp_data.get("model1"):
                    print(f"      Model1: {resp_data['model1']['label']} (conf: {resp_data['model1']['confidence']:.2f})")
                if resp_data.get("model2"):
                    print(f"      Model2: {resp_data['model2']['label']} (conf: {resp_data['model2']['confidence']:.2f})")
                print("-" * 60)
        except urllib.error.URLError as e:
            print(f"[{test_id}] Request failed: {e}")

if __name__ == "__main__":
    run_tests()
