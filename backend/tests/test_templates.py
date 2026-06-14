"""Tests for template library router."""
import pytest
from fastapi.testclient import TestClient
from api.main import create_app

app = create_app()
client = TestClient(app)

def test_list_templates():
    resp = client.get("/api/v1/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 12
    ids = {row["id"] for row in data}
    assert {
        "data-processing-agreement-sg",
        "independent-contractor-sg",
        "loan-agreement-sg",
        "restraint-of-trade-sg",
        "saas-terms-sg",
        "service-agreement-sg",
    } <= ids

def test_get_template():
    resp = client.get("/api/v1/templates/nda-sg")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Non-Disclosure Agreement"
    assert len(data["variables"]) > 0

def test_get_template_not_found():
    resp = client.get("/api/v1/templates/nonexistent")
    assert resp.status_code == 404

def test_render_template():
    resp = client.post("/api/v1/templates/nda-sg/render", json={
        "values": {"discloser": "Acme Pte Ltd", "recipient": "Beta Corp", "purpose": "testing", "duration": "3", "date": "2026-01-01"}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "Acme Pte Ltd" in data["rendered"]
    assert "Beta Corp" in data["rendered"]

def test_get_markdown_template_includes_sources():
    resp = client.get("/api/v1/templates/data-processing-agreement-sg")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_urls"]
    assert "README.md" in data["content"]

def test_render_markdown_template():
    resp = client.post("/api/v1/templates/service-agreement-sg/render", json={
        "values": {"supplier": "Alpha Services Pte Ltd", "customer": "Beta Pte Ltd", "services": "implementation services", "fees": "SGD 12,000", "date": "2026-02-01"}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "Alpha Services Pte Ltd" in data["rendered"]
    assert "implementation services" in data["rendered"]
