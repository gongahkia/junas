import json
import urllib.request
import urllib.error
import sys

def run_tests():
    try:
        with open("test.json", "r") as f:
            tests = json.load(f)
    except Exception as e:
        print(f"Failed to load test.json: {e}")
        return

    url = "http://127.0.0.1:8000/classify"
    headers = {"Content-Type": "application/json"}

    for item in tests:
        text = item.get("text", "")
        test_id = item.get("id", "unknown")
        entity_id = item.get("entity_id")
        req_data = {"text": text}
        if entity_id:
            req_data["entity_id"] = entity_id
            
        req = urllib.request.Request(
            url, 
            data=json.dumps(req_data).encode('utf-8'),
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
                if resp_data.get("mosaic"):
                    print(f"      Mosaic: escalated={resp_data['mosaic']['escalated']} (count: {resp_data['mosaic']['count']})")
                print("-" * 60)
        except urllib.error.URLError as e:
            print(f"[{test_id}] Request failed: {e}")

if __name__ == "__main__":
    run_tests()
