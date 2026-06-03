"""Tests for compliance router (SG-only after pivot)."""
from fastapi.testclient import TestClient
from api.main import create_app

app = create_app()
client = TestClient(app)

def test_list_rules():
    resp = client.get("/api/v1/compliance/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10
    assert all(row["jurisdiction"] == "sg" for row in data)


def test_list_rules_jurisdiction_query_param_ignored():
    # Non-SG jurisdiction values collapse to SG after pivot.
    resp = client.get("/api/v1/compliance/rules?jurisdiction=us")
    assert resp.status_code == 200
    data = resp.json()
    assert all(row["jurisdiction"] == "sg" for row in data)

def test_check_compliance_pass():
    text = "This agreement is governed by the laws of Singapore. The consent of the individual is obtained for personal data collection under the PDPA. Data protection measures are in place."
    resp = client.post("/api/v1/compliance/check", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "summary" in data
    assert data["summary"]["total"] >= 10
    gov_law = [r for r in data["results"] if r["rule_id"] == "governing-law"]
    assert gov_law[0]["status"] == "pass"

def test_check_compliance_fail():
    resp = client.post("/api/v1/compliance/check", json={"text": "Hello world"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["failed"] > 0


def test_check_compliance_normalizes_to_sg():
    text = "This contract is governed by the laws of Singapore and includes arbitration venue."
    resp = client.post("/api/v1/compliance/check", json={"text": text, "jurisdiction": "us"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["jurisdiction"] == "sg"
